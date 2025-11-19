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
    
    if not matches and len(ai_response) > 10:
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for fname, content in matches:
        fname = fname.strip()
        content = re.sub(r"^```[a-zA-Z]*\n", "", content.strip())
        content = re.sub(r"\n```$", "", content)
        write_file(fname, content)
        print(f"-> Zapisano/Zaktualizowano: {fname}")
        created.append(fname)
    return created

def coder_node(state: AgentState):
    plan = state.get("plan", "")
    feedback = state.get("feedback", "")
    revisions = state.get("revision_count", 0)
    
    # --- NOWOŚĆ: KONTEKST KODU (MEMORY) ---
    # Pobieramy listę plików, które już są na dysku
    existing_files = get_all_file_paths()
    code_context = ""
    
    if existing_files:
        print(f"--- PROGRAMISTA: WCZYTUJĘ ISTNIEJĄCY KOD ({len(existing_files)} plików) ---")
        for f in existing_files:
            # Czytamy treść, żeby dać AI kontekst
            content = read_file(f)
            # Ograniczamy wielkość pliku do kontekstu (np. 4000 znaków), żeby nie zapchać modelu
            code_context += f"\n--- TREŚĆ PLIKU: {f} ---\n{content[:4000]}\n"
    else:
        code_context = "Brak istniejących plików (Nowy projekt)."

    model_name = state.get("model_names", {}).get("coder", "qwen3-coder:30b")
    llm = get_llm(model_name, temperature=0.1, num_ctx=16384) # Większy kontekst na czytanie plików!

    instruction = "Napisz lub zaktualizuj kod na podstawie planu."
    if feedback and "REJECT" in str(feedback).upper():
        instruction = f"TO JEST POPRAWKA. Błędy do naprawy:\n{feedback}"
        revisions += 1

    msg = HumanMessage(content=f"""
    {instruction}
    
    PLAN DZIAŁANIA:
    {plan}
    
    KONTEKST (OBECNY KOD NA DYSKU):
    {code_context}
    
    ZASADY:
    1. Jeśli edytujesz plik, musisz przepisać go W CAŁOŚCI ze zmianami.
    2. Zachowaj strukturę folderów z nagłówków ### FILE.
    3. Jeśli plik nie wymaga zmian, NIE generuj go ponownie.
    
    FORMAT:
    ### FILE: sciezka/plik.ext
    NOWA_TRESC
    ### ENDFILE
    """)

    print(f"--- PROGRAMISTA ({model_name}): PISZE KOD ---")
    
    full_res = ""
    try:
        res = llm.invoke([msg])
        full_res = res.content
    except Exception as e:
        print(f"BŁĄD LLM: {e}")
        write_file("error_log.txt", str(e))

    saved = parse_and_save_files(full_res)
    
    # Jeśli Coder nic nie wygenerował (bo np. uznał że nie trzeba zmian),
    # to i tak musimy zwrócić listę aktualnych plików, żeby Reviewer miał co robić.
    if not saved:
        print("--- BRAK ZMIAN W KODZIE ---")
        # Zwracamy stare pliki jako "current", żeby proces szedł dalej
        saved = existing_files 

    return {
        "current_files": saved,
        "messages": [AIMessage(content=f"Zaktualizowano: {saved}")],
        "revision_count": revisions,
        "feedback": None
    }