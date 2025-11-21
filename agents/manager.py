import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from state import AgentState

load_dotenv()

def manager_node(state: AgentState):
    """
    Agent Zarządzający.
    POPRAWKA: Priorytet ma sukces (APPROVE) nad limitem prób.
    """
    plan = state.get("plan")
    files = state.get("current_files")
    feedback = state.get("feedback")
    revision_count = state.get("revision_count", 0)
    plan_approved = state.get("plan_approved", False)

    # --- 1. NAJWAŻNIEJSZE: CZY MAMY SUKCES? ---
    # Sprawdzamy to JAKO PIERWSZE. Jeśli Recenzent dał APPROVE,
    # to nie obchodzi nas, że to była 10. próba. Ważne, że się udało.
    if files and feedback and "APPROVE" in str(feedback).upper():
        print("✅ MANAGER: Projekt zatwierdzony (Mimo licznika).")
        return {"next_node": "end"}

    # --- 2. BEZPIECZNIK (LIMIT POPRAWEK) ---
    # Dopiero jeśli NIE MA sukcesu, sprawdzamy czy nie kręcimy się w kółko.
    if revision_count >= 3:
        print(f"🛑 MANAGER: Limit poprawek ({revision_count}). Kończę, oddaję co mam.")
        # Tutaj kończymy, nawet jeśli kod jest błędny, żeby nie zawiesić komputera.
        return {"next_node": "end"}

    # --- 3. STANDARDOWY PRZEPŁYW ---
    
    # Brak planu -> Planner
    if not plan:
        return {"next_node": "planner"}

    # Czekanie na zatwierdzenie planu (UI)
    if plan and not plan_approved:
        if feedback: return {"next_node": "planner"} # Poprawki planu od człowieka
        return {"next_node": "end"} # Pauza dla UI

    # Plan zatwierdzony, brak plików -> Coder
    if plan and plan_approved and not files:
        return {"next_node": "coder"}

    # Pętla Jakości (Jeśli feedback to REJECT)
    if files and feedback and "REJECT" in str(feedback).upper():
        print(f"⚠️ MANAGER: Błędy wykryte. Zarządzam poprawkę (Próba {revision_count + 1}).")
        return {"next_node": "coder"}

    # Fallback
    return {"next_node": "end"}