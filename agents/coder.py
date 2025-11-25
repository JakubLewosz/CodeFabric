import re
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file, read_file, get_all_file_paths
from tools.llm_factory import get_llm

def smart_truncate(content: str, max_length: int = 6000) -> str:
    """
    Inteligentne obcinanie kodu - zachowuje początek (importy) i koniec (main logic).
    """
    if len(content) <= max_length:
        return content
    
    head_size = max_length // 2
    tail_size = max_length // 2
    omitted = len(content) - max_length
    
    return (
        content[:head_size] + 
        f"\n\n# ... [POMINIĘTO {omitted} ZNAKÓW] ...\n\n" + 
        content[-tail_size:]
    )

def parse_diff_edits(ai_response: str) -> list:
    """
    Parsuje edycje w formacie SEARCH/REPLACE (tryb diff).
    Zwraca listę tupli: (filepath, search_block, replace_block)
    """
    pattern = r"###\s*EDIT:\s*([^\n]+)\nSEARCH:\n(.*?)\nREPLACE:\n(.*?)\n###\s*END_EDIT"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    return [(f.strip(), s.strip(), r.strip()) for f, s, r in matches]

def apply_diff_edits(edits: list) -> list:
    """
    Aplikuje edycje SEARCH/REPLACE do istniejących plików.
    """
    modified_files = []
    for filepath, search_block, replace_block in edits:
        current_content = read_file(filepath)
        
        if not current_content:
            print(f"⚠️ Plik {filepath} nie istnieje, pomijam EDIT.")
            continue
        
        # Normalizacja whitespace (usuń różnice w spacjach/tabulatorach)
        search_normalized = " ".join(search_block.split())
        content_normalized = " ".join(current_content.split())
        
        # Dokładne dopasowanie
        if search_block in current_content:
            new_content = current_content.replace(search_block, replace_block, 1)
            write_file(filepath, new_content)
            print(f"✏️ Zaktualizowano (DIFF): {filepath}")
            modified_files.append(filepath)
        
        # Fuzzy matching (jeśli różnice w whitespace)
        elif search_normalized in content_normalized:
            print(f"⚠️ Znaleziono podobny blok w {filepath} (różnice w spacjach)")
            # Znajdź oryginalny fragment
            lines = current_content.split('\n')
            search_lines = search_block.split('\n')
            
            # Prosta heurystyka - znajdź pierwszą linię
            first_line = search_lines[0].strip()
            for i, line in enumerate(lines):
                if first_line in line:
                    # Zastąp od tej linii
                    lines_count = len(search_lines)
                    new_lines = lines[:i] + replace_block.split('\n') + lines[i+lines_count:]
                    new_content = '\n'.join(new_lines)
                    write_file(filepath, new_content)
                    print(f"✏️ Zaktualizowano (FUZZY): {filepath}")
                    modified_files.append(filepath)
                    break
        
        # Nie znaleziono
        else:
            print(f"❌ NIE ZNALEZIONO bloku SEARCH w {filepath}")
            print(f"   Szukano: {search_block[:100]}...")
            
            # Diagnostyka
            debug_content = f"""
BŁĄD DIFF-EDITING
=================

PLIK: {filepath}

SZUKANO (pierwsze 500 znaków):
{search_block[:500]}

ZAWARTOŚĆ PLIKU (pierwsze 1000 znaków):
{current_content[:1000]}

SUGESTIA:
LLM prawdopodobnie nie skopiował DOKŁADNIE kodu z pliku.
Coder powinien użyć trybu FULL REWRITE dla tego pliku.
"""
            write_file(f"debug_diff_fail_{filepath.replace('/', '_')}.txt", debug_content)
            print(f"   Zapisano diagnostykę: debug_diff_fail_{filepath.replace('/', '_')}.txt")
    
    return modified_files

def parse_and_save_files(ai_response: str):
    """Parsuje odpowiedź AI i zapisuje pliki (tryb full rewrite)."""
    if not ai_response: 
        return []

    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []
    
    if not matches and len(ai_response.strip()) > 50:
        if any(keyword in ai_response for keyword in ["def ", "class ", "import ", "function ", "const "]):
            print("⚠️ AI nie użyło znaczników FILE:, zapisuję jako raw_code.txt")
            write_file("raw_code.txt", ai_response)
            return ["raw_code.txt"]
        return []

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        if len(content) < 10:
            print(f"⚠️ Plik {filename} jest podejrzanie krótki ({len(content)} znaków), pomijam.")
            continue
        
        write_file(filename, content)
        print(f"→ Zaktualizowano plik: {filename}")
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state.get("plan", "Brak planu.")
    feedback = state.get("feedback", "")
    current_revisions = state.get("revision_count", 0)
    chat_workspace = state.get("chat_workspace")  # NOWOŚĆ
    
    # Ustaw workspace jeśli podany
    if chat_workspace:
        import tools.file_ops as file_ops_module
        file_ops_module.WORKSPACE_DIR = chat_workspace
    
    model_name = state.get("model_names", {}).get("coder", "qwen3-coder:30b")
    llm = get_llm(model_name, temperature=0.0, num_ctx=32768) 

    # === 1. WCZYTANIE KONTEKSTU (PAMIĘĆ) ===
    existing_files = get_all_file_paths()
    code_context = ""
    
    if existing_files:
        print(f"--- PROGRAMISTA: ANALIZA {len(existing_files)} PLIKÓW ---")
        total_chars = 0
        
        for f in existing_files:
            if f.endswith(('.py', '.js', '.html', '.css', '.cs', '.json', '.md', '.txt', '.jsx', '.tsx')):
                content = read_file(f)
                truncated = smart_truncate(content, max_length=8000)
                code_context += f"\n=== PLIK ISTNIEJĄCY: {f} ===\n{truncated}\n============================\n"
                total_chars += len(truncated)
        
        print(f"→ Załadowano {total_chars} znaków kontekstu.")
    else:
        code_context = "BRAK PLIKÓW (Nowy projekt)."

    # === 2. OKREŚLENIE TRYBU PRACY ===
    use_diff_mode = False
    total_lines = 0
    
    # Policz linie tylko dla plików kodowych
    if existing_files:
        for f in existing_files:
            if f.endswith(('.py', '.js', '.html', '.css', '.jsx', '.tsx')):
                content = read_file(f)
                total_lines += content.count('\n')
    
    if feedback and "REJECT" in str(feedback).upper():
        mode = "TRYB NAPRAWY (DEBUGGING)"
        task_desc = f"Tester zgłosił błędy:\n{feedback}\n\nTwoim zadaniem jest je naprawić."
        current_revisions += 1
        # DIFF tylko dla DUŻYCH projektów (>10 plików LUB >300 linii)
        use_diff_mode = len(existing_files) > 10 or total_lines > 300
        
    elif existing_files:
        mode = "TRYB ROZWOJU (REFACTORING)"
        task_desc = "Zaimplementuj zmiany opisane w planie, modyfikując istniejący kod."
        # DIFF dla średnich/dużych projektów
        use_diff_mode = len(existing_files) > 10 or total_lines > 300
        
    else:
        mode = "TRYB TWORZENIA (GREENFIELD)"
        task_desc = "Napisz kod od zera na podstawie planu."

    print(f"--- PROGRAMISTA ({model_name}): {mode} ---")
    if use_diff_mode:
        print(f"→ Używam DIFF editing ({len(existing_files)} plików, {total_lines} linii)")
    else:
        print(f"→ Używam FULL REWRITE ({len(existing_files)} plików, {total_lines} linii - za mały projekt dla DIFF)")

    # === 3. PRZYGOTOWANIE PROMPTU ===
    
    if use_diff_mode:
        sys_msg = SystemMessage(content=f"""
Jesteś Expert Software Engineerem specjalizującym się w chirurgicznych edycjach kodu.

--- TRYB PRACY: DIFF EDITING ---
Zamiast przepisywać całe pliki, użyj formatu SEARCH/REPLACE:

### EDIT: ścieżka/plik.ext
SEARCH:
[DOKŁADNY fragment kodu do znalezienia - MUSISZ SKOPIOWAĆ GO 1:1 Z ISTNIEJĄCEGO PLIKU]
REPLACE:
[Nowa wersja tego fragmentu]
### END_EDIT

ZASADY KRYTYCZNE (PRZECZYTAJ 3 RAZY):
1. Blok SEARCH musi być IDENTYCZNY z fragmentem w pliku (co do znaku).
2. Otwórz plik mentalnie, SKOPIUJ dokładny fragment (ze spacjami, wcięciami).
3. Jeśli edytujesz funkcję - SKOPIUJ JĄ CAŁĄ w SEARCH (od "def" do końca).
4. NIE WYMYŚLAJ kodu w SEARCH - KOPIUJ CO WIDZISZ.
5. NIE SKRACAJ - jeśli funkcja ma 10 linii, SEARCH musi mieć 10 linii.

PRZYKŁAD DOBRY:
### EDIT: game.py
SEARCH:
def spawn_food(self):
    self.food_pos = [random.randint(0, 19), random.randint(0, 19)]
REPLACE:
def spawn_food(self):
    self.food_pos = [random.randint(0, 19), random.randint(0, 19)]
    self.food2_pos = [random.randint(0, 19), random.randint(0, 19)]
### END_EDIT

PRZYKŁAD ZŁY (❌ NIE RÓB TEGO):
### EDIT: game.py
SEARCH:
def spawn_food(self):
    # spawn food
REPLACE:
def spawn_food(self):
    # spawn two foods
### END_EDIT
☝️ To jest ZŁE bo SEARCH nie jest dokładnym kodem z pliku!

JEŚLI NIE JESTEŚ PEWIEN DOKŁADNEGO KODU:
Użyj trybu FULL REWRITE (### FILE: ... ### ENDFILE) zamiast EDIT.

Teraz przeanalizuj kod i zaplanuj edycje.
""")
    else:
        sys_msg = SystemMessage(content=f"""
Jesteś Expert Software Engineerem. Twoim celem jest dostarczenie DZIAŁAJĄCEGO, KOMPLETNEGO kodu.

--- ZASADY EDYCJI PLIKÓW (KRYTYCZNE) ---
1. Jeśli edytujesz plik, musisz zwrócić jego PEŁNĄ, NOWĄ ZAWARTOŚĆ.
2. ABSOLUTNY ZAKAZ używania skrótów: `// ... reszta kodu`, `# ... existing code`. TO PSUJE PLIK.
3. Musisz zachować istniejące funkcjonalności, chyba że plan każe je usunąć.
4. Upewnij się, że nowe funkcje są faktycznie WYWOŁYWANE w głównym kodzie.

--- FORMAT ODPOWIEDZI ---
Krok 1: ANALIZA (Jako komentarz). Napisz krótko: co zmienisz, w którym miejscu.
Krok 2: KOD. Użyj znaczników:

### FILE: sciezka/plik.ext
PEŁNY_KOD_PLIKU
### ENDFILE

UWAGA: Jeśli plik ma 200 linii, musisz zwrócić WSZYSTKIE 200 linii (ze zmianami).
""")

    user_msg = HumanMessage(content=f"""
TRYB PRACY: {mode}

PLAN ARCHITEKTA (CO ZROBIĆ):
{plan}

ZADANIE SZCZEGÓŁOWE:
{task_desc}

AKTUALNY KOD PROJEKTU (KONTEKST):
{code_context}

{'Użyj formatu EDIT/SEARCH/REPLACE dla precyzyjnych zmian.' if use_diff_mode else 'Rozpocznij od analizy zmian, a potem wygeneruj PEŁNE pliki.'}
""")
    
    # === 4. WYWOŁANIE LLM ===
    full_response = ""
    try:
        print("--- WYSYŁANIE DO AI (To może chwilę potrwać)... ---")
        response_obj = llm.invoke([sys_msg, user_msg])
        full_response = response_obj.content
        print(f"→ Otrzymano {len(full_response)} znaków.")
        
    except Exception as e:
        err = f"BŁĄD LLM: {e}"
        print(err)
        write_file("error_log.txt", err)
        return {
            "current_files": existing_files,
            "messages": [AIMessage(content=f"Błąd: {e}")],
            "revision_count": current_revisions,
            "feedback": None
        }

    # === 5. PARSOWANIE I ZAPIS ===
    saved_files = []
    
    if use_diff_mode:
        edits = parse_diff_edits(full_response)
        if edits:
            print(f"→ Znaleziono {len(edits)} edycji DIFF.")
            saved_files = apply_diff_edits(edits)
            
            # NOWOŚĆ: Jeśli diff nie zadziałał dla żadnego pliku -> fallback na FILE
            if not saved_files:
                print("⚠️ Wszystkie edycje DIFF FAILED. Próbuję FULL REWRITE...")
                saved_files = parse_and_save_files(full_response)
        else:
            print("⚠️ Brak edycji DIFF, próbuję trybu FILE...")
            saved_files = parse_and_save_files(full_response)
    else:
        saved_files = parse_and_save_files(full_response)
    
    if not saved_files and existing_files:
        print("⚠️ AI nie zwróciło zmian, zachowuję poprzednie pliki.")
        saved_files = existing_files
    elif not saved_files:
        write_file("error_report.txt", f"Brak kodu. Odpowiedź AI:\n{full_response[:1000]}")
        saved_files.append("error_report.txt")

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Zaktualizowano pliki: {saved_files}")],
        "revision_count": current_revisions,
        "feedback": None
    }