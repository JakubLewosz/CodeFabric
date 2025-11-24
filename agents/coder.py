import re
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file, read_file, get_all_file_paths
from tools.llm_factory import get_llm

def parse_and_save_files(ai_response: str):
    if not ai_response: return []
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created = []
    
    if not matches and len(ai_response.strip()) > 10:
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for fname, content in matches:
        fname = fname.strip()
        content = content.strip()
        # Usuwanie markdowna i komentarzy "myślowych" z początku
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        write_file(fname, content)
        print(f"-> Zaktualizowano: {fname}")
        created.append(fname)
    return created

def coder_node(state: AgentState):
    plan = state.get("plan", "")
    feedback = state.get("feedback", "")
    revs = state.get("revision_count", 0)
    
    model_name = state.get("model_names", {}).get("coder", "qwen3-coder:30b")
    # TEMP 0.0 DLA PRECYZJI EDYCJI!
    llm = get_llm(model_name, temperature=0.0, num_ctx=16384)

    # Wczytujemy kontekst plików
    existing_files = get_all_file_paths()
    code_context = ""
    if existing_files:
        print(f"--- PROGRAMISTA: ANALIZA {len(existing_files)} PLIKÓW ---")
        for f in existing_files:
            content = read_file(f)
            code_context += f"\n=== PLIK: {f} ===\n{content}\n==================\n"

    # Budowanie Promptu
    instruction = "Wykonaj zmiany w kodzie zgodnie z planem."
    if feedback and "REJECT" in str(feedback).upper():
        instruction = f"POPRAW BŁĘDY:\n{feedback}"
        revs += 1

    msg = HumanMessage(content=f"""
    {instruction}
    
    PLAN DZIAŁANIA:
    {plan}
    
    --- AKTUALNY KOD PROJEKTU (DO EDYCJI) ---
    {code_context}
    
    --- INSTRUKCJA MASTER ---
    1. Jesteś "Inteligentnym Edytorem". Twoim celem jest WPROWADZENIE ZMIAN bez psucia reszty.
    2. Jeśli edytujesz plik, musisz wypisać go W CAŁOŚCI (od pierwszej do ostatniej linijki).
    3. ZABRONIONE: Używanie skrótów typu `// ... reszta kodu bez zmian`. To zniszczy plik!
    4. Zachowaj istniejące funkcje, chyba że plan każe je usunąć.
    
    --- FORMAT ODPOWIEDZI ---
    Najpierw napisz krótko plan działania (myślenie), a potem kod.
    
    PRZYKŁAD:
    ### MYŚLENIE
    Muszę dodać klasę BlueFruit do main.py i wywołać ją w pętli gry.
    
    ### FILE: folder/main.py
    import pygame
    ... CAŁY KOD Z NOWYMI ZMIANAMI ...
    ### ENDFILE
    """)
    
    print(f"--- PROGRAMISTA ({model_name}): EDYCJA KODU ---")
    
    full_res = ""
    try:
        res = llm.invoke([msg])
        full_res = res.content
    except Exception as e:
        print(f"BŁĄD LLM: {e}")
        write_file("error_log.txt", str(e))

    saved = parse_and_save_files(full_res)
    
    # Jeśli coder nic nie zmienił, zwracamy stare pliki
    if not saved and existing_files: saved = existing_files
    if not saved: saved.append("error_report.txt")

    return {
        "current_files": saved,
        "messages": [AIMessage(content=f"Zmiany wprowadzone: {saved}")],
        "revision_count": revs,
        "feedback": None
    }