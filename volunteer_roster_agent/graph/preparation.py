import calendar
from collections import Counter, defaultdict
from datetime import date

from pydantic import BaseModel

from volunteer_roster_agent.graph.state import RosterState
from volunteer_roster_agent.models import DayOfWeek, Shift, Volunteer

_WEEKDAY_INDEX = {day: index for index, day in enumerate(DayOfWeek)}


class _SlotVolunteers(BaseModel):
    """The usual volunteers for a single slot."""

    slot_id: int
    volunteers: list[Volunteer]


def _dates_in_month_for_weekday(year: int, month: int, day_of_week: DayOfWeek) -> list[date]:
    """Every calendar date in `year`/`month` that falls on `day_of_week`."""
    target_weekday = _WEEKDAY_INDEX[day_of_week]
    _, days_in_month = calendar.monthrange(year, month)
    return [
        date(year, month, day)
        for day in range(1, days_in_month + 1)
        if date(year, month, day).weekday() == target_weekday
    ]


def _generate_shifts(state: RosterState) -> list[Shift]:
    """Generate monthly shifts from the recurring slot schedule."""
    shifts = [
        Shift(
            id=f"{shift_date.isoformat()}-slot-{slot.id}",
            special_event="",
            date=shift_date,
            slot=slot,
            min_volunteers=1,
        )
        for slot in state.get("recurring_slots", [])
        for shift_date in _dates_in_month_for_weekday(
            state["year"], state["month"], slot.day_of_week
        )
    ]
    shifts.sort(key=lambda shift: (shift.date, shift.slot.id))
    return shifts


def _find_usual_volunteers(state: RosterState) -> list[_SlotVolunteers]:
    """Return the most frequently assigned volunteers for every historical slot."""
    previous_shifts = state.get("previous_shifts", [])
    if not previous_shifts:
        return []

    volunteers_by_id = {volunteer.id: volunteer for volunteer in state.get("volunteers", [])}
    assignments_by_slot: dict[int, Counter[str]] = defaultdict(Counter)
    for shift in previous_shifts:
        assignments_by_slot[shift.slot.id].update(shift.assigned_volunteer_ids)

    usual_volunteers = []
    for slot_id in sorted(assignments_by_slot):
        counts = assignments_by_slot[slot_id]
        highest_count = max(counts.values())
        volunteers = [
            volunteers_by_id[volunteer_id]
            for volunteer_id, count in sorted(counts.items())
            if count == highest_count and volunteer_id in volunteers_by_id
        ]
        if volunteers:
            usual_volunteers.append(_SlotVolunteers(slot_id=slot_id, volunteers=volunteers))

    return usual_volunteers


def _assign_usual_volunteers(state: RosterState, shifts: list[Shift]) -> list[Shift]:
    """Assign usual, available volunteers while retaining existing assignments."""
    usual_by_slot = {
        assignment.slot_id: assignment.volunteers
        for assignment in _find_usual_volunteers(state)
    }
    if not usual_by_slot:
        return shifts

    updated_shifts = []
    for shift in shifts:
        assigned_ids = list(shift.assigned_volunteer_ids)
        for volunteer in usual_by_slot.get(shift.slot.id, []):
            if volunteer.id in assigned_ids or not volunteer.is_available_for_shift(shift.date):
                continue
            if shift.max_volunteers is not None and len(assigned_ids) >= shift.max_volunteers:
                break
            assigned_ids.append(volunteer.id)
        updated_shifts.append(shift.model_copy(update={"assigned_volunteer_ids": tuple(assigned_ids)}))

    return updated_shifts


def prepare_roster(state: RosterState) -> dict:
    """Generate missing monthly shifts and fill their usual volunteers."""
    shifts = state.get("shifts") or _generate_shifts(state)
    return {"shifts": _assign_usual_volunteers(state, shifts)}
