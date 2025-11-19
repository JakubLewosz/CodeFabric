import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

# --- GLOBALNA KONFIGURACJA ---
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

def get_llm(model_name: str, temperature: float = 0.1, num_ctx: int = 8192):
    """
    Tworzy i zwraca skonfigurowaną instancję ChatOllama.
    """
    print(f"🔧 Init LLM: {model_name} (Ctx: {num_ctx}, Temp: {temperature})")
    
    return ChatOllama(
        model=model_name,
        base_url=OLLAMA_URL,
        temperature=temperature,
        num_ctx=num_ctx,       # Duże okno pamięci
        timeout=300.0,         # Długi timeout na start
        client_kwargs={
            "verify": VERIFY_SSL,
            "headers": {"Authorization": f"Bearer {OLLAMA_TOKEN}"} if OLLAMA_TOKEN else {}
        }
    )