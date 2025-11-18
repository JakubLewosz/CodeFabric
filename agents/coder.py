from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState
from tools.file_ops import write_file

# Używamy DeepSeek Coder (jeśli dostępny) lub Llama3 do pisania kodu
# UWAGA: Upewnij się, że masz ten model pobrany w Ollama!
llm = ChatOllama(model="deepseek-coder-v2", temperature=0.2)

def coder_node(state: AgentState):
    plan = state["plan"]
    
    # System Prompt dla Programisty
    sys_msg = SystemMessage(content=f"""
    Jesteś Senior Developerem. Twoim zadaniem jest napisać kod na podstawie otrzymanego PLANU.
    
    PLAN:
    {plan}
    
    INSTRUKCJE:
    1. Dla każdego pliku z planu, wygeneruj kompletny, działający kod.
    2. Twoja odpowiedź musi być sformatowana tak, abym mógł ją łatwo przetworzyć (lub po prostu napisz kod).
    
    WAŻNE:
    Jako AI w tej symulacji, musisz użyć "myślenia", ale ostatecznie powinieneś wygenerować treść plików.
    """)
    
    # Wywołanie modelu (tutaj w wersji uproszczonej prosimy o wygenerowanie treści)
    response = llm.invoke([sys_msg])
    
    # --- LOGIKA ZAPISU PLIKÓW (PARSOWANIE) ---
    # W pełnej wersji użylibyśmy "Tool Calling", ale dla prostoty przy modelach lokalnych
    # zrobimy prostą symulację: Programista "udaje", że zapisał plik main.py.
    # W kolejnym kroku (za chwilę) dodamy tu prawdziwe wywołanie write_file.
    
    # Na potrzeby testu, niech stworzy prosty plik powitalny, żebyś widział, że działa.
    write_file("README_FROM_AI.md", f"Projekt wygenerowany na podstawie planu:\n{plan}")
    
    return {
        "current_files": ["README_FROM_AI.md"],
        "messages": [response]
    }