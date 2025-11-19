import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from state import AgentState

load_dotenv()

# --- KONFIGURACJA (Dla porządku, choć manager używa głównie logiki) ---
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

def manager_node(state: AgentState):
    """
    Agent Zarządzający. Pilnuje, żeby proces nie wpadł w pętlę.
    """
    plan = state.get("plan")
    files = state.get("current_files")
    feedback = state.get("feedback")
    revision_count = state.get("revision_count", 0)
    plan_approved = state.get("plan_approved", False)

    # 1. BEZPIECZNIK (CIRCUIT BREAKER) - NAJWAŻNIEJSZE!
    # Jeśli próbowaliśmy naprawiać kod już 3 razy, przerywamy.
    if revision_count >= 3:
        print(f"🛑 MANAGER: Osiągnięto limit poprawek ({revision_count}). Kończę wymuszenie.")
        return {"next_node": "end"}

    # 2. Brak planu -> Planner
    if not plan:
        return {"next_node": "planner"}

    # 3. Plan jest, ale niezatwierdzony -> Czekaj na UI (end) lub Planner
    if plan and not plan_approved:
        if feedback: # Jeśli człowiek zgłosił uwagi do planu
            return {"next_node": "planner"}
        return {"next_node": "end"} # Czekamy na kliknięcie w Streamlit

    # 4. Plan zatwierdzony, brak plików -> Coder
    if plan and plan_approved and not files:
        return {"next_node": "coder"}

    # 5. Pętla Jakości (Reviewer)
    # Jeśli mamy pliki i feedback od Reviewera
    if files and feedback:
        if "APPROVE" in str(feedback).upper():
            print("✅ MANAGER: Projekt zatwierdzony.")
            return {"next_node": "end"}
        
        elif "REJECT" in str(feedback).upper():
            print(f"⚠️ MANAGER: Błędy wykryte. Zarządzam poprawkę (Próba {revision_count + 1}/3).")
            return {"next_node": "coder"}
            
        else:
            # Fallback: Jeśli Reviewer napisał coś dziwnego
            return {"next_node": "end"}

    # Domyślny koniec
    return {"next_node": "end"}