import os
import re
import sys
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file

# --- 1. ŁADOWANIE KONFIGURACJI ---
load_dotenv()

# Pobieramy adres z .env lub domyślny localhost (dla tunelu SSH)
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
# Jeśli w .env nie ma modelu, używamy bezpiecznego 'llama3'
MODEL_NAME = os.getenv("MODEL_CODER", "llama3") 
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

print(f"--- INICJALIZACJA PROGRAMISTY ---")
print(f"Model: {MODEL_NAME}")
print(f"Adres: {OLLAMA_URL}")

# --- 2. KONFIGURACJA MODELU (Z TIMEOUTEM) ---
try:
    llm = ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_URL,
        temperature=0.1,    # Niska temperatura = dokładniejszy kod
        num_ctx=8192,       # Zwiększamy pamięć podręczną (ważne przy dużych planach!)
        timeout=300.0,      # WAŻNE: Czekamy do 5 minut na odpowiedź (na wypadek "zimnego startu")
        client_kwargs={
            "verify": VERIFY_SSL,
            "headers": {
                "Authorization": f"Bearer {OLLAMA_TOKEN}"
            } if OLLAMA_TOKEN else {}
        }
    )
except Exception as e:
    print(f"BŁĄD KONFIGURACJI LLM: {e}")

# --- 3. FUNKCJA PARSUJĄCA (REGEX) ---
def parse_and_save_files(ai_response: str):
    """
    Wyciąga kod spomiędzy znaczników ### FILE: ... ### ENDFILE
    """
    if not ai_response:
        print("!!! OSTRZEŻENIE: AI zwróciło pusty tekst.")
        return []

    # Regex szuka bloków kodu
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    
    created_files = []
    
    # Fallback: Jeśli AI napisało kod, ale zapomniało tagów, ratujemy go w jednym pliku
    if not matches and len(ai_response) > 20:
        print("DEBUG: Brak znaczników ### FILE. Zapisuję całość jako raw_code.txt")
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        
        # Czyszczenie: Usuwamy znaczniki Markdown (```python ... ```) z wnętrza pliku
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        # Zapis fizyczny
        write_file(filename, content)
        print(f"-> Zapisano plik: {filename}")
        created_files.append(filename)
        
    return created_files

# --- 4. GŁÓWNA LOGIKA AGENTA ---
def coder_node(state: AgentState):
    plan = state.get("plan", "Brak planu.")
    
    # Bardzo konkretny prompt wymuszający formatowanie
    sys_msg = SystemMessage(content=f"""
    Jesteś doświadczonym programistą Python/Web.
    Twoim zadaniem jest napisać kod dla WSZYSTKICH plików opisanych w planie.
    
    PLAN PROJEKTU:
    {plan}
    
    --- INSTRUKCJA FORMATOWANIA (KRYTYCZNE) ---
    Musisz użyć poniższego formatu dla każdego pliku. 
    System automatycznie dzieli pliki na podstawie tych znaczników.
    
    ### FILE: nazwa_pliku.rozszerzenie
    TU_WKLEJ_KOD_PLIKU
    ### ENDFILE
    
    Przykład:
    ### FILE: script.py
    print("Hello World")
    ### ENDFILE
    
    Nie dodawaj zbędnych komentarzy. Zacznij pisać kod.
    """)
    
    print(f"\n--- PROGRAMISTA ROZPOCZYNA GENEROWANIE ---")
    
    full_response = ""
    
    try:
        # Używamy STREAM, aby utrzymać połączenie i widzieć postęp
        for chunk in llm.stream([sys_msg]):
            content = chunk.content
            if content:
                print(content, end="", flush=True) # Wypisuje literki w konsoli
                full_response += content
                
        print("\n--- KONIEC GENEROWANIA ---")
        
    except Exception as e:
        error_msg = f"BŁĄD POŁĄCZENIA Z OLLAMA: {str(e)}"
        print(f"\n!!! {error_msg}")
        # Zapisujemy błąd do pliku, żeby wiedzieć co się stało
        write_file("connection_error.log", error_msg)
        full_response = ""

    # Parsowanie i zapis
    saved_files = parse_and_save_files(full_response)
    
    # --- HAMULEC BEZPIECZEŃSTWA ---
    # Jeśli lista plików jest pusta (błąd lub pusta odpowiedź), tworzymy raport.
    # Dzięki temu Manager zobaczy, że "coś" powstało i nie zapętli się.
    if not saved_files:
        report_name = "error_report.txt"
        msg = "AI nie wygenerowało żadnych plików. Sprawdź logi w konsoli."
        write_file(report_name, msg)
        saved_files.append(report_name)

    # Zwracamy stan
    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Zadanie zakończone. Pliki: {saved_files}")]
    }