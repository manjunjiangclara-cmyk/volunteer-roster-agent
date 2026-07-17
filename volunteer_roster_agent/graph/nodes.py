from datetime import date
from typing import TypeVar

from pydantic import BaseModel

from volunteer_roster_agent.config import get_llm
from volunteer_roster_agent.graph.state import RosterState
from volunteer_roster_agent.models import RosterRequest, Shift

_SchemaT = TypeVar("_SchemaT", bound=BaseModel)


class _ShiftsResult(BaseModel):
    """Structured-output schema for an updated list of shifts."""

    shifts: list[Shift]


def _invoke_structured(schema: type[_SchemaT], prompt: str) -> _SchemaT:
    """Call the LLM, coercing its response into `schema`."""
    return get_llm().with_structured_output(schema).invoke(prompt)


def classify_messages(state: RosterState) -> dict:
    """Convert system and volunteer messages into typed roster requests.

    This node only interprets messages. It deliberately does not create or
    update a roster, so uncertain details can be confirmed first.
    """
    incoming_messages = [
        ("system", message.text) for message in state.get("system_messages", [])
    ] + [
        ("volunteer", message.text)
        for message in state.get("volunteer_leave_messages", [])
    ]
    if not incoming_messages:
        return {}

    reference_date = state.get("reference_date", date.today())
    volunteers_json = [
        volunteer.model_dump_json() for volunteer in state.get("volunteers", [])
    ]
    previous_shifts_json = [
        shift.model_dump_json() for shift in state.get("previous_shifts", [])
    ]
    classified_messages: list[RosterRequest] = []

    for message_source, message_text in incoming_messages:
        prompt = f"""
        Interpret the roster message as structured data. Do not generate or
        modify a roster.

        Message source: {message_source}
        Message: {message_text}
        Reference date: {reference_date.isoformat()}
        Target roster month: {state.get("year")}-{state.get("month"):02d}

        Resolve relative dates such as "next Thursday" from the reference
        date. When a volunteer says "my usual shift", use the previous roster
        and volunteer directory to identify the employee and shift. Do not
        guess when the evidence is insufficient: use null for unknown fields,
        lower confidence, and set needs_confirmation to true.

        Volunteer directory:
        {volunteers_json}

        Previous roster (use only as identity/usual-shift context):
        {previous_shifts_json}
        """
        classified_messages.append(_invoke_structured(RosterRequest, prompt))

    return {"classified_messages": classified_messages}


def apply_system_messages(state: RosterState) -> dict:
    """Apply mandatory natural-language operational instructions first."""
    messages = state.get("system_messages", [])
    if not messages:
        return {}

    shifts = state.get("shifts", [])
    for message in messages:
        shifts_json = [shift.model_dump_json() for shift in shifts]
        prompt = f"""
        Apply this mandatory system instruction to the roster. System
        instructions are non-negotiable: create, remove, or modify shifts as
        directed, and retain the resulting requirement for later scheduling.

        System instruction:
        {message.text}

        Current shifts:
        {shifts_json}

        Return the complete updated list of shifts.
        """
        result = _invoke_structured(_ShiftsResult, prompt)
        shifts = result.shifts

    return {"shifts": shifts}


def apply_volunteer_leave_messages(state: RosterState) -> dict:
    """Apply natural-language volunteer leave requests after system messages."""
    messages = state.get("volunteer_leave_messages", [])
    if not messages:
        return {}

    shifts = state.get("shifts", [])
    volunteers_json = [volunteer.model_dump_json() for volunteer in state.get("volunteers", [])]
    for message in messages:
        shifts_json = [shift.model_dump_json() for shift in shifts]
        prompt = f"""
        Apply this volunteer leave or availability request to the roster.
        Identify the volunteer by matching the message to the volunteer
        directory. Remove that volunteer from shifts they cannot attend and
        respect any alternative availability in the message. Do not remove or
        cancel shifts: system instructions have already established the
        required shifts.

        Volunteer request:
        {message.text}

        Volunteer directory:
        {volunteers_json}

        Current shifts:
        {shifts_json}

        Return the complete updated list of shifts.
        """
        result = _invoke_structured(_ShiftsResult, prompt)
        shifts = result.shifts

    return {"shifts": shifts}


def review_roster(state: RosterState) -> dict:
    """Review the roster and resolve any conflicts."""
    shifts_json = [shift.model_dump_json() for shift in state.get("shifts", [])]
    prompt = f"""
    Review the roster below. Ensure that every shift's assigned volunteers are
    valid for its slot and that no volunteer is double-booked. Resolve any
    conflicts you find.

    Shifts:
    {shifts_json}

    Mandatory system instructions:
    {[message.text for message in state.get("system_messages", [])]}

    Volunteer leave requests:
    {[message.text for message in state.get("volunteer_leave_messages", [])]}
    """

    result = _invoke_structured(_ShiftsResult, prompt)
    return {"shifts": result.shifts}
