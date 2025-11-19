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
    files_context = ", ".join(current_files) if current_files else "BRAK (Pusty folder)"
    
    # Pobieramy STARY PLAN (żeby go nie zapomnieć)
    existing_plan = state.get("plan", "")

    # --- CZĘŚĆ WSPÓLNA PROMPTU (ZASADY) ---
    tech_requirements = """
    --- WYMAGANIA TECHNOLOGICZNE (KRYTYCZNE) ---
    1. C# / .NET:
       - OBOWIĄZKOWO: Plik `.csproj`.
       - OBOWIĄZKOWO: `Program.cs` z `Main`.
    2. Python:
       - `requirements.txt`, `main.py`.
    3. Web:
       - `index.html`, `style.css`, `script.js`.
    
    --- ZASADY OGÓLNE ---
    1. ZAWSZE używaj folderu głównego (np. 'MyApp/').
    2. ZAWSZE dodaj 'README.md'.
    """

    # --- LOGIKA WYBORU TRYBU ---
    if feedback and existing_plan:
        # TRYB POPRAWKI (Maintenance Mode)
        print(f"--- ARCHITEKT ({model_name}): AKTUALIZACJA ISTNIEJĄCEGO PLANU ---")
        sys_msg = SystemMessage(content=f"""
        Jesteś Tech Leadem. Jesteśmy w trakcie projektu.
        Użytkownik lub Tester zgłosił problemy.
        
        POPRZEDNI PLAN PROJEKTU:
        {existing_plan}
        
        UWAGI/BŁĘDY DO NAPRAWIENIA:
        {feedback}
        
        ZADANIE:
        Zaktualizuj powyższy plan, aby rozwiązać problemy.
        NIE ZMIENIAJ całej koncepcji. Nie zmieniaj technologii, jeśli nie zostałeś o to poproszony.
        Zachowaj istniejące pliki, chyba że trzeba je usunąć/zmienić.
        
        {tech_requirements}
        
        TWOJA ODPOWIEDŹ (TYLKO PLAN):
        Zwróć poprawioną listę plików i opisów.
        """)
    else:
        # TRYB NOWY PROJEKT
        print(f"--- ARCHITEKT ({model_name}): TWORZENIE NOWEGO PLANU ---")
        sys_msg = SystemMessage(content=f"""
        Jesteś Tech Leadem. Stwórz strukturę nowego projektu.
        
        STAN WORKSPACE: [{files_context}]
        
        ZADANIE: Stwórz listę plików i opisów.
        
        {tech_requirements}
        """)
    
    response = llm.invoke([sys_msg] + messages)
    
    return {
        "plan": response.content,
        "messages": [response],
        "feedback": None
    }