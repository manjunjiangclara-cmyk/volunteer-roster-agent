"""Assign volunteers to prepared shifts with one OR-Tools solve."""

from collections import defaultdict
from datetime import date

from ortools.sat.python import cp_model

from volunteer_roster_agent.graph.state import RosterState
from volunteer_roster_agent.models import (
    Shift,
    TimeSlot,
    VolunteerRequest,
    VolunteerRequestType,
)

_LeaveKey = tuple[str, date, TimeSlot | None]


def solve_roster(state: RosterState) -> dict:
    """Choose all volunteer assignments in one CP-SAT solve."""
    shifts = state.get("shifts", [])
    volunteers = state.get("volunteers", [])
    unavailable = _build_unavailable_set(state)

    model = cp_model.CpModel()
    assignments = {
        (volunteer.id, shift.id): model.new_bool_var(f"{volunteer.id}_{shift.id}")
        for volunteer in volunteers
        for shift in shifts
    }

    # Every shift must meet its required staffing level. When no maximum is
    # configured, the minimum is also the target so the solver does not add
    # unnecessary volunteers.
    for shift in shifts:
        assigned_to_shift = [
            assignments[(volunteer.id, shift.id)] for volunteer in volunteers
        ]
        model.add(sum(assigned_to_shift) >= shift.min_volunteers)
        maximum = shift.max_volunteers or shift.min_volunteers
        model.add(sum(assigned_to_shift) <= maximum)

    # Leave and declared unavailable dates are hard constraints.
    for volunteer in volunteers:
        for shift in shifts:
            if _is_unavailable(volunteer.id, shift, unavailable):
                model.add(assignments[(volunteer.id, shift.id)] == 0)

    # Respect an optional scheduling-period cap for each volunteer.
    for volunteer in volunteers:
        if volunteer.max_shifts is not None:
            model.add(
                sum(assignments[(volunteer.id, shift.id)] for shift in shifts)
                <= volunteer.max_shifts
            )

    # Keep as many prepared/previous assignments as the hard constraints allow.
    previous_assignments = [
        assignments[(volunteer_id, shift.id)]
        for shift in shifts
        for volunteer_id in shift.assigned_volunteer_ids
        if (volunteer_id, shift.id) in assignments
    ]
    model.maximize(sum(previous_assignments))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError(
            "No feasible roster satisfies leave, availability, and staffing constraints."
        )

    return {
        "shifts": [
            shift.model_copy(
                update={
                    "assigned_volunteer_ids": tuple(
                        volunteer.id
                        for volunteer in volunteers
                        if solver.value(assignments[(volunteer.id, shift.id)])
                    )
                }
            )
            for shift in shifts
        ]
    }


def _build_unavailable_set(state: RosterState) -> set[_LeaveKey]:
    """Combine volunteer availability data with confirmed leave requests."""
    volunteers_by_name: dict[str, list[str]] = defaultdict(list)
    unavailable: set[_LeaveKey] = set()

    for volunteer in state.get("volunteers", []):
        volunteers_by_name[volunteer.name.casefold()].append(volunteer.id)
        unavailable.update(
            (volunteer.id, unavailable_date, None)
            for unavailable_date in volunteer.unavailable_dates
        )

    for message in state.get("classified_messages", []):
        if not (
            isinstance(message, VolunteerRequest)
            and message.request_type == VolunteerRequestType.LEAVE
            and not message.needs_confirmation
        ):
            continue
        if message.employee is None or message.date is None:
            raise ValueError(
                "A confirmed leave request must include employee and date."
            )

        matching_ids = volunteers_by_name[message.employee.casefold()]
        if len(matching_ids) != 1:
            raise ValueError(
                f"Confirmed leave employee {message.employee!r} is unknown or ambiguous."
            )
        unavailable.add((matching_ids[0], message.date, message.shift))

    return unavailable


def _is_unavailable(
    volunteer_id: str, shift: Shift, unavailable: set[_LeaveKey]
) -> bool:
    return (volunteer_id, shift.date, None) in unavailable or (
        volunteer_id,
        shift.date,
        shift.slot.time_slot,
    ) in unavailable
