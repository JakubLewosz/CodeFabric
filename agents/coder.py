import os
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_CODER", "llama3")

# Wersja uproszczona - bez skomplikowanych headersów
llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0.1
)

def parse_and_save_files(ai_response: str):
    if not ai_response:
        return []
    
    # Regex szuka: ### FILE: nazwa ... ### ENDFILE
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []
    
    # Fallback - jeśli AI zapomniało o znacznikach, zapisz całość
    if not matches and len(ai_response) > 10:
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        write_file(filename, content)
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state["plan"]
    
    print(f"--- PROGRAMISTA (Model: {MODEL_NAME}) ---")
    print("Generowanie kodu... (Proszę czekać, to może potrwać chwilę)")

    sys_msg = SystemMessage(content=f"""
    Jesteś programistą. Napisz kod plików z planu.
    
    PLAN: {plan}
    
    FORMAT WYMAGANY:
    ### FILE: nazwa_pliku
    TRESC
    ### ENDFILE
    """)
    
    try:
        # Używamy invoke (czekamy na całość), to jest stabilniejsze
        response = llm.invoke([sys_msg])
        full_response = response.content
        print("-> Otrzymano odpowiedź od AI.")
        
    except Exception as e:
        print(f"BLAD: {e}")
        write_file("error_log.txt", str(e))
        full_response = ""

    saved_files = parse_and_save_files(full_response)
    
    if not saved_files:
        write_file("error_report.txt", "Brak plikow. Tresc od AI: " + full_response[:100])
        saved_files.append("error_report.txt")

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content="Gotowe")]
    }