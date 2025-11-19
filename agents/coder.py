import re
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file
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
        print("DEBUG: Brak znaczników ### FILE. Zapisuję raw_code.txt")
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        # Usuwanie markdowna (```python)
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        # write_file automatycznie utworzy foldery
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
    # Ustawiamy duży kontekst (8k) i niski temp dla kodu
    llm = get_llm(model_name, temperature=0.1, num_ctx=8192)

    # 2. Logika Poprawek (Feedback Loop)
    if feedback and "REJECT" in str(feedback).upper():
        print(f"--- PROGRAMISTA ({model_name}): POPRAWKI (v{current_revisions + 1}) ---")
        instruction_prefix = f"""
        UWAGA: To jest POPRAWKA kodu.
        Twój poprzedni kod został odrzucony przez testera.
        
        LISTA BŁĘDÓW DO NAPRAWIENIA:
        {feedback}
        
        Zadanie: Przepisz kod plików, naprawiając powyższe błędy.
        """
        new_revision_count = current_revisions + 1
    else:
        print(f"--- PROGRAMISTA ({model_name}): START ---")
        instruction_prefix = "Zadanie: Napisz kod plików na podstawie planu od zera."
        new_revision_count = current_revisions

    # 3. AGRESYWNY PROMPT FORMATUJĄCY
    msg = HumanMessage(content=f"""
    {instruction_prefix}
    
    PLAN PROJEKTU:
    {plan}
    
    --- ZASADY KRYTYCZNE ---
    1. W nagłówku ### FILE: musisz podać PEŁNĄ ŚCIEŻKĘ z planu (łącznie z nazwą folderu głównego).
    
    PRZYKŁAD DOBRY:
    ### FILE: moja_gra/main.py
    
    PRZYKŁAD ZŁY:
    ### FILE: main.py
    
    FORMAT WYMAGANY (Użyj go dokładnie):
    ### FILE: nazwa_projektu/sciezka/plik.ext
    TRESC_KODU
    ### ENDFILE
    
    Nie pisz wstępów. Tylko bloki kodu.
    """)
    
    print(f"--- WYSYŁANIE ZAPYTANIA... ---")
    
    full_response = ""
    try:
        # Używamy invoke dla stabilności
        response_obj = llm.invoke([msg])
        full_response = response_obj.content
    except Exception as e:
        err = f"BŁĄD KRYTYCZNY LLM: {e}"
        print(f"\n{err}")
        write_file("error_log.txt", err)

    saved_files = parse_and_save_files(full_response)
    
    # Raport błędu jeśli pusto
    if not saved_files:
        write_file("error_report.txt", f"Brak plików. Treść:\n{full_response[:500]}")
        saved_files.append("error_report.txt")

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Pliki: {saved_files}")],
        "revision_count": new_revision_count,
        "feedback": None # Czyścimy feedback
    }