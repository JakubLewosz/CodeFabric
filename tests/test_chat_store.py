import zipfile
from datetime import timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest

from tools import chat_store
from tools.chat_store import ChatStore, ChatStoreError, InvalidChatId


def test_create_save_list_and_load(tmp_path: Path) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()

    store.save_messages(
        chat_id,
        [{"role": "user", "content": "Zbuduj API"}],
        name="Projekt API",
    )

    state = store.load(chat_id)
    assert state is not None
    assert state["name"] == "Projekt API"
    assert state["messages"][0]["content"] == "Zbuduj API"
    assert store.list()[0]["id"] == chat_id


def test_list_orders_aware_utc_and_legacy_local_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_timezone = timezone(timedelta(hours=2))
    monkeypatch.setattr(chat_store, "_local_timezone_at", lambda _value: local_timezone)
    store = ChatStore(tmp_path / "chats")

    timestamps = {
        "aware-newest": "2024-01-01T10:30:00+00:00",
        "aware-offset": "2024-01-01T12:15:00+02:00",
        "legacy-local": "2024-01-01T12:00:00",
        "invalid-date": "not-a-date",
    }
    for chat_id, updated in timestamps.items():
        store.save(chat_id, {"name": chat_id, "messages": [], "updated": updated})

    assert [project["id"] for project in store.list()] == [
        "aware-newest",
        "aware-offset",
        "legacy-local",
        "invalid-date",
    ]


def test_save_messages_drops_legacy_runtime_graph_state(tmp_path: Path) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    state = store.load(chat_id) or {}
    state["graph_state"] = {"messages": "legacy string"}
    store.save(chat_id, state)

    store.save_messages(chat_id, [{"role": "assistant", "content": "Gotowe"}])

    assert "graph_state" not in (store.load(chat_id) or {})


@pytest.mark.parametrize("chat_id", ["../escape", "a/b", "", ".hidden", "id with space"])
def test_rejects_unsafe_chat_ids(tmp_path: Path, chat_id: str) -> None:
    store = ChatStore(tmp_path / "chats")
    with pytest.raises(InvalidChatId):
        store.workspace_path(chat_id)


def test_save_is_json_strict_and_keeps_previous_state(tmp_path: Path) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    original = store.load(chat_id)

    with pytest.raises(ChatStoreError):
        store.save(chat_id, {"messages": [object()]})

    assert store.load(chat_id) == original


def test_corrupt_state_is_ignored_by_listing_but_reported_on_load(tmp_path: Path) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    store.state_path(chat_id).write_text("{broken", encoding="utf-8")

    assert store.list() == []
    with pytest.raises(ChatStoreError):
        store.load(chat_id)


def test_invalid_utf8_state_is_ignored_by_listing_but_reported_on_load(tmp_path: Path) -> None:
    store = ChatStore(tmp_path / "chats")
    valid_id = store.create()
    invalid_id = store.create()
    store.state_path(invalid_id).write_bytes(b"\xff\xfe\x00")

    assert [project["id"] for project in store.list()] == [valid_id]
    with pytest.raises(ChatStoreError):
        store.load(invalid_id)


def test_unreadable_state_is_wrapped_and_skipped_by_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    blocked_state = store.state_path(chat_id)
    original_exists = Path.exists

    def fail_blocked_state(path):
        if path == blocked_state:
            raise PermissionError("blocked")
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", fail_blocked_state)

    with pytest.raises(ChatStoreError):
        store.load(chat_id)
    assert store.list() == []


def test_backup_restore_and_in_memory_zip(tmp_path: Path) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    workspace = store.workspace_path(chat_id)
    source = workspace / "src" / "main.py"
    source.parent.mkdir()
    source.write_text("print('v1')\n", encoding="utf-8")

    backup_name = store.create_backup(chat_id)
    assert backup_name is not None
    source.write_text("print('v2')\n", encoding="utf-8")
    (workspace / "temporary.txt").write_text("remove me", encoding="utf-8")

    assert store.restore_latest_backup(chat_id) == backup_name
    assert source.read_text(encoding="utf-8") == "print('v1')\n"
    assert not (workspace / "temporary.txt").exists()

    archive_bytes = store.build_zip(chat_id)
    assert archive_bytes is not None
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        assert archive.namelist() == ["src/main.py"]
        assert archive.read("src/main.py") == b"print('v1')\n"


def test_backups_are_ordered_by_utc_and_legacy_local_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local_timezone = timezone(timedelta(hours=2))
    monkeypatch.setattr(chat_store, "_local_timezone_at", lambda _value: local_timezone)
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    backups_dir = store.backups_path(chat_id)
    backups_dir.mkdir()

    expected_order = [
        "backup_20240101T103000_000000Z",
        "backup_20240101_120000_500000",
        "backup_20240101_120000",
        "backup_20240101T090000Z",
        "backup_manual",
    ]
    for backup_name in expected_order:
        backup_path = backups_dir / backup_name
        backup_path.mkdir()
        (backup_path / "version.txt").write_text(backup_name, encoding="utf-8")

    assert store.list_backups(chat_id) == expected_order
    assert store.restore_latest_backup(chat_id) == expected_order[0]
    assert (store.workspace_path(chat_id) / "version.txt").read_text(encoding="utf-8") == (
        expected_order[0]
    )


def test_failed_backup_copy_never_exposes_partial_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    (store.workspace_path(chat_id) / "main.py").write_text("complete", encoding="utf-8")

    def fail_after_partial_copy(_source, destination, **_kwargs):
        destination = Path(destination)
        destination.mkdir()
        (destination / "partial.txt").write_text("partial", encoding="utf-8")
        raise OSError("disk full")

    monkeypatch.setattr(chat_store.shutil, "copytree", fail_after_partial_copy)

    with pytest.raises(ChatStoreError):
        store.create_backup(chat_id)

    assert store.list_backups(chat_id) == []
    assert list(store.backups_path(chat_id).iterdir()) == []


def test_backup_io_errors_use_chat_store_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    workspace = store.workspace_path(chat_id)
    (workspace / "main.py").write_text("content", encoding="utf-8")
    backups = store.backups_path(chat_id)
    backups.mkdir()
    original_iterdir = Path.iterdir

    def fail_selected_directory(path):
        if path in {workspace, backups}:
            raise PermissionError("unreadable")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fail_selected_directory)

    with pytest.raises(ChatStoreError):
        store.create_backup(chat_id)
    with pytest.raises(ChatStoreError):
        store.list_backups(chat_id)


def test_restore_path_io_error_is_wrapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    workspace = store.workspace_path(chat_id)
    (workspace / "main.py").write_text("version", encoding="utf-8")
    backup_name = store.create_backup(chat_id)
    assert backup_name is not None
    original_contained = store._contained_path

    def fail_backup_resolution(path):
        if path.name == backup_name:
            raise PermissionError("blocked backup")
        return original_contained(path)

    monkeypatch.setattr(store, "_contained_path", fail_backup_resolution)

    with pytest.raises(ChatStoreError):
        store.restore_backup(chat_id, backup_name)


def test_failed_restore_reports_manual_recovery_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ChatStore(tmp_path / "chats")
    chat_id = store.create()
    workspace = store.workspace_path(chat_id)
    source = workspace / "main.py"
    source.write_text("original", encoding="utf-8")
    backup_name = store.create_backup(chat_id)
    assert backup_name is not None
    source.write_text("live version", encoding="utf-8")
    original_replace = chat_store.os.replace

    def fail_install_and_recovery(source_path, destination_path):
        source_path = Path(source_path)
        if source_path == workspace:
            return original_replace(source_path, destination_path)
        raise OSError("filesystem failure")

    monkeypatch.setattr(chat_store.os, "replace", fail_install_and_recovery)

    with pytest.raises(ChatStoreError, match="można odzyskać z") as error:
        store.restore_backup(chat_id, backup_name)

    recovery_dirs = list(store.chat_dir(chat_id).glob(".workspace-previous-*"))
    assert not workspace.exists()
    assert len(recovery_dirs) == 1
    assert str(recovery_dirs[0]) in str(error.value)
    assert (recovery_dirs[0] / "main.py").read_text(encoding="utf-8") == "live version"


def test_project_name_is_single_line_and_bounded() -> None:
    assert ChatStore.project_name("  Nowy\nprojekt   API  ") == "Nowy projekt API"
    assert len(ChatStore.project_name("x" * 100)) == 48
    assert ChatStore.project_name(" \n ") == "Nowy projekt"


def test_delete_removes_only_the_selected_project(tmp_path: Path) -> None:
    store = ChatStore(tmp_path / "chats")
    first = store.create()
    second = store.create()

    store.delete(first)

    assert not store.chat_dir(first).exists()
    assert store.chat_dir(second).is_dir()
