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
        }
    }
)

def manager_node(state: AgentState):
    plan = state.get("plan")
    files = state.get("current_files")
    
    if not plan:
        return {"next_node": "planner"}
    if plan and not files:
        return {"next_node": "coder"}
        
    return {"next_node": "end"}