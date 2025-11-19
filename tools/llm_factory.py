import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

# Globalne ustawienia z .env
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

def get_llm(model_name: str, temperature: float = 0.1, num_ctx: int = 8192):
    """
    Tworzy instancję modelu z odpowiednimi parametrami (Timeout, SSL, Context).
    """
    # print(f"🔧 Fabryka: Tworzę model {model_name}...") # Opcjonalny log
    
    return ChatOllama(
        model=model_name,
        base_url=OLLAMA_URL,
        temperature=temperature,
        num_ctx=num_ctx,       
        timeout=300.0,         
        client_kwargs={
            "verify": VERIFY_SSL,
            "headers": {"Authorization": f"Bearer {OLLAMA_TOKEN}"} if OLLAMA_TOKEN else {}
        }
    )