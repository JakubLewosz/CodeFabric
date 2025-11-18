# Plik: state.py
from typing import TypedDict, Annotated, List
import operator

class AgentState(TypedDict):
    """
    Współdzielony stan między agentami.
    Przechowuje historię rozmowy, plan działania i listę plików.
    """
    messages: Annotated[List[str], operator.add]  # Historia czatu
    next_node: str                                # Decyzja managera: kto następny?
    plan: str                                     # Tekstowy plan projektu
    current_files: List[str]                      # Lista plików stworzonych w /workspace
    revision_count: int                           # Licznik poprawek (pętla bezpieczeństwa)
    feedback: str                                 # Uwagi od Reviewera