from pathlib import Path

from langchain_core.messages import AIMessage
from streamlit.testing.v1 import AppTest

from agents import coder, planner, reviewer
from tools import llm_factory
from tools.chat_store import ChatStore, ChatStoreError

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_app_starts_without_ollama(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODEFABRIC_DATA_DIR", str(tmp_path / "chats"))
    monkeypatch.setattr(
        llm_factory,
        "get_ollama_status",
        lambda timeout=2.0: llm_factory.OllamaStatus(
            available=False, error="offline in smoke test"
        ),
    )
    monkeypatch.chdir(tmp_path)

    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()

    assert not app.exception
    assert app.title[0].value == "CodeFabric AI"
    assert len(app.chat_input) == 1
    assert app.chat_input[0].disabled is False
    assert (tmp_path / "chats").is_dir()


class _FakePlanner:
    def invoke(self, _messages):
        return AIMessage(
            content=(
                "- demo/main.py: Punkt wejścia aplikacji\n- demo/README.md: Instrukcja uruchomienia"
            )
        )


class _FakeCoder:
    def __init__(self):
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        return AIMessage(
            content=(
                "### FILE: demo/main.py\n"
                "print('CodeFabric smoke test')\n"
                "### ENDFILE\n\n"
                "### FILE: demo/README.md\n"
                "# Demo\n\nUruchom: `python main.py`.\n"
                "### ENDFILE"
            )
        )


class _FakeReviewer:
    def invoke(self, _messages):
        return AIMessage(content="APPROVE: Pliki są kompletne i zgodne z planem.")


def test_streamlit_happy_path_without_real_ollama(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODEFABRIC_DATA_DIR", str(tmp_path / "chats"))
    monkeypatch.setattr(
        llm_factory,
        "get_ollama_status",
        lambda timeout=2.0: llm_factory.OllamaStatus(available=True, models=("test-model",)),
    )
    monkeypatch.setattr(planner, "get_llm", lambda *_args, **_kwargs: _FakePlanner())
    fake_coder = _FakeCoder()
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake_coder)
    monkeypatch.setattr(reviewer, "get_llm", lambda *_args, **_kwargs: _FakeReviewer())

    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=20).run()
    app.chat_input[0].set_value("Stwórz minimalną aplikację demonstracyjną")
    app = app.run()

    approve = next(
        button for button in app.button if button.label == "✅ Zatwierdź i rozpocznij kodowanie"
    )
    approve.click()
    app = app.run()

    assert not app.exception
    assert app.chat_input[0].disabled is False
    generated = list((tmp_path / "chats").glob("*/workspace/demo/main.py"))
    assert len(generated) == 1
    assert "CodeFabric smoke test" in generated[0].read_text(encoding="utf-8")
    assert any("Projekt przeszedł pełny przepływ" in markdown.value for markdown in app.markdown)

    # Changes to an existing workspace must also pause for human approval.
    app.chat_input[0].set_value("Dodaj komentarz do punktu wejścia")
    app = app.run()
    assert any(button.label == "✅ Zatwierdź i rozpocznij kodowanie" for button in app.button)
    assert next(button for button in app.button if button.label == "➕ Nowy projekt").disabled

    next(
        button for button in app.button if button.label == "✅ Zatwierdź i rozpocznij kodowanie"
    ).click()
    app = app.run()
    assert fake_coder.calls == 2
    assert app.chat_input[0].disabled is False

    # A third plan can be cancelled without mutating the workspace.
    app.chat_input[0].set_value("Zmień nazwę funkcji")
    app = app.run()
    next(button for button in app.button if button.label == "Anuluj").click()
    app = app.run()
    assert app.chat_input[0].disabled is False
    assert not next(button for button in app.button if button.label == "➕ Nowy projekt").disabled


class _RecoveringCoder:
    def __init__(self):
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if len(self.calls) == 2:
            raise ConnectionError("temporary coder outage")
        return AIMessage(
            content=(f"### FILE: main.py\nprint('implementation {len(self.calls)}')\n### ENDFILE")
        )


class _RejectThenApproveReviewer:
    def __init__(self):
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(content="REJECT: dodaj walidację wejścia XYZ")
        return AIMessage(content="APPROVE: poprawka została wykonana")


def test_retry_after_coder_outage_preserves_review_feedback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODEFABRIC_DATA_DIR", str(tmp_path / "chats"))
    monkeypatch.setattr(
        llm_factory,
        "get_ollama_status",
        lambda timeout=2.0: llm_factory.OllamaStatus(available=True, models=("test-model",)),
    )
    monkeypatch.setattr(planner, "get_llm", lambda *_args, **_kwargs: _FakePlanner())
    fake_coder = _RecoveringCoder()
    fake_reviewer = _RejectThenApproveReviewer()
    monkeypatch.setattr(coder, "get_llm", lambda *_args, **_kwargs: fake_coder)
    monkeypatch.setattr(reviewer, "get_llm", lambda *_args, **_kwargs: fake_reviewer)

    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=20).run()
    app.chat_input[0].set_value("Zbuduj aplikację z walidacją")
    app = app.run()
    next(
        button for button in app.button if button.label == "✅ Zatwierdź i rozpocznij kodowanie"
    ).click()
    app = app.run()

    assert not app.exception
    assert len(fake_coder.calls) == 2
    next(button for button in app.button if button.label == "🔄 Spróbuj ponownie").click()
    app = app.run()

    assert not app.exception
    assert len(fake_coder.calls) == 3
    retry_prompt = "\n".join(message.content for message in fake_coder.calls[2])
    assert "TRYB NAPRAWY" in retry_prompt
    assert "dodaj walidację wejścia XYZ" in retry_prompt
    assert any("Projekt przeszedł pełny przepływ" in item.value for item in app.markdown)


def test_project_switch_is_cancelled_when_current_history_cannot_be_saved(
    tmp_path: Path, monkeypatch
) -> None:
    data_dir = tmp_path / "chats"
    store = ChatStore(data_dir)
    first_id = store.create()
    store.save_messages(first_id, [], name="Projekt pierwszy")
    second_id = store.create()
    store.save_messages(second_id, [], name="Projekt drugi")
    monkeypatch.setenv("CODEFABRIC_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        llm_factory,
        "get_ollama_status",
        lambda timeout=2.0: llm_factory.OllamaStatus(available=False, error="offline"),
    )

    def fail_save(_self, _chat_id, _messages, *, name=None):
        raise ChatStoreError("dysk tylko do odczytu")

    monkeypatch.setattr(ChatStore, "save_messages", fail_save)

    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()
    next(button for button in app.button if button.label == "○ Projekt pierwszy").click()
    app = app.run()

    assert not app.exception
    assert any("Nie udało się zapisać" in error.value for error in app.error)
    assert any(button.label == "▶ Projekt drugi" for button in app.button)


def test_every_project_remains_selectable_after_sidebar_button_limit(
    tmp_path: Path, monkeypatch
) -> None:
    data_dir = tmp_path / "chats"
    store = ChatStore(data_dir)
    oldest_id = None
    for index in range(13):
        chat_id = store.create()
        store.save_messages(chat_id, [], name=f"Projekt {index:02d}")
        oldest_id = oldest_id or chat_id

    monkeypatch.setenv("CODEFABRIC_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        llm_factory,
        "get_ollama_status",
        lambda timeout=2.0: llm_factory.OllamaStatus(available=False, error="offline"),
    )

    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()
    selector = next(
        selectbox for selectbox in app.selectbox if selectbox.label == "Pozostałe projekty"
    )

    assert "Projekt 00" in selector.options
    selector.set_value(oldest_id)
    app = app.run()
    next(button for button in app.button if button.label == "Otwórz wybrany projekt").click()
    app = app.run()

    assert not app.exception
    assert app.session_state["active_chat_id"] == oldest_id


def test_sidebar_survives_backup_listing_error(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "chats"
    ChatStore(data_dir).create()
    monkeypatch.setenv("CODEFABRIC_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        llm_factory,
        "get_ollama_status",
        lambda timeout=2.0: llm_factory.OllamaStatus(available=False, error="offline"),
    )
    monkeypatch.setattr(
        ChatStore,
        "list_backups",
        lambda _self, _chat_id: (_ for _ in ()).throw(ChatStoreError("brak dostępu")),
    )

    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=15).run()

    assert not app.exception
    assert any("brak dostępu" in error.value for error in app.error)
