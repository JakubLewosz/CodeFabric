import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from state import AgentState

load_dotenv()

def manager_node(state: AgentState):
    plan = state.get("plan")
    files = state.get("current_files")
    feedback = state.get("feedback")
    revision_count = state.get("revision_count", 0)
    plan_approved = state.get("plan_approved", False)

    # 1. Bezpiecznik
    if revision_count > 3:
        print("🛑 MANAGER: Limit poprawek.")
        return {"next_node": "end"}

    # 2. Brak planu -> Planner
    if not plan:
        return {"next_node": "planner"}

    # 3. Czekanie na zatwierdzenie (UI)
    if plan and not plan_approved:
        if feedback: return {"next_node": "planner"}
        return {"next_node": "end"} 

    # 4. START KODOWANIA (POPRAWIONA LOGIKA)
    # Jeśli plan jest zatwierdzony, a nie ma jeszcze recenzji (feedback jest pusty),
    # to znaczy, że musimy uruchomić Programistę.
    # Ignorujemy fakt istnienia plików (mogą być stare).
    if plan and plan_approved and not feedback:
        return {"next_node": "coder"}

    # 5. Pętla Jakości
    if files and feedback:
        if "APPROVE" in str(feedback).upper():
            return {"next_node": "end"}
        elif "REJECT" in str(feedback).upper():
            return {"next_node": "coder"}

    return {"next_node": "end"}