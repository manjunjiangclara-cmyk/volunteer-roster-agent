from datetime import date
from unittest.mock import patch

from volunteer_roster_agent.graph import build_roster_graph
from volunteer_roster_agent.graph.classification import (
    _ClassifiedMessages,
    classify_messages,
)
from volunteer_roster_agent.graph.preparation import (
    _find_usual_volunteers,
    prepare_roster,
)
from volunteer_roster_agent.graph.requirements import apply_roster_requirements
from volunteer_roster_agent.graph.scheduling import solve_roster
from volunteer_roster_agent.models import (
    Confidence,
    DayOfWeek,
    Shift,
    Slot,
    SystemInstructionType,
    SystemMessage,
    SystemRosterInstruction,
    TimeSlot,
    Volunteer,
    VolunteerLeaveMessage,
    VolunteerRequest,
    VolunteerRequestType,
)


class _FakeClassificationLLM:
    def __init__(self, result: _ClassifiedMessages) -> None:
        self._result = result
        self.invoke_count = 0

    def with_structured_output(self, schema: type) -> "_FakeClassificationLLM":
        assert schema is _ClassifiedMessages
        return self

    def invoke(self, prompt: str) -> _ClassifiedMessages:
        self.invoke_count += 1
        assert "in one batch" in prompt
        assert "Reference date: 2026-07-17" in prompt
        return self._result


def test_classify_messages_returns_typed_request_without_changing_shifts() -> None:
    expected = VolunteerRequest(
        employee="Alice",
        date=date(2026, 7, 23),
        shift=TimeSlot.EVENING,
        request_type=VolunteerRequestType.LEAVE,
        confidence=Confidence.HIGH,
        needs_confirmation=False,
    )
    state = {
        "month": 7,
        "year": 2026,
        "reference_date": date(2026, 7, 17),
        "previous_shifts": [],
        "shifts": [],
        "recurring_slots": [],
        "volunteers": [Volunteer(id="v-alice", name="Alice")],
        "system_messages": [],
        "volunteer_leave_messages": [
            VolunteerLeaveMessage(
                text="Hi, I can't do my usual Thursday evening shift next week. "
                "Could someone cover it?"
            )
        ],
    }

    with patch(
        "volunteer_roster_agent.graph.classification.get_llm",
        return_value=_FakeClassificationLLM(
            _ClassifiedMessages(system_instructions=[], volunteer_requests=[expected])
        ),
    ):
        update = classify_messages(state)

    assert update == {"classified_messages": [expected]}
    assert "shifts" not in update
    assert expected.model_dump(mode="json") == {
        "employee": "Alice",
        "date": "2026-07-23",
        "shift": "evening",
        "request_type": "leave",
        "confidence": "high",
        "needs_confirmation": False,
    }


def test_classify_messages_preserves_system_instruction_details() -> None:
    expected = SystemRosterInstruction(
        date=date(2026, 8, 7),
        shift=TimeSlot.EVENING,
        instruction_type=SystemInstructionType.SET_REQUIREMENT,
        event="special event",
        min_volunteers=3,
        max_volunteers=None,
        confidence=Confidence.HIGH,
        needs_confirmation=False,
    )
    state = {
        "month": 8,
        "year": 2026,
        "reference_date": date(2026, 7, 17),
        "previous_shifts": [],
        "shifts": [],
        "recurring_slots": [],
        "volunteers": [],
        "system_messages": [
            SystemMessage(
                text="August 7 has a special event in the evening and requires "
                "3 volunteers."
            )
        ],
        "volunteer_leave_messages": [],
    }

    with patch(
        "volunteer_roster_agent.graph.classification.get_llm",
        return_value=_FakeClassificationLLM(
            _ClassifiedMessages(system_instructions=[expected], volunteer_requests=[])
        ),
    ):
        update = classify_messages(state)

    assert update == {"classified_messages": [expected]}
    assert expected.model_dump(mode="json") == {
        "date": "2026-08-07",
        "shift": "evening",
        "instruction_type": "set_requirement",
        "event": "special event",
        "min_volunteers": 3,
        "max_volunteers": None,
        "confidence": "high",
        "needs_confirmation": False,
    }


def test_classify_messages_uses_one_llm_call_for_the_whole_batch() -> None:
    system_instruction = SystemRosterInstruction(
        date=date(2026, 8, 7),
        shift=TimeSlot.EVENING,
        instruction_type=SystemInstructionType.SET_REQUIREMENT,
        event="special event",
        min_volunteers=3,
        max_volunteers=None,
        confidence=Confidence.HIGH,
        needs_confirmation=False,
    )
    volunteer_request = VolunteerRequest(
        employee="Alice",
        date=date(2026, 7, 23),
        shift=TimeSlot.EVENING,
        request_type=VolunteerRequestType.LEAVE,
        confidence=Confidence.HIGH,
        needs_confirmation=False,
    )
    fake_llm = _FakeClassificationLLM(
        _ClassifiedMessages(
            system_instructions=[system_instruction],
            volunteer_requests=[volunteer_request],
        )
    )
    state = {
        "month": 8,
        "year": 2026,
        "reference_date": date(2026, 7, 17),
        "previous_shifts": [],
        "shifts": [],
        "recurring_slots": [],
        "volunteers": [Volunteer(id="v-alice", name="Alice")],
        "system_messages": [SystemMessage(text="August 7 evening needs 3 people")],
        "volunteer_leave_messages": [
            VolunteerLeaveMessage(text="Alice cannot work next Thursday evening")
        ],
    }

    with patch(
        "volunteer_roster_agent.graph.classification.get_llm",
        return_value=fake_llm,
    ):
        update = classify_messages(state)

    assert fake_llm.invoke_count == 1
    assert update["classified_messages"] == [
        system_instruction,
        volunteer_request,
    ]


def test_roster_graph_solves_once_without_messages_or_llm_calls() -> None:
    alex = Volunteer(id="v-alex", name="Alex")
    bailey = Volunteer(id="v-bailey", name="Bailey")
    shift = Shift(
        id="s1",
        special_event="Sunday Service",
        date=date(2026, 7, 20),
        slot=Slot(id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING),
        min_volunteers=2,
        assigned_volunteer_ids=(alex.id, bailey.id),
    )

    with patch(
        "volunteer_roster_agent.graph.classification.get_llm",
        side_effect=AssertionError("the LLM should not be called"),
    ):
        graph = build_roster_graph()
        result = graph.invoke(
            {
                "month": 7,
                "year": 2026,
                "previous_shifts": [],
                "shifts": [shift],
                "recurring_slots": [],
                "volunteers": [alex, bailey],
                "system_messages": [],
                "volunteer_leave_messages": [],
            }
        )

    assert result["shifts"] == [shift]


def test_solver_treats_leave_as_hard_and_preserves_other_assignments() -> None:
    monday_morning = Slot(
        id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING
    )
    tuesday_morning = Slot(
        id=2, day_of_week=DayOfWeek.TUESDAY, time_slot=TimeSlot.MORNING
    )
    alice = Volunteer(id="v-alice", name="Alice")
    bob = Volunteer(id="v-bob", name="Bob")
    shifts = [
        Shift(
            id="monday",
            special_event="",
            date=date(2026, 7, 20),
            slot=monday_morning,
            assigned_volunteer_ids=(alice.id,),
        ),
        Shift(
            id="tuesday",
            special_event="",
            date=date(2026, 7, 21),
            slot=tuesday_morning,
            assigned_volunteer_ids=(bob.id,),
        ),
    ]

    update = solve_roster(
        {
            "month": 7,
            "year": 2026,
            "previous_shifts": [],
            "shifts": shifts,
            "recurring_slots": [monday_morning, tuesday_morning],
            "volunteers": [alice, bob],
            "system_messages": [],
            "volunteer_leave_messages": [],
            "classified_messages": [
                VolunteerRequest(
                    employee="Alice",
                    date=date(2026, 7, 20),
                    shift=TimeSlot.MORNING,
                    request_type=VolunteerRequestType.LEAVE,
                    confidence=Confidence.HIGH,
                    needs_confirmation=False,
                )
            ],
        }
    )

    assert update["shifts"][0].assigned_volunteer_ids == (bob.id,)
    assert update["shifts"][1].assigned_volunteer_ids == (bob.id,)


def test_solver_applies_system_requirement_before_single_assignment_run() -> None:
    friday_evening = Slot(
        id=1, day_of_week=DayOfWeek.FRIDAY, time_slot=TimeSlot.EVENING
    )
    alice = Volunteer(id="v-alice", name="Alice")
    bob = Volunteer(id="v-bob", name="Bob")
    shift = Shift(
        id="special-event",
        special_event="",
        date=date(2026, 8, 7),
        slot=friday_evening,
        assigned_volunteer_ids=(alice.id,),
    )

    state = {
        "month": 8,
        "year": 2026,
        "previous_shifts": [],
        "shifts": [shift],
        "recurring_slots": [friday_evening],
        "volunteers": [alice, bob],
        "system_messages": [],
        "volunteer_leave_messages": [],
        "classified_messages": [
            SystemRosterInstruction(
                date=date(2026, 8, 7),
                shift=TimeSlot.EVENING,
                instruction_type=SystemInstructionType.SET_REQUIREMENT,
                event="special event",
                min_volunteers=2,
                max_volunteers=2,
                confidence=Confidence.HIGH,
                needs_confirmation=False,
            )
        ],
    }
    state.update(apply_roster_requirements(state))
    update = solve_roster(state)

    solved = update["shifts"][0]
    assert solved.special_event == "special event"
    assert solved.min_volunteers == 2
    assert solved.max_volunteers == 2
    assert solved.assigned_volunteer_ids == (alice.id, bob.id)


def test_prepare_roster_generates_shifts_from_recurring_slots() -> None:
    monday_morning = Slot(
        id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING
    )

    # No LLM is patched here: `prepare_roster` is pure code, and
    # `stop_after` keeps the (LLM-driven) rest of the graph from running.
    graph = build_roster_graph(stop_after="prepare_roster")
    result = graph.invoke(
        {
            "month": 7,
            "year": 2026,
            "previous_shifts": [],
            "shifts": [],
            "recurring_slots": [monday_morning],
            "volunteers": [],
            "system_messages": [],
            "volunteer_leave_messages": [],
        }
    )

    # July 2026 has Mondays on the 6th, 13th, 20th, and 27th.
    assert [shift.date for shift in result["shifts"]] == [
        date(2026, 7, 6),
        date(2026, 7, 13),
        date(2026, 7, 20),
        date(2026, 7, 27),
    ]
    assert all(shift.slot == monday_morning for shift in result["shifts"])
    assert all(shift.assigned_volunteer_ids == () for shift in result["shifts"])


def test_find_usual_volunteers_counts_assignments_and_keeps_ties() -> None:
    monday_morning = Slot(
        id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING
    )
    alex = Volunteer(id="v-alex", name="Alex")
    bailey = Volunteer(id="v-bailey", name="Bailey")
    casey = Volunteer(id="v-casey", name="Casey")

    previous_shifts = [
        Shift(
            id="previous-1",
            special_event="",
            date=date(2026, 6, 1),
            slot=monday_morning,
            assigned_volunteer_ids=(alex.id, bailey.id),
        ),
        Shift(
            id="previous-2",
            special_event="",
            date=date(2026, 6, 8),
            slot=monday_morning,
            assigned_volunteer_ids=(alex.id, casey.id),
        ),
        Shift(
            id="previous-3",
            special_event="",
            date=date(2026, 6, 15),
            slot=monday_morning,
            assigned_volunteer_ids=(bailey.id,),
        ),
    ]

    usual_volunteers = _find_usual_volunteers(
        {
            "month": 7,
            "year": 2026,
            "previous_shifts": previous_shifts,
            "shifts": [],
            "recurring_slots": [],
            "volunteers": [alex, bailey, casey],
            "system_messages": [],
            "volunteer_leave_messages": [],
        }
    )

    assert len(usual_volunteers) == 1
    assert usual_volunteers[0].slot_id == monday_morning.id
    assert [volunteer.id for volunteer in usual_volunteers[0].volunteers] == [
        alex.id,
        bailey.id,
    ]


def test_prepare_roster_assigns_available_historical_volunteers() -> None:
    monday_morning = Slot(
        id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING
    )
    alex = Volunteer(id="v-alex", name="Alex", unavailable_dates=(date(2026, 7, 13),))
    bailey = Volunteer(id="v-bailey", name="Bailey")
    previous_shifts = [
        Shift(
            id="previous-1",
            special_event="",
            date=date(2026, 6, 1),
            slot=monday_morning,
            assigned_volunteer_ids=(alex.id,),
        ),
        Shift(
            id="previous-2",
            special_event="",
            date=date(2026, 6, 8),
            slot=monday_morning,
            assigned_volunteer_ids=(alex.id,),
        ),
        Shift(
            id="previous-3",
            special_event="",
            date=date(2026, 6, 15),
            slot=monday_morning,
            assigned_volunteer_ids=(bailey.id,),
        ),
    ]
    shifts = [
        Shift(
            id="current-available",
            special_event="",
            date=date(2026, 7, 6),
            slot=monday_morning,
            min_volunteers=2,
            max_volunteers=2,
            assigned_volunteer_ids=(bailey.id,),
        ),
        Shift(
            id="current-unavailable",
            special_event="",
            date=date(2026, 7, 13),
            slot=monday_morning,
        ),
    ]

    update = prepare_roster(
        {
            "month": 7,
            "year": 2026,
            "previous_shifts": previous_shifts,
            "shifts": shifts,
            "recurring_slots": [],
            "volunteers": [alex, bailey],
            "system_messages": [],
            "volunteer_leave_messages": [],
        }
    )

    assert update["shifts"][0].assigned_volunteer_ids == (bailey.id, alex.id)
    assert update["shifts"][1].assigned_volunteer_ids == ()
