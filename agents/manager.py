import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from state import AgentState

# --- KONFIGURACJA ---
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_CHAT", "llama3")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

# Inicjalizacja modelu (nawet jeśli w tej wersji logiki manager używa głównie if/else, 
# warto to mieć na przyszłość do bardziej skomplikowanych decyzji)
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
    """
    Agent Zarządzający (Supervisor). 
    Decyduje o przepływie pracy na podstawie stanu projektu.
    """
    # Pobieramy dane ze stanu
    plan = state.get("plan")
    files = state.get("current_files")
    feedback = state.get("feedback")
    revision_count = state.get("revision_count", 0)

    # 1. HAMULEC BEZPIECZEŃSTWA (Max 3 poprawki)
    # Zapobiega nieskończonej pętli, jeśli Coder i Reviewer nie mogą się dogadać.
    if revision_count > 3:
        print("!!! LIMIT POPRAWEK OSIĄGNIĘTY. KOŃCZĘ MIMO BŁĘDÓW.")
        return {"next_node": "end"}

    # 2. Brak planu -> Idziemy do Plannera
    if not plan:
        return {"next_node": "planner"}

    # 3. Jest plan, ale nie ma plików -> Idziemy do Codera
    if plan and not files:
        return {"next_node": "coder"}

    # 4. Są pliki i jest feedback od Reviewera -> Analiza decyzji
    # (To się wydarzy, gdy workflow przejdzie Coder -> Reviewer -> Manager)
    if files and feedback:
        if "APPROVE" in str(feedback).upper():
            print("--- MANAGER: PROJEKT ZAAKCEPTOWANY ---")
            return {"next_node": "end"}
        
        elif "REJECT" in str(feedback).upper():
            print(f"--- MANAGER: ODRZUCONE. WRACAM DO PROGRAMISTY (Próba {revision_count+1}) ---")
            return {"next_node": "coder"}
            
        else:
            # Fallback: Jeśli Reviewer napisał coś niejasnego, dla bezpieczeństwa kończymy
            print("--- MANAGER: FEEDBACK NIEJASNY, KOŃCZĘ ---")
            return {"next_node": "end"}

    # 5. Fallback (np. gdy są pliki, ale jeszcze nie ma feedbacku - choć w tym grafie to rzadkie)
    # Jeśli mamy pliki, ale nie wpadliśmy w pętlę feedbacku, uznajemy że gotowe.
    return {"next_node": "end"}