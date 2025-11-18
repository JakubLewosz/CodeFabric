import os
import re
import sys
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
    temperature=0.3, # Lekko podnosimy, żeby model się nie "zaciął"
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        } if OLLAMA_TOKEN else {}
    }
)

def parse_and_save_files(ai_response: str):
    # Jeśli odpowiedź jest pusta, nie ma sensu parsować
    if not ai_response:
        print("BLAD: Otrzymano pusty ciąg znaków od AI.")
        return []

    # Pattern szuka: ### FILE: nazwa ... ### ENDFILE
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    
    created_files = []
    
    if not matches:
        print("DEBUG: Nie wykryto znaczników. Zapisuję raw_code.txt dla bezpieczeństwa.")
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        # Czyszczenie bloków markdown
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        write_file(filename, content)
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state["plan"]
    
    sys_msg = SystemMessage(content=f"""
    Jesteś generatorem kodu.
    Zadanie: Napisz kod dla plików z poniższego planu.
    
    PLAN:
    {plan}
    
    WYMAGANY FORMAT:
    ### FILE: nazwa.rozszerzenie
    TRESC_KODU
    ### ENDFILE
    
    Użyj tego formatu dla każdego pliku. Nie dodawaj komentarzy przed ani po.
    """)
    
    print(f"--- PROGRAMISTA ROZPOCZYNA PISANIE (Model: {MODEL_NAME}) ---")
    
    # --- ZMIANA: UŻYWAMY STREAM ZAMIAST INVOKE ---
    full_response = ""
    try:
        # Pobieramy odpowiedź kawałek po kawałku i sklejamy ją
        for chunk in llm.stream([sys_msg]):
            content = chunk.content
            if content:
                print(content, end="", flush=True) # Wypisuje na żywo w konsoli
                full_response += content
                
        print("\n--- KONIEC GENEROWANIA ---")
        
    except Exception as e:
        print(f"\nBŁĄD PODCZAS GENEROWANIA: {str(e)}")
        return {
            "current_files": [],
            "messages": []
        }

    # Parsujemy dopiero jak mamy całość
    saved_files = parse_and_save_files(full_response)
    
    # Tworzymy sztuczną wiadomość z pełną treścią, żeby zachować spójność stanu
    # (ponieważ stream nie zwraca jednego obiektu AIMessage)
    from langchain_core.messages import AIMessage
    final_message = AIMessage(content=full_response)
    
    return {
        "current_files": saved_files,
        "messages": [final_message]
    }