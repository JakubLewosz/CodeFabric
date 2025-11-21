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
        content = re.sub(r"^```[a-zA-Z]*\n", "", content.strip())
        content = re.sub(r"\n```$", "", content)
        write_file(fname, content)
        print(f"-> Zapisano: {fname}")
        created.append(fname)
    return created

def coder_node(state: AgentState):
    plan = state.get("plan", "")
    feedback = state.get("feedback", "")
    revs = state.get("revision_count", 0)
    
    model_name = state.get("model_names", {}).get("coder", "qwen3-coder:30b")
    # Używamy Qwen, bo on najlepiej rozumie logikę
    llm = get_llm(model_name, temperature=0.1, num_ctx=16384)

    existing_files = get_all_file_paths()
    code_context = ""
    if existing_files:
        for f in existing_files:
            content = read_file(f)
            code_context += f"\n--- PLIK: {f} ---\n{content[:6000]}\n"

    instruction = "Napisz ROBUSTNY (odporny na błędy) i KOMPLETNY kod."
    if feedback and "REJECT" in str(feedback).upper():
        instruction = f"POPRAW BŁĘDY LOGICZNE:\n{feedback}\nUpewnij się, że program się uruchomi."
        revs += 1

    # NOWY PROMPT Z NACISKIEM NA DZIAŁANIE
    msg = HumanMessage(content=f"""
    {instruction}
    
    PLAN: {plan}
    KONTEKST: {code_context}
    
    --- STANDARDY JAKOŚCI (MUST HAVE) ---
    1. KOMPLETNOŚĆ: Nie zostawiaj "TODO" ani pustych funkcji. Kod ma działać od razu.
    2. IMPORTY: Upewnij się, że wszystkie biblioteki są zaimportowane.
    3. PUNKT STARTOWY: Python musi mieć `if __name__ == "__main__":`. C# musi mieć `Main`.
    4. GUI (jeśli dotyczy): Pamiętaj o pętli `mainloop()` (Tkinter) lub `while True` (Pygame) i obsłudze `QUIT`.
    
    FORMAT:
    ### FILE: folder/plik.ext
    KOD
    ### ENDFILE
    """)
    
    print(f"--- PROGRAMISTA ({model_name}): PISZE KOD ---")
    
    full_res = ""
    try:
        res = llm.invoke([msg])
        full_res = res.content
    except Exception as e:
        print(e)
        write_file("error_log.txt", str(e))

    saved = parse_and_save_files(full_res)
    if not saved: saved.append("error_report.txt")
    if not saved and existing_files: saved = existing_files

    return {
        "current_files": saved,
        "messages": [AIMessage(content=f"Gotowe: {saved}")],
        "revision_count": revs,
        "feedback": None
    }