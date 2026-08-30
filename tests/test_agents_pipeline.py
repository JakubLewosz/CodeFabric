from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from agents import coder, planner, reviewer
from agents.common import review_decision
from agents.manager import manager_node
from agents.workspace import WorkspaceFiles, WorkspaceListError
from graph import workflow as workflow_module
from graph.workflow import route_manager
from state import AgentState
from tools import file_ops
from tools.text_files import is_text_file


class FakeLLM:
    def __init__(self, content: Any = None, error: Exception = None):
        self.content = content
        self.error = error
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return AIMessage(content=self.content)


@pytest.mark.parametrize(
    ("feedback", "expected"),
    [
        ("APPROVE: gotowe", "APPROVE"),
        ("  **REJECT**: błąd", "REJECT"),
        ("Nie APPROVE tego projektu", None),
        ("APPROVED", None),
        ("Opis zawiera REJECT", None),
    ],
)
def test_review_decision_requires_a_leading_standalone_marker(feedback: str, expected: str) -> None:
    assert review_decision(feedback) == expected


def test_manager_never_approves_from_a_substring(tmp_path: Path) -> None:
    state = {
        "plan": "Plan",
        "plan_approved": True,
        "current_files": ["main.py"],
        "revision_count": 0,
        "feedback": "REJECT: opis problemu wspomina słowo APPROVE",
        "chat_workspace": str(tmp_path),
    }

    result = manager_node(state)

    assert result["next_node"] == "coder"

    state["feedback"] = "To nie jest decyzja APPROVE"
    result = manager_node(state)
    assert result["next_node"] == "coder"
    assert result["feedback"].startswith("REJECT:")
    assert "APPROVE" not in result["feedback"]


def test_manager_requires_plan_approval_even_for_an_existing_project(
    tmp_path: Path,
) -> None:
    result = manager_node(
        {
            "plan": "Bezpieczny plan zmian",
            "plan_approved": False,
            "current_files": ["main.py"],
            "revision_count": 0,
            "feedback": None,
            "chat_workspace": str(tmp_path),
        }
    )

    assert result == {"next_node": "end"}


def test_manager_routes_approved_existing_project_to_coder(tmp_path: Path) -> None:
    result = manager_node(
        {
            "plan": "Bezpieczny plan zmian",
            "plan_approved": True,
            "current_files": ["main.py"],
            "revision_count": 0,
            "feedback": None,
            "chat_workspace": str(tmp_path),
        }
    )

    assert result == {"next_node": "coder"}


def test_manager_stops_after_planner_error_and_allows_explicit_retry(
    tmp_path: Path,
) -> None:
    failed = {
        "plan": None,
        "current_files": [],
        "last_error": "Ollama offline",
        "feedback": None,
        "next_node": "planner",
        "chat_workspace": str(tmp_path),
    }
    result = manager_node(failed)
    assert result["next_node"] == "end"
    assert result["feedback"].startswith("REJECT:")

    failed["next_node"] = "manager"
    retry = manager_node(failed)
    assert retry == {
        "next_node": "planner",
        "feedback": None,
        "last_error": None,
        "error_stage": None,
    }


def test_manager_stops_on_reviewer_failure_and_retries_only_review(tmp_path: Path) -> None:
    failed = {
        "plan": "Plan",
        "plan_approved": True,
        "current_files": ["main.py"],
        "feedback": "REJECT: Błąd recenzenta LLM: offline",
        "last_error": "Błąd recenzenta LLM: offline",
        "error_stage": "reviewer",
        "chat_workspace": str(tmp_path),
    }

    stopped = manager_node(failed)
    assert stopped["next_node"] == "end"
    assert stopped["error_stage"] == "reviewer"

    failed["retry_stage"] = "reviewer"
    retried = manager_node(failed)
    assert retried == {
        "next_node": "reviewer",
        "feedback": None,
        "last_error": None,
        "error_stage": None,
        "retry_stage": None,
        "retry_feedback": None,
    }


def test_manager_retries_coder_error_without_synthetic_quality_rejection(
    tmp_path: Path,
) -> None:
    result = manager_node(
        {
            "plan": "Plan",
            "plan_approved": True,
            "last_error": "BŁĄD LLM: offline",
            "error_stage": "coder",
            "retry_stage": "coder",
            "revision_count": 0,
            "chat_workspace": str(tmp_path),
        }
    )

    assert result == {
        "next_node": "coder",
        "feedback": None,
        "last_error": None,
        "error_stage": None,
        "retry_stage": None,
        "retry_feedback": None,
    }


def test_coder_error_preserves_review_feedback_without_spending_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "main.py").write_text("print('before')\n", encoding="utf-8")
    feedback = "REJECT: dodaj walidację wejścia XYZ"
    fake = FakeLLM(error=ConnectionError("offline"))
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    failed = coder.coder_node(
        {
            "plan": "Popraw aplikację",
            "plan_approved": True,
            "feedback": feedback,
            "revision_count": 2,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert failed["error_stage"] == "coder"
    assert failed["revision_count"] == 2
    assert failed["feedback"] is None
    assert failed["retry_feedback"] == feedback

    retried = manager_node(
        {
            **failed,
            "plan": "Popraw aplikację",
            "plan_approved": True,
            "retry_stage": "coder_quality",
            "chat_workspace": str(tmp_path),
        }
    )
    assert retried["next_node"] == "coder"
    assert retried["feedback"] == feedback
    assert retried["last_error"] is None


def test_revision_limit_is_exact_and_report_uses_explicit_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unrelated = tmp_path / "unrelated"
    target = tmp_path / "chat" / "workspace"
    monkeypatch.setattr(file_ops, "WORKSPACE_DIR", str(unrelated))

    result = manager_node(
        {
            "plan": "Plan",
            "plan_approved": True,
            "current_files": ["main.py"],
            "revision_count": 3,
            "feedback": "REJECT: nadal źle; nie używaj APPROVE",
            "chat_workspace": str(target),
        }
    )

    assert result["next_node"] == "end"
    assert result["feedback"] == "REJECT: Osiągnięto limit 3 prób poprawek."
    assert result["error_stage"] == "quality"
    assert result["retry_feedback"] == "REJECT: nadal źle; nie używaj APPROVE"
    assert (target / "FAILURE_REPORT.md").is_file()
    assert not (unrelated / "FAILURE_REPORT.md").exists()

    retry = manager_node(
        {
            "plan": "Plan",
            "plan_approved": True,
            "revision_count": 0,
            "last_error": result["last_error"],
            "error_stage": "quality",
            "retry_stage": "coder_quality",
            "retry_feedback": result["retry_feedback"],
            "chat_workspace": str(target),
        }
    )
    assert retry["next_node"] == "coder"
    assert retry["feedback"] == "REJECT: nadal źle; nie używaj APPROVE"
    assert retry["last_error"] is None


def test_router_has_a_safe_deterministic_fallback() -> None:
    assert route_manager({}) == "end"
    assert route_manager({"next_node": " CODER "}) == "coder"
    assert route_manager({"next_node": "reviewer"}) == "reviewer"
    assert route_manager({"next_node": object()}) == "end"


def test_agent_state_message_reducer_accumulates_langchain_messages() -> None:
    workflow = StateGraph(AgentState)
    workflow.add_node("reply", lambda _state: {"messages": [AIMessage(content="odpowiedź")]})
    workflow.set_entry_point("reply")
    workflow.add_edge("reply", END)

    result = workflow.compile().invoke({"messages": [HumanMessage(content="pytanie")]})

    assert [type(message) for message in result["messages"]] == [
        HumanMessage,
        AIMessage,
    ]
    assert [message.content for message in result["messages"]] == [
        "pytanie",
        "odpowiedź",
    ]


def test_graph_pauses_for_plan_approval_then_completes_without_ollama(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = WorkspaceFiles(str(tmp_path))

    def fake_planner(_state):
        return {
            "plan": "- main.py: utwórz program",
            "messages": [AIMessage(content="Plan gotowy")],
            "feedback": None,
            "last_error": None,
        }

    def fake_coder(state):
        assert state["plan_approved"] is True
        assert workspace.write("main.py", "print('ok')\n")
        return {
            "current_files": workspace.list(),
            "messages": [AIMessage(content="Kod gotowy")],
            "revision_count": 0,
            "feedback": None,
            "last_error": None,
        }

    def fake_reviewer(_state):
        return {
            "feedback": "APPROVE: testowa recenzja",
            "messages": [AIMessage(content="Recenzja gotowa")],
            "current_files": workspace.list(),
            "last_error": None,
        }

    monkeypatch.setattr(workflow_module, "planner_node", fake_planner)
    monkeypatch.setattr(workflow_module, "coder_node", fake_coder)
    monkeypatch.setattr(workflow_module, "reviewer_node", fake_reviewer)
    graph = workflow_module.create_graph()

    state = graph.invoke(
        {
            "messages": [HumanMessage(content="Zbuduj program")],
            "current_files": [],
            "plan": None,
            "plan_approved": False,
            "feedback": None,
            "revision_count": 0,
            "next_node": "manager",
            "model_names": {},
            "chat_workspace": str(tmp_path),
            "last_error": None,
        }
    )
    assert state["next_node"] == "end"
    assert state["plan"] == "- main.py: utwórz program"
    assert state["plan_approved"] is False

    state.update({"plan_approved": True, "next_node": "manager"})
    completed = graph.invoke(state)

    assert completed["next_node"] == "end"
    assert completed["plan"] is None
    assert completed["feedback"] is None
    assert completed["revision_count"] == 0
    assert len(completed["messages"]) == 4


def test_planner_failure_is_a_real_message_and_not_an_approvable_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeLLM(error=ConnectionError("offline"))
    monkeypatch.setattr(planner, "get_llm", lambda *_args, **_kwargs: fake)

    result = planner.planner_node(
        {
            "messages": [{"role": "user", "content": "Zbuduj API"}],
            "current_files": [],
            "model_names": {},
        }
    )

    assert result["plan"] is None
    assert result["last_error"].startswith("Błąd podczas planowania:")
    assert isinstance(result["messages"][0], AIMessage)


def test_new_project_plan_revision_includes_user_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeLLM("- app.py: poprawiony plan")
    monkeypatch.setattr(planner, "get_llm", lambda *_args, **_kwargs: fake)

    planner.planner_node(
        {
            "messages": [HumanMessage(content="Zbuduj aplikację")],
            "current_files": [],
            "feedback": "Dodaj testy jednostkowe i CLI",
            "model_names": {},
        }
    )

    sent_text = "\n".join(message.content for message in fake.calls[0])
    assert "Dodaj testy jednostkowe i CLI" in sent_text


def test_planner_bounds_large_file_lists_before_calling_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeLLM("- app.py: plan")
    monkeypatch.setattr(planner, "get_llm", lambda *_args, **_kwargs: fake)
    paths = [f"very/long/module_{index:05d}_with_description.py" for index in range(5000)]

    planner.planner_node(
        {
            "messages": [HumanMessage(content="Zmień projekt")],
            "current_files": paths,
            "model_names": {},
        }
    )

    prompt = "\n".join(message.content for message in fake.calls[0])
    assert "pominięto" in prompt
    assert len(prompt) < 25_000


def test_reviewer_fails_closed_when_llm_is_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    fake = FakeLLM(error=ConnectionError("offline"))
    monkeypatch.setattr(reviewer, "get_llm", lambda *_args, **_kwargs: fake)

    result = reviewer.reviewer_node(
        {
            "plan": "Uruchamialny plik main.py",
            "current_files": ["main.py"],
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert result["feedback"].startswith("REJECT:")
    assert "APPROVE" not in result["feedback"]
    assert "offline" in result["last_error"]
    assert (tmp_path / "review_report.md").is_file()


def test_reviewer_rejects_malformed_model_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    fake = FakeLLM("Kod wygląda dobrze i chyba można go APPROVE")
    monkeypatch.setattr(reviewer, "get_llm", lambda *_args, **_kwargs: fake)

    result = reviewer.reviewer_node(
        {
            "plan": "Uruchamialny plik main.py",
            "current_files": ["main.py"],
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert result["feedback"] == ("REJECT: Recenzent nie zwrócił jednoznacznej decyzji.")


def test_reviewer_reads_typescript_and_rejects_binary_only_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = "TYPESCRIPT_CONTEXT_MARKER"
    (tmp_path / "app.ts").write_text(f"export const marker = '{marker}';\n", encoding="utf-8")
    fake = FakeLLM("APPROVE: TypeScript jest zgodny z planem.")
    monkeypatch.setattr(reviewer, "get_llm", lambda *_args, **_kwargs: fake)

    result = reviewer.reviewer_node(
        {"plan": "Sprawdź TypeScript", "chat_workspace": str(tmp_path), "model_names": {}}
    )

    assert result["last_error"] is None
    assert marker in "\n".join(message.content for message in fake.calls[0])

    (tmp_path / "review_report.md").write_text(
        "REJECT: stary błąd infrastruktury", encoding="utf-8"
    )
    reviewer.reviewer_node(
        {"plan": "Ponów review", "chat_workspace": str(tmp_path), "model_names": {}}
    )
    retry_prompt = "\n".join(message.content for message in fake.calls[-1])
    assert "stary błąd infrastruktury" not in retry_prompt

    (tmp_path / "app.ts").unlink()
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(
        reviewer,
        "get_llm",
        lambda *_args, **_kwargs: pytest.fail("binary-only workspace must not call the LLM"),
    )
    rejected = reviewer.reviewer_node(
        {"plan": "Sprawdź projekt", "chat_workspace": str(tmp_path), "model_names": {}}
    )
    assert rejected["feedback"].startswith("REJECT:")
    assert rejected["error_stage"] == "coder"


def test_agent_context_never_contains_streamlit_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "app.py").write_text("print('visible marker')\n", encoding="utf-8")
    secrets_path = tmp_path / ".streamlit" / "secrets.toml"
    secrets_path.parent.mkdir()
    secrets_path.write_text('api_key = "SUPER_SECRET_TOKEN"\n', encoding="utf-8")
    oauth_token = tmp_path / "token.json"
    oauth_token.write_text('{"refresh_token":"OAUTH_REFRESH_SECRET"}\n', encoding="utf-8")
    fake = FakeLLM("### FILE: note.txt\nupdated project safely\n### ENDFILE")
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    coder.coder_node(
        {
            "plan": "Dodaj notatkę",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    prompt = "\n".join(message.content for message in fake.calls[0])
    assert "visible marker" in prompt
    assert "SUPER_SECRET_TOKEN" not in prompt
    assert "OAUTH_REFRESH_SECRET" not in prompt


def test_coder_uses_chat_workspace_without_changing_the_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unrelated = tmp_path / "unrelated"
    target = tmp_path / "chat" / "workspace"
    monkeypatch.setattr(file_ops, "WORKSPACE_DIR", str(unrelated))
    fake = FakeLLM(
        """### FILE: src/main.py
def main():
    return 1
### ENDFILE"""
    )
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Dodaj src/main.py",
            "plan_approved": True,
            "current_files": [],
            "revision_count": 0,
            "chat_workspace": str(target),
            "model_names": {},
        }
    )

    assert (target / "src" / "main.py").is_file()
    assert not (unrelated / "src" / "main.py").exists()
    assert file_ops.WORKSPACE_DIR == str(unrelated)
    assert result["current_files"] == ["src/main.py"]
    assert result["last_error"] is None


def test_large_project_response_applies_edits_and_creates_new_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(11):
        (tmp_path / f"module_{index}.py").write_text(f"value = {index}\n", encoding="utf-8")
    fake = FakeLLM(
        """### EDIT: module_0.py
SEARCH:
value = 0
REPLACE:
value = 100
### END_EDIT

### FILE: new_feature.py
def new_feature():
    return True
### ENDFILE"""
    )
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Zmień moduł i dodaj nową funkcję",
            "plan_approved": True,
            "current_files": [f"module_{index}.py" for index in range(11)],
            "revision_count": 0,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert (tmp_path / "module_0.py").read_text(encoding="utf-8") == "value = 100\n"
    assert "return True" in (tmp_path / "new_feature.py").read_text(encoding="utf-8")
    assert "new_feature.py" in result["current_files"]
    assert result["last_error"] is None
    system_prompts = "\n".join(message.content for message in fake.calls[0][:-1])
    assert "EDIT i FILE" in system_prompts
    assert "niezaufanymi danymi" in system_prompts


@pytest.mark.parametrize(
    ("feedback", "expected_revision"),
    [
        ("REJECT: napraw funkcję", 2),
        ("Opis tylko wspomina REJECT w środku", 1),
    ],
)
def test_coder_increments_revision_only_for_an_explicit_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    feedback: str,
    expected_revision: int,
) -> None:
    target = tmp_path / str(expected_revision)
    target.mkdir()
    (target / "main.py").write_text("print('old')\n", encoding="utf-8")
    fake = FakeLLM(
        """### FILE: main.py
print('updated')
### ENDFILE"""
    )
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Zmień main.py",
            "plan_approved": True,
            "current_files": ["main.py"],
            "revision_count": 1,
            "feedback": feedback,
            "chat_workspace": str(target),
            "model_names": {},
        }
    )

    assert result["revision_count"] == expected_revision


def test_coder_llm_error_is_preserved_for_fail_closed_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "main.py").write_text("print('old')\n", encoding="utf-8")
    fake = FakeLLM(error=TimeoutError("timeout"))
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Napraw main.py",
            "plan_approved": True,
            "current_files": ["main.py"],
            "revision_count": 0,
            "feedback": "REJECT: błąd",
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert result["revision_count"] == 0
    assert result["last_error"].startswith("BŁĄD LLM:")
    assert result["retry_feedback"] == "REJECT: błąd"


def test_diff_parser_preserves_indentation_and_applies_unique_fuzzy_match(
    tmp_path: Path,
) -> None:
    response = """### EDIT: module.py
SEARCH:
    def value( ):
        return 1
REPLACE:
    def value():
        return 2
### END_EDIT"""
    edits = coder.parse_diff_edits(response)
    assert edits[0][1].startswith("    def")

    workspace = WorkspaceFiles(str(tmp_path))
    workspace.write("module.py", "class Example:\n\tdef value( ):\n\t\treturn 1\n")
    assert coder.apply_diff_edits(edits, workspace) == ["module.py"]
    assert "return 2" in workspace.read("module.py")


def test_full_file_parser_rejects_workspace_escape(tmp_path: Path) -> None:
    workspace = WorkspaceFiles(str(tmp_path / "workspace"))
    created = coder.parse_and_save_files(
        """### FILE: ../escape.py
print('outside')
### ENDFILE""",
        workspace,
    )

    assert created == []
    assert not (tmp_path / "escape.py").exists()


def test_coder_reports_partial_file_failures_instead_of_claiming_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLLM(
        """### FILE: good.py
print('valid file')
### ENDFILE

### FILE: ../escaped.py
print('must not escape')
### ENDFILE"""
    )
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Dodaj dwa pliki",
            "plan_approved": True,
            "chat_workspace": str(tmp_path / "workspace"),
            "model_names": {},
        }
    )

    assert (tmp_path / "workspace" / "good.py").is_file()
    assert not (tmp_path / "escaped.py").exists()
    assert "../escaped.py" in result["last_error"]
    assert result["error_stage"] == "coder"


def test_coder_reports_unclosed_file_block_beside_a_valid_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLLM(
        """### FILE: main.py
print('valid file')
### ENDFILE

### FILE: README.md
# Missing closing marker"""
    )
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Dodaj aplikację i dokumentację",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert (tmp_path / "main.py").is_file()
    assert not (tmp_path / "README.md").exists()
    assert "niekompletny" in result["last_error"]


def test_coder_can_retry_greenfield_after_a_no_files_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLLM("### FILE: main.py\nprint('retry works')\n### ENDFILE")
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Utwórz aplikację",
            "plan_approved": True,
            "feedback": "REJECT: Poprzednia próba nie utworzyła plików.",
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert result["last_error"] is None
    assert (tmp_path / "main.py").is_file()


def test_coder_loads_complete_moderate_file_before_full_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = "MIDDLE_OF_EXISTING_FILE_MUST_BE_VISIBLE"
    lines = [f"value_{index} = {index}" for index in range(203)]
    lines[101] = f"marker = '{marker}'"
    (tmp_path / "app.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    fake = FakeLLM("### FILE: app.py\nprint('updated safely')\n### ENDFILE")
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Zmień aplikację",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    prompt = "\n".join(message.content for message in fake.calls[0])
    assert marker in prompt
    assert "POMINIĘTO" not in prompt
    assert result["last_error"] is None


def test_coder_forces_diff_and_rejects_full_overwrite_for_large_minified_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = "const payload = '" + ("x" * 70_000) + "';\n"
    (tmp_path / "app.ts").write_text(original, encoding="utf-8")
    fake = FakeLLM("### FILE: app.ts\nconsole.log('destructive rewrite');\n### ENDFILE")
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Zmień TypeScript",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert (tmp_path / "app.ts").read_text(encoding="utf-8") == original
    assert "trybie DIFF" in result["last_error"]
    assert "DIFF EDITING" in "\n".join(message.content for message in fake.calls[0])


def test_diff_mode_existing_file_protection_is_case_insensitive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "main.py").write_text("print('original')\n", encoding="utf-8")
    for index in range(10):
        (tmp_path / f"module_{index}.py").write_text(f"value = {index}\n", encoding="utf-8")
    fake = FakeLLM("### FILE: MAIN.py\nprint('destructive rewrite')\n### ENDFILE")
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Zmień projekt",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert (tmp_path / "main.py").read_text(encoding="utf-8") == "print('original')\n"
    assert "pełne nadpisanie" in result["last_error"]


def test_coder_reports_unclosed_edit_beside_a_valid_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(11):
        (tmp_path / f"module_{index}.py").write_text(f"value = {index}\n", encoding="utf-8")
    fake = FakeLLM(
        """### EDIT: module_0.py
SEARCH:
value = 0
REPLACE:
value = 100
### END_EDIT

### EDIT: module_1.py
SEARCH:
value = 1
REPLACE:
value = 101"""
    )
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Zmień dwa moduły",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert (tmp_path / "module_0.py").read_text(encoding="utf-8") == "value = 100\n"
    assert (tmp_path / "module_1.py").read_text(encoding="utf-8") == "value = 1\n"
    assert "niekompletny" in result["last_error"]


def test_coder_fails_closed_on_invalid_utf8_before_calling_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = b"ORIGINAL\xffDATA"
    (tmp_path / "main.py").write_bytes(original)
    monkeypatch.setattr(
        coder,
        "get_llm",
        lambda *_args, **_kwargs: pytest.fail("unreadable source must stop before the LLM"),
    )

    result = coder.coder_node(
        {
            "plan": "Zmień main.py",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert result["last_error"].startswith("BŁĄD ODCZYTU PLIKU main.py")
    assert result["error_stage"] == "coder"
    assert (tmp_path / "main.py").read_bytes() == original
    assert file_ops.read_file("main.py", workspace_dir=tmp_path).startswith(
        "Error reading file: invalid UTF-8"
    )


def test_strict_workspace_read_does_not_confuse_legal_content_with_an_error(
    tmp_path: Path,
) -> None:
    content = "Error reading file: this is a legitimate troubleshooting section"
    (tmp_path / "README.md").write_text(content, encoding="utf-8")

    assert WorkspaceFiles(str(tmp_path)).read_strict("README.md") == content


def test_coder_fails_closed_when_workspace_listing_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "main.py"
    source.write_text("ORIGINAL\n", encoding="utf-8")
    fake = FakeLLM("### FILE: main.py\nOVERWRITTEN\n### ENDFILE")
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)
    monkeypatch.setattr(
        WorkspaceFiles,
        "list",
        lambda _self: (_ for _ in ()).throw(WorkspaceListError("permission denied")),
    )

    result = coder.coder_node(
        {
            "plan": "Zmień aplikację",
            "plan_approved": True,
            "current_files": ["main.py"],
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert result["error_stage"] == "coder"
    assert "LISTOWANIA" in result["last_error"]
    assert fake.calls == []
    assert source.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_file_parser_allows_valid_empty_and_short_text_files(tmp_path: Path) -> None:
    workspace = WorkspaceFiles(str(tmp_path))

    created = coder.parse_and_save_files(
        """### FILE: package/__init__.py

### ENDFILE

### FILE: config.json
{}
### ENDFILE""",
        workspace,
    )

    assert created == ["package/__init__.py", "config.json"]
    assert (tmp_path / "package" / "__init__.py").read_text(encoding="utf-8") == ""
    assert (tmp_path / "config.json").read_text(encoding="utf-8") == "{}"


def test_diff_mode_can_populate_a_confirmed_empty_text_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_path = tmp_path / "package" / "__init__.py"
    empty_path.parent.mkdir()
    empty_path.write_text("", encoding="utf-8")
    for index in range(10):
        (tmp_path / f"module_{index}.py").write_text(f"value = {index}\n", encoding="utf-8")
    fake = FakeLLM("### FILE: package/__init__.py\nfrom .core import Application\n### ENDFILE")
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Dodaj eksport pakietu",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert result["last_error"] is None
    assert empty_path.read_text(encoding="utf-8") == "from .core import Application"


def test_empty_alias_never_unprotects_a_nonempty_case_variant() -> None:
    protected = coder._protected_existing_keys(
        ["main.py", "MAIN.py"],
        {"main.py": "print('nonempty')\n", "MAIN.py": ""},
    )

    assert protected == {"main.py"}


def test_coder_never_overwrites_sensitive_or_binary_files_from_file_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = tmp_path / ".env"
    binary = tmp_path / "logo.png"
    secret.write_text("API_KEY=REAL_SECRET\n", encoding="utf-8")
    binary.write_bytes(b"\x89PNG\r\nORIGINAL")
    (tmp_path / "app.py").write_text("print('app')\n", encoding="utf-8")
    fake = FakeLLM(
        """### FILE: .env
API_KEY=placeholder
### ENDFILE

### FILE: logo.png
not-a-real-png-data
### ENDFILE

### FILE: note.txt
safe project note
### ENDFILE"""
    )
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Dodaj notatkę",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert secret.read_text(encoding="utf-8") == "API_KEY=REAL_SECRET\n"
    assert binary.read_bytes() == b"\x89PNG\r\nORIGINAL"
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "safe project note"
    assert "plik wrażliwy" in result["last_error"]
    assert "nieobsługiwany typ" in result["last_error"]


def test_coder_context_budget_counts_headers_for_many_empty_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(1500):
        (tmp_path / f"module_{index:04d}.py").write_text("", encoding="utf-8")
    fake = FakeLLM("### FILE: note.txt\nbounded context works\n### ENDFILE")
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    coder.coder_node(
        {
            "plan": "Dodaj notatkę",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    prompt = "\n".join(message.content for message in fake.calls[0])
    assert "LIMIT KONTEKSTU" in prompt
    assert len(prompt) < 100_000


@pytest.mark.parametrize(
    "path",
    ["logo.svg", "Dockerfile.dev", "Cargo.lock", "build.gradle", "schema.proto"],
)
def test_common_project_text_formats_are_reviewable(path: str) -> None:
    assert is_text_file(path) is True


def test_diff_edit_never_modifies_sensitive_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = tmp_path / ".env"
    secret.write_text("API_KEY=REAL_SECRET\n", encoding="utf-8")
    for index in range(11):
        (tmp_path / f"module_{index}.py").write_text(f"value = {index}\n", encoding="utf-8")
    fake = FakeLLM(
        """### EDIT: .env
SEARCH:
API_KEY=REAL_SECRET
REPLACE:
API_KEY=placeholder
### END_EDIT"""
    )
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake)

    result = coder.coder_node(
        {
            "plan": "Zmień konfigurację",
            "plan_approved": True,
            "chat_workspace": str(tmp_path),
            "model_names": {},
        }
    )

    assert secret.read_text(encoding="utf-8") == "API_KEY=REAL_SECRET\n"
    assert result["last_error"] is not None


@pytest.mark.parametrize(
    "path",
    ["LICENSE", "NOTICE", "CNAME", "Jenkinsfile", "Vagrantfile", "Justfile"],
)
def test_common_extensionless_project_files_are_reviewable(path: str) -> None:
    assert is_text_file(path) is True
