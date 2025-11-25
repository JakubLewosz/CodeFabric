import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState
from tools.llm_factory import get_llm

def planner_node(state: AgentState):
    model_name = state.get("model_names", {}).get("chat", "bielik2.6:11b")
    llm = get_llm(model_name, temperature=0, num_ctx=16384) 
    
    messages = state["messages"]
    feedback = state.get("feedback", "")
    current_files = state.get("current_files", [])
    
    files_list_str = "\n".join([f"- {f}" for f in current_files]) if current_files else "BRAK (Pusty folder)"
    
    # === ANALIZA KONTEKSTU ===
    is_new_project = not current_files
    has_user_feedback = bool(feedback)
    
    # === TRYB ROZWOJU (GDY SĄ PLIKI) ===
    if current_files:
        print(f"--- ARCHITEKT ({model_name}): TRYB CHIRURGICZNY (ROZWÓJ) ---")
        
        if has_user_feedback:
            context_info = f"\n🔄 UWAGI UŻYTKOWNIKA:\n{feedback}\n"
        else:
            context_info = ""
        
        system_instruction = f"""
Jesteś Głównym Architektem. Projekt już istnieje.

OBECNE PLIKI:
{files_list_str}
{context_info}

=== ZADANIE ===
Zaplanuj PRECYZYJNE zmiany w kodzie, aby spełnić prośbę użytkownika.

=== ZASADY KRYTYCZNE DLA EDYCJI ===
1. **NIE każ pisać plików od nowa**, jeśli wystarczą drobne zmiany.
2. Używaj formatu: "W pliku X: [konkretna zmiana]"
3. Jeśli zmieniasz logikę, wskaż:
   - Który plik
   - Którą funkcję/klasę
   - Co dokładnie dodać/zmienić/usunąć

❗ KRYTYCZNE: MYŚL O PEŁNEJ INTEGRACJI ❗
Gdy użytkownik prosi o nową funkcję (np. "dodaj niebieski owoc"):
- Nie wystarczy tylko zmienić food.py
- Musisz zaplanować integrację w WSZYSTKICH miejscach:
  * Gdzie zdefiniować (food.py)
  * Gdzie zainicjalizować (main.py: blue_food = ...)
  * Gdzie renderować (main.py game loop: blue_food.draw())
  * Gdzie obsłużyć logikę (main.py: kolizja, punkty)

=== PRZYKŁAD DOBREGO PLANU (Z INTEGRACJĄ) ===
Zadanie: "Dodaj niebieski owoc który daje 2 punkty"
```
- config.py (nowy plik):
  * Dodaj stałe: GRID_SIZE = 20, RED_COLOR = (255,0,0), BLUE_COLOR = (0,0,255)
  
- food.py:
  * Dodaj parametr 'color' i 'points' do __init__
  * Dodaj type hints: def __init__(self, color: str, points: int)
  * self.color = color, self.points = points
  
- main.py inicjalizacja:
  * Import z config.py
  * Dodaj: red_food = Food(color='red', points=1)
  * Dodaj: blue_food = Food(color='blue', points=2)
  
- main.py game loop:
  * Dodaj: blue_food.draw(screen)
  
- main.py kolizje:
  * Refactor: Stwórz funkcję check_food_collision(snake, foods_list)
  * Użyj dla obu owocow zamiast duplikować kod
```

⭐ JAKOŚĆ: Dodaj config.py dla stałych, unikaj duplikacji w kolizjach

=== PRZYKŁAD ZŁEGO PLANU (BEZ INTEGRACJI) ===
❌ "food.py: Dodaj blue_food" (i tyle - brak integracji!)
❌ "Zaktualizuj grę o system punktacji" (za ogólne)

=== FORMAT ODPOWIEDZI ===
Odpowiedz TYLKO w formacie listy z konkretnymi instrukcjami.
Nie pisz wstępów typu "Oto plan:", tylko bezpośrednio:

- plik.py: [konkretna akcja]
- inny_plik.js: [konkretna akcja]
"""
    
    # === TRYB NOWY PROJEKT ===
    else:
        print(f"--- ARCHITEKT ({model_name}): NOWY PROJEKT ---")
        system_instruction = f"""
Jesteś Głównym Architektem. Tworzysz strukturę NOWEGO projektu od zera.

=== ZADANIE ===
Stwórz pełną strukturę plików dla projektu opisanego przez użytkownika.

=== ZASADY ===
1. Wymyśl nazwę folderu głównego (np. 'snake_game/', 'todo_app/')
2. Zaplanuj wszystkie potrzebne pliki z pełnymi ścieżkami
3. Uwzględnij:
   - Plik główny (main.py, app.js, index.html)
   - Moduły/komponenty
   - Konfigurację (jeśli potrzebna)
   - README.md (OBOWIĄZKOWY)

=== PRZYKŁAD DOBREGO PLANU (NOWY PROJEKT) ===
```
- snake_game/main.py: Główna pętla gry, inicjalizacja Pygame
- snake_game/snake.py: Klasa Snake z logiką ruchu
- snake_game/food.py: Klasa Food do zarządzania jedzeniem
- snake_game/config.py: Stałe (SCREEN_WIDTH, COLORS)
- snake_game/README.md: Instrukcja uruchomienia, wymagania
```

=== FORMAT ODPOWIEDZI ===
Lista plików z krótkim opisem ich zadania:
- folder/plik.ext: [co robi ten plik]
"""

    tech_requirements = """

=== WYMAGANIA TECHNICZNE ===
- Używaj pełnych ścieżek (folder/plik.ext)
- Każdy plik musi mieć krótki opis co robi
- NIE używaj zagnieżdżeń głębszych niż 2 poziomy (folder/subfolder/file max)
- README.md jest OBOWIĄZKOWY
"""

    final_prompt = SystemMessage(content=system_instruction + tech_requirements)
    
    # === WYWOŁANIE LLM ===
    try:
        response = llm.invoke([final_prompt] + messages)
        print(f"→ Plan wygenerowany ({len(response.content)} znaków)")
    except Exception as e:
        print(f"⚠️ Błąd podczas planowania: {e}")
        response = type('obj', (object,), {'content': f"BŁĄD: {e}"})()
    
    return {
        "plan": response.content,
        "messages": [response],
        "feedback": None
    }