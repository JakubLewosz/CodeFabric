from typing import Literal

from langgraph.graph import END, StateGraph

from agents.coder import coder_node
from agents.manager import manager_node
from agents.planner import planner_node
from agents.reviewer import reviewer_node
from state import AgentState


def route_manager(state: AgentState) -> Literal["planner", "coder", "reviewer", "end"]:
    """Return only a route understood by the graph.

    A missing or malformed manager result ends the current run safely instead
    of raising a routing ``KeyError`` or accidentally selecting another node.
    """
    route = state.get("next_node")
    if isinstance(route, str):
        normalized = route.strip().lower()
        if normalized in {"planner", "coder", "reviewer", "end"}:
            return normalized  # type: ignore[return-value]
    return "end"


def create_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("manager", manager_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("reviewer", reviewer_node)

    workflow.set_entry_point("manager")

    workflow.add_conditional_edges(
        "manager",
        route_manager,
        {
            "planner": "planner",
            "coder": "coder",
            "reviewer": "reviewer",
            "end": END,
        },
    )

    workflow.add_edge("planner", "manager")
    workflow.add_edge("coder", "reviewer")
    workflow.add_edge("reviewer", "manager")

    return workflow.compile()


app = create_graph()
