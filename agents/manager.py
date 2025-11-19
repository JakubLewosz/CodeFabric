# Manager używa prostej logiki Pythonowej, ale gdyby potrzebował AI:
from state import AgentState
# (Tutaj nie musimy inicjalizować LLM, bo manager to router logiczny if/else)

def manager_node(state: AgentState):
    plan = state.get("plan")
    files = state.get("current_files")
    feedback = state.get("feedback")
    revision_count = state.get("revision_count", 0)

    if revision_count > 3: return {"next_node": "end"}
    if not plan: return {"next_node": "planner"}
    if plan and not files: return {"next_node": "coder"}

    if files and feedback:
        if "APPROVE" in str(feedback).upper(): return {"next_node": "end"}
        elif "REJECT" in str(feedback).upper(): return {"next_node": "coder"}
    
    return {"next_node": "end"}