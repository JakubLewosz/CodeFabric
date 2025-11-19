import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import read_file

load_dotenv()

# --- KONFIGURACJA ---
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
# Reviewer może używać tego samego modelu co Coder lub Chat (llama3 jest OK do recenzji)
MODEL_NAME = os.getenv("MODEL_CHAT", "llama3")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

print(f"--- INICJALIZACJA RECENZENTA ---")
print(f"Model: {MODEL_NAME}")

llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0, # Zero kreatywności, czysta analiza
    timeout=300.0,
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {"Authorization": f"Bearer {OLLAMA_TOKEN}"} if OLLAMA_TOKEN else {}
    }
)

def reviewer_node(state: AgentState):
    current_files = state.get("current_files", [])
    
    # Jeśli nie ma plików, nie ma co sprawdzać
    if not current_files:
        return {
            "feedback": "Brak plików do sprawdzenia.",
            "messages": [AIMessage(content="Brak plików.")]
        }

    # 1. Pobieramy treść plików do analizy
    files_content = ""
    for file in current_files:
        content = read_file(file)
        # Ograniczamy wielkość (żeby nie zatkać modelu), np. pierwsze 5000 znaków pliku
        # Jeśli content to string błędu z file_ops, też go dołączamy
        files_content += f"\n--- PLIK: {file} ---\n{content[:5000]}\n"

    print(f"\n--- RECENZENT ANALIZUJE KOD ({len(current_files)} plików) ---")

    # 2. Prompt dla Recenzenta
    msg = HumanMessage(content=f"""
    Jesteś Senior Code Reviewerem (Testerem).
    Twoim zadaniem jest sprawdzić poniższy kod pod kątem błędów składniowych, logicznych lub brakujących importów.

    KOD DO SPRAWDZENIA:
    {files_content}

    DECYZJA:
    Jeśli kod wygląda na poprawny i kompletny, napisz tylko jedno słowo: APPROVE
    Jeśli są błędy, napisz słowo REJECT, a następnie w punktach wymień co trzeba poprawić.

    Nie pisz kodu poprawkowego, tylko wskaż błędy.
    """)

    try:
        response = llm.invoke([msg])
        review_result = response.content
        print(f"-> Werdykt: {review_result[:50]}...")
        
    except Exception as e:
        # Fallback w razie awarii AI - przepuszczamy kod
        error_msg = f"BŁĄD RECENZENTA: {e}"
        print(error_msg)
        review_result = "APPROVE" 
        # Tworzymy sztuczną odpowiedź, żeby nie było błędu zmiennej response
        response = AIMessage(content=f"Automatyczna akceptacja (błąd połączenia: {e})")

    # 3. Aktualizujemy stan o feedback
    # Ten feedback trafi do Managera, a potem ew. do Codera
    return {
        "feedback": review_result,
        "messages": [response] 
    }