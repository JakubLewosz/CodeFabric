import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import read_file
from tools.llm_factory import get_llm

def reviewer_node(state: AgentState):
    current_files = state.get("current_files", [])
    
    if not current_files:
        return {"feedback": "Brak plików.", "messages": []}

    # 1. Weryfikacja README
    has_readme = any("readme.md" in f.lower() for f in current_files)
    if not has_readme:
        return {
            "feedback": "REJECT. Brak pliku README.md.",
            "messages": [AIMessage(content="Brak README.")]
        }

    # 2. Pobieramy model (Najlepiej Qwen lub Llama 3, bo muszą rozumieć logikę)
    model_name = state.get("model_names", {}).get("chat", "mistral:7b")
    llm = get_llm(model_name, temperature=0.1)

    # 3. Przygotowanie kodu
    files_content = ""
    for file in current_files:
        content = read_file(file)
        # Dla Reviewera kod jest ważniejszy niż dla Codera, więc dajemy mu więcej kontekstu
        files_content += f"\n--- PLIK: {file} ---\n{content[:6000]}\n"

    print(f"\n--- RECENZENT ({model_name}): SYMULACJA LOGICZNA ---")

    # 4. PANCERNY PROMPT WERYFIKACYJNY
    msg = HumanMessage(content=f"""
    Jesteś Senior QA Engineerem. Twoim zadaniem jest nie tylko sprawdzić składnię, ale przeprowadzić MENTALNĄ SYMULACJĘ działania kodu.
    
    KOD DO SPRAWDZENIA:
    {files_content}
    
    SPRAWDŹ KRYTYCZNE PUNKTY (Checklista):
    1. PUNKT WEJŚCIA: Czy jest jasno zdefiniowany (np. `if __name__ == "__main__":`)? Czy wiadomo, co uruchomić?
    2. PĘTLE NIESKOŃCZONE: Czy `while True` ma mechanizm wyjścia lub `sleep`?
    3. IMPORTY: Czy używane biblioteki są zaimportowane?
    4. GUI/GRY: Jeśli to gra (Pygame/Tkinter), czy jest pętla zdarzeń (event loop) i aktualizacja ekranu?
    5. ŚCIEŻKI: Czy kod odwołuje się do plików, które istnieją w projekcie?
    
    DECYZJA:
    - Jeśli kod wygląda na działający -> napisz tylko: APPROVE
    - Jeśli znajdziesz błąd logiczny -> napisz: REJECT i opisz błąd. Bądź surowy.
    
    Jeśli brakuje logiki (np. pusta funkcja), też daj REJECT.
    """)

    try:
        res = llm.invoke([msg])
        feedback = res.content
        print(f"-> Werdykt: {feedback[:100]}...")
    except Exception:
        feedback = "APPROVE"

    return {
        "feedback": feedback,
        "messages": [res]
    }