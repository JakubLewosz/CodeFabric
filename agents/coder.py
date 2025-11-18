import re
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState
from tools.file_ops import write_file

# --- KONFIGURACJA NA SZTYWNO (Omijamy .env dla pewności) ---
# Używamy IP 127.0.0.1, bo localhost czasem nie działa na Windows
HARDCODED_URL = "http://127.0.0.1:11434"
HARDCODED_MODEL = "llama3" 

print(f"--- INICJALIZACJA MODELU: {HARDCODED_MODEL} na {HARDCODED_URL} ---")

llm = ChatOllama(
    model=HARDCODED_MODEL,
    base_url=HARDCODED_URL,
    temperature=0.1
)

def parse_and_save_files(ai_response: str):
    if not ai_response: 
        return []
    
    pattern = r"###\s*FILE:\s*([^\n]+)\n(.*?)\n###\s*ENDFILE"
    matches = re.findall(pattern, ai_response, re.DOTALL | re.IGNORECASE)
    created_files = []
    
    # Fallback
    if not matches and len(ai_response) > 5:
        write_file("raw_code.txt", ai_response)
        return ["raw_code.txt"]

    for filename, content in matches:
        filename = filename.strip()
        content = content.strip()
        # Usuwanie markdowna
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        
        write_file(filename, content)
        created_files.append(filename)
        
    return created_files

def coder_node(state: AgentState):
    plan = state.get("plan", "Brak planu")
    
    print("--- PROGRAMISTA ROZPOCZYNA PRACĘ ---")
    
    # Bardzo prosty prompt bez skomplikowanych instrukcji systemowych
    prompt = f"""
    Zadanie: Napisz kod plików na podstawie tego planu:
    {plan}
    
    Ważne: Użyj formatu:
    ### FILE: nazwa.txt
    tresc
    ### ENDFILE
    """
    
    try:
        # Proste wywołanie invoke
        response = llm.invoke(prompt)
        full_response = response.content
        print(f"-> Otrzymano znaków: {len(full_response)}")
        
        if len(full_response) == 0:
            print("!!! OSTRZEŻENIE: Model zwrócił pusty tekst.")
            
    except Exception as e:
        print(f"!!! BLAD KRYTYCZNY: {e}")
        full_response = str(e)

    saved_files = parse_and_save_files(full_response)
    
    if not saved_files:
        write_file("error_debug.txt", f"Brak plikow. Model odpowiedzial:\n{full_response}")
        saved_files.append("error_debug.txt")

    return {
        "current_files": saved_files,
        "messages": [] 
    }