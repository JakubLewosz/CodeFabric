from state import AgentState

def manager_node(state: AgentState):
    plan = state.get("plan")
    files = state.get("current_files")
    feedback = state.get("feedback")
    revision_count = state.get("revision_count", 0)
    plan_approved = state.get("plan_approved", False) # Czy zatwierdzono?

    # 1. Hamulec bezpieczeństwa
    if revision_count > 3: 
        return {"next_node": "end"}

    # 2. Brak planu -> Planner
    if not plan:
        return {"next_node": "planner"}

    # 3. Jest plan, ale NIEZATWIERDZONY przez człowieka
    if plan and not plan_approved:
        # Jeśli są uwagi od człowieka (User Feedback) -> Wracamy do Plannera poprawić plan
        if feedback: 
            return {"next_node": "planner"}
        
        # Jeśli nie ma uwag, ale plan jest gotowy -> ZATRZYMUJEMY SIĘ (Czekamy na UI)
        # Zwracamy "end", żeby Streamlit mógł wyświetlić przyciski
        print("--- MANAGER: CZEKAM NA ZATWIERDZENIE PLANU ---")
        return {"next_node": "end"}

    # 4. Plan zatwierdzony, brak plików -> Coder
    if plan and plan_approved and not files:
        return {"next_node": "coder"}

    # 5. Pętla jakości (Recenzent)
    if files and feedback:
        if "APPROVE" in str(feedback).upper(): return {"next_node": "end"}
        elif "REJECT" in str(feedback).upper(): return {"next_node": "coder"}
    
    return {"next_node": "end"}