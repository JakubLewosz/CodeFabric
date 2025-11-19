from langgraph.graph import StateGraph, END
from state import AgentState

# Importy agentów
from agents.manager import manager_node
from agents.planner import planner_node
from agents.coder import coder_node
from agents.reviewer import reviewer_node

def create_graph():
    workflow = StateGraph(AgentState)
    
    # Dodajemy węzły
    workflow.add_node("manager", manager_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("reviewer", reviewer_node)
    
    # Start
    workflow.set_entry_point("manager")
    
    # --- POPRAWIONY ROUTER ---
    def router(state: AgentState):
        # Manager zwraca po prostu string: "planner", "coder", "end"
        return state["next_node"]

    # Mapa przejść
    workflow.add_conditional_edges(
        "manager",
        router,
        {
            "planner": "planner",
            "coder": "coder",
            "end": END  # <--- Tu mapujemy string "end" na obiekt END
        }
    )
    
    # Krawędzie zwykłe
    workflow.add_edge("planner", "manager")
    workflow.add_edge("coder", "reviewer")
    workflow.add_edge("reviewer", "manager")
    
    return workflow.compile()

app = create_graph()