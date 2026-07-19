"""Apply classified system instructions to shift requirements."""

from volunteer_roster_agent.graph.state import RosterState
from volunteer_roster_agent.models import (
    Shift,
    SystemInstructionType,
    SystemRosterInstruction,
)


def apply_roster_requirements(state: RosterState) -> dict:
    """Update shift structure without assigning any volunteers."""
    shifts = list(state.get("shifts", []))

    for message in state.get("classified_messages", []):
        if not isinstance(message, SystemRosterInstruction):
            continue
        if (
            message.needs_confirmation
            or message.instruction_type == SystemInstructionType.OTHER
        ):
            continue
        if message.date is None:
            raise ValueError("A confirmed system instruction must include a date.")

        matching_indexes = [
            index
            for index, shift in enumerate(shifts)
            if shift.date == message.date
            and (message.shift is None or shift.slot.time_slot == message.shift)
        ]

        if message.instruction_type == SystemInstructionType.CANCEL_SHIFT:
            shifts = [
                shift
                for index, shift in enumerate(shifts)
                if index not in matching_indexes
            ]
        elif matching_indexes:
            for index in matching_indexes:
                shifts[index] = _update_shift(shifts[index], message)
        else:
            shifts.append(_create_shift(message, state))

    shifts.sort(key=lambda shift: (shift.date, shift.slot.id))
    return {"shifts": shifts}


def _create_shift(instruction: SystemRosterInstruction, state: RosterState) -> Shift:
    if instruction.date is None or instruction.shift is None:
        raise ValueError(
            "Creating a shift from a system instruction requires a date and time slot."
        )

    slot = next(
        (
            slot
            for slot in state.get("recurring_slots", [])
            if slot.day_of_week.value == instruction.date.strftime("%A")
            and slot.time_slot == instruction.shift
        ),
        None,
    )
    if slot is None:
        raise ValueError("No recurring slot matches the confirmed system instruction.")

    return Shift(
        id=f"{instruction.date.isoformat()}-slot-{slot.id}",
        special_event=instruction.event or "",
        date=instruction.date,
        slot=slot,
        min_volunteers=instruction.min_volunteers or 1,
        max_volunteers=instruction.max_volunteers,
    )


def _update_shift(shift: Shift, instruction: SystemRosterInstruction) -> Shift:
    updates: dict[str, object] = {}
    if instruction.event is not None:
        updates["special_event"] = instruction.event
    if instruction.min_volunteers is not None:
        updates["min_volunteers"] = instruction.min_volunteers
        if (
            instruction.max_volunteers is None
            and shift.max_volunteers is not None
            and shift.max_volunteers < instruction.min_volunteers
        ):
            updates["max_volunteers"] = instruction.min_volunteers
    if instruction.max_volunteers is not None:
        updates["max_volunteers"] = instruction.max_volunteers

    assigned_ids = shift.assigned_volunteer_ids
    maximum = updates.get("max_volunteers", shift.max_volunteers)
    if isinstance(maximum, int):
        assigned_ids = assigned_ids[:maximum]

    return Shift.model_validate(
        {
            **shift.model_dump(),
            **updates,
            "assigned_volunteer_ids": assigned_ids,
        }
    )
