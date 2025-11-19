from typing import TypedDict, Annotated, List, Dict
import operator

class AgentState(TypedDict):
    messages: Annotated[List[str], operator.add]
    next_node: str
    plan: str
    current_files: List[str]
    revision_count: int
    feedback: str
    
    # --- NOWE POLE ---
    # Czy użytkownik kliknął "Zatwierdź Plan"?
    plan_approved: bool
    
    # Konfiguracja modeli
    model_names: Dict[str, str]