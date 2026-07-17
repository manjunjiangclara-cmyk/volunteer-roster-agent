from __future__ import annotations

from datetime import date as CalendarDate
from enum import StrEnum

from pydantic import BaseModel, Field

from volunteer_roster_agent.models.slot import TimeSlot


class RequestType(StrEnum):
    """The roster intent expressed by a natural-language message."""

    LEAVE = "leave"
    AVAILABILITY = "availability"
    COVER = "cover"
    SHIFT_REQUIREMENT = "shift_requirement"
    OTHER = "other"


class Confidence(StrEnum):
    """How confidently a message could be converted to structured data."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RosterRequest(BaseModel):
    """A normalized, non-mutating interpretation of a roster message."""

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
    request_type: RequestType
    confidence: Confidence
    needs_confirmation: bool


class SystemMessage(BaseModel):
    """A mandatory natural-language instruction about the roster."""

    text: str = Field(min_length=1)


class VolunteerLeaveMessage(BaseModel):
    """A volunteer's natural-language leave or availability request."""

    text: str = Field(min_length=1)
