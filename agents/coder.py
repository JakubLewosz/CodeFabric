import re
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file, read_file, get_all_file_paths
from tools.llm_factory import get_llm

def parse_and_save_files(ai_response: str):
    if not ai_response: return []
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []
    
    if not matches and len(ai_response.strip()) > 10:
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
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
    
    model_name = state.get("model_names", {}).get("coder", "qwen3-coder:30b")
    # Zwiększamy num_predict, żeby nie ucinało kodu w połowie
    llm = get_llm(model_name, temperature=0.1, num_ctx=16384) 

    # Kontekst plików
    existing_files = get_all_file_paths()
    code_context = ""
    if existing_files:
        print(f"--- PROGRAMISTA: ANALIZA {len(existing_files)} PLIKÓW ---")
        for f in existing_files:
            content = read_file(f)
            code_context += f"\n--- PLIK: {f} ---\n{content[:6000]}\n"

    # Logika promptu
    if feedback and "REJECT" in str(feedback).upper():
        print(f"--- PROGRAMISTA ({model_name}): NAPRAWA BŁĘDÓW (v{current_revisions + 1}) ---")
        new_revision_count = current_revisions + 1
        instruction = f"""
        TO JEST TRYB NAPRAWY (DEBUGGING).
        Twój poprzedni kod nie działał lub został odrzucony.
        
        LISTA BŁĘDÓW:
        {feedback}
        
        ZADANIE: Przepisz kod plików, naprawiając błędy.
        Upewnij się, że kod jest KOMPLETNY i DZIAŁAJĄCY.
        """
    else:
        print(f"--- PROGRAMISTA ({model_name}): IMPLEMENTACJA ---")
        new_revision_count = current_revisions
        instruction = "Napisz profesjonalny, działający kod na podstawie planu."

    msg = HumanMessage(content=f"""
    {instruction}
    
    PLAN PROJEKTU:
    {plan}
    
    ISTNIEJĄCY KOD (KONTEKST):
    {code_context}
    
    --- ZASADY GENEROWANIA ---
    1. Nie używaj skrótów typu `// ... reszta kodu`. PISZ CAŁY KOD.
    2. Pamiętaj o importach i strukturze (np. namespace w C#).
    3. Użyj pełnych ścieżek w nagłówkach (z folderem głównym).
    
    FORMAT:
    ### FILE: folder/plik.ext
    PEŁNY_KOD_ŹRÓDŁOWY
    ### ENDFILE
    """)
    
    print(f"--- WYSYŁANIE DO AI... ---")
    
    full_response = ""
    try:
        response_obj = llm.invoke([msg])
        full_response = response_obj.content
    except Exception as e:
        err = f"BŁĄD LLM: {e}"
        print(err)
        write_file("error_log.txt", err)

    saved_files = parse_and_save_files(full_response)
    
    if not saved_files:
        write_file("error_report.txt", f"Brak plików. Odpowiedź:\n{full_response[:500]}")
        saved_files.append("error_report.txt")
    
    if not saved_files and existing_files:
        saved_files = existing_files

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Pliki: {saved_files}")],
        "revision_count": new_revision_count,
        "feedback": None
    }