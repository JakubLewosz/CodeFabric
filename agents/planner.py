import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState
from tools.llm_factory import get_llm

def planner_node(state: AgentState):
    # 1. Pobieramy model wybrany w UI
    model_name = state.get("model_names", {}).get("chat", "mistral:7b")
    
    # Używamy fabryki (0 temperatury dla precyzji)
    llm = get_llm(model_name, temperature=0) 
    
    messages = state["messages"]
    feedback = state.get("feedback", "")
    current_files = state.get("current_files", [])
    files_context = ", ".join(current_files) if current_files else "BRAK (Pusty folder)"
    
    # Logika wyboru promptu (Poprawka vs Nowy)
    if feedback and not state.get("plan_approved"):
        print(f"--- ARCHITEKT ({model_name}): POPRAWIA PLAN ---")
        context_msg = f"Użytkownik zgłosił uwagi: {feedback}"
    else:
        print(f"--- ARCHITEKT ({model_name}): ANALIZA PROJEKTU ---")
        context_msg = "Stwórz lub zaktualizuj strukturę plików."

    # 2. ROZBUDOWANY PROMPT ARCHITEKTA
    sys_msg = SystemMessage(content=f"""
    Jesteś Głównym Architektem Oprogramowania (Tech Lead).
    Twoim zadaniem jest stworzyć PRECYZYJNĄ strukturę plików dla projektu.
    
    STAN OBECNY WORKSPACE: [{files_context}]
    
    --- WYMAGANIA TECHNOLOGICZNE (KRYTYCZNE) ---
    Jeśli projekt jest w danym języku, MUSISZ uwzględnić pliki konfiguracyjne:
    
    1. C# / .NET:
       - OBOWIĄZKOWO: Plik projektu `.csproj` (np. `MyApp.csproj`).
       - OBOWIĄZKOWO: `Program.cs` z metodą `static void Main(string[] args)`.
       - Opcjonalnie: `Startup.cs` (dla starszego .NET Web API).
       
    2. Python:
       - `requirements.txt` lub `pyproject.toml`.
       - `main.py` lub `app.py` jako punkt wejścia.
       
    3. Node.js / JavaScript:
       - `package.json` (z definicją scripts i dependencies).
       - `index.js` lub `app.js`.
    
    --- ZASADY OGÓLNE ---
    1. ZAWSZE twórz folder główny projektu (np. `CalculatorApp/`).
    2. Wszystkie pliki muszą być wewnątrz tego folderu.
    3. ZAWSZE dodaj `README.md` z instrukcją:
       - Jak skompilować (np. `dotnet build`).
       - Jak uruchomić (np. `dotnet run`).
    
    ZADANIE:
    {context_msg}
    
    TWOJA ODPOWIEDŹ (Tylko PLAN, bez kodu):
    1. Nazwa folderu głównego.
    2. Lista PEŁNYCH ŚCIEŻEK (np. `MyApp/Program.cs`, `MyApp/MyApp.csproj`).
    3. Krótki opis zawartości każdego pliku.
    """)
    
    # 3. Wywołanie
    response = llm.invoke([sys_msg] + messages)
    
    return {
        "plan": response.content,
        "messages": [response],
        "feedback": None
    }