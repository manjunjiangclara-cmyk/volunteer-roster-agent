from datetime import date

from typing_extensions import NotRequired, TypedDict

from volunteer_roster_agent.models import (
    RosterRequest,
    Shift,
    Slot,
    SystemMessage,
    Volunteer,
    VolunteerLeaveMessage,
)


class RosterState(TypedDict):
    """Shared state passed between LangGraph nodes."""

    previous_shifts: list[Shift]
    shifts: list[Shift]
    system_messages: list[SystemMessage]
    volunteer_leave_messages: list[VolunteerLeaveMessage]
    recurring_slots: list[Slot]
    volunteers: list[Volunteer]
    month: int
    year: int
    reference_date: NotRequired[date]
    classified_messages: NotRequired[list[RosterRequest]]
