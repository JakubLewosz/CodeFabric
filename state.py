from typing import TypedDict, Annotated, List, Dict
import operator

class AgentState(TypedDict):
    messages: Annotated[List[str], operator.add]
    next_node: str
    plan: str
    current_files: List[str]
    revision_count: int
    feedback: str
    
    # To jest kluczowe dla wyboru modeli w Sidebarze
    model_names: Dict[str, str]