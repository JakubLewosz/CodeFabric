# Plik: agents/coder.py
import os
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState
from tools.file_ops import write_file

# --- KONFIGURACJA POŁĄCZENIA ---
OLLAMA_TOKEN = "twoj-tajny-token"
OLLAMA_URL = "https://localhost:11434"

# Używamy DeepSeek Coder z autoryzacją i pominięciem SSL
llm = ChatOllama(
    model="deepseek-coder-v2", # Lub "llama3" jeśli nie masz deepseeka
    base_url=OLLAMA_URL,
    temperature=0.2,
    client_kwargs={
        "verify": False,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        }
    }
)

def coder_node(state: AgentState):
    plan = state["plan"]
    
    sys_msg = SystemMessage(content=f"""
    Jesteś Senior Developerem. Twoim zadaniem jest napisać kod na podstawie otrzymanego PLANU.
    
    PLAN:
    {plan}
    
    INSTRUKCJE:
    1. Dla każdego pliku z planu, wygeneruj kompletny, działający kod.
    2. Twoja odpowiedź musi być sformatowana tak, abym mógł ją łatwo przetworzyć.
    
    WAŻNE:
    Symulujemy pracę. Napisz treść plików, a ja (system) zapiszę je na dysku.
    """)
    
    response = llm.invoke([sys_msg])
    
    # Symulacja zapisu (dla uproszczenia w MVP)
    # W pełnej wersji AI powinno wywoływać narzędzie, tutaj robimy to "na sztywno" dla testu
    write_file("README_AI.md", f"Projekt wygenerowany na podstawie planu:\n{plan}\n\nKod:\n{response.content}")
    
    return {
        "current_files": ["README_AI.md"],
        "messages": [response]
    }