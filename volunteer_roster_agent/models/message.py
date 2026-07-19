from __future__ import annotations

from datetime import date as CalendarDate
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from volunteer_roster_agent.models.slot import TimeSlot


class VolunteerRequestType(StrEnum):
    """The intent expressed by a volunteer's roster message."""

    LEAVE = "leave"
    AVAILABILITY = "availability"
    COVER = "cover"
    OTHER = "other"


class SystemInstructionType(StrEnum):
    """The roster operation expressed by a system message."""

    CREATE_SHIFT = "create_shift"
    UPDATE_SHIFT = "update_shift"
    CANCEL_SHIFT = "cancel_shift"
    SET_REQUIREMENT = "set_requirement"
    OTHER = "other"


class Confidence(StrEnum):
    """How confidently a message could be converted to structured data."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VolunteerRequest(BaseModel):
    """A normalized, non-mutating interpretation of a volunteer message."""

    employee: str | None = Field(
        default=None,
        description="Volunteer name, or null when the message is not about one person.",
    )
    date: CalendarDate | None = Field(
        default=None,
        description="Resolved calendar date, or null when it cannot be determined.",
    )
    shift: TimeSlot | None = Field(
        default=None,
        description="Affected part of the day, or null when it is not specified.",
    )
    request_type: VolunteerRequestType
    confidence: Confidence
    needs_confirmation: bool

    @model_validator(mode="after")
    def mark_incomplete_leave_for_confirmation(self) -> "VolunteerRequest":
        if (
            self.request_type == VolunteerRequestType.LEAVE
            and (self.employee is None or self.date is None)
        ):
            self.needs_confirmation = True
        return self


class SystemRosterInstruction(BaseModel):
    """A normalized, non-mutating interpretation of a system message."""

    date: CalendarDate | None = Field(
        default=None,
        description="Affected calendar date, or null when it cannot be determined.",
    )
    shift: TimeSlot | None = Field(
        default=None,
        description="Affected part of the day, or null when it is not specified.",
    )
    instruction_type: SystemInstructionType
    event: str | None = Field(
        default=None,
        description="Event name or description, when the instruction names one.",
    )
    min_volunteers: int | None = Field(default=None, ge=0)
    max_volunteers: int | None = Field(default=None, ge=0)
    confidence: Confidence
    needs_confirmation: bool


ClassifiedMessage = VolunteerRequest | SystemRosterInstruction


class SystemMessage(BaseModel):
    """A mandatory natural-language instruction about the roster."""

    text: str = Field(min_length=1)


class VolunteerLeaveMessage(BaseModel):
    """A volunteer's natural-language leave or availability request."""

    text: str = Field(min_length=1)
