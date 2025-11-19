from langgraph.graph import StateGraph, END
from state import AgentState

# Importujemy wszystkich agentów
from agents.manager import manager_node
from agents.planner import planner_node
from agents.coder import coder_node
from agents.reviewer import reviewer_node  # <--- NOWOŚĆ

def create_graph():
    """Tworzy i kompiluje graf przepływu pracy (workflow)."""
    
    # 1. Inicjalizacja grafu
    workflow = StateGraph(AgentState)
    
    # 2. Dodajemy węzły (Nodes)
    workflow.add_node("manager", manager_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("reviewer", reviewer_node) # <--- NOWOŚĆ
    
    # 3. Punkt startowy
    workflow.set_entry_point("manager")
    
    # 4. Logika warunkowa (Router Managera)
    def router(state: AgentState):
        decision = state["next_node"]
        if decision == "end":
            return END
        return decision

    # Manager decyduje: Planner, Coder lub Koniec
    workflow.add_conditional_edges(
        "manager",
        router,
        {
            "planner": "planner",
            "coder": "coder",
            END: END
        }
    )
    
    # 5. Definicja krawędzi (Edges) - PRZEPŁYW PRACY
    
    # Planista zawsze wraca do Managera z planem
    workflow.add_edge("planner", "manager")
    
    # --- ZMIANA TRASY (PĘTLA JAKOŚCI) ---
    # Programista NIE wraca do Managera. 
    # Programista oddaje kod do Recenzenta.
    workflow.add_edge("coder", "reviewer")
    
    # Recenzent ocenia kod i wysyła raport do Managera
    # Manager wtedy decyduje, czy wrócić do Codera (poprawki), czy zakończyć.
    workflow.add_edge("reviewer", "manager")
    
    # 6. Kompilacja
    return workflow.compile()

# Tworzymy gotową instancję aplikacji
app = create_graph()