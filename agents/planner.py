import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState

load_dotenv()

# --- KONFIGURACJA ---
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_CHAT", "llama3")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0,
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {"Authorization": f"Bearer {OLLAMA_TOKEN}"} if OLLAMA_TOKEN else {}
    }
)

def planner_node(state: AgentState):
    messages = state["messages"]
    
    # NOWY PROMPT Z ZASADĄ ROOT FOLDERU
    sys_msg = SystemMessage(content="""
    Jesteś Głównym Architektem Oprogramowania (Tech Lead).
    Twoim zadaniem jest stworzyć strukturę plików dla zadanego projektu.
    
    ZASADA KATALOGU GŁÓWNEGO (NAJWAŻNIEJSZE):
    1. Wymyśl krótką, bezpieczną nazwę dla projektu (np. 'snake_game', 'todo_app').
    2. WSZYSTKIE pliki muszą znajdować się wewnątrz tego katalogu.
    
    Przykład poprawnej struktury:
    - snake_game/main.py
    - snake_game/README.md
    - snake_game/assets/style.css
    
    Przykład BŁĘDNEJ struktury (nie rób tak):
    - main.py (brak folderu głównego)
    - assets/style.css (brak folderu głównego)
    
    TWOJA ODPOWIEDŹ MUSI ZAWIERAĆ:
    1. Nazwę wybranego folderu głównego.
    2. Listę pełnych ścieżek (z folderem głównym).
    3. Opis zawartości plików.
    4. Obowiązkowo plik 'README.md' wewnątrz folderu głównego.
    
    Nie pisz kodu, tylko PLAN.
    """)
    
    print("--- ARCHITEKT PLANUJE STRUKTURĘ (ROOT FOLDER) ---")
    response = llm.invoke([sys_msg] + messages)
    
    return {
        "plan": response.content,
        "messages": [response]
    }