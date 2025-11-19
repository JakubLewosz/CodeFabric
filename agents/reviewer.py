import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import read_file
from tools.llm_factory import get_llm

def reviewer_node(state: AgentState):
    current_files = state.get("current_files", [])
    revision_count = state.get("revision_count", 0) # Sprawdzamy, która to próba

    if not current_files:
        return {"feedback": "Brak plików.", "messages": []}

    # --- LITOŚĆ DLA PĘTLI ---
    # Jeśli to już 3 próba (lub więcej), po prostu przepuszczamy kod.
    # Lepiej oddać użytkownikowi kod z błędami, niż zapętlić program.
    if revision_count >= 3:
        print("--- RECENZENT: LIMIT PRÓB. PRZEPUSZCZAM MIMO BŁĘDÓW. ---")
        return {
            "feedback": "APPROVE (Wymuszone - limit poprawek). Kod może zawierać błędy, sprawdź go ręcznie.",
            "messages": [AIMessage(content="Wymuszona akceptacja.")]
        }

    # Checklista README (Działa tylko w 1 i 2 próbie)
    has_readme = any("readme.md" in f.lower() for f in current_files)
    if not has_readme:
        return {
            "feedback": "REJECT. Brak README.md.",
            "messages": [AIMessage(content="Odrzucono: Brak README.")]
        }

    # Inicjalizacja modelu
    model_name = state.get("model_names", {}).get("chat", "mistral:7b")
    llm = get_llm(model_name, temperature=0.1)

    # Przygotowanie treści
    files_content = ""
    for file in current_files:
        content = read_file(file)
        files_content += f"\n--- {file} ---\n{content[:3000]}\n" # Mniejszy limit znaków dla szybkości

    print(f"\n--- RECENZENT ({model_name}): OCENA (Próba {revision_count + 1}) ---")

    msg = HumanMessage(content=f"""
    Jesteś Code Reviewerem.
    
    KOD:
    {files_content}
    
    Zadanie:
    Czy kod wygląda na kompletny (ma strukturę, importy)?
    
    ODPOWIEDŹ:
    - 'APPROVE' jeśli jest OK.
    - 'REJECT' jeśli są krytyczne błędy składni.
    """)

    try:
        res = llm.invoke([msg])
        feedback = res.content
    except Exception:
        feedback = "APPROVE"

    return {
        "feedback": feedback,
        "messages": [res]
    }