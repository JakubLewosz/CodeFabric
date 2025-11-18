import os
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file

load_dotenv()

# Konfiguracja
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_CODER", "llama3")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

print(f"--- INICJALIZACJA PROGRAMISTY ---")
print(f"Model: {MODEL_NAME} | URL: {OLLAMA_URL}")

# Inicjalizacja modelu (Bez streamingu, z dużym oknem kontekstowym)
llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0.1,
    num_ctx=8192,       # WAŻNE: Pamięć modelu
    timeout=300.0,      # Timeout 5 minut
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {"Authorization": f"Bearer {OLLAMA_TOKEN}"} if OLLAMA_TOKEN else {}
    }
)

def parse_and_save_files(ai_response: str):
    if not ai_response:
        return []

    # Regex szukający plików
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []

    # Jeśli brak znaczników, ale jest treść -> zapisz jako raw
    if not matches and len(ai_response.strip()) > 0:
        print("DEBUG: Zapisuję raw_code.txt (brak znaczników)")
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = re.sub(r"^```[a-zA-Z]*\n", "", content.strip()) # Usuń ```python
        content = re.sub(r"\n```$", "", content)
        
        write_file(filename, content)
        print(f"-> Zapisano: {filename}")
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state.get("plan", "Brak planu.")
    
    # Używamy HumanMessage zamiast SystemMessage (bezpieczniej dla Llama3)
    msg = HumanMessage(content=f"""
    Zadanie: Napisz kod plików na podstawie tego planu:
    {plan}
    
    FORMAT WYMAGANY (Użyj go dokładnie):
    ### FILE: nazwa_pliku.ext
    TRESC_KODU
    ### ENDFILE
    
    Nie pisz wstępów. Tylko bloki kodu.
    """)
    
    print(f"\n--- WYSYŁANIE ZAPYTANIA (Czekam na odpowiedź, brak podglądu na żywo)... ---")
    
    full_response = ""
    try:
        # Używamy INVOKE (nie stream). To blokuje program aż przyjdzie całość.
        response_obj = llm.invoke([msg])
        
        # Wyciągamy treść
        full_response = response_obj.content
        
        print(f"-> Otrzymano odpowiedź! Długość: {len(full_response)} znaków.")
        
        if not full_response:
            print("!!! OSTRZEŻENIE: Odpowiedź jest pusta (pusty string).")

    except Exception as e:
        err = f"BŁĄD KRYTYCZNY LLM: {e}"
        print(f"\n{err}")
        write_file("error_log.txt", err)

    # Parsowanie
    saved_files = parse_and_save_files(full_response)
    
    # Jeśli pusto, raport
    if not saved_files:
        debug_info = f"Brak plikow. Odpowiedz modelu: {full_response[:200]}..."
        write_file("error_report.txt", debug_info)
        saved_files.append("error_report.txt")

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Pliki: {saved_files}")]
    }