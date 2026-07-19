from datetime import date
from typing import TypeVar

from pydantic import BaseModel

from volunteer_roster_agent.config import get_llm
from volunteer_roster_agent.graph.state import RosterState
from volunteer_roster_agent.models import (
    ClassifiedMessage,
    SystemRosterInstruction,
    VolunteerRequest,
)

_SchemaT = TypeVar("_SchemaT", bound=BaseModel)


class _ClassifiedMessages(BaseModel):
    """Structured output for one batch containing both message sources."""

    system_instructions: list[SystemRosterInstruction]
    volunteer_requests: list[VolunteerRequest]


def _invoke_structured(schema: type[_SchemaT], prompt: str) -> _SchemaT:
    """Call the LLM, coercing its response into `schema`."""
    return get_llm().with_structured_output(schema).invoke(prompt)


def classify_messages(state: RosterState) -> dict:
    """Convert system and volunteer messages into typed classifications.

    This node only interprets messages. It deliberately does not create or
    update a roster, so uncertain details can be confirmed first.
    """
    system_messages = [message.text for message in state.get("system_messages", [])]
    volunteer_messages = [
        message.text for message in state.get("volunteer_leave_messages", [])
    ]
    if not system_messages and not volunteer_messages:
        return {}

    reference_date = state.get("reference_date", date.today())
    volunteers_json = [
        volunteer.model_dump_json() for volunteer in state.get("volunteers", [])
    ]
    current_shifts_json = [shift.model_dump_json() for shift in state.get("shifts", [])]
    prompt = f"""
    Interpret all roster messages below as structured data in one batch. Do
    not generate or modify a roster. Keep system instructions and volunteer
    requests in their corresponding output lists.

    System messages:
    {system_messages}

    Volunteer messages:
    {volunteer_messages}

    Reference date: {reference_date.isoformat()}
    Target roster month: {state.get("year")}-{state.get("month"):02d}

    Resolve relative dates such as "next Thursday" from the reference date.
    When a volunteer says "my usual shift", use the current roster and
    volunteer directory to identify the employee and shift. A message that
    contains multiple distinct requests may produce multiple structured
    volunteer requests. Do not guess when evidence is insufficient: use null
    for unknown fields, lower confidence, and needs_confirmation=true.

    Volunteer directory:
    {volunteers_json}

    Current roster:
    {current_shifts_json}
    """
    result = _invoke_structured(_ClassifiedMessages, prompt)
    classified_messages: list[ClassifiedMessage] = [
        *result.system_instructions,
        *result.volunteer_requests,
    ]
    return {"classified_messages": classified_messages}
