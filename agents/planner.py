# Plik: agents/planner.py
import os
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState

# --- KONFIGURACJA POŁĄCZENIA ---
# Wpisz tutaj swój token i URL (jeśli jest inny niż domyślny)
OLLAMA_TOKEN = "twoj-tajny-token" 
OLLAMA_URL = "https://localhost:11434" # Upewnij się, że to https, skoro masz SSL

llm = ChatOllama(
    model="llama3",
    base_url=OLLAMA_URL,
    temperature=0,
    # Tutaj przekazujemy parametry do klienta HTTP (httpx):
    client_kwargs={
        "verify": False,  # Wyłącza weryfikację certyfikatu SSL (self-signed)
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        }
    }
)

def planner_node(state: AgentState):
    messages = state["messages"]
    
    sys_msg = SystemMessage(content="""
    Jesteś Głównym Architektem Oprogramowania (Tech Lead).
    Twoim zadaniem jest przeanalizowanie prośby użytkownika i stworzenie precyzyjnego planu implementacji.
    
    Twoja odpowiedź musi zawierać:
    1. Wybór technologii (Python, HTML, etc.).
    2. Listę plików do utworzenia.
    3. Krótki opis co ma być w każdym pliku.
    
    Nie pisz kodu, tylko PLAN. Bądź zwięzły.
    """)
    
    response = llm.invoke([sys_msg] + messages)
    
    return {
        "plan": response.content,
        "messages": [response]
    }