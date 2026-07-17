from datetime import date

import pytest

from volunteer_roster_agent.models import DayOfWeek, Shift, Slot, TimeSlot


def test_shift_accepts_date_matching_slot_day_of_week() -> None:
    shift = Shift(
        id="s1",
        special_event="Sunday Service",
        date=date(2026, 7, 20),  # a Monday
        slot=Slot(id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING),
        min_volunteers=1,
    )
    assert shift.slot.day_of_week == DayOfWeek.MONDAY


def test_shift_rejects_date_mismatched_with_slot_day_of_week() -> None:
    with pytest.raises(ValueError, match="does not match slot day_of_week"):
        Shift(
            id="s1",
            special_event="Sunday Service",
            date=date(2026, 7, 20),  # a Monday
            slot=Slot(id=1, day_of_week=DayOfWeek.TUESDAY, time_slot=TimeSlot.MORNING),
            min_volunteers=1,
        )


def test_shift_with_assignment_tracks_volunteers() -> None:
    shift = Shift(
        id="s1",
        special_event="Sunday Service",
        date=date(2026, 7, 20),
        slot=Slot(id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING),
        min_volunteers=1,
    )
    updated = shift.with_assignment("v1")
    assert updated.assigned_volunteer_ids == ("v1",)
    assert shift.assigned_volunteer_ids == ()
