"""Sample roster data used by the local main entry point."""

from datetime import date

from volunteer_roster_agent.graph import RosterState
from volunteer_roster_agent.models import (
    DayOfWeek,
    Shift,
    Slot,
    SystemMessage,
    TimeSlot,
    Volunteer,
    VolunteerLeaveMessage,
)

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

_RECURRING_SLOTS = [
    Slot(id=slot_id, day_of_week=day, time_slot=time_slot)
    for slot_id, (day, time_slot) in enumerate(
        ((day, time_slot) for day in DayOfWeek for time_slot in TimeSlot),
        start=1,
    )
]
_SLOT = {(slot.day_of_week, slot.time_slot): slot for slot in _RECURRING_SLOTS}

_PREVIOUS_SHIFTS = [
    Shift(
        id="prev-mon-morning",
        special_event="",
        date=date(2026, 6, 1),
        slot=_SLOT[(DayOfWeek.MONDAY, TimeSlot.MORNING)],
        assigned_volunteer_ids=(_WANGFANG.id,),
    ),
    Shift(
        id="prev-mon-afternoon",
        special_event="",
        date=date(2026, 6, 1),
        slot=_SLOT[(DayOfWeek.MONDAY, TimeSlot.AFTERNOON)],
        assigned_volunteer_ids=(_CHENWEI.id,),
    ),
    Shift(
        id="prev-tue-morning",
        special_event="",
        date=date(2026, 6, 2),
        slot=_SLOT[(DayOfWeek.TUESDAY, TimeSlot.MORNING)],
        assigned_volunteer_ids=(_LIMING.id,),
    ),
    Shift(
        id="prev-tue-afternoon",
        special_event="",
        date=date(2026, 6, 2),
        slot=_SLOT[(DayOfWeek.TUESDAY, TimeSlot.AFTERNOON)],
        assigned_volunteer_ids=(_OLIVIA.id,),
    ),
    Shift(
        id="prev-wed-afternoon",
        special_event="",
        date=date(2026, 6, 3),
        slot=_SLOT[(DayOfWeek.WEDNESDAY, TimeSlot.AFTERNOON)],
        assigned_volunteer_ids=(_SARAH.id,),
    ),
    Shift(
        id="prev-wed-evening",
        special_event="",
        date=date(2026, 6, 3),
        slot=_SLOT[(DayOfWeek.WEDNESDAY, TimeSlot.EVENING)],
        assigned_volunteer_ids=(_EMILY.id,),
    ),
    Shift(
        id="prev-thu-morning",
        special_event="",
        date=date(2026, 6, 4),
        slot=_SLOT[(DayOfWeek.THURSDAY, TimeSlot.MORNING)],
        assigned_volunteer_ids=(_DANIEL.id,),
    ),
    Shift(
        id="prev-fri-morning",
        special_event="",
        date=date(2026, 6, 5),
        slot=_SLOT[(DayOfWeek.FRIDAY, TimeSlot.MORNING)],
        assigned_volunteer_ids=(_ZHANGJING.id,),
    ),
]

_SYSTEM_MESSAGES = [
    SystemMessage(
        text="August 7 has a special event in the evening and requires 3 volunteers."
    )
]

_VOLUNTEER_MESSAGES = [
    VolunteerLeaveMessage(text="Sarah 下周三下午不能来，但周五晚上可以。"),
    VolunteerLeaveMessage(text="李明这周二上午需要请假，周四上午可以补班。"),
    VolunteerLeaveMessage(text="Emily 周三晚上有课，不能参加该时段。"),
    VolunteerLeaveMessage(text="王芳周一上午不能来，周二下午和周四下午均可安排。"),
    VolunteerLeaveMessage(text="Daniel 周四上午需处理家庭事务，无法值班。"),
    VolunteerLeaveMessage(text="陈伟下周一下午不能来，但周三上午和周五上午可以。"),
    VolunteerLeaveMessage(text="Olivia 周二下午不能来，周五晚上优先安排。"),
    VolunteerLeaveMessage(text="张静周五上午不能来，其余已登记的时段可以参加。"),
]


def build_sample_state() -> RosterState:
    """Return a fresh state for the August 2026 demonstration roster."""
    return {
        "month": 8,
        "year": 2026,
        "reference_date": date(2026, 7, 17),
        "previous_shifts": list(_PREVIOUS_SHIFTS),
        "shifts": [],
        "recurring_slots": list(_RECURRING_SLOTS),
        "volunteers": list(_VOLUNTEERS),
        "system_messages": list(_SYSTEM_MESSAGES),
        "volunteer_leave_messages": list(_VOLUNTEER_MESSAGES),
    }
