import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from state import AgentState

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN")
MODEL_NAME = os.getenv("MODEL_CHAT", "llama3")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    format="json",
    temperature=0,
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        } if OLLAMA_TOKEN else {}
    }
)

def manager_node(state: AgentState):
    messages = state["messages"]
    plan = state.get("plan")
    files = state.get("current_files")
    
    # --- HAMULEC BEZPIECZEŃSTWA ---
    # Jeśli w historii mamy już więcej niż 3 wiadomości (User + Planner + Coder),
    # to znaczy, że Coder już pracował. Niezależnie od wyniku - kończymy pętlę.
    if len(messages) >= 3:
        return {"next_node": "end"}
    
    # Standardowa logika
    if not plan:
        return {"next_node": "planner"}
    
    # Jeśli jest plan, ale jeszcze nie byliśmy u Codera (patrz hamulec wyżej)
    if plan:
        return {"next_node": "coder"}
        
    return {"next_node": "end"}