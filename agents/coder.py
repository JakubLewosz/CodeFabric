import os
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_CODER", "llama3")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

print(f"--- INICJALIZACJA PROGRAMISTY ---")
print(f"Model: {MODEL_NAME} | URL: {OLLAMA_URL}")

llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0.1,
    num_ctx=8192,
    timeout=300.0,
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {"Authorization": f"Bearer {OLLAMA_TOKEN}"} if OLLAMA_TOKEN else {}
    }
)

def parse_and_save_files(ai_response: str):
    """Parsuje odpowiedź AI i zapisuje pliki."""
    if not ai_response:
        return []

    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []

    if not matches and len(ai_response.strip()) > 0:
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        # write_file automatycznie utworzy strukturę folderów (w tym folder główny)
        write_file(filename, content)
        print(f"-> Zapisano: {filename}")
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state.get("plan", "Brak planu.")
    feedback = state.get("feedback", "")
    current_revisions = state.get("revision_count", 0)
    
    if feedback and "REJECT" in str(feedback).upper():
        print(f"--- PROGRAMISTA: POPRAWKI (Iteracja {current_revisions + 1}) ---")
        instruction_prefix = f"TO JEST POPRAWKA. Tester zgłosił błędy:\n{feedback}\nNapraw je."
        new_revision_count = current_revisions + 1
    else:
        print(f"--- PROGRAMISTA: START ---")
        instruction_prefix = "Napisz kod na podstawie planu."
        new_revision_count = current_revisions

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
    
    FORMAT DLA KAŻDEGO PLIKU:
    ### FILE: nazwa_projektu/sciezka/plik.ext
    TRESC_KODU
    ### ENDFILE
    
    Nie pisz wstępów. Tylko kod.
    """)
    
    print(f"--- WYSYŁANIE ZAPYTANIA... ---")
    
    full_response = ""
    try:
        response_obj = llm.invoke([msg])
        full_response = response_obj.content
        if not full_response:
            print("!!! OSTRZEŻENIE: Pusta odpowiedź.")
    except Exception as e:
        err = f"BŁĄD LLM: {e}"
        print(f"\n{err}")
        write_file("error_log.txt", err)

    saved_files = parse_and_save_files(full_response)
    
    if not saved_files:
        write_file("error_report.txt", f"Brak plików. Treść:\n{full_response[:500]}")
        saved_files.append("error_report.txt")

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Pliki: {saved_files}")],
        "revision_count": new_revision_count,
        "feedback": None
    }