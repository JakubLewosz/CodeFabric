import re
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file, read_file, get_all_file_paths
from tools.llm_factory import get_llm

def parse_and_save_files(ai_response: str):
    """Parsuje odpowiedź AI i zapisuje pliki."""
    if not ai_response: return []

    # Regex szuka bloków: ### FILE: nazwa ... ### ENDFILE
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []
    
    # Fallback
    if not matches and len(ai_response.strip()) > 50:
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        # Usuwanie śmieci (markdown, komentarze z planem myślowym jeśli wpadły)
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        write_file(filename, content)
        print(f"-> Zaktualizowano plik: {filename}")
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state.get("plan", "Brak planu.")
    feedback = state.get("feedback", "")
    current_revisions = state.get("revision_count", 0)
    
    # Konfiguracja modelu (Qwen jest tu kluczowy!)
    model_name = state.get("model_names", {}).get("coder", "qwen3-coder:30b")
    # Bardzo duży kontekst, żeby zmieścił cały stary kod + nowy kod
    llm = get_llm(model_name, temperature=0.0, num_ctx=24000) 

    # 1. WCZYTANIE KONTEKSTU (PAMIĘĆ)
    existing_files = get_all_file_paths()
    code_context = ""
    if existing_files:
        print(f"--- PROGRAMISTA: ANALIZA {len(existing_files)} PLIKÓW ---")
        for f in existing_files:
            # Ignorujemy pliki binarne/systemowe, czytamy tylko kod
            if f.endswith(('.py', '.js', '.html', '.css', '.cs', '.json', '.md', '.txt')):
                content = read_file(f)
                code_context += f"\n=== PLIK ISTNIEJĄCY: {f} ===\n{content}\n============================\n"
    else:
        code_context = "BRAK PLIKÓW (Nowy projekt)."

    # 2. PRZYGOTOWANIE INSTRUKCJI (System vs User)
    
    if feedback and "REJECT" in str(feedback).upper():
        mode = "TRYB NAPRAWY (DEBUGGING)"
        task_desc = f"Tester zgłosił błędy:\n{feedback}\nTwoim zadaniem jest je naprawić."
        current_revisions += 1
    elif existing_files:
        mode = "TRYB ROZWOJU (REFACTORING)"
        task_desc = "Zaimplementuj zmiany opisane w planie, modyfikując istniejący kod."
    else:
        mode = "TRYB TWORZENIA (GREENFIELD)"
        task_desc = "Napisz kod od zera na podstawie planu."

    print(f"--- PROGRAMISTA ({model_name}): {mode} ---")

    # SYSTEM PROMPT: Definiuje osobowość i zasady techniczne
    sys_msg = SystemMessage(content=f"""
    Jesteś Expert Software Engineerem specjalizującym się w refaktoryzacji.
    Twoim celem jest dostarczenie DZIAŁAJĄCEGO, KOMPLETNEGO kodu.
    
    --- ZASADY EDYCJI PLIKÓW (KRYTYCZNE) ---
    1. Jeśli edytujesz plik, musisz zwrócić jego PEŁNĄ, NOWĄ ZAWARTOŚĆ.
    2. ABSOLUTNY ZAKAZ używania skrótów: `// ... reszta kodu`, `# ... existing code`. TO PSUJE PLIK.
    3. Musisz zachować istniejące funkcjonalności, chyba że plan każe je usunąć.
    4. Upewnij się, że nowe funkcje (np. nowa klasa) są faktycznie WYWOŁYWANE w głównym kodzie (np. w game loop).
    
    --- FORMAT ODPOWIEDZI ---
    Krok 1: ANALIZA (Jako komentarz). Napisz krótko: co zmienisz, w którym miejscu.
    Krok 2: KOD. Użyj znaczników:
    
    ### FILE: sciezka/plik.ext
    PEŁNY_KOD_PLIKU
    ### ENDFILE
    """)

    # USER PROMPT: Zawiera konkretne dane
    user_msg = HumanMessage(content=f"""
    TRYB PRACY: {mode}
    
    PLAN ARCHITEKTA (CO ZROBIĆ):
    {plan}
    
    ZADANIE SZCZEGÓŁOWE:
    {task_desc}
    
    AKTUALNY KOD PROJEKTU (KONTEKST):
    {code_context}
    
    Rozpocznij od analizy zmian, a potem wygeneruj PEŁNE pliki.
    """)
    
    full_response = ""
    try:
        # Używamy invoke (bezpieczniej przy dużym kontekście)
        print("--- WYSYŁANIE DO AI (To może chwilę potrwać)... ---")
        response_obj = llm.invoke([sys_msg, user_msg])
        full_response = response_obj.content
        print(f"-> Otrzymano {len(full_response)} znaków.")
        
    except Exception as e:
        err = f"BŁĄD LLM: {e}"
        print(err)
        write_file("error_log.txt", err)

    saved_files = parse_and_save_files(full_response)
    
    # Jeśli Coder nic nie zwrócił, a mieliśmy pliki, to znaczy że "nie widział potrzeby zmian"
    # Ale my chcemy, żeby proces szedł dalej, więc zwracamy stare pliki.
    if not saved_files and existing_files:
        saved_files = existing_files
    elif not saved_files:
        write_file("error_report.txt", f"Brak kodu. Odpowiedź AI:\n{full_response[:500]}")
        saved_files.append("error_report.txt")

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Zaktualizowano pliki: {saved_files}")],
        "revision_count": current_revisions,
        "feedback": None
    }