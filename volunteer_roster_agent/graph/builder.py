from langgraph.graph import END, START, StateGraph

from volunteer_roster_agent.graph.classification import classify_messages
from volunteer_roster_agent.graph.preparation import prepare_roster
from volunteer_roster_agent.graph.requirements import apply_roster_requirements
from volunteer_roster_agent.graph.scheduling import solve_roster
from volunteer_roster_agent.graph.state import RosterState

# Node names in pipeline order, exposed so callers can stop the graph early
# (e.g. for testing a single node without running the rest of the,
# LLM-driven, pipeline).
NODE_ORDER = [
    "prepare_roster",
    "classify_messages",
    "apply_roster_requirements",
    "solve_roster",
]


def build_roster_graph(*, stop_after: str | None = None):
    """Compile the volunteer roster LangGraph workflow.

    If `stop_after` is set to one of the names in `NODE_ORDER` (other than the
    last), the graph will run up to and including that node, then return the
    state as it stood at that point, without running the remaining nodes.
    """
    builder = StateGraph(RosterState)

    builder.add_node("prepare_roster", prepare_roster)
    builder.add_node("classify_messages", classify_messages)
    builder.add_node("apply_roster_requirements", apply_roster_requirements)
    builder.add_node("solve_roster", solve_roster)

    builder.add_edge(START, "prepare_roster")
    builder.add_edge("prepare_roster", "classify_messages")
    builder.add_edge("classify_messages", "apply_roster_requirements")
    builder.add_edge("apply_roster_requirements", "solve_roster")
    builder.add_edge("solve_roster", END)

    interrupt_before = None
    if stop_after is not None:
        next_index = NODE_ORDER.index(stop_after) + 1
        if next_index < len(NODE_ORDER):
            interrupt_before = [NODE_ORDER[next_index]]

    return builder.compile(interrupt_before=interrupt_before)
