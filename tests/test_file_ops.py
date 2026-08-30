import os
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tools import file_ops


@pytest.fixture
def legacy_paths(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    backups = tmp_path / "backups"
    monkeypatch.setattr(file_ops, "WORKSPACE_DIR", str(workspace))
    monkeypatch.setattr(file_ops, "BACKUP_DIR", str(backups))
    return workspace, backups


def test_write_and_read_keep_legacy_api_and_create_directories(legacy_paths):
    workspace, _ = legacy_paths

    result = file_ops.write_file("src\\module.py", "print('ok')\n")

    assert result == "Successfully wrote to src/module.py"
    assert (workspace / "src" / "module.py").read_text(encoding="utf-8") == "print('ok')\n"
    assert file_ops.read_file("src/module.py") == "print('ok')\n"
    assert file_ops.read_file("missing.txt") == ""
    with pytest.raises(FileNotFoundError):
        file_ops.read_file_strict("missing.txt")


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "../workspace-evil/pwned.txt",
        "../../pwned.txt",
        "/tmp/pwned.txt",
        "C:\\pwned.txt",
        "main.py:stream",
        "main.py.",
        "main.py ",
        "bad\nname.py",
    ],
)
def test_write_rejects_traversal_prefix_collisions_and_absolute_paths(legacy_paths, unsafe_name):
    workspace, _ = legacy_paths
    workspace.mkdir()

    result = file_ops.write_file(unsafe_name, "do not write")

    assert result.startswith("Error:")
    assert not (workspace.parent / "workspace-evil" / "pwned.txt").exists()
    assert not (workspace.parent / "pwned.txt").exists()


def test_read_rejects_traversal_and_does_not_leak_prefix_collision(legacy_paths):
    workspace, _ = legacy_paths
    outside = workspace.parent / "workspace-evil"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")

    assert file_ops.read_file("../workspace-evil/secret.txt") == "Error: Security violation."
    assert file_ops.read_file(str(outside / "secret.txt")) == "Error: Security violation."


def test_read_and_write_reject_symlink_escape(legacy_paths):
    workspace, _ = legacy_paths
    outside = workspace.parent / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    try:
        (workspace / "escape").symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks are unavailable on this platform")

    assert file_ops.read_file("escape/secret.txt") == "Error: Security violation."
    assert file_ops.write_file("escape/new.txt", "unsafe").startswith("Error:")
    assert not (outside / "new.txt").exists()


def test_listing_is_sorted_and_skips_ignored_or_symlinked_directories(legacy_paths):
    workspace, _ = legacy_paths
    (workspace / "z").mkdir(parents=True)
    (workspace / "a").mkdir()
    (workspace / ".git").mkdir()
    (workspace / ".github" / "workflows").mkdir(parents=True)
    (workspace / ".streamlit").mkdir()
    (workspace / ".VENV").mkdir()
    (workspace / "Node_Modules").mkdir()
    (workspace / "z" / "last.txt").write_text("z", encoding="utf-8")
    (workspace / "a" / "first.txt").write_text("a", encoding="utf-8")
    (workspace / "middle.txt").write_text("m", encoding="utf-8")
    (workspace / ".hidden").write_text("hidden", encoding="utf-8")
    (workspace / ".gitignore").write_text(".venv\n", encoding="utf-8")
    (workspace / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (workspace / ".env.local").write_text("SECRET=local\n", encoding="utf-8")
    (workspace / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
    (workspace / ".streamlit" / "secrets.toml").write_text(
        'api_key = "SUPER_SECRET"\n', encoding="utf-8"
    )
    (workspace / ".streamlit" / "config.toml").write_text(
        '[theme]\nbase = "dark"\n', encoding="utf-8"
    )
    (workspace / ".gitkeep").write_text("", encoding="utf-8")
    (workspace / ".git" / "config").write_text("hidden", encoding="utf-8")
    (workspace / ".VENV" / "library.py").write_text("hidden", encoding="utf-8")
    (workspace / "Node_Modules" / "package.js").write_text("hidden", encoding="utf-8")
    (workspace / ".github" / "workflows" / "ci.yml").write_text("name: CI\n", encoding="utf-8")

    outside = workspace.parent / "outside"
    outside.mkdir()
    (outside / "outside.txt").write_text("outside", encoding="utf-8")
    try:
        (workspace / "linked-dir").symlink_to(outside, target_is_directory=True)
        (workspace / "linked-file.txt").symlink_to(outside / "outside.txt")
    except (NotImplementedError, OSError):
        pass

    expected = [
        ".env.example",
        ".github/workflows/ci.yml",
        ".gitignore",
        ".hidden",
        ".streamlit/config.toml",
        "a/first.txt",
        "middle.txt",
        "z/last.txt",
    ]
    assert file_ops.get_all_file_paths() == expected
    assert file_ops.list_files() == ", ".join(expected)


def test_strict_listing_raises_while_legacy_listing_fails_softly(legacy_paths, monkeypatch):
    workspace, _ = legacy_paths
    workspace.mkdir()

    def fail_walk(*_args, **_kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(file_ops.os, "walk", fail_walk)

    with pytest.raises(PermissionError, match="permission denied"):
        file_ops.get_all_file_paths_strict()
    assert file_ops.get_all_file_paths() == []


@pytest.mark.skipif(os.name == "nt", reason="Windows nie zachowuje bitów POSIX w ten sam sposób")
def test_atomic_write_preserves_existing_mode_and_uses_readable_default(legacy_paths):
    workspace, _ = legacy_paths
    workspace.mkdir()
    executable = workspace / "run.sh"
    executable.write_text("#!/bin/sh\necho old\n", encoding="utf-8")
    executable.chmod(0o755)

    assert file_ops.write_file("run.sh", "#!/bin/sh\necho updated\n").startswith("Successfully")
    assert stat.S_IMODE(executable.stat().st_mode) == 0o755

    assert file_ops.write_file("new.txt", "new content\n").startswith("Successfully")
    assert stat.S_IMODE((workspace / "new.txt").stat().st_mode) == 0o644


def test_explicit_workspace_does_not_mutate_legacy_global(legacy_paths, tmp_path):
    legacy_workspace, _ = legacy_paths
    explicit_workspace = tmp_path / "explicit" / "workspace"

    assert (
        file_ops.write_file("file.txt", "explicit", workspace_dir=explicit_workspace)
        == "Successfully wrote to file.txt"
    )

    assert (explicit_workspace / "file.txt").read_text(encoding="utf-8") == "explicit"
    assert not (legacy_workspace / "file.txt").exists()
    assert file_ops.get_workspace_dir() == str(legacy_workspace)


def test_workspace_context_is_nested_and_isolated_between_threads(legacy_paths, tmp_path):
    legacy_workspace, _ = legacy_paths
    first_workspace = tmp_path / "chat-one" / "workspace"
    second_workspace = tmp_path / "chat-two" / "workspace"
    barrier = threading.Barrier(2)

    def write_in_context(workspace: Path, value: str):
        with file_ops.workspace_context(workspace):
            barrier.wait(timeout=5)
            assert file_ops.get_workspace_dir() == str(workspace)
            assert file_ops.write_file("shared.txt", value).startswith("Successfully")
            return file_ops.read_file("shared.txt"), file_ops.get_backup_dir()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(write_in_context, first_workspace, "one")
        second = executor.submit(write_in_context, second_workspace, "two")

    assert first.result() == ("one", str(first_workspace.parent / "backups"))
    assert second.result() == ("two", str(second_workspace.parent / "backups"))
    assert file_ops.get_workspace_dir() == str(legacy_workspace)

    with file_ops.workspace_context(first_workspace):
        with file_ops.workspace_context(second_workspace):
            assert file_ops.get_workspace_dir() == str(second_workspace)
        assert file_ops.get_workspace_dir() == str(first_workspace)


def test_backup_create_restore_list_overwrite_and_delete_cycle(legacy_paths):
    workspace, backups = legacy_paths
    (workspace / "nested").mkdir(parents=True)
    (workspace / "nested" / "value.txt").write_text("version one", encoding="utf-8")

    created = file_ops.create_backup("snapshot")
    assert created == str(backups / "snapshot")
    assert file_ops.list_backups() == ["snapshot"]

    (workspace / "nested" / "value.txt").write_text("version two", encoding="utf-8")
    assert file_ops.create_backup("snapshot") == str(backups / "snapshot")
    (workspace / "nested" / "value.txt").write_text("damaged", encoding="utf-8")
    (workspace / "extra.txt").write_text("remove me", encoding="utf-8")

    assert file_ops.restore_backup("snapshot") is True
    assert (workspace / "nested" / "value.txt").read_text(encoding="utf-8") == "version two"
    assert not (workspace / "extra.txt").exists()
    assert file_ops.delete_backup("snapshot") is True
    assert file_ops.delete_backup("snapshot") is False
    assert file_ops.list_backups() == []


def test_backup_api_uses_explicit_workspace_and_derived_backup_dir(tmp_path):
    workspace = tmp_path / "chat" / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "app.py").write_text("original", encoding="utf-8")

    created = file_ops.create_backup("initial", workspace_dir=workspace)

    expected_root = workspace.parent / "backups"
    assert created == str(expected_root / "initial")
    assert file_ops.list_backups(workspace_dir=workspace) == ["initial"]
    (workspace / "src" / "app.py").write_text("changed", encoding="utf-8")
    assert file_ops.restore_backup("initial", workspace_dir=workspace) is True
    assert (workspace / "src" / "app.py").read_text(encoding="utf-8") == "original"


def test_backup_return_path_keeps_relative_legacy_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(file_ops, "WORKSPACE_DIR", "workspace")
    monkeypatch.setattr(file_ops, "BACKUP_DIR", "backups")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file.txt").write_text("content", encoding="utf-8")

    assert file_ops.create_backup("snapshot") == str(Path("backups") / "snapshot")


@pytest.mark.parametrize("unsafe_name", ["../victim", "nested/name", "nested\\name", ".", ".."])
def test_backup_names_cannot_escape_backup_root(legacy_paths, unsafe_name):
    workspace, backups = legacy_paths
    workspace.mkdir()
    (workspace / "file.txt").write_text("content", encoding="utf-8")
    victim = backups.parent / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("keep", encoding="utf-8")

    assert file_ops.create_backup(unsafe_name) is None
    assert file_ops.restore_backup(unsafe_name) is False
    assert file_ops.delete_backup(unsafe_name) is False
    assert (victim / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_symlink_is_not_treated_as_a_backup(legacy_paths):
    workspace, backups = legacy_paths
    workspace.mkdir()
    backups.mkdir()
    outside = backups.parent / "outside-backup"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    try:
        (backups / "linked").symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks are unavailable on this platform")

    assert file_ops.list_backups() == []
    assert file_ops.restore_backup("linked") is False
    assert file_ops.delete_backup("linked") is False
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_failed_restore_keeps_current_workspace(legacy_paths, monkeypatch):
    workspace, _ = legacy_paths
    workspace.mkdir()
    current = workspace / "value.txt"
    current.write_text("backup value", encoding="utf-8")
    assert file_ops.create_backup("snapshot") is not None
    current.write_text("current value", encoding="utf-8")

    def fail_copy(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(file_ops.shutil, "copytree", fail_copy)
    assert file_ops.restore_backup("snapshot") is False
    assert current.read_text(encoding="utf-8") == "current value"


def test_list_and_clean_backups_are_deterministic(legacy_paths):
    _, backups = legacy_paths
    for name in ["backup_001", "backup_003", "backup_002"]:
        (backups / name).mkdir(parents=True)
    (backups / "not-a-directory").write_text("ignore", encoding="utf-8")

    assert file_ops.list_backups() == ["backup_003", "backup_002", "backup_001"]
    file_ops.clean_old_backups(keep_last=2)
    assert file_ops.list_backups() == ["backup_003", "backup_002"]

    file_ops.clean_old_backups(keep_last=0)
    assert file_ops.list_backups() == []


def test_backup_directory_inside_workspace_is_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    backup_inside_workspace = workspace / "backups"
    workspace.mkdir()
    (workspace / "file.txt").write_text("content", encoding="utf-8")

    assert (
        file_ops.create_backup(
            "unsafe", workspace_dir=workspace, backup_dir=backup_inside_workspace
        )
        is None
    )
    assert not (backup_inside_workspace / "unsafe").exists()


def test_backup_api_never_treats_live_workspace_as_a_backup(tmp_path):
    workspace = tmp_path / "backup_live"
    workspace.mkdir()
    (workspace / "important.txt").write_text("keep", encoding="utf-8")

    assert (
        file_ops.create_backup("backup_live", workspace_dir=workspace, backup_dir=tmp_path) is None
    )
    assert file_ops.list_backups(workspace_dir=workspace, backup_dir=tmp_path) == []
    assert (
        file_ops.delete_backup("backup_live", workspace_dir=workspace, backup_dir=tmp_path) is False
    )
    assert (workspace / "important.txt").read_text(encoding="utf-8") == "keep"


def test_empty_workspace_has_no_backup(legacy_paths):
    workspace, _ = legacy_paths
    workspace.mkdir()

    assert file_ops.create_backup() is None
