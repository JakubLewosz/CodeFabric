import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState
from tools.llm_factory import get_llm

def planner_node(state: AgentState):
    model_name = state.get("model_names", {}).get("chat", "mistral:7b")
    llm = get_llm(model_name, temperature=0) 
    
    messages = state["messages"]
    feedback = state.get("feedback", "")
    current_files = state.get("current_files", [])
    
    files_list_str = "\n".join([f"- {f}" for f in current_files]) if current_files else "BRAK (Pusty folder)"
    
    # --- TRYB ROZWOJU (GDY SĄ PLIKI) ---
    if current_files:
        print(f"--- ARCHITEKT ({model_name}): TRYB CHIRURGICZNY (ROZWÓJ) ---")
        system_instruction = f"""
        Jesteś Głównym Architektem. Projekt już istnieje.
        
        OBECNE PLIKI:
        {files_list_str}
        
        ZADANIE:
        Zaplanuj PRECYZYJNE zmiany w kodzie, aby spełnić prośbę użytkownika.
        
        ZASADY KRYTYCZNE DLA EDYCJI:
        1. Nie każ pisać plików od nowa, jeśli to niekonieczne.
        2. Jeśli zmieniamy logikę, wskaż KONKRETNY PLIK i co w nim dodać/zmienić.
        3. Przykład planu edycji: 
           "- main.py: Dodaj zmienną 'score' w klasie Game. Zaktualizuj pętlę draw()."
        
        Nie pisz ogólników typu "Zaktualizuj grę". Pisz technicznie: "W pliku X dodaj Y".
        """
    
    # --- TRYB NOWY PROJEKT ---
    else:
        print(f"--- ARCHITEKT ({model_name}): NOWY PROJEKT ---")
        system_instruction = """
        Jesteś Głównym Architektem.
        Stwórz strukturę plików dla NOWEGO projektu od zera.
        Wymyśl nazwę folderu głównego (np. 'snake_game/').
        """

    tech_requirements = """
    --- WYMAGANIA ODNOŚNIE ODPOWIEDZI ---
    Twoja odpowiedź musi zawierać TYLKO PLAN w formacie listy.
    Używaj pełnych ścieżek (folder/plik).
    """

    final_prompt = SystemMessage(content=system_instruction + "\n" + tech_requirements)
    response = llm.invoke([final_prompt] + messages)
    
    return {
        "plan": response.content,
        "messages": [response],
        "feedback": None
    }