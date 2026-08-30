"""Streamlit interface for the CodeFabric multi-agent workflow."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import streamlit as st
from langchain_core.messages import HumanMessage

from graph.workflow import app as workflow_app
from tools import file_ops
from tools.chat_store import DEFAULT_PROJECT_NAME, ChatStore, ChatStoreError
from tools.llm_factory import OllamaStatus, get_ollama_status

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
_data_dir = os.getenv("CODEFABRIC_DATA_DIR", "").strip()
_configured_data_dir = Path(_data_dir).expanduser() if _data_dir else Path("chats")
CHATS_DIR = (
    _configured_data_dir if _configured_data_dir.is_absolute() else BASE_DIR / _configured_data_dir
)
CHAT_STORE = ChatStore(CHATS_DIR)

GREETING = (
    "Cześć! Opisz pomysł, a przygotuję plan i przeprowadzę go przez implementację oraz review."
)
INITIAL_MESSAGES = [{"role": "assistant", "content": GREETING}]
DEFAULT_MODELS = [
    model.strip()
    for model in os.getenv(
        "CODEFABRIC_MODELS",
        "qwen2.5-coder:7b",
    ).split(",")
    if model.strip()
]
CODE_LANGUAGES = {
    ".css": "css",
    ".html": "html",
    ".js": "javascript",
    ".json": "json",
    ".jsx": "jsx",
    ".md": "markdown",
    ".py": "python",
    ".sh": "bash",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".yaml": "yaml",
    ".yml": "yaml",
}


st.set_page_config(
    page_title="CodeFabric | AI Software House",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "CodeFabric — lokalny zespół agentów AI do tworzenia oprogramowania"},
)


def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
            .main { background-color: #0e1117; }
            h1 {
                background: -webkit-linear-gradient(45deg, #00d2ff, #7b61ff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 750 !important;
            }
            section[data-testid="stSidebar"] {
                background-color: #161b22;
                border-right: 1px solid #30363d;
            }
            .stButton > button { border-radius: 8px; font-weight: 600; }
            .stChatMessage {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 12px;
                padding: 10px;
                margin-bottom: 10px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def create_project() -> str:
    chat_id = CHAT_STORE.create()
    try:
        CHAT_STORE.save_messages(chat_id, list(INITIAL_MESSAGES))
    except ChatStoreError:
        try:
            CHAT_STORE.delete(chat_id)
        except ChatStoreError:
            LOGGER.exception("Could not clean up a partially initialized project")
        raise
    return chat_id


def load_project(chat_id: str) -> dict[str, Any] | None:
    try:
        return CHAT_STORE.load(chat_id)
    except ChatStoreError as exc:
        LOGGER.warning("Cannot load project %s: %s", chat_id, exc)
        return None


def persist_messages(chat_id: str, *, name: str | None = None) -> None:
    messages = st.session_state.get("messages", INITIAL_MESSAGES)
    CHAT_STORE.save_messages(chat_id, messages, name=name)


def select_project(chat_id: str) -> None:
    st.session_state["active_chat_id"] = chat_id
    st.session_state["current_chat_loaded"] = None
    st.session_state["pipeline_active"] = False
    st.session_state.pop("graph_state", None)
    st.session_state.pop("archive_payload", None)
    st.session_state.pop("archive_chat_id", None)


def set_flash(level: str, message: str) -> None:
    st.session_state["flash_message"] = {"level": level, "message": message}


def render_flash() -> None:
    flash = st.session_state.pop("flash_message", None)
    if not flash:
        return
    renderer = getattr(st, flash.get("level", "info"), st.info)
    renderer(flash.get("message", ""))


def review_decision(feedback: Any) -> str | None:
    if not isinstance(feedback, str):
        return None
    match = re.match(r"^\s*(APPROVE|REJECT)\b", feedback, flags=re.IGNORECASE)
    return match.group(1).upper() if match else None


def merge_graph_update(target: dict[str, Any], update: dict[str, Any]) -> None:
    """Merge LangGraph updates while preserving the message reducer semantics."""
    for key, value in update.items():
        if key == "messages" and value:
            target[key] = [*target.get(key, []), *value]
        else:
            target[key] = value


def workspace_files(chat_id: str) -> list[str]:
    return file_ops.get_all_file_paths(workspace_dir=str(CHAT_STORE.workspace_path(chat_id)))


def safe_archive_name(name: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("._")
    return f"{slug or 'codefabric-project'}.zip"


@st.cache_data(ttl=20, show_spinner=False)
def cached_ollama_status() -> OllamaStatus:
    return get_ollama_status(timeout=1.5)


def preferred_model_index(models: list[str], keywords: tuple[str, ...]) -> int:
    for index, model in enumerate(models):
        if any(keyword in model.lower() for keyword in keywords):
            return index
    return 0


inject_custom_css()

# Make sure the active project still exists (it may have been removed externally).
try:
    projects = CHAT_STORE.list()
except ChatStoreError as exc:
    st.error(f"Nie można odczytać katalogu projektów: {exc}")
    st.stop()
project_ids = {project["id"] for project in projects}
active_chat_id = st.session_state.get("active_chat_id")
if active_chat_id not in project_ids:
    active_chat_id = projects[0]["id"] if projects else create_project()
    st.session_state["active_chat_id"] = active_chat_id
    projects = CHAT_STORE.list()

active_project = load_project(active_chat_id) or {
    "name": DEFAULT_PROJECT_NAME,
    "messages": list(INITIAL_MESSAGES),
}

# Load the selected project's visible state before rendering either panel.
if st.session_state.get("current_chat_loaded") != active_chat_id:
    stored_messages = active_project.get("messages")
    st.session_state["messages"] = (
        stored_messages
        if isinstance(stored_messages, list) and stored_messages
        else list(INITIAL_MESSAGES)
    )
    st.session_state["current_chat_loaded"] = active_chat_id
    st.session_state["pipeline_active"] = False
    st.session_state.pop("graph_state", None)

ollama_status = cached_ollama_status()
available_models = list(ollama_status.models) or list(DEFAULT_MODELS)
if not available_models:
    available_models = ["qwen2.5-coder:7b"]
pipeline_locked = bool(st.session_state.get("pipeline_active"))


with st.sidebar:
    st.markdown("## 🧩 CodeFabric")
    st.caption("Planowanie → kod → automatyczne review")

    if ollama_status.available:
        if ollama_status.models:
            st.success(f"Ollama online · {len(ollama_status.models)} modeli", icon="🟢")
        else:
            st.warning("Ollama działa, ale nie ma zainstalowanych modeli.", icon="🟡")
    else:
        st.warning("Ollama offline — generowanie nie będzie dostępne.", icon="🟠")

    if st.button("Odśwież połączenie", use_container_width=True, key="refresh_ollama"):
        cached_ollama_status.clear()
        st.rerun()

    st.divider()
    st.markdown("#### Projekty")

    if st.button(
        "➕ Nowy projekt",
        use_container_width=True,
        type="primary",
        disabled=pipeline_locked,
    ):
        try:
            persist_messages(active_chat_id)
            new_chat_id = create_project()
        except ChatStoreError as exc:
            st.error(f"Nie udało się zapisać bieżącego projektu: {exc}")
        else:
            select_project(new_chat_id)
            st.rerun()

    visible_projects = projects[:12]
    if active_chat_id not in {project["id"] for project in visible_projects}:
        active_summary = next(project for project in projects if project["id"] == active_chat_id)
        visible_projects = [active_summary, *projects[:11]]

    for project in visible_projects:
        is_active = project["id"] == active_chat_id
        display_name = project["name"]
        if len(display_name) > 34:
            display_name = f"{display_name[:31]}…"
        if st.button(
            f"{'▶' if is_active else '○'} {display_name}",
            key=f"project_{project['id']}",
            use_container_width=True,
            disabled=is_active or pipeline_locked,
        ):
            try:
                persist_messages(active_chat_id)
            except ChatStoreError as exc:
                st.error(f"Nie udało się zapisać bieżącego projektu: {exc}")
            else:
                select_project(project["id"])
                st.rerun()

    if len(projects) > 12:
        visible_ids = {project["id"] for project in visible_projects}
        remaining_projects = [project for project in projects if project["id"] not in visible_ids]
        selected_project = st.selectbox(
            "Pozostałe projekty",
            options=[None, *[project["id"] for project in remaining_projects]],
            format_func=lambda project_id: (
                "Wybierz projekt…"
                if project_id is None
                else next(
                    project["name"] for project in remaining_projects if project["id"] == project_id
                )
            ),
            disabled=pipeline_locked,
            key=f"remaining_project_selector_{active_chat_id}",
        )
        if st.button(
            "Otwórz wybrany projekt",
            use_container_width=True,
            disabled=not selected_project or pipeline_locked,
        ):
            try:
                persist_messages(active_chat_id)
            except ChatStoreError as exc:
                st.error(f"Nie udało się zapisać bieżącego projektu: {exc}")
            else:
                select_project(selected_project)
                st.rerun()

    if pipeline_locked:
        st.caption("Zakończ lub anuluj bieżący etap, aby zmienić projekt.")

    with st.popover(
        "⚙️ Zarządzaj projektem",
        use_container_width=True,
        disabled=pipeline_locked,
    ):
        current_name = str(active_project.get("name") or DEFAULT_PROJECT_NAME)
        renamed = st.text_input("Nazwa", value=current_name, key=f"rename_{active_chat_id}")
        if st.button("Zapisz nazwę", use_container_width=True):
            try:
                persist_messages(active_chat_id, name=CHAT_STORE.project_name(renamed))
                set_flash("success", "Nazwa projektu została zmieniona.")
                st.rerun()
            except ChatStoreError as exc:
                st.error(str(exc))

        st.divider()
        confirm_delete = st.checkbox(
            "Rozumiem, że projekt zostanie usunięty",
            key=f"confirm_delete_{active_chat_id}",
        )
        if st.button(
            "🗑️ Usuń projekt",
            use_container_width=True,
            disabled=not confirm_delete,
        ):
            try:
                CHAT_STORE.delete(active_chat_id)
                remaining = CHAT_STORE.list()
                next_id = remaining[0]["id"] if remaining else create_project()
                select_project(next_id)
                set_flash("success", "Projekt został usunięty.")
                st.rerun()
            except ChatStoreError as exc:
                st.error(str(exc))

    st.divider()
    st.markdown("#### Modele")
    widgets_disabled = pipeline_locked
    chat_model = st.selectbox(
        "Architekt",
        available_models,
        index=preferred_model_index(available_models, ("bielik", "mistral", "llama")),
        key=f"chat_model_{active_chat_id}",
        disabled=widgets_disabled,
    )
    coder_model = st.selectbox(
        "Programista",
        available_models,
        index=preferred_model_index(available_models, ("coder", "qwen")),
        key=f"coder_model_{active_chat_id}",
        disabled=widgets_disabled,
    )
    reviewer_model = st.selectbox(
        "Recenzent",
        available_models,
        index=preferred_model_index(available_models, ("bielik", "mistral", "llama")),
        key=f"reviewer_model_{active_chat_id}",
        disabled=widgets_disabled,
    )

    st.divider()
    st.markdown("#### Pliki")
    files = workspace_files(active_chat_id)
    if files:
        selected_file = st.selectbox("Podgląd", files, index=None)
        if selected_file:
            content = file_ops.read_file(
                selected_file,
                workspace_dir=str(CHAT_STORE.workspace_path(active_chat_id)),
            )
            language = CODE_LANGUAGES.get(Path(selected_file).suffix.lower(), "text")
            with st.expander(selected_file, expanded=True):
                st.code(content, language=language, line_numbers=True)
    else:
        st.info("Workspace jest pusty.", icon="📂")

    try:
        backups = CHAT_STORE.list_backups(active_chat_id)
    except ChatStoreError as exc:
        backups = []
        st.error(str(exc))
    with st.popover(
        f"⏮️ Rollback ({len(backups)})",
        use_container_width=True,
        disabled=not backups or pipeline_locked,
    ):
        selected_backup = st.selectbox("Wersja", backups, key=f"backup_{active_chat_id}")
        st.caption("Przed rollbackiem bieżący stan zostanie zabezpieczony.")
        confirm_restore = st.checkbox(
            "Potwierdzam przywrócenie",
            key=f"confirm_restore_{active_chat_id}",
        )
        if st.button(
            "Przywróć backup",
            use_container_width=True,
            disabled=not confirm_restore,
        ):
            try:
                CHAT_STORE.create_backup(active_chat_id)
                CHAT_STORE.restore_backup(active_chat_id, selected_backup)
                st.session_state.pop("archive_payload", None)
                set_flash("success", f"Przywrócono {selected_backup}.")
                st.rerun()
            except ChatStoreError as exc:
                st.error(str(exc))

    if st.button(
        "📦 Przygotuj ZIP",
        use_container_width=True,
        disabled=not files or pipeline_locked,
    ):
        try:
            st.session_state["archive_payload"] = CHAT_STORE.build_zip(active_chat_id)
            st.session_state["archive_chat_id"] = active_chat_id
        except (ChatStoreError, OSError) as exc:
            st.error(f"Nie udało się utworzyć ZIP-a: {exc}")

    if (
        st.session_state.get("archive_payload")
        and st.session_state.get("archive_chat_id") == active_chat_id
    ):
        st.download_button(
            "⬇️ Pobierz ZIP",
            data=st.session_state["archive_payload"],
            file_name=safe_archive_name(str(active_project.get("name") or "projekt")),
            mime="application/zip",
            use_container_width=True,
        )


st.title("CodeFabric AI")
st.markdown("Lokalny zespół agentów, który zamienia opis projektu w plan, kod i raport jakości.")
render_flash()

for message in st.session_state["messages"]:
    if not isinstance(message, dict):
        continue
    role = message.get("role") if message.get("role") in {"user", "assistant"} else "assistant"
    content = str(message.get("content", ""))
    with st.chat_message(role, avatar="🧑‍💻" if role == "user" else "🤖"):
        st.markdown(content)

pipeline_active = bool(st.session_state.get("pipeline_active"))
user_input = st.chat_input(
    "Opisz projekt albo kolejną zmianę…",
    disabled=pipeline_active,
    max_chars=20_000,
)

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    try:
        backup_name = CHAT_STORE.create_backup(active_chat_id)
        if backup_name:
            st.toast("Bieżący workspace zabezpieczony", icon="💾")

        project_state = load_project(active_chat_id) or {}
        project_name = str(project_state.get("name") or DEFAULT_PROJECT_NAME)
        if project_name == DEFAULT_PROJECT_NAME:
            project_name = CHAT_STORE.project_name(user_input)
        persist_messages(active_chat_id, name=project_name)
    except ChatStoreError as exc:
        st.session_state["messages"].pop()
        st.error(str(exc))
    else:
        st.session_state["pipeline_active"] = True
        st.session_state.pop("graph_state", None)
        st.session_state.pop("archive_payload", None)
        st.rerun()


if st.session_state.get("pipeline_active"):
    if "graph_state" not in st.session_state:
        last_user_message = next(
            (
                str(message.get("content", ""))
                for message in reversed(st.session_state["messages"])
                if isinstance(message, dict) and message.get("role") == "user"
            ),
            "",
        )
        st.session_state["graph_state"] = {
            "messages": [HumanMessage(content=last_user_message)],
            "current_files": workspace_files(active_chat_id),
            "plan": None,
            "plan_approved": False,
            "feedback": None,
            "revision_count": 0,
            "next_node": "manager",
            "model_names": {
                "chat": chat_model,
                "coder": coder_model,
                "reviewer": reviewer_model,
            },
            "chat_workspace": str(CHAT_STORE.workspace_path(active_chat_id)),
        }

    current_state = st.session_state["graph_state"]
    plan = current_state.get("plan")
    plan_approved = current_state.get("plan_approved", False)
    feedback = current_state.get("feedback")
    next_node = current_state.get("next_node")
    decision = review_decision(feedback)

    should_run_graph = not (
        (plan and not plan_approved and feedback is None)
        or next_node == "end"
        or decision == "APPROVE"
    )

    if should_run_graph:
        status = st.status("AI pracuje…", expanded=True)
        progress_bar = st.progress(0, text="Uruchamiam zespół…")
        step = 0
        try:
            for event in workflow_app.stream(
                current_state,
                config={"recursion_limit": 20},
                stream_mode="updates",
            ):
                step += 1
                progress = min(0.12 + step * 0.11, 0.95)
                for node, update in event.items():
                    merge_graph_update(st.session_state["graph_state"], update)
                    if node == "planner":
                        progress_bar.progress(progress, "Architekt przygotowuje plan…")
                        status.write("🧠 **Architekt:** plan techniczny gotowy do oceny.")
                    elif node == "coder":
                        revision = update.get("revision_count", 0)
                        label = (
                            "implementuje projekt"
                            if revision == 0
                            else f"wprowadza poprawki v{revision}"
                        )
                        progress_bar.progress(progress, f"Programista {label}…")
                        status.write(f"👨‍💻 **Programista:** {label}.")
                    elif node == "reviewer":
                        progress_bar.progress(progress, "Recenzent sprawdza wynik…")
                        status.write("🔎 **Recenzent:** sprawdzam kompletność i jakość.")

            progress_bar.progress(1.0, "Etap zakończony")
            status.update(label="Etap zakończony", state="complete", expanded=False)
        except Exception as exc:  # Streamlit must remain usable after provider errors.
            LOGGER.exception("CodeFabric workflow failed")
            error_message = f"Proces został przerwany: {exc}"
            st.session_state["messages"].append(
                {"role": "assistant", "content": f"⚠️ {error_message}"}
            )
            try:
                persist_messages(active_chat_id)
            except ChatStoreError:
                LOGGER.exception("Could not persist workflow error")
            st.session_state["pipeline_active"] = False
            set_flash("error", error_message)
            st.rerun()

    current_state = st.session_state["graph_state"]
    plan = current_state.get("plan")
    plan_approved = current_state.get("plan_approved", False)
    next_node = current_state.get("next_node")
    feedback = current_state.get("feedback")
    decision = review_decision(feedback)

    if plan and not plan_approved:
        st.info("Architekt przygotował plan. Zatwierdź go albo doprecyzuj wymagania.", icon="📋")
        with st.expander("Plan techniczny", expanded=True):
            st.markdown(str(plan))

        approve_col, cancel_col = st.columns([3, 1])
        if approve_col.button(
            "✅ Zatwierdź i rozpocznij kodowanie",
            type="primary",
            use_container_width=True,
        ):
            current_state["plan_approved"] = True
            current_state["feedback"] = None
            current_state["next_node"] = "manager"
            st.rerun()
        if cancel_col.button("Anuluj", use_container_width=True):
            st.session_state["messages"].append(
                {"role": "assistant", "content": "Plan został anulowany bez zmiany plików."}
            )
            try:
                persist_messages(active_chat_id)
            except ChatStoreError:
                LOGGER.exception("Could not persist cancelled plan")
            st.session_state["pipeline_active"] = False
            st.session_state.pop("graph_state", None)
            set_flash("info", "Plan anulowano. Możesz podać nowe wymagania.")
            st.rerun()

        plan_feedback = st.text_area(
            "Uwagi do planu",
            placeholder="Np. użyj FastAPI zamiast Flask i dodaj testy integracyjne…",
            max_chars=5_000,
        )
        if st.button("🔄 Popraw plan", use_container_width=True):
            if plan_feedback.strip():
                current_state["feedback"] = plan_feedback.strip()
                current_state["plan"] = None
                current_state["plan_approved"] = False
                current_state["next_node"] = "manager"
                st.rerun()
            else:
                st.warning("Dodaj krótką informację, co należy zmienić.")

    elif next_node == "end" and not current_state.get("last_error") and decision != "REJECT":
        generated_files = workspace_files(active_chat_id)
        file_summary = "\n".join(f"- `{path}`" for path in generated_files[:20])
        if len(generated_files) > 20:
            file_summary += f"\n- …oraz {len(generated_files) - 20} kolejnych"
        completion = "✅ Projekt przeszedł pełny przepływ CodeFabric."
        if file_summary:
            completion += f"\n\nPliki w workspace:\n{file_summary}"
        st.session_state["messages"].append({"role": "assistant", "content": completion})
        try:
            persist_messages(active_chat_id)
        except ChatStoreError:
            LOGGER.exception("Could not persist completion message")
        st.session_state["pipeline_active"] = False
        set_flash("success", "Projekt jest gotowy. Możesz teraz opisać kolejną zmianę.")
        st.rerun()

    elif next_node == "end":
        failure_stage = current_state.get("error_stage") or "reviewer"
        failure_stage_label = {
            "planner": "planowania",
            "coder": "kodowania",
            "reviewer": "recenzji",
            "quality": "pętli poprawek jakościowych",
        }.get(failure_stage, "przetwarzania")
        st.warning(f"Proces zatrzymał się na etapie {failure_stage_label}.", icon="⚠️")
        if feedback:
            with st.expander("Ostatni raport", expanded=True):
                st.markdown(str(feedback))
                if current_state.get("last_error"):
                    st.caption(f"Szczegóły techniczne: {current_state['last_error']}")
        retry_col, stop_col = st.columns(2)
        if retry_col.button("🔄 Spróbuj ponownie", use_container_width=True):
            current_state["revision_count"] = 0
            current_state["next_node"] = "manager"
            if current_state.get("plan"):
                if current_state.get("error_stage") == "reviewer":
                    current_state["retry_stage"] = "reviewer"
                elif current_state.get("error_stage") == "quality" or (
                    current_state.get("error_stage") == "coder"
                    and review_decision(current_state.get("retry_feedback")) == "REJECT"
                ):
                    current_state["retry_stage"] = "coder_quality"
                else:
                    current_state["retry_stage"] = "coder"
            else:
                current_state["feedback"] = None
            st.rerun()
        if stop_col.button("Zakończ", use_container_width=True):
            st.session_state["messages"].append(
                {
                    "role": "assistant",
                    "content": (
                        f"⚠️ Proces zakończono na etapie {failure_stage_label}. "
                        "Pliki pozostają dostępne w workspace."
                    ),
                }
            )
            try:
                persist_messages(active_chat_id)
            except ChatStoreError:
                LOGGER.exception("Could not persist stopped workflow state")
            st.session_state["pipeline_active"] = False
            st.session_state.pop("graph_state", None)
            set_flash("warning", f"Proces zakończono na etapie {failure_stage_label}.")
            st.rerun()
