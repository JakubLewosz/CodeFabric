import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState

# 1. Ładujemy zmienne z pliku .env
load_dotenv()

# 2. Pobieramy konfigurację
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN")
MODEL_NAME = os.getenv("MODEL_CHAT", "llama3") # Domyślnie llama3
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0,
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        }
    }
)

def planner_node(state: AgentState):
    messages = state["messages"]
    sys_msg = SystemMessage(content="""
    Jesteś Głównym Architektem Oprogramowania (Tech Lead).
    Stwórz plan implementacji: technologie, lista plików, opis zawartości.
    """)
    response = llm.invoke([sys_msg] + messages)
    return {"plan": response.content, "messages": [response]}