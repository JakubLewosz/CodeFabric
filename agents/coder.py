import os
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState
from tools.file_ops import write_file

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN")
MODEL_NAME = os.getenv("MODEL_CODER", "deepseek-coder-v2") 
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0.1, # Zmniejszamy temperaturę, żeby był bardziej "robotyczny"
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        } if OLLAMA_TOKEN else {}
    }
)

def parse_and_save_files(ai_response: str):
    """
    Wersja ulepszona regexa - bardziej odporna na błędy formatowania AI.
    """
    print(f"DEBUG: Otrzymano od AI ({len(ai_response)} znaków):\n{ai_response[:200]}...") # Podgląd w konsoli
    
    # Szukamy: ### FILE: nazwa (koniec linii) tresc ### ENDFILE
    # Flag re.DOTALL sprawia, że kropka łapie też nowe linie
    # Flag re.IGNORECASE sprawia, że nie ma znaczenia czy AI napisze 'file' czy 'FILE'
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    
    created_files = []
    
    if not matches:
        print("DEBUG: Nie znaleziono znaczników ### FILE. Używam fallback.")
        fallback_name = "raw_code.txt"
        write_file(fallback_name, ai_response)
        return [fallback_name]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        
        # Usuń ewentualne znaczniki Markdowna (```python ... ```), jeśli AI je dodało wewnątrz bloku
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        result = write_file(filename, content)
        print(f"Log: {result}")
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state["plan"]
    
    # BARDZO SUROWY PROMPT
    sys_msg = SystemMessage(content=f"""
    Jesteś generatorem plików. NIE JESTEŚ ASYSTENTEM CZATU.
    Twoim jedynym zadaniem jest wygenerowanie kodu dla plików na podstawie planu.
    
    PLAN:
    {plan}
    
    ZASADY KRYTYCZNE:
    1. NIE pisz żadnego wstępu (np. "Oto kod...").
    2. NIE pisz żadnego zakończenia.
    3. Każdy plik musi być objęty specjalnymi znacznikami.
    
    FORMAT WYMAGANY (UŻYJ GO DOKŁADNIE):
    
    ### FILE: nazwa_pliku.ext
    TUTAJ_TRESC_PLIKU
    ### ENDFILE
    
    Przykład:
    ### FILE: main.py
    print("Hello")
    ### ENDFILE
    
    Jeśli plan wymaga 3 plików, musisz wygenerować 3 takie bloki.
    ZACZNIJ OD RAZU OD PIERWSZEGO ZNACZNIKA "### FILE:".
    """)
    
    print("--- PROGRAMISTA ROZPOCZYNA PISANIE ---")
    response = llm.invoke([sys_msg])
    
    saved_files = parse_and_save_files(response.content)
    
    return {
        "current_files": saved_files,
        "messages": [response]
    }