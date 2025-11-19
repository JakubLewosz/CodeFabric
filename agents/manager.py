import os
from state import AgentState

def manager_node(state: AgentState):
    plan = state.get("plan")
    files = state.get("current_files")
    feedback = state.get("feedback")
    revision_count = state.get("revision_count", 0)
    plan_approved = state.get("plan_approved", False)

    # 1. Bezpiecznik (Limit poprawek)
    if revision_count > 3:
        return {"next_node": "end"}

    # 2. Brak planu -> Planner
    if not plan:
        return {"next_node": "planner"}

    # 3. Czekanie na zatwierdzenie planu (UI)
    if plan and not plan_approved:
        if feedback: return {"next_node": "planner"} # Poprawki planu
        return {"next_node": "end"} # Stop dla UI

    # 4. Plan OK, brak plików -> Coder
    if plan and plan_approved and not files:
        return {"next_node": "coder"}

    # 5. Pętla jakości (Reviewer)
    if files and feedback:
        if "APPROVE" in str(feedback).upper():
            # SUKCES - KONIEC
            return {"next_node": "end"}
        
        elif "REJECT" in str(feedback).upper():
            # POPRAWKI - DO KODERA
            return {"next_node": "coder"}
            
    # Domyślny koniec
    return {"next_node": "end"}