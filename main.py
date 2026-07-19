from pathlib import Path

from volunteer_roster_agent.graph import build_roster_graph
from volunteer_roster_agent.sample_data import build_sample_state

_OUTPUT_PATH = Path("roster_output.txt")


def main() -> None:
    result = build_roster_graph().invoke(build_sample_state())
    lines = [
        "Volunteer roster agent",
        *(
            f"- {shift.id} ({shift.date}, {shift.slot.day_of_week} "
            f"{shift.slot.time_slot}): {shift.status} "
            f"volunteers={shift.assigned_volunteer_ids}"
            for shift in result["shifts"]
        ),
    ]
    _OUTPUT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(result['shifts'])} shifts to {_OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
