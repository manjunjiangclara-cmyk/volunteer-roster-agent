from datetime import date

from pydantic import BaseModel, Field, field_validator


class Volunteer(BaseModel):
    """A person available to be scheduled onto roster shifts."""

    id: str
    name: str
    email: str | None = None
    phone: str | None = None
    unavailable_dates: tuple[date, ...] = Field(
        default_factory=tuple,
        description="Calendar dates the volunteer cannot work.",
    )
    max_shifts: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of shifts to assign in a scheduling period.",
    )
    notes: str | None = None

    model_config = {"frozen": True}

    @field_validator("unavailable_dates", mode="before")
    @classmethod
    def _dedupe_unavailable_dates(cls, value: object) -> object:
        if isinstance(value, (list, tuple, set, frozenset)):
            return tuple(sorted(set(value)))
        return value

    def is_available_on(self, day: date) -> bool:
        return day not in self.unavailable_dates

    def is_available_for_shift(self, shift_date: date) -> bool:
        return self.is_available_on(shift_date)
