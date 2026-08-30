"""Shared LangGraph state used by every CodeFabric agent."""

from typing import Annotated, Dict, List, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

RouteName = Literal["planner", "coder", "reviewer", "end"]


class AgentState(TypedDict, total=False):
    """
    State exchanged between graph nodes.

    Nodes intentionally return partial dictionaries, therefore every key is
    optional at the type level. ``messages`` is the only accumulating field;
    LangGraph's message reducer preserves message IDs and understands both
    ``BaseMessage`` objects and their dictionary representation.
    """

    messages: Annotated[List[BaseMessage], add_messages]
    next_node: RouteName
    plan: Optional[str]
    current_files: List[str]
    revision_count: int
    feedback: Optional[str]
    plan_approved: bool
    model_names: Dict[str, str]
    chat_workspace: Optional[str]
    last_error: Optional[str]
    error_stage: Optional[Literal["planner", "coder", "reviewer", "quality"]]
    retry_stage: Optional[Literal["coder", "coder_quality", "reviewer"]]
    retry_feedback: Optional[str]
