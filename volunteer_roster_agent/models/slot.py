from enum import StrEnum

from pydantic import BaseModel, Field

from volunteer_roster_agent.models.volunteer import Volunteer


class DayOfWeek(StrEnum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"


class TimeSlot(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class Slot(BaseModel):
    """A recurring timeslot on a particular day of the week, e.g. Monday morning."""
    id: int
    day_of_week: DayOfWeek
    time_slot: TimeSlot
    usual_volunteers: list[Volunteer] = Field(default_factory=list)

    model_config = {"frozen": True}
