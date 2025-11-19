import os
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file

load_dotenv()

# --- KONFIGURACJA ---
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
    num_ctx=8192,       # WAŻNE: Pamięć modelu (Context Window)
    timeout=300.0,      # Timeout 5 minut (dla "zimnego startu")
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {"Authorization": f"Bearer {OLLAMA_TOKEN}"} if OLLAMA_TOKEN else {}
    }
)

def parse_and_save_files(ai_response: str):
    """Parsuje odpowiedź AI i zapisuje pliki."""
    if not ai_response:
        return []

    # Regex szukający plików: ### FILE: nazwa ... ### ENDFILE
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []

    # Fallback: Jeśli brak znaczników, ale jest treść -> zapisz jako raw
    if not matches and len(ai_response.strip()) > 0:
        print("DEBUG: Zapisuję raw_code.txt (brak znaczników)")
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
    
    # --- LOGIKA POPRAWEK (NOWOŚĆ) ---
    # Sprawdzamy, czy Recenzent odrzucił kod
    if feedback and "REJECT" in str(feedback).upper():
        print(f"--- PROGRAMISTA: TRYB NAPRAWY (Iteracja {current_revisions + 1}) ---")
        instruction_prefix = f"""
        UWAGA: To jest POPRAWKA kodu.
        Twój poprzedni kod zawierał błędy wykryte przez testera.
        
        LISTA BŁĘDÓW DO NAPRAWIENIA:
        {feedback}
        
        Zadanie: Przepisz kod plików, naprawiając te błędy.
        """
        new_revision_count = current_revisions + 1
    else:
        print(f"--- PROGRAMISTA: TWORZENIE OD ZERA ---")
        instruction_prefix = "Zadanie: Napisz kod plików na podstawie planu od zera."
        new_revision_count = current_revisions

    # Budujemy Prompt
    msg = HumanMessage(content=f"""
    {instruction_prefix}
    
    PLAN PROJEKTU:
    {plan}
    
    FORMAT WYMAGANY (Użyj go dokładnie):
    ### FILE: nazwa_pliku.ext
    TRESC_KODU
    ### ENDFILE
    
    Nie pisz wstępów. Tylko bloki kodu.
    """)
    
    print(f"--- WYSYŁANIE ZAPYTANIA (Czekam na odpowiedź)... ---")
    
    full_response = ""
    try:
        # Używamy INVOKE (nie stream) dla stabilności połączenia
        response_obj = llm.invoke([msg])
        full_response = response_obj.content
        
        print(f"-> Otrzymano odpowiedź! Długość: {len(full_response)} znaków.")
        
        if not full_response:
            print("!!! OSTRZEŻENIE: Odpowiedź jest pusta.")

    except Exception as e:
        err = f"BŁĄD KRYTYCZNY LLM: {e}"
        print(f"\n{err}")
        write_file("error_log.txt", err)

    # Parsowanie i zapis
    saved_files = parse_and_save_files(full_response)
    
    # Raport błędu jeśli pusto
    if not saved_files:
        debug_info = f"Brak plikow. Odpowiedz modelu: {full_response[:200]}..."
        write_file("error_report.txt", debug_info)
        saved_files.append("error_report.txt")

    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Pliki gotowe: {saved_files}")],
        "revision_count": new_revision_count, # Aktualizujemy licznik prób
        "feedback": None # Ważne! Czyścimy feedback, żeby nie wpaść w pętlę
    }