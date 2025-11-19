from langchain_core.messages import SystemMessage
from state import AgentState
from tools.llm_factory import get_llm

def planner_node(state: AgentState):
    model_name = state.get("model_names", {}).get("chat", "mistral:7b")
    llm = get_llm(model_name, temperature=0) 
    
    messages = state["messages"]
    feedback = state.get("feedback", "")
    
    # --- NOWOŚĆ: CZYTAMY ISTNIEJĄCE PLIKI ZE STANU ---
    current_files = state.get("current_files", [])
    files_context = ", ".join(current_files) if current_files else "BRAK (Pusty folder)"
    
    # Logika wyboru promptu
    if feedback and not state.get("plan_approved"):
        print(f"--- ARCHITEKT ({model_name}): POPRAWKI PLANU ---")
        context_msg = f"Użytkownik zgłosił uwagi: {feedback}"
    else:
        print(f"--- ARCHITEKT ({model_name}): ANALIZA PROJEKTU ---")
        context_msg = "Stwórz lub zaktualizuj strukturę plików."

    sys_msg = SystemMessage(content=f"""
    Jesteś Głównym Architektem Oprogramowania.
    
    STAN OBECNY WORKSPACE (Pliki, które już istnieją):
    [{files_context}]
    
    ZADANIE:
    {context_msg}
    
    ZASADY:
    1. Jeśli workspace jest pusty -> Zaplanuj pełną strukturę (folder główny, README.md).
    2. Jeśli pliki istnieją -> Zaplanuj TYLKO niezbędne zmiany lub nowe pliki. Nie niszcz tego, co działa, jeśli nie trzeba.
    3. Jeśli użytkownik prosi o zmianę (np. "zmień kolor"), wskaż plik do edycji.
    
    TWOJA ODPOWIEDŹ MUSI ZAWIERAĆ:
    1. Listę plików do utworzenia LUB nadpisania.
    2. Opis co w nich zmienić/napisać.
    
    Nie pisz kodu. Tylko plan.
    """)
    
    response = llm.invoke([sys_msg] + messages)
    
    return {
        "plan": response.content,
        "messages": [response],
        "feedback": None
    }