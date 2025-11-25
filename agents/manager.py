import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from state import AgentState
from tools.file_ops import write_file

load_dotenv()

def manager_node(state: AgentState):
    """
    Agent Zarządzający.
    Priorytet: sukces (APPROVE) > limit prób.
    """
    plan = state.get("plan")
    files = state.get("current_files")
    feedback = state.get("feedback")
    revision_count = state.get("revision_count", 0)
    plan_approved = state.get("plan_approved", False)

    # === 1. NAJWAŻNIEJSZE: CZY MAMY SUKCES? ===
    if files and feedback and "APPROVE" in str(feedback).upper():
        print("✅ MANAGER: Projekt zatwierdzony.")
        # Resetuj state dla kolejnego prompta (w tym samym chacie)
        return {
            "next_node": "end",
            "plan": None,
            "plan_approved": False,
            "feedback": None,
            "revision_count": 0
        }

    # === 2. BEZPIECZNIK (LIMIT POPRAWEK) ===
    if revision_count >= 3:
        print(f"🛑 MANAGER: Limit poprawek ({revision_count}). Kończę, oddaję co mam.")
        
        # === DIAGNOSTYKA - Zapisz raport niepowodzenia ===
        failure_report = f"""# 🚨 RAPORT NIEPOWODZENIA

## Status
- **Iteracje**: {revision_count}
- **Ostatni feedback**: {feedback if feedback else 'Brak'}
- **Pliki wygenerowane**: {len(files) if files else 0}

## Plan
```
{plan if plan else 'Brak planu'}
```

## Ostatnie pliki
{chr(10).join(f'- {f}' for f in files) if files else 'Brak'}

## Analiza
System zatrzymał się po {revision_count} próbach poprawek.
Możliwe przyczyny:
1. LLM nie rozumie specyfikacji
2. Zbyt skomplikowane wymagania
3. Problem z kontekstem (zbyt długi kod)

## Zalecenia
- Uprość zadanie
- Zmień model (spróbuj Qwen 2.5 Coder)
- Podziel projekt na mniejsze części
"""
        write_file("FAILURE_REPORT.md", failure_report)
        print("→ Zapisano FAILURE_REPORT.md")
        
        return {"next_node": "end"}

    # === 3. STANDARDOWY PRZEPŁYW ===
    
    # Brak planu -> Planner
    if not plan:
        print("📋 MANAGER: Brak planu → Wysyłam do Plannera")
        return {"next_node": "planner"}

    # Czekanie na zatwierdzenie planu (UI)
    if plan and not plan_approved:
        # Auto-approve gdy są już pliki (kontynuacja projektu)
        if files and len(files) > 0:
            print("📋 MANAGER: Kontynuacja projektu - auto-zatwierdzam plan")
            return {
                "next_node": "coder",
                "plan_approved": True
            }
        
        # Nowy projekt - czekaj na użytkownika
        if feedback:
            print("🔄 MANAGER: Plan wymaga poprawek → Planner")
            return {"next_node": "planner"}
        
        print("⏸️ MANAGER: Czekam na zatwierdzenie planu przez użytkownika")
        return {"next_node": "end"}

    # Plan zatwierdzony, brak plików -> Coder
    if plan and plan_approved and not files:
        print("💻 MANAGER: Plan zatwierdzony → Coder rozpoczyna pracę")
        return {"next_node": "coder"}

    # Pętla Jakości (Jeśli feedback to REJECT)
    if files and feedback and "REJECT" in str(feedback).upper():
        print(f"⚠️ MANAGER: Błędy wykryte. Zarządzam poprawkę (Próba {revision_count + 1}/3).")
        return {"next_node": "coder"}

    # Fallback
    print("🏁 MANAGER: Nie ma więcej akcji → END")
    return {"next_node": "end"}