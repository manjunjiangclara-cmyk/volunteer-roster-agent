from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from volunteer_roster_agent.models.slot import Slot


class ShiftStatus(StrEnum):
    OPEN = "open"
    FILLED = "filled"
    OVERSTAFFED = "overstaffed"


class Shift(BaseModel):
    """A concrete, dated occurrence of a Slot that needs volunteers."""

    id: str
    special_event: str
    date: date
    slot: Slot
    min_volunteers: int = Field(default=1, ge=1)
    max_volunteers: int | None = Field(default=None, ge=1)
    assigned_volunteer_ids: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_shift_bounds(self) -> "Shift":
        if self.date.strftime("%A") != self.slot.day_of_week.value:
            raise ValueError(
                f"Shift date {self.date} falls on {self.date.strftime('%A')}, "
                f"which does not match slot day_of_week {self.slot.day_of_week.value}."
            )
        if self.max_volunteers is not None and self.max_volunteers < self.min_volunteers:
            raise ValueError("max_volunteers must be greater than or equal to min_volunteers.")
        if len(self.assigned_volunteer_ids) > len(set(self.assigned_volunteer_ids)):
            raise ValueError("assigned_volunteer_ids must be unique.")
        if self.max_volunteers is not None and len(self.assigned_volunteer_ids) > self.max_volunteers:
            raise ValueError("Too many volunteers assigned for this shift.")
        return self

    @property
    def status(self) -> ShiftStatus:
        count = len(self.assigned_volunteer_ids)
        if count < self.min_volunteers:
            return ShiftStatus.OPEN
        if self.max_volunteers is not None and count > self.max_volunteers:
            return ShiftStatus.OVERSTAFFED
        return ShiftStatus.FILLED

    @property
    def slots_remaining(self) -> int:
        return max(0, self.min_volunteers - len(self.assigned_volunteer_ids))

    def with_assignment(self, volunteer_id: str) -> "Shift":
        if volunteer_id in self.assigned_volunteer_ids:
            raise ValueError(f"Volunteer {volunteer_id!r} is already assigned.")
        return self.model_copy(
            update={"assigned_volunteer_ids": (*self.assigned_volunteer_ids, volunteer_id)}
        )
