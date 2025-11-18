import os
import re
import sys
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file
from langchain_core.messages import HumanMessage 


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
        temperature=0.1,
        
        # --- DODAJ TE DWIE LINIJKI ---
        num_ctx=8192,       # Zwiększamy pamięć 4-krotnie (do 8k tokenów)
        num_predict=2000,   # Pozwalamy modelowi generować długi kod
        # -----------------------------
        
        timeout=300.0,
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
    
    # ZMIANA: Zamiast SystemMessage używamy HumanMessage.
    # Llama 3 czasem ignoruje SystemMessage przy długich promptach.
    prompt_content = f"""
    Zadanie: Jesteś programistą Python. Napisz kod dla plików z tego planu:
    
    {plan}
    
    --- INSTRUKCJA ---
    Dla każdego pliku użyj formatu:
    
    ### FILE: nazwa_pliku
    TUTAJ KOD
    ### ENDFILE
    
    Nie pisz nic innego. Tylko bloki kodu.
    """
    
    msg = HumanMessage(content=prompt_content)
    
    print(f"\n--- PROGRAMISTA ROZPOCZYNA PRACĘ (Ctx: 8192) ---")
    
    full_response = ""
    try:
        # Próbujemy invoke (zwykłe zapytanie), jest stabilniejsze przy błędach kontekstu
        response = llm.invoke([msg])
        full_response = response.content
        print(f"-> Otrzymano znaków: {len(full_response)}")
        
    except Exception as e:
        print(f"!!! BŁĄD LLM: {e}")
        full_response = ""

    # Parsowanie...
    saved_files = parse_and_save_files(full_response)
    
    if not saved_files:
        # Jeśli nadal pusto, zapisujemy co dostaliśmy (nawet jak puste) do debugowania
        debug_msg = f"Otrzymano pusty tekst. Długość planu wejściowego: {len(plan)} znaków."
        write_file("error_debug.txt", debug_msg)
        saved_files.append("error_debug.txt")

    return {
        "current_files": saved_files,
        "messages": [] 
    }