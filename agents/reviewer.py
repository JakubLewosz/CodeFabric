from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from state import AgentState
from tools.file_ops import get_all_file_paths, read_file, write_file
from tools.llm_factory import get_llm


def _truncate(content: str, max_length: int = 6000) -> str:
    if len(content) <= max_length:
        return content

    half = max_length // 2
    omitted = len(content) - max_length
    return (
        content[:half]
        + f"\n\n# ... [POMINIĘTO {omitted} ZNAKÓW] ...\n\n"
        + content[-half:]
    )


def _build_review_context(files: list[str]) -> str:
    context_parts = []
    for path in files:
        if not path.endswith((".py", ".js", ".html", ".css", ".json", ".md", ".txt", ".jsx", ".tsx")):
            continue

        content = read_file(path)
        if content:
            context_parts.append(
                f"=== PLIK: {path} ===\n{_truncate(content)}\n===================="
            )

    return "\n\n".join(context_parts) if context_parts else "Brak plików do recenzji."


def reviewer_node(state: AgentState):
    chat_workspace = state.get("chat_workspace")
    if chat_workspace:
        import tools.file_ops as file_ops_module

        file_ops_module.WORKSPACE_DIR = chat_workspace

    files = state.get("current_files") or get_all_file_paths()
    plan = state.get("plan") or "Brak planu."
    model_name = state.get("model_names", {}).get("reviewer") or state.get(
        "model_names", {}
    ).get("chat", "bielik2.6:11b")

    review_context = _build_review_context(files)
    llm = get_llm(model_name, temperature=0.0, num_ctx=16384)

    system_message = SystemMessage(
        content="""
Jesteś recenzentem kodu w projekcie generowanym przez AI.

Odpowiedz w jednym z formatów:

APPROVE: krótki opis, dlaczego wynik można zaakceptować
REJECT: konkretna lista problemów do poprawy

Oceniaj praktycznie: czy pliki istnieją, czy odpowiadają planowi, czy nie ma oczywistych braków integracji.
Nie wymagaj perfekcji produkcyjnej od prototypu, ale odrzuć wynik, jeśli brakuje kluczowych elementów.
"""
    )
    user_message = HumanMessage(
        content=f"""
PLAN:
{plan}

PLIKI DO RECENZJI:
{review_context}
"""
    )

    try:
        response = llm.invoke([system_message, user_message])
        review = response.content.strip()
    except Exception as exc:
        review = (
            "APPROVE: Nie udało się wykonać recenzji LLM, ale pliki zostały "
            f"wygenerowane. Błąd recenzenta: {exc}"
        )

    if not review.upper().startswith(("APPROVE", "REJECT")):
        review = "REJECT: Recenzent nie zwrócił jednoznacznej decyzji.\n\n" + review

    write_file("review_report.md", review)

    return {
        "feedback": review,
        "messages": [AIMessage(content=f"Recenzja: {review}")],
        "current_files": files,
    }
