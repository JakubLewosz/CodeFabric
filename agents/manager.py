"""Deterministic orchestration decisions for the CodeFabric graph."""

from typing import Iterable

from agents.common import review_decision
from agents.workspace import WorkspaceFiles, WorkspaceListError
from state import AgentState
from tools.text_files import is_internal_artifact

MAX_REVISIONS = 3


def _file_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [path for path in value if isinstance(path, str) and path.strip()]


def _failure_report(
    revision_count: int,
    feedback: object,
    files: Iterable[str],
    plan: object,
) -> str:
    file_list = list(files)
    return f"""# 🚨 RAPORT NIEPOWODZENIA

## Status
- **Iteracje**: {revision_count}
- **Ostatni feedback**: {feedback if feedback else "Brak"}
- **Pliki wygenerowane**: {len(file_list)}

## Plan
```
{plan if plan else "Brak planu"}
```

## Ostatnie pliki
{chr(10).join(f"- {path}" for path in file_list) if file_list else "Brak"}

## Analiza
System zatrzymał się po {revision_count} próbach poprawek.
Możliwe przyczyny:
1. LLM nie rozumie specyfikacji
2. Zbyt skomplikowane wymagania
3. Problem z kontekstem (zbyt długi kod)

## Zalecenia
- Uprość zadanie
- Zmień model
- Podziel projekt na mniejsze części
"""


def manager_node(state: AgentState):
    """Choose the next node using explicit state and exact review decisions."""
    plan = state.get("plan")
    state_files = _file_list(state.get("current_files"))
    feedback = state.get("feedback")
    try:
        revision_count = max(0, int(state.get("revision_count", 0) or 0))
    except (TypeError, ValueError):
        revision_count = 0
    plan_approved = bool(state.get("plan_approved", False))
    decision = review_decision(feedback)
    workspace = WorkspaceFiles(state.get("chat_workspace"))
    try:
        workspace_files = [path for path in workspace.list() if not is_internal_artifact(path)]
    except WorkspaceListError as exc:
        error = f"Nie można bezpiecznie odczytać listy plików workspace: {exc}"
        return {
            "next_node": "end",
            "feedback": f"REJECT: {error}",
            "last_error": error,
            "error_stage": "coder" if plan else "planner",
        }
    files = workspace_files if state.get("chat_workspace") else state_files
    last_error = state.get("last_error")
    error_stage = state.get("error_stage")

    retry_stage = state.get("retry_stage")
    if retry_stage in {"coder", "coder_quality", "reviewer"}:
        print(f"🔄 MANAGER: Ponawiam wyłącznie etap {retry_stage}.")
        next_node = "coder" if retry_stage == "coder_quality" else retry_stage
        retry_feedback = state.get("retry_feedback") if retry_stage == "coder_quality" else None
        return {
            "next_node": next_node,
            "feedback": retry_feedback,
            "last_error": None,
            "error_stage": None,
            "retry_stage": None,
            "retry_feedback": None,
        }

    # Planner failures carry no plan. End this graph run so the UI can expose
    # an actionable error instead of cycling manager -> planner indefinitely.
    if last_error and not plan:
        if state.get("next_node") == "manager":
            print("🔄 MANAGER: Ponawiam planowanie po żądaniu użytkownika.")
            return {
                "next_node": "planner",
                "feedback": None,
                "last_error": None,
                "error_stage": None,
            }
        print("🛑 MANAGER: Planowanie nie powiodło się.")
        return {
            "next_node": "end",
            "plan": None,
            "feedback": "REJECT: Nie udało się przygotować planu.",
            "last_error": str(last_error),
            "error_stage": error_stage or "planner",
        }

    # Błąd infrastruktury albo formatu nie jest jakościowym REJECT-em. Nie
    # wolno automatycznie przepisywać kodu, gdy zawiódł sam recenzent.
    if last_error:
        print(f"🛑 MANAGER: Etap {error_stage or 'pipeline'} zakończył się błędem.")
        return {
            "next_node": "end",
            "feedback": feedback or f"REJECT: Proces przerwany: {last_error}",
            "last_error": str(last_error),
            "error_stage": error_stage,
        }

    # An approval is meaningful only after an approved plan produced files.
    if decision == "APPROVE" and plan_approved and files:
        print("✅ MANAGER: Projekt zatwierdzony.")
        return {
            "next_node": "end",
            "plan": None,
            "plan_approved": False,
            "feedback": None,
            "revision_count": 0,
            "current_files": files,
            "last_error": None,
            "error_stage": None,
        }

    # Stop after exactly MAX_REVISIONS correction attempts. Replace the raw
    # review with an unambiguous marker so substring checks cannot mistake a
    # REJECT explanation mentioning APPROVE for success.
    if revision_count >= MAX_REVISIONS:
        print(f"🛑 MANAGER: Limit poprawek ({revision_count}). Kończę, oddaję co mam.")
        workspace.write(
            "FAILURE_REPORT.md",
            _failure_report(revision_count, feedback, files, plan),
        )
        error = f"Osiągnięto limit {MAX_REVISIONS} prób poprawek."
        print("→ Zapisano FAILURE_REPORT.md")
        return {
            "next_node": "end",
            "feedback": f"REJECT: {error}",
            "current_files": files,
            "last_error": error,
            "error_stage": "quality",
            "retry_feedback": str(feedback) if feedback else None,
        }

    if not plan:
        print("📋 MANAGER: Brak planu → Wysyłam do Plannera")
        return {"next_node": "planner"}

    if not plan_approved:
        if feedback:
            print("🔄 MANAGER: Plan wymaga poprawek → Planner")
            return {"next_node": "planner"}
        print("⏸️ MANAGER: Czekam na zatwierdzenie planu przez użytkownika")
        return {"next_node": "end"}

    if feedback and decision is None:
        # Quality feedback must always carry a leading decision. Treat any
        # malformed value as rejection, never as implicit approval.
        print("⚠️ MANAGER: Niejednoznaczna recenzja → Coder")
        return {
            "next_node": "coder",
            "feedback": "REJECT: Recenzent nie zwrócił jednoznacznej decyzji.",
        }

    # Immediately after the user approves a plan there is no review feedback
    # yet. This applies both to a greenfield project and to changes in an
    # existing workspace.
    if not feedback:
        print("💻 MANAGER: Plan zatwierdzony → Coder rozpoczyna pracę")
        return {"next_node": "coder"}

    if not files:
        if decision == "APPROVE":
            feedback = "REJECT: Recenzja zatwierdziła projekt, ale brak plików."
        print("💻 MANAGER: Plan zatwierdzony → Coder rozpoczyna pracę")
        result = {"next_node": "coder"}
        if feedback:
            result["feedback"] = feedback
        return result

    if decision == "REJECT":
        print(
            "⚠️ MANAGER: Błędy wykryte. Zarządzam poprawkę "
            f"(Próba {revision_count + 1}/{MAX_REVISIONS})."
        )
        return {"next_node": "coder"}

    print("🏁 MANAGER: Nie ma więcej akcji → END")
    return {"next_node": "end"}
