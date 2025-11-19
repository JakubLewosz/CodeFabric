import re
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file, read_file, get_all_file_paths
from tools.llm_factory import get_llm

def parse_and_save_files(ai_response: str):
    """Parsuje odpowiedź AI i zapisuje pliki zachowując strukturę katalogów."""
    if not ai_response: return []

    # Regex szuka: ### FILE: nazwa ... ### ENDFILE
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []
    
    # Fallback: Jeśli brak znaczników, ale jest treść -> zapisz jako raw
    if not matches and len(ai_response.strip()) > 10:
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        # Usuwanie markdowna (```python)
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        write_file(filename, content)
        print(f"-> Zapisano: {filename}")
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state.get("plan", "Brak planu.")
    feedback = state.get("feedback", "")
    current_revisions = state.get("revision_count", 0)
    
    # 1. Pobieranie modelu z factory
    model_name = state.get("model_names", {}).get("coder", "qwen3-coder:30b")
    llm = get_llm(model_name, temperature=0.1, num_ctx=16384) # Duży kontekst na czytanie plików

    # 2. KONTEKST (PAMIĘĆ) - Wczytujemy istniejące pliki
    existing_files = get_all_file_paths()
    code_context = ""
    if existing_files:
        print(f"--- PROGRAMISTA: WCZYTUJĘ ISTNIEJĄCY KOD ({len(existing_files)} plików) ---")
        for f in existing_files:
            content = read_file(f)
            code_context += f"\n--- PLIK: {f} ---\n{content[:4000]}\n"
    else:
        code_context = "Brak istniejących plików (Nowy projekt)."

    # 3. LOGIKA LICZNIKA POPRAWEK (KLUCZOWA ZMIANA)
    if feedback and "REJECT" in str(feedback).upper():
        new_revision_count = current_revisions + 1 # <--- ZWIĘKSZAMY LICZNIK
        print(f"--- PROGRAMISTA ({model_name}): POPRAWKI (Próba {new_revision_count}) ---")
        
        instruction_prefix = f"""
        UWAGA: To jest POPRAWKA kodu (Próba {new_revision_count}).
        Twój poprzedni kod został odrzucony przez testera.
        
        LISTA BŁĘDÓW DO NAPRAWIENIA:
        {feedback}
        
        Zadanie: Przepisz kod plików, naprawiając powyższe błędy.
        """
    else:
        new_revision_count = current_revisions # Bez zmian
        print(f"--- PROGRAMISTA ({model_name}): START ---")
        instruction_prefix = "Zadanie: Napisz kod na podstawie planu."

    # 4. PROMPT
    msg = HumanMessage(content=f"""
    {instruction_prefix}
    
    PLAN PROJEKTU:
    {plan}
    
    KONTEKST (OBECNY KOD NA DYSKU):
    {code_context}
    
    --- ZASADY KRYTYCZNE ---
    1. W nagłówku ### FILE: musisz podać PEŁNĄ ŚCIEŻKĘ z planu (łącznie z nazwą folderu głównego).
    2. Jeśli plik wymaga edycji, przepisz go w całości.
    
    FORMAT WYMAGANY (Użyj go dokładnie):
    ### FILE: folder/plik.ext
    TRESC_KODU
    ### ENDFILE
    
    Nie pisz wstępów. Tylko bloki kodu.
    """)
    
    print(f"--- WYSYŁANIE ZAPYTANIA... ---")
    
    full_response = ""
    try:
        response_obj = llm.invoke([msg])
        full_response = response_obj.content
    except Exception as e:
        err = f"BŁĄD KRYTYCZNY LLM: {e}"
        print(f"\n{err}")
        write_file("error_log.txt", err)

    saved_files = parse_and_save_files(full_response)
    
    # Raport błędu jeśli pusto (żeby manager widział plik)
    if not saved_files:
        write_file("error_report.txt", f"Brak plików. Treść:\n{full_response[:500]}")
        saved_files.append("error_report.txt")
    
    # Jeśli Coder nic nie zmienił, zwracamy stare pliki, żeby proces szedł dalej
    if not saved_files and existing_files:
        saved_files = existing_files

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Pliki gotowe: {saved_files}")],
        "revision_count": new_revision_count, # <--- ZWRACAMY ZAKTUALIZOWANY LICZNIK
        "feedback": None # Czyścimy feedback
    }