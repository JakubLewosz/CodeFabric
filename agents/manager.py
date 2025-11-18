# Plik: agents/manager.py
import os
from langchain_ollama import ChatOllama
from state import AgentState

# --- KONFIGURACJA POŁĄCZENIA ---
OLLAMA_TOKEN = "twoj-tajny-token"
OLLAMA_URL = "https://localhost:11434"

llm = ChatOllama(
    model="llama3",
    base_url=OLLAMA_URL,
    format="json",
    temperature=0,
    client_kwargs={
        "verify": False,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        }
    }
)

def manager_node(state: AgentState):
    # Tutaj logika pozostaje bez zmian, bo jest w Pythonie (if/else)
    # Ale jeśli w przyszłości użyjesz llm.invoke(), to obiekt llm jest już skonfigurowany.
    
    plan = state.get("plan")
    files = state.get("current_files")
    
    if not plan:
        return {"next_node": "planner"}
    
    if plan and not files:
        return {"next_node": "coder"}
        
    return {"next_node": "end"}