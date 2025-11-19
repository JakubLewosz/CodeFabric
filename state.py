from typing import TypedDict, Annotated, List, Dict
import operator

class AgentState(TypedDict):
    messages: Annotated[List[str], operator.add]  # Historia czatu
    next_node: str                                # Decyzja routera
    plan: str                                     # Plan projektu
    current_files: List[str]                      # Lista plików
    revision_count: int                           # Licznik poprawek
    feedback: str                                 # Uwagi Recenzenta
    
    # --- NOWE POLE: Konfiguracja Modeli ---
    # Przechowuje np. {"chat": "bielik2.6:11b", "coder": "qwen3-coder:30b"}
    model_names: Dict[str, str]