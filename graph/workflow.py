# Plik: graph/workflow.py
from langgraph.graph import StateGraph, END
from state import AgentState

# Importujemy nasze "mózgi"
from agents.manager import manager_node
from agents.planner import planner_node
from agents.coder import coder_node

def create_graph():
    """Tworzy i kompiluje graf przepływu pracy (workflow)."""
    
    # 1. Inicjalizacja grafu z naszym modelem stanu
    workflow = StateGraph(AgentState)
    
    # 2. Dodajemy węzły (Nodes) - czyli naszych pracowników
    workflow.add_node("manager", manager_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    
    # 3. Ustawiamy punkt startowy
    # Zawsze zaczynamy od Managera, który oceni sytuację
    workflow.set_entry_point("manager")
    
    # 4. Logika warunkowa (Conditional Edges)
    # To jest kluczowe: Manager decyduje, gdzie idziemy dalej
    def router(state: AgentState):
        # Pobieramy decyzję managera (np. "planner", "coder", "end")
        decision = state["next_node"]
        
        # Jeśli manager mówi "end", kończymy pracę
        if decision == "end":
            return END
        
        # W przeciwnym razie idziemy do wskazanego agenta
        return decision

    # Dodajemy krawędzie warunkowe wychodzące od Managera
    workflow.add_conditional_edges(
        "manager",
        router,
        {
            "planner": "planner",
            "coder": "coder",
            END: END
        }
    )
    
    # 5. Powrót do Managera
    # Po wykonaniu pracy Planner i Coder ZAWSZE wracają do Managera na raport
    workflow.add_edge("planner", "manager")
    workflow.add_edge("coder", "manager")
    
    # 6. Kompilacja grafu (zamiana w działającą aplikację)
    return workflow.compile()

# Tworzymy gotową instancję aplikacji
app = create_graph()