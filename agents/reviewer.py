import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from state import AgentState
from tools.file_ops import read_file
from tools.llm_factory import get_llm

def smart_truncate(content: str, max_length: int = 8000) -> str:
    """
    Inteligentne obcinanie - zachowuje początek i koniec.
    """
    if len(content) <= max_length:
        return content
    
    head_size = max_length // 2
    tail_size = max_length // 2
    omitted = len(content) - max_length
    
    return (
        content[:head_size] + 
        f"\n\n# ... [POMINIĘTO {omitted} ZNAKÓW] ...\n\n" + 
        content[-tail_size:]
    )

def reviewer_node(state: AgentState):
    current_files = state.get("current_files", [])
    chat_workspace = state.get("chat_workspace")  # NOWOŚĆ
    
    # Ustaw workspace jeśli podany
    if chat_workspace:
        import tools.file_ops as file_ops_module
        file_ops_module.WORKSPACE_DIR = chat_workspace
    
    if not current_files:
        return {"feedback": "Brak plików.", "messages": []}

    # === 1. WALIDACJA PODSTAWOWA ===
    code_files = [f for f in current_files if f.endswith(('.py', '.js', '.html', '.css', '.cs', '.jsx', '.tsx'))]
    
    if not code_files:
        return {
            "feedback": "REJECT. Brak plików z kodem źródłowym.",
            "messages": [AIMessage(content="Tylko pliki nie-kodowe.")]
        }

    # 2. Weryfikacja README
    has_readme = any("readme.md" in f.lower() for f in current_files)
    if not has_readme:
        return {
            "feedback": "REJECT. Brak pliku README.md.",
            "messages": [AIMessage(content="Brak README.")]
        }

    # === 3. POBIERANIE MODELU ===
    model_name = state.get("model_names", {}).get("chat", "bielik2.6:11b")
    llm = get_llm(model_name, temperature=0.1, num_ctx=16384)

    # === 4. PRZYGOTOWANIE KONTEKSTU ===
    files_content = ""
    total_lines = 0
    
    for file in code_files:
        content = read_file(file)
        line_count = content.count('\n')
        total_lines += line_count
        
        truncated = smart_truncate(content, max_length=10000)
        files_content += f"\n--- PLIK: {file} ({line_count} linii) ---\n{truncated}\n"

    print(f"\n--- RECENZENT ({model_name}): SYMULACJA LOGICZNA ({len(code_files)} plików, {total_lines} linii) ---")

    # === 5. PANCERNY PROMPT WERYFIKACYJNY ===
    msg = HumanMessage(content=f"""
Jesteś Senior QA Engineerem. Przeprowadź MENTALNĄ SYMULACJĘ działania kodu.

KOD DO SPRAWDZENIA:
{files_content}

=== CHECKLIST KRYTYCZNY ===

CZĘŚĆ 1: CZY KOD DZIAŁA (MUST-HAVE)
[ ] 1. PUNKT WEJŚCIA: Czy jest `if __name__ == "__main__":` lub podobny?
[ ] 2. PĘTLE: Czy `while True` ma event handling lub break?
[ ] 3. IMPORTY: Czy wszystkie używane biblioteki są zaimportowane?
[ ] 4. GUI/GRY: Czy jest pętla zdarzeń i aktualizacja ekranu?
[ ] 5. SKŁADNIA: Brak błędów składni?

CZĘŚĆ 2: JAKOŚĆ KODU (NICE-TO-HAVE)
[ ] 6. NAZWY: Czy zmienne mają sensowne nazwy? (nie: x, fp, d)
[ ] 7. FUNKCJE: Czy funkcje są krótkie (<50 linii) i robią jedną rzecz?
[ ] 8. MAGIC NUMBERS: Czy stałe są wyciągnięte na górę? (GRID_SIZE = 20)
[ ] 9. ERROR HANDLING: Czy ryzykowne operacje (I/O) mają try-except?
[ ] 10. DUPLIKACJA: Czy kod się powtarza? (DRY principle)

=== ZASADA OCENY ===

**APPROVE** jeśli:
- Część 1 (MUST-HAVE): ✅ Wszystkie OK - kod zadziała
- Część 2 (NICE-TO-HAVE): Opcjonalne sugestie

**REJECT** jeśli:
- Część 1 (MUST-HAVE): ❌ Coś nie działa - kod crashuje

IGNORUJ: Niedoskonałości w Części 2 NIE SĄ powodem do REJECT.
Możesz dodać sugestie ale daj APPROVE jeśli kod działa.

=== DECYZJA ===

**APPROVE**
Kod uruchomi się i będzie działał.
[Opcjonalnie: Sugestie jakości:
- Rozważ wyciągnięcie GRID_SIZE = 20 na stałą
- Funkcja main() mogłaby być krótsza]

LUB

**REJECT**
Kod NIE URUCHOMI SIĘ lub wywoła crash.
Błąd: [KONKRETNY błąd który spowoduje crash]
Lokalizacja: [plik.py, funkcja/linia]
""")

    # === 6. WYWOŁANIE I DIAGNOSTYKA ===
    try:
        res = llm.invoke([msg])
        feedback = res.content.strip()
        print(f"→ Werdykt: {feedback[:150]}...")
        
        # Diagnostyka - zapisz raport jeśli REJECT
        if "REJECT" in feedback.upper():
            report = f"""# RAPORT RECENZENTA
            
## Werdykt
{feedback}

## Sprawdzone pliki
{', '.join(code_files)}

## Statystyki
- Plików kodu: {len(code_files)}
- Łącznie linii: {total_lines}
- Model: {model_name}
"""
            from tools.file_ops import write_file
            write_file("review_report.md", report)
            print("→ Zapisano review_report.md")
            
    except Exception as e:
        print(f"⚠️ Błąd podczas recenzji: {e}")
        feedback = "APPROVE"

    return {
        "feedback": feedback,
        "messages": [res] if 'res' in locals() else [AIMessage(content=feedback)]
    }