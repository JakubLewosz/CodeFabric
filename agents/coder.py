import os
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState
from tools.file_ops import write_file

# Ładujemy konfigurację
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN")
MODEL_NAME = os.getenv("MODEL_CODER", "deepseek-coder-v2") 
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

# Inicjalizacja modelu
llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0.2,
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        } if OLLAMA_TOKEN else {}
    }
)

def parse_and_save_files(ai_response: str):
    """
    Funkcja szuka w tekście fragmentów kodu oznaczonych specjalnymi tagami
    i zapisuje je jako osobne pliki.
    """
    # Szukamy wzorca: ### FILE: nazwa_pliku ...treść... ### ENDFILE
    # Używamy re.DOTALL, żeby kropka łapała też nowe linie
    pattern = r"### FILE: (.*?)\s(.*?)\s### ENDFILE"
    
    matches = re.findall(pattern, ai_response, re.DOTALL)
    
    created_files = []
    
    if not matches:
        # Fallback: Jeśli model zapomniał formatu, zapisz wszystko do jednego pliku
        # żeby nie stracić kodu.
        fallback_name = "raw_code.txt"
        write_file(fallback_name, ai_response)
        return [fallback_name]

    for filename, content in matches:
        filename = filename.strip()
        # Zapisz plik używając naszego narzędzia
        result = write_file(filename, content.strip())
        print(f"Log: {result}") # Logowanie w konsoli dla debugowania
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state["plan"]
    
    # NOWY PROMPT: Wymusza na modelu używanie konkretnego formatu
    sys_msg = SystemMessage(content=f"""
    Jesteś Senior Developerem. Twoim zadaniem jest napisać kod na podstawie PLANU.
    
    PLAN:
    {plan}
    
    INSTRUKCJA FORMATOWANIA (BARDZO WAŻNE):
    Aby stworzyć pliki, musisz użyć dokładnie tego formatu dla KAŻDEGO pliku:

    ### FILE: nazwa_pliku.rozszerzenie
    ... tutaj wklej kod tego pliku ...
    ### ENDFILE
    
    Przykład:
    ### FILE: main.py
    print("Hello World")
    ### ENDFILE
    
    ### FILE: styles.css
    body {{ background: blue; }}
    ### ENDFILE
    
    Napisz kod dla wszystkich plików z planu w jednej wiadomości.
    """)
    
    print("--- PROGRAMISTA ROZPOCZYNA PISANIE ---")
    response = llm.invoke([sys_msg])
    
    # Używamy naszej nowej funkcji parsującej
    saved_files = parse_and_save_files(response.content)
    
    return {
        "current_files": saved_files,
        "messages": [response]
    }