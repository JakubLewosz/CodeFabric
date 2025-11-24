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
    Tworzy instancję modelu z odpowiednimi parametrami.
    
    Args:
        model_name: Nazwa modelu (np. "qwen2.5-coder:32b")
        temperature: 0.0 = deterministyczny, 1.0 = kreatywny
        num_ctx: Rozmiar okna kontekstowego (tokeny)
    
    Returns:
        ChatOllama instance
    """
    
    if num_ctx > 16384:
        print(f"⚠️ UWAGA: Duże okno kontekstowe ({num_ctx} tokenów). To może spowolnić generację.")
    
    if num_ctx >= 32000:
        recommended_models = ["qwen2.5-coder:32b", "llama3.3:70b", "qwq:32b"]
        if not any(rec in model_name for rec in recommended_models):
            print(f"💡 Dla {num_ctx} tokenów zalecane: {', '.join(recommended_models)}")
    
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

def estimate_tokens(text: str) -> int:
    """
    Przybliżona estymacja liczby tokenów (1 token ≈ 4 znaki dla języków zachodnich).
    """
    return len(text) // 4

def check_context_usage(text: str, num_ctx: int, warn_threshold: float = 0.8):
    """
    Sprawdza czy tekst nie przekracza limitu kontekstu.
    
    Args:
        text: Tekst do sprawdzenia
        num_ctx: Maksymalny rozmiar kontekstu
        warn_threshold: Próg ostrzeżenia (0.0-1.0)
    
    Returns:
        tuple: (estimated_tokens, is_safe, warning_message)
    """
    estimated = estimate_tokens(text)
    usage_ratio = estimated / num_ctx
    
    is_safe = usage_ratio < 1.0
    warning = None
    
    if usage_ratio >= 1.0:
        warning = f"🚨 PRZEKROCZONO LIMIT! {estimated} tokenów > {num_ctx} (kontekst)"
    elif usage_ratio >= warn_threshold:
        warning = f"⚠️ Kontekst prawie pełny: {estimated}/{num_ctx} tokenów ({usage_ratio*100:.1f}%)"
    
    return estimated, is_safe, warning