from langchain_core.messages import SystemMessage
from state import AgentState
from tools.llm_factory import get_llm

def planner_node(state: AgentState):
    # 1. Pobieramy model wybrany w UI (lub domyślny)
    model_name = state.get("model_names", {}).get("chat", "mistral:7b")
    
    # Używamy fabryki (0 temperatury dla precyzji)
    llm = get_llm(model_name, temperature=0) 
    
    messages = state["messages"]
    
    # 2. PEŁNY, ROZBUDOWANY PROMPT
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
    4. Obowiązkowo plik 'README.md' wewnątrz folderu głównego z instrukcją uruchomienia.
    
    Nie pisz kodu, tylko PLAN.
    """)
    
    print(f"--- ARCHITEKT ({model_name}): PLANUJE STRUKTURĘ ---")
    
    # 3. Wywołanie
    response = llm.invoke([sys_msg] + messages)
    
    return {
        "plan": response.content,
        "messages": [response]
    }