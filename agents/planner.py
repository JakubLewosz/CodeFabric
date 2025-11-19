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
    
    # NOWY PROMPT DLA PLANISTY
    sys_msg = SystemMessage(content="""
    Jesteś Głównym Architektem Oprogramowania (Tech Lead).
    Twoim zadaniem jest przeanalizowanie prośby użytkownika i stworzenie precyzyjnego planu implementacji.
    
    TWOJA ODPOWIEDŹ MUSI ZAWIERAĆ:
    1. Wybór technologii (Python, HTML, etc.).
    2. Listę wszystkich plików do utworzenia.
    3. Krótki opis co ma być w każdym pliku.
    
    ZASADA OBOWIĄZKOWA:
    W planie ZAWSZE musisz uwzględnić plik 'README.md'.
    Plik ten musi zawierać:
    - Opis projektu.
    - Instrukcję instalacji (np. pip install ...).
    - Instrukcję uruchomienia (np. python app.py).
    
    Nie pisz kodu, tylko PLAN. Bądź zwięzły.
    """)
    
    print("--- ARCHITEKT TWORZY PLAN ---")
    response = llm.invoke([sys_msg] + messages)
    
    return {
        "plan": response.content,
        "messages": [response]
    }