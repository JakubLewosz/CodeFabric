import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState
from tools.llm_factory import get_llm

def planner_node(state: AgentState):
    # 1. Konfiguracja modelu
    model_name = state.get("model_names", {}).get("chat", "mistral:7b")
    llm = get_llm(model_name, temperature=0) 
    
    messages = state["messages"]
    feedback = state.get("feedback", "")
    current_files = state.get("current_files", [])
    
    # Formatujemy listę istniejących plików do promptu
    files_list_str = "\n".join([f"- {f}" for f in current_files]) if current_files else "BRAK (Pusty folder)"
    
    # --- LOGIKA WYBORU TRYBU ---
    
    # SCENARIUSZ 1: POPRAWKI TESTERA (Feedback Loop)
    if feedback and not state.get("plan_approved"):
        print(f"--- ARCHITEKT ({model_name}): TRYB NAPRAWY PLANU ---")
        system_instruction = f"""
        Jesteś Tech Leadem. Poprawiasz plan na podstawie uwag użytkownika.
        
        UWAGI: {feedback}
        POPRZEDNI PLAN: {state.get("plan", "")}
        
        Zaktualizuj plan. Nie zmieniaj tego, co było dobre.
        """

    # SCENARIUSZ 2: ROZWÓJ ISTNIEJĄCEGO PROJEKTU (To naprawia Twój problem!)
    elif current_files:
        print(f"--- ARCHITEKT ({model_name}): TRYB ROZWOJU (FEATURE REQUEST) ---")
        system_instruction = f"""
        Jesteś Tech Leadem. Projekt już istnieje.
        Użytkownik prosi o ZMIANY lub NOWE FUNKCJE w istniejącym kodzie.
        
        OBECNA STRUKTURA PLIKÓW:
        {files_list_str}
        
        ZADANIE:
        Zaplanuj edycję istniejących plików, aby spełnić prośbę użytkownika.
        
        ZASADY KRYTYCZNE DLA ROZWOJU:
        1. NIE twórz nowej struktury folderów, jeśli obecna jest dobra. Użyj istniejących nazw.
        2. Jeśli trzeba zmienić kod w `main.py`, napisz w planie: "Zmodyfikuj main.py, aby dodać..."
        3. NIE usuwaj istniejących plików, chyba że to konieczne.
        4. Jeśli użytkownik chce nową funkcję (np. "dodaj owoc"), wskaż konkretny plik do edycji.
        """

    # SCENARIUSZ 3: NOWY PROJEKT (Pusty folder)
    else:
        print(f"--- ARCHITEKT ({model_name}): NOWY PROJEKT ---")
        system_instruction = f"""
        Jesteś Tech Leadem. Folder roboczy jest pusty.
        Stwórz strukturę plików dla NOWEGO projektu od zera.
        
        ZASADY:
        1. Wymyśl nazwę folderu głównego (np. 'snake_game/').
        2. Wszystkie pliki muszą być w tym folderze.
        3. Uwzględnij 'README.md'.
        """

    # --- WSPÓLNE WYMAGANIA TECHNICZNE ---
    tech_requirements = """
    --- WYMAGANIA ODNOŚNIE ODPOWIEDZI ---
    Twoja odpowiedź musi zawierać TYLKO PLAN w formacie listy punktowanej.
    Dla każdego pliku podaj:
    - Pełną ścieżkę (np. snake/main.py)
    - Instrukcję co ma się w nim znaleźć (lub co zmienić).
    
    Nie pisz kodu.
    """

    # Sklejenie promptu
    final_prompt = SystemMessage(content=system_instruction + "\n" + tech_requirements)
    
    # Wywołanie
    response = llm.invoke([final_prompt] + messages)
    
    return {
        "plan": response.content,
        "messages": [response],
        "feedback": None
    }