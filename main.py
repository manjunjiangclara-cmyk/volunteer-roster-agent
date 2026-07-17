import argparse
from datetime import date
from pathlib import Path

from volunteer_roster_agent.graph import NODE_ORDER, build_roster_graph
from volunteer_roster_agent.models import (
    DayOfWeek,
    Shift,
    Slot,
    SystemMessage,
    TimeSlot,
    Volunteer,
    VolunteerLeaveMessage,
)

# Volunteers mentioned in the incoming leave-request messages, plus the
# recurring slot each of them usually covers (inferred from the "usual" half
# of each message, e.g. "Sarah ... 下周三下午不能来" -> Sarah's usual slot is
# Wednesday afternoon).
_SARAH = Volunteer(id="v-sarah", name="Sarah")
_LIMING = Volunteer(id="v-liming", name="李明")
_EMILY = Volunteer(id="v-emily", name="Emily")
_WANGFANG = Volunteer(id="v-wangfang", name="王芳")
_DANIEL = Volunteer(id="v-daniel", name="Daniel")
_CHENWEI = Volunteer(id="v-chenwei", name="陈伟")
_OLIVIA = Volunteer(id="v-olivia", name="Olivia")
_ZHANGJING = Volunteer(id="v-zhangjing", name="张静")
_VOLUNTEERS = [
    _SARAH,
    _LIMING,
    _EMILY,
    _WANGFANG,
    _DANIEL,
    _CHENWEI,
    _OLIVIA,
    _ZHANGJING,
]

# The recurring weekly schedule: every day of the week has a morning,
# afternoon, and evening slot. `prepare_roster` creates one shift per slot for
# every date in the target month that falls on that slot's `day_of_week` -- no
# LLM call is needed, since this schedule is already known.
_RECURRING_SLOTS = [
    Slot(id=slot_id, day_of_week=day, time_slot=time_slot)
    for slot_id, (day, time_slot) in enumerate(
        ((day, time_slot) for day in DayOfWeek for time_slot in TimeSlot),
        start=1,
    )
]
_SLOT_BY_DAY_AND_TIME = {(slot.day_of_week, slot.time_slot): slot for slot in _RECURRING_SLOTS}

# A previous (June 2026) roster showing who usually covers each slot, so
# `prepare_roster` can fill the new roster deterministically.
_PREVIOUS_SHIFTS = [
    Shift(
        id="prev-mon-morning",
        special_event="",
        date=date(2026, 6, 1),
        slot=_SLOT_BY_DAY_AND_TIME[(DayOfWeek.MONDAY, TimeSlot.MORNING)],
        min_volunteers=1,
        assigned_volunteer_ids=(_WANGFANG.id,),
    ),
    Shift(
        id="prev-mon-afternoon",
        special_event="",
        date=date(2026, 6, 1),
        slot=_SLOT_BY_DAY_AND_TIME[(DayOfWeek.MONDAY, TimeSlot.AFTERNOON)],
        min_volunteers=1,
        assigned_volunteer_ids=(_CHENWEI.id,),
    ),
    Shift(
        id="prev-tue-morning",
        special_event="",
        date=date(2026, 6, 2),
        slot=_SLOT_BY_DAY_AND_TIME[(DayOfWeek.TUESDAY, TimeSlot.MORNING)],
        min_volunteers=1,
        assigned_volunteer_ids=(_LIMING.id,),
    ),
    Shift(
        id="prev-tue-afternoon",
        special_event="",
        date=date(2026, 6, 2),
        slot=_SLOT_BY_DAY_AND_TIME[(DayOfWeek.TUESDAY, TimeSlot.AFTERNOON)],
        min_volunteers=1,
        assigned_volunteer_ids=(_OLIVIA.id,),
    ),
    Shift(
        id="prev-wed-afternoon",
        special_event="",
        date=date(2026, 6, 3),
        slot=_SLOT_BY_DAY_AND_TIME[(DayOfWeek.WEDNESDAY, TimeSlot.AFTERNOON)],
        min_volunteers=1,
        assigned_volunteer_ids=(_SARAH.id,),
    ),
    Shift(
        id="prev-wed-evening",
        special_event="",
        date=date(2026, 6, 3),
        slot=_SLOT_BY_DAY_AND_TIME[(DayOfWeek.WEDNESDAY, TimeSlot.EVENING)],
        min_volunteers=1,
        assigned_volunteer_ids=(_EMILY.id,),
    ),
    Shift(
        id="prev-thu-morning",
        special_event="",
        date=date(2026, 6, 4),
        slot=_SLOT_BY_DAY_AND_TIME[(DayOfWeek.THURSDAY, TimeSlot.MORNING)],
        min_volunteers=1,
        assigned_volunteer_ids=(_DANIEL.id,),
    ),
    Shift(
        id="prev-fri-morning",
        special_event="",
        date=date(2026, 6, 5),
        slot=_SLOT_BY_DAY_AND_TIME[(DayOfWeek.FRIDAY, TimeSlot.MORNING)],
        min_volunteers=1,
        assigned_volunteer_ids=(_ZHANGJING.id,),
    ),
]

# Mandatory operational instructions are applied before volunteer requests.
_SYSTEM_MESSAGES = [
    SystemMessage(text="August 7 has a special event in the evening and requires 3 volunteers."),
]

# Natural-language volunteer requests are interpreted by the LLM only after
# mandatory system instructions have been applied.
_VOLUNTEER_LEAVE_MESSAGES = [
    VolunteerLeaveMessage(text="Sarah 下周三下午不能来，但周五晚上可以。"),
    VolunteerLeaveMessage(text="李明这周二上午需要请假，周四上午可以补班。"),
    VolunteerLeaveMessage(text="Emily 周三晚上有课，不能参加该时段。"),
    VolunteerLeaveMessage(text="王芳周一上午不能来，周二下午和周四下午均可安排。"),
    VolunteerLeaveMessage(text="Daniel 周四上午需处理家庭事务，无法值班。"),
    VolunteerLeaveMessage(text="陈伟下周一下午不能来，但周三上午和周五上午可以。"),
    VolunteerLeaveMessage(text="Olivia 周二下午不能来，周五晚上优先安排。"),
    VolunteerLeaveMessage(text="张静周五上午不能来，其余已登记的时段可以参加。"),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the volunteer roster agent.")
    parser.add_argument(
        "--stop-after",
        choices=NODE_ORDER,
        default=None,
        help=(
            "Stop the graph early, right after this node, instead of running "
            "the full pipeline. Useful for quickly testing a single node."
        ),
    )
    parser.add_argument(
        "--output",
        default="roster_output.txt",
        help="File to write the resulting roster to (default: roster_output.txt).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    graph = build_roster_graph(stop_after=args.stop_after)
    result = graph.invoke(
        {
            "month": 8,
            "year": 2026,
            "previous_shifts": _PREVIOUS_SHIFTS,
            "shifts": [
            ],
            "recurring_slots": _RECURRING_SLOTS,
            "volunteers": _VOLUNTEERS,
            "system_messages": _SYSTEM_MESSAGES,
            "volunteer_leave_messages": _VOLUNTEER_LEAVE_MESSAGES,
        }
    )

    lines = ["Volunteer roster agent"]
    for shift in result["shifts"]:
        lines.append(
            f"- {shift.id} ({shift.date}, {shift.slot.day_of_week} "
            f"{shift.slot.time_slot}): {shift.status} "
            f"volunteers={shift.assigned_volunteer_ids}"
        )

    output_path = Path(args.output)
    output_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(result['shifts'])} shift(s) to {output_path.resolve()}")


if __name__ == "__main__":
    main()
