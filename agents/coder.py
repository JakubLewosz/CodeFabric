import os
import re
import sys
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, AIMessage
from state import AgentState
from tools.file_ops import write_file

# 1. Ładowanie konfiguracji
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN")
# Używamy modelu z .env, a jak nie ma to deepseek
MODEL_NAME = os.getenv("MODEL_CODER", "deepseek-coder-v2") 
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

# 2. Inicjalizacja LLM z obsługą SSL/Token
llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0.2, # Niska temperatura dla precyzji kodu
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        } if OLLAMA_TOKEN else {}
    }
)

def parse_and_save_files(ai_response: str):
    """
    Parsuje odpowiedź AI, wyciąga bloki kodu i zapisuje je na dysku.
    Zwraca listę utworzonych plików.
    """
    if not ai_response:
        print("BLAD: Otrzymano pusty ciąg znaków od AI.")
        return []

    # Szukamy wzorca: ### FILE: nazwa ... ### ENDFILE
    # Regex jest elastyczny na spacje i nowe linie
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    
    # flags=re.DOTALL sprawia, że kropka (.) łapie też znaki nowej linii (całą treść pliku)
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    
    created_files = []
    
    # FALLBACK: Jeśli AI napisało kod, ale zapomniało tagów
    if not matches and len(ai_response) > 10:
        print("DEBUG: Nie wykryto znaczników ### FILE. Zapisuję wszystko jako raw_code.txt")
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        
        # Usuwanie znaczników Markdown (np. ```python ... ```) jeśli AI je dodało
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        write_file(filename, content)
        created_files.append(filename)
        print(f"-> Utworzono: {filename}")
        
    return created_files

def coder_node(state: AgentState):
    plan = state["plan"]
    
    # 3. PROMPT (Instrukcja)
    sys_msg = SystemMessage(content=f"""
    Jesteś generatorem kodu (AI Developer).
    Twoim zadaniem jest napisać kod dla plików z poniższego PLANU.
    
    PLAN PROJEKTU:
    {plan}
    
    --- INSTRUKCJA FORMATOWANIA ---
    Dla KAŻDEGO pliku musisz użyć poniższego formatu. 
    Nie dodawaj żadnego tekstu przed ani po blokach plików.
    
    ### FILE: nazwa_pliku.rozszerzenie
    TUTAJ_TRESC_PLIKU
    ### ENDFILE
    
    Przykład:
    ### FILE: main.py
    print("Hello World")
    ### ENDFILE
    
    Napisz teraz kod dla wszystkich plików z planu.
    """)
    
    print(f"\n--- PROGRAMISTA ROZPOCZYNA PISANIE (Model: {MODEL_NAME}) ---")
    
    full_response = ""
    
    # 4. GENEROWANIE (STREAMING)
    try:
        for chunk in llm.stream([sys_msg]):
            content = chunk.content
            if content:
                print(content, end="", flush=True) # Efekt pisania w konsoli
                full_response += content
                
        print("\n--- KONIEC GENEROWANIA ---")
        
    except Exception as e:
        error_msg = f"Blad polaczenia z Ollama: {str(e)}"
        print(f"\n!!! {error_msg}")
        write_file("error_log.txt", error_msg)
        full_response = "" # Pusta odpowiedź triggeruje mechanizm bezpieczeństwa poniżej

    # 5. ZAPIS PLIKÓW
    saved_files = parse_and_save_files(full_response)
    
    # 6. HAMULEC BEZPIECZEŃSTWA (Zapobiega pętli Recursion Limit)
    # Jeśli po pracy codera nadal nie ma plików (bo był błąd lub pusta odp),
    # tworzymy plik raportu, żeby Manager widział, że "coś" powstało.
    if not saved_files:
        report_content = "AI nie wygenerowalo zadnych plikow lub wystapil blad polaczenia."
        write_file("error_report.txt", report_content)
        saved_files.append("error_report.txt")

    # Zwracamy stan - current_files nie może być puste!
    return {
        "current_files": saved_files,
        "messages": [AIMessage(content=f"Wygenerowano pliki: {saved_files}")]
    }