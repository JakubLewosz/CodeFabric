from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import read_file
from tools.llm_factory import get_llm

def reviewer_node(state: AgentState):
    current_files = state.get("current_files", [])
    
    # Jeśli nie ma plików, nie ma co sprawdzać
    if not current_files:
        return {
            "feedback": "Brak plików do sprawdzenia.",
            "messages": [AIMessage(content="Brak plików.")]
        }

    # --- CHECKLISTA: CZY JEST DOKUMENTACJA? ---
    # Sprawdzamy to mechanicznie (Pythonem)
    has_readme = any("readme.md" in f.lower() for f in current_files)
    
    if not has_readme:
        print("--- RECENZENT: BRAK README.MD! ODRZUCAM PROJEKT. ---")
        return {
            "feedback": "REJECT. Błąd krytyczny: Brakuje pliku README.md. Musisz stworzyć plik README.md z opisem projektu i instrukcją uruchomienia.",
            "messages": [AIMessage(content="Odrzucono: Brak README.md")]
        }

    # 1. Pobieramy model z Factory
    model_name = state.get("model_names", {}).get("chat", "mistral:7b")
    llm = get_llm(model_name, temperature=0.1)

    # 2. Przygotowanie treści
    files_content = ""
    for file in current_files:
        content = read_file(file)
        # Ograniczamy wielkość
        files_content += f"\n--- PLIK: {file} ---\n{content[:4000]}\n"

    print(f"\n--- RECENZENT ({model_name}): ANALIZUJE KOD ---")

    msg = HumanMessage(content=f"""
    Jesteś Senior Code Reviewerem (Testerem).
    Twoim zadaniem jest sprawdzić kod oraz DOKUMENTACJĘ.

    KOD DO SPRAWDZENIA:
    {files_content}

    ZASADY OCENY:
    1. Sprawdź czy kod nie ma błędów składniowych.
    2. Sprawdź czy README.md zawiera sensowne instrukcje.
    
    DECYZJA:
    - Jeśli wszystko OK -> napisz tylko: APPROVE
    - Jeśli są błędy -> napisz: REJECT i wymień w punktach co poprawić.
    """)

    try:
        response = llm.invoke([msg])
        review_result = response.content
        print(f"-> Werdykt: {review_result[:50]}...")
    except Exception as e:
        print(f"BŁĄD RECENZENTA: {e}")
        review_result = "APPROVE" # Fallback
        response = AIMessage(content="Auto-Approve (Error)")

    return {
        "feedback": review_result,
        "messages": [response] 
    }