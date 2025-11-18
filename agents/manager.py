from langchain_ollama import ChatOllama
from state import AgentState
from langchain_core.messages import SystemMessage

llm = ChatOllama(model="llama3", format="json", temperature=0)

def manager_node(state: AgentState):
    messages = state["messages"]
    plan = state.get("plan")
    files = state.get("current_files")
    
    # Prosta logika decyzyjna w Pythonie (bardziej niezawodna niż LLM na tym etapie)
    # 1. Jeśli nie ma planu -> idź do Plannera
    if not plan:
        return {"next_node": "planner"}
    
    # 2. Jeśli jest plan, ale nie ma plików -> idź do Codera
    if plan and not files:
        return {"next_node": "coder"}
        
    # 3. Jeśli są pliki -> Koniec
    return {"next_node": "end"}