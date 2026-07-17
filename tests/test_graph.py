from datetime import date
from unittest.mock import patch

from volunteer_roster_agent.graph import build_roster_graph
from volunteer_roster_agent.graph.nodes import _ShiftsResult, classify_messages
from volunteer_roster_agent.graph.preparation import _find_usual_volunteers, prepare_roster
from volunteer_roster_agent.models import (
    Confidence,
    DayOfWeek,
    RequestType,
    RosterRequest,
    Shift,
    Slot,
    TimeSlot,
    Volunteer,
    VolunteerLeaveMessage,
)


class _FakeStructuredLLM:
    """Stands in for `ChatOpenAI(...).with_structured_output(schema)`."""

    def __init__(self, shifts: list[Shift]) -> None:
        self._shifts = shifts

    def invoke(self, prompt: str) -> _ShiftsResult:
        return _ShiftsResult(shifts=self._shifts)


class _FakeLLM:
    """Stands in for `get_llm()`, returning canned structured output."""

    def __init__(self, shifts: list[Shift]) -> None:
        self._shifts = shifts

    def with_structured_output(self, schema: type) -> _FakeStructuredLLM:
        return _FakeStructuredLLM(self._shifts)


class _FakeClassificationLLM:
    def __init__(self, result: RosterRequest) -> None:
        self._result = result

    def with_structured_output(self, schema: type) -> "_FakeClassificationLLM":
        assert schema is RosterRequest
        return self

    def invoke(self, prompt: str) -> RosterRequest:
        assert "Do not generate or" in prompt
        assert "Reference date: 2026-07-17" in prompt
        return self._result


def test_classify_messages_returns_typed_request_without_changing_shifts() -> None:
    expected = RosterRequest(
        employee="Alice",
        date=date(2026, 7, 23),
        shift=TimeSlot.EVENING,
        request_type=RequestType.LEAVE,
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
        "volunteer_roster_agent.graph.nodes.get_llm",
        return_value=_FakeClassificationLLM(expected),
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


def test_roster_graph_runs_without_calling_the_real_llm() -> None:
    shift = Shift(
        id="s1",
        special_event="Sunday Service",
        date=date(2026, 7, 20),
        slot=Slot(id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING),
        min_volunteers=2,
    )

    with patch(
        "volunteer_roster_agent.graph.nodes.get_llm",
        return_value=_FakeLLM([shift]),
    ):
        graph = build_roster_graph()
        result = graph.invoke(
            {
                "month": 7,
                "year": 2026,
                "previous_shifts": [],
                "shifts": [shift],
                "recurring_slots": [],
                "volunteers": [],
                "system_messages": [],
                "volunteer_leave_messages": [],
            }
        )

    # `shifts` were already provided and both message lists are empty, so only
    # `review_roster` should have called the (fake) LLM; the rest are no-ops.
    assert result["shifts"] == [shift]


def test_prepare_roster_generates_shifts_from_recurring_slots() -> None:
    monday_morning = Slot(id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING)

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
    monday_morning = Slot(id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING)
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
    monday_morning = Slot(id=1, day_of_week=DayOfWeek.MONDAY, time_slot=TimeSlot.MORNING)
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
