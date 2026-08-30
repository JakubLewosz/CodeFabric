"""Bezpieczne operacje na plikach workspace i jego backupach.

Stare wywołania korzystające z globalnych ``WORKSPACE_DIR`` i ``BACKUP_DIR``
pozostają wspierane. Nowy kod powinien przekazywać ``workspace_dir`` jawnie albo
korzystać z :func:`workspace_context`, dzięki czemu równoległe chaty nie muszą
modyfikować globalnego stanu modułu.
"""

import ntpath
import os
import shutil
import stat
import tempfile
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Union

from tools.text_files import is_sensitive_file

PathValue = Union[str, os.PathLike]

# Wartości globalne są częścią dotychczasowego API. ContextVar i jawne
# parametry poniżej umożliwiają bezpieczniejsze użycie z wieloma workspace'ami.
WORKSPACE_DIR = "./workspace"
BACKUP_DIR = "./backups"

_WORKSPACE_OVERRIDE: ContextVar[Optional[str]] = ContextVar(
    "codefabric_workspace_dir", default=None
)
_BACKUP_OVERRIDE: ContextVar[Optional[str]] = ContextVar("codefabric_backup_dir", default=None)

_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS = {}
_INTERNAL_BACKUP_PREFIXES = (
    ".codefabric-backup-",
    ".codefabric-previous-",
    ".codefabric-restore-",
)
_IGNORED_PROJECT_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)
_IGNORED_PROJECT_FILES = frozenset({".ds_store", ".gitkeep"})


def _path_text(path: PathValue, label: str) -> str:
    """Zwraca ścieżkę jako tekst i odrzuca nieobsługiwane typy."""
    try:
        value = os.fspath(path)
    except TypeError as exc:
        raise ValueError(f"{label} must be a path-like value") from exc

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a text path")
    if "\x00" in value:
        raise ValueError(f"{label} contains a null byte")
    return value


def _derived_backup_dir(workspace_dir: PathValue) -> str:
    workspace = Path(_path_text(workspace_dir, "workspace_dir"))
    return os.fspath(workspace.parent / "backups")


def get_workspace_dir(workspace_dir: Optional[PathValue] = None) -> str:
    """Zwraca jawny, kontekstowy lub globalny katalog workspace."""
    if workspace_dir is not None:
        return _path_text(workspace_dir, "workspace_dir")

    contextual = _WORKSPACE_OVERRIDE.get()
    return contextual if contextual is not None else _path_text(WORKSPACE_DIR, "WORKSPACE_DIR")


def get_backup_dir(
    backup_dir: Optional[PathValue] = None,
    workspace_dir: Optional[PathValue] = None,
) -> str:
    """Zwraca katalog backupów właściwy dla bieżącego workspace.

    Jawny ``backup_dir`` ma pierwszeństwo. Gdy podano tylko jawny
    ``workspace_dir``, backupy trafiają do katalogu ``backups`` obok niego.
    """
    if backup_dir is not None:
        return _path_text(backup_dir, "backup_dir")
    if workspace_dir is not None:
        return _derived_backup_dir(workspace_dir)

    contextual = _BACKUP_OVERRIDE.get()
    return contextual if contextual is not None else _path_text(BACKUP_DIR, "BACKUP_DIR")


@contextmanager
def workspace_context(
    workspace_dir: PathValue,
    backup_dir: Optional[PathValue] = None,
) -> Iterator[str]:
    """Ustawia workspace tylko dla bieżącego wątku/zadania asynchronicznego.

    Jeśli ``backup_dir`` nie podano, użyty zostanie katalog ``backups`` obok
    workspace. Kontekst może być bezpiecznie zagnieżdżany.
    """
    selected_workspace = _path_text(workspace_dir, "workspace_dir")
    selected_backup = (
        _path_text(backup_dir, "backup_dir")
        if backup_dir is not None
        else _derived_backup_dir(selected_workspace)
    )
    workspace_token = _WORKSPACE_OVERRIDE.set(selected_workspace)
    backup_token = _BACKUP_OVERRIDE.set(selected_backup)
    try:
        yield selected_workspace
    finally:
        _BACKUP_OVERRIDE.reset(backup_token)
        _WORKSPACE_OVERRIDE.reset(workspace_token)


def _normalise_relative_path(filename: PathValue) -> str:
    value = _path_text(filename, "filename").replace("\\", "/")
    if not value or not value.strip():
        raise ValueError("filename is empty")

    drive, _ = ntpath.splitdrive(value)
    if drive or value.startswith("/"):
        raise ValueError("absolute paths are not allowed")
    components = value.split("/")
    if any(
        not component
        or component != component.strip()
        or component.endswith(".")
        or ":" in component
        or any(ord(character) < 32 or ord(character) == 127 for character in component)
        for component in components
    ):
        raise ValueError("path contains a Windows-unsafe component")
    return value


def _is_within(path: Path, directory: Path) -> bool:
    """Sprawdza relację ścieżek bez podatności na kolizję prefiksów."""
    try:
        return os.path.commonpath((os.fspath(path), os.fspath(directory))) == os.fspath(directory)
    except (OSError, ValueError):
        return False


def _resolve_workspace_path(filename: PathValue, workspace_dir: PathValue) -> Path:
    workspace = Path(_path_text(workspace_dir, "workspace_dir")).resolve(strict=False)
    relative = _normalise_relative_path(filename)
    candidate = (workspace / relative).resolve(strict=False)

    if candidate == workspace or not _is_within(candidate, workspace):
        raise ValueError("path escapes workspace")
    return candidate


def _path_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(os.fspath(path.resolve(strict=False)))
    with _LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _atomic_replace_directory(staging: Path, destination: Path) -> None:
    """Podmienia katalog, zachowując poprzednią wersję do czasu sukcesu."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous = None

    if os.path.lexists(os.fspath(destination)):
        previous = Path(
            tempfile.mkdtemp(prefix=".codefabric-previous-", dir=os.fspath(destination.parent))
        )
        previous.rmdir()
        os.replace(os.fspath(destination), os.fspath(previous))

    try:
        os.replace(os.fspath(staging), os.fspath(destination))
    except Exception:
        if previous is not None and not os.path.lexists(os.fspath(destination)):
            os.replace(os.fspath(previous), os.fspath(destination))
        raise

    if previous is not None:
        try:
            _remove_path(previous)
        except OSError:
            # Nowy katalog jest już poprawnie zainstalowany. Osierocony katalog
            # techniczny nie może zmieniać wyniku operacji ani listy backupów.
            pass


def write_file(
    filename: str,
    content: str,
    *,
    workspace_dir: Optional[PathValue] = None,
) -> str:
    """Zapisuje plik wewnątrz workspace, atomowo tworząc jego nową treść."""
    display_name = str(filename).strip().replace("\\", "/")
    try:
        workspace = get_workspace_dir(workspace_dir)
        full_path = _resolve_workspace_path(filename, workspace)

        with _path_lock(full_path):
            full_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = None
            target_mode = stat.S_IMODE(full_path.stat().st_mode) if full_path.is_file() else 0o644
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    prefix=f".{full_path.name}.",
                    suffix=".tmp",
                    dir=os.fspath(full_path.parent),
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.chmod(temporary_path, target_mode)
                os.replace(os.fspath(temporary_path), os.fspath(full_path))
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()

        return f"Successfully wrote to {display_name}"
    except ValueError:
        return f"Error: Próba zapisu poza workspace: {display_name}"
    except Exception as exc:
        return f"Error writing file: {exc}"


def read_file_strict(
    filename: str,
    *,
    workspace_dir: Optional[PathValue] = None,
) -> str:
    """Read a UTF-8 file, preserving failures as exceptions for trusted callers."""
    workspace = get_workspace_dir(workspace_dir)
    full_path = _resolve_workspace_path(filename, workspace)
    if not full_path.exists():
        raise FileNotFoundError(f"workspace file does not exist: {filename}")

    with full_path.open("r", encoding="utf-8") as file:
        return file.read()


def read_file(
    filename: str,
    *,
    workspace_dir: Optional[PathValue] = None,
) -> str:
    """Odczytuje plik z workspace; legacy API koduje błędy jako tekst."""
    try:
        return read_file_strict(filename, workspace_dir=workspace_dir)
    except FileNotFoundError:
        return ""
    except UnicodeError as exc:
        return f"Error reading file: invalid UTF-8 data ({exc})"
    except ValueError:
        return "Error: Security violation."
    except Exception as exc:
        return f"Error reading file: {exc}"


def list_files(
    startpath: Optional[PathValue] = None,
    *,
    workspace_dir: Optional[PathValue] = None,
) -> str:
    """Zwraca deterministyczną, sformatowaną listę plików dla UI."""
    files = get_all_file_paths(startpath, workspace_dir=workspace_dir)
    return ", ".join(files) if files else "No files in workspace."


def get_all_file_paths(
    startpath: Optional[PathValue] = None,
    *,
    workspace_dir: Optional[PathValue] = None,
) -> list[str]:
    """Legacy listing API; return an empty list when the filesystem fails."""
    try:
        return get_all_file_paths_strict(startpath, workspace_dir=workspace_dir)
    except Exception:
        return []


def get_all_file_paths_strict(
    startpath: Optional[PathValue] = None,
    *,
    workspace_dir: Optional[PathValue] = None,
) -> list[str]:
    """Return a complete listing or raise when it cannot be established."""
    if startpath is not None and workspace_dir is not None:
        raise ValueError("startpath and workspace_dir are mutually exclusive")

    selected = startpath if startpath is not None else get_workspace_dir(workspace_dir)
    root_path = Path(_path_text(selected, "startpath")).resolve(strict=False)
    if not root_path.is_dir():
        return []

    def raise_walk_error(error: OSError) -> None:
        raise error

    file_list = []
    for root, dirs, files in os.walk(
        os.fspath(root_path), followlinks=False, onerror=raise_walk_error
    ):
        dirs[:] = sorted(
            directory
            for directory in dirs
            if directory.casefold() not in _IGNORED_PROJECT_DIRS
            and not Path(root, directory).is_symlink()
        )

        for name in sorted(files):
            absolute_path = Path(root, name)
            if absolute_path.is_symlink():
                continue
            relative_path = os.path.relpath(os.fspath(absolute_path), os.fspath(root_path))
            portable_path = relative_path.replace("\\", "/")
            if (
                name.casefold() in _IGNORED_PROJECT_FILES
                or is_sensitive_file(portable_path)
                or any(ord(character) < 32 or ord(character) == 127 for character in portable_path)
            ):
                continue
            file_list.append(portable_path)

    return sorted(file_list)


def _validate_backup_name(backup_name: PathValue) -> str:
    name = _path_text(backup_name, "backup_name").strip()
    drive, _ = ntpath.splitdrive(name)
    if (
        not name
        or drive
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or name.startswith(_INTERNAL_BACKUP_PREFIXES)
    ):
        raise ValueError("invalid backup name")
    return name


def _backup_root(backup_dir: Optional[PathValue], workspace_dir: Optional[PathValue]) -> Path:
    return Path(get_backup_dir(backup_dir, workspace_dir)).resolve(strict=False)


def _paths_overlap(first: Path, second: Path) -> bool:
    return _is_within(first, second) or _is_within(second, first)


def create_backup(
    custom_name: Optional[str] = None,
    *,
    workspace_dir: Optional[PathValue] = None,
    backup_dir: Optional[PathValue] = None,
) -> Optional[str]:
    """Tworzy kompletny backup workspace i zwraca jego ścieżkę.

    Istniejący backup o jawnie podanej nazwie jest zastępowany dopiero po
    poprawnym skopiowaniu nowej wersji.
    """
    staging = None
    try:
        workspace = Path(get_workspace_dir(workspace_dir)).resolve(strict=False)
        if not workspace.is_dir() or not any(workspace.iterdir()):
            return None

        configured_root = get_backup_dir(backup_dir, workspace_dir)
        root = Path(configured_root).resolve(strict=False)
        if _is_within(root, workspace):
            return None

        name = (
            _validate_backup_name(custom_name)
            if custom_name is not None
            else datetime.now().strftime("backup_%Y%m%d_%H%M%S_%f")
        )
        root.mkdir(parents=True, exist_ok=True)
        destination = root / name
        if _paths_overlap(destination.resolve(strict=False), workspace):
            return None
        if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
            return None

        staging = Path(tempfile.mkdtemp(prefix=".codefabric-backup-", dir=os.fspath(root)))
        shutil.copytree(
            os.fspath(workspace),
            os.fspath(staging),
            dirs_exist_ok=True,
            symlinks=True,
        )

        with _path_lock(destination):
            if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
                return None
            _atomic_replace_directory(staging, destination)
            staging = None
        return os.path.join(configured_root, name)
    except Exception as exc:
        print(f"⚠️ Błąd podczas tworzenia backupu: {exc}")
        return None
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def restore_backup(
    backup_name: str,
    *,
    workspace_dir: Optional[PathValue] = None,
    backup_dir: Optional[PathValue] = None,
) -> bool:
    """Atomowo przywraca workspace ze wskazanego backupu."""
    staging = None
    try:
        name = _validate_backup_name(backup_name)
        root = _backup_root(backup_dir, workspace_dir)
        source = root / name
        if source.is_symlink() or not source.is_dir():
            print(f"⚠️ Backup {name} nie istnieje.")
            return False

        workspace = Path(get_workspace_dir(workspace_dir)).resolve(strict=False)
        if _paths_overlap(source.resolve(strict=False), workspace):
            return False

        workspace.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=".codefabric-restore-", dir=os.fspath(workspace.parent))
        )
        shutil.copytree(
            os.fspath(source),
            os.fspath(staging),
            dirs_exist_ok=True,
            symlinks=True,
        )

        with _path_lock(workspace):
            _atomic_replace_directory(staging, workspace)
            staging = None
        print(f"✅ Przywrócono backup: {name}")
        return True
    except Exception as exc:
        print(f"⚠️ Błąd podczas przywracania backupu: {exc}")
        return False
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def list_backups(
    *,
    workspace_dir: Optional[PathValue] = None,
    backup_dir: Optional[PathValue] = None,
) -> list[str]:
    """Zwraca deterministyczną listę backupów od najnowszej nazwy."""
    try:
        root = _backup_root(backup_dir, workspace_dir)
        if not root.is_dir():
            return []

        backups = []
        workspace = Path(get_workspace_dir(workspace_dir)).resolve(strict=False)
        with os.scandir(os.fspath(root)) as entries:
            for entry in entries:
                if entry.name.startswith(_INTERNAL_BACKUP_PREFIXES):
                    continue
                try:
                    _validate_backup_name(entry.name)
                except ValueError:
                    continue
                entry_path = Path(entry.path).resolve(strict=False)
                if entry.is_dir(follow_symlinks=False) and not _paths_overlap(
                    entry_path, workspace
                ):
                    backups.append(entry.name)
        return sorted(backups, reverse=True)
    except Exception:
        # Publiczne API listowania historycznie zwraca pustą listę przy błędzie.
        return []


def delete_backup(
    backup_name: str,
    *,
    workspace_dir: Optional[PathValue] = None,
    backup_dir: Optional[PathValue] = None,
) -> bool:
    """Usuwa wyłącznie rzeczywisty katalog backupu o bezpiecznej nazwie."""
    try:
        name = _validate_backup_name(backup_name)
        destination = _backup_root(backup_dir, workspace_dir) / name
        workspace = Path(get_workspace_dir(workspace_dir)).resolve(strict=False)
        if _paths_overlap(destination.resolve(strict=False), workspace):
            return False
        with _path_lock(destination):
            if destination.is_symlink() or not destination.is_dir():
                return False
            shutil.rmtree(destination)
        print(f"🗑️ Usunięto backup: {name}")
        return True
    except Exception as exc:
        print(f"⚠️ Błąd podczas usuwania backupu: {exc}")
        return False


def clean_old_backups(
    keep_last: int = 5,
    *,
    workspace_dir: Optional[PathValue] = None,
    backup_dir: Optional[PathValue] = None,
) -> None:
    """Usuwa stare backupy, zachowując ``keep_last`` najnowszych nazw."""
    if isinstance(keep_last, bool) or not isinstance(keep_last, int) or keep_last < 0:
        print("⚠️ Błąd podczas czyszczenia backupów: keep_last musi być >= 0")
        return

    backups = list_backups(workspace_dir=workspace_dir, backup_dir=backup_dir)
    to_delete = backups[keep_last:]
    deleted = 0
    for backup in to_delete:
        if delete_backup(backup, workspace_dir=workspace_dir, backup_dir=backup_dir):
            deleted += 1

    if deleted:
        print(f"🧹 Wyczyszczono {deleted} starych backupów.")
