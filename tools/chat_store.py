"""Persistent storage for CodeFabric projects.

The Streamlit UI reruns the application on every interaction.  Keeping all
filesystem concerns in this module makes those reruns predictable and keeps
project data isolated from the repository itself.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PROJECT_NAME = "Nowy projekt"
_CHAT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_BACKUP_NAME_PATTERN = re.compile(r"^backup_[A-Za-z0-9_-]+$")
_UTC_BACKUP_PATTERN = re.compile(r"^backup_(?P<timestamp>\d{8}T\d{6}(?:_\d{1,6})?Z)$")
_LEGACY_BACKUP_PATTERN = re.compile(r"^backup_(?P<timestamp>\d{8}_\d{6}(?:_\d{1,6})?)$")
_MIN_UTC = datetime.min.replace(tzinfo=timezone.utc)


class ChatStoreError(RuntimeError):
    """Raised when project data cannot be read or written safely."""


class InvalidChatId(ChatStoreError, ValueError):
    """Raised when a project identifier could escape the data directory."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_timezone_at(value: datetime) -> tzinfo:
    """Return the system-local offset applicable to a legacy naive value."""
    return value.astimezone().tzinfo or timezone.utc


def _normalize_timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp and normalize it to an aware UTC datetime.

    Current state files include an explicit offset.  State files created by
    older CodeFabric versions used naive local time, which must be localized
    before values from both generations can be compared chronologically.
    """
    if not isinstance(value, str) or not value.strip():
        return None

    candidate = value.strip()
    if candidate[-1:] in {"Z", "z"}:
        candidate = f"{candidate[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=_local_timezone_at(parsed))
        return parsed.astimezone(timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _backup_timestamp(name: str) -> datetime | None:
    """Parse current UTC and legacy local backup directory names."""
    utc_match = _UTC_BACKUP_PATTERN.fullmatch(name)
    if utc_match:
        raw_timestamp = utc_match.group("timestamp")
        format_string = "%Y%m%dT%H%M%S_%fZ" if "_" in raw_timestamp else "%Y%m%dT%H%M%SZ"
        try:
            return datetime.strptime(raw_timestamp, format_string).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    legacy_match = _LEGACY_BACKUP_PATTERN.fullmatch(name)
    if not legacy_match:
        return None

    raw_timestamp = legacy_match.group("timestamp")
    format_string = "%Y%m%d_%H%M%S_%f" if raw_timestamp.count("_") == 2 else "%Y%m%d_%H%M%S"
    try:
        local_timestamp = datetime.strptime(raw_timestamp, format_string)
        return local_timestamp.replace(tzinfo=_local_timezone_at(local_timestamp)).astimezone(
            timezone.utc
        )
    except (OSError, OverflowError, ValueError):
        return None


def _chronological_key(value: Any, fallback: str) -> tuple[bool, datetime, str]:
    timestamp = _normalize_timestamp(value)
    return timestamp is not None, timestamp or _MIN_UTC, fallback


def _backup_sort_key(name: str) -> tuple[bool, datetime, str]:
    timestamp = _backup_timestamp(name)
    return timestamp is not None, timestamp or _MIN_UTC, name


class ChatStore:
    """Store project metadata, workspaces and backups below one root path."""

    def __init__(self, root: os.PathLike[str] | str):
        try:
            self.root = Path(root).expanduser().resolve()
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ChatStoreError("Nie można przygotować katalogu danych CodeFabric.") from exc

    @staticmethod
    def project_name(first_message: str, max_length: int = 48) -> str:
        """Build a compact, single-line display name from a user prompt."""
        clean = " ".join(str(first_message).split())
        return clean[:max_length].strip() or DEFAULT_PROJECT_NAME

    def _contained_path(self, path: Path) -> Path:
        try:
            resolved = path.resolve(strict=False)
        except OSError as exc:
            raise ChatStoreError("Nie można bezpiecznie rozwiązać ścieżki projektu.") from exc
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise InvalidChatId("Ścieżka projektu wychodzi poza katalog danych.") from exc
        return path

    def chat_dir(self, chat_id: str) -> Path:
        if not isinstance(chat_id, str) or not _CHAT_ID_PATTERN.fullmatch(chat_id):
            raise InvalidChatId(f"Nieprawidłowy identyfikator projektu: {chat_id!r}")
        return self._contained_path(self.root / chat_id)

    def state_path(self, chat_id: str) -> Path:
        return self._contained_path(self.chat_dir(chat_id) / "state.json")

    def workspace_path(self, chat_id: str) -> Path:
        return self._contained_path(self.chat_dir(chat_id) / "workspace")

    def backups_path(self, chat_id: str) -> Path:
        return self._contained_path(self.chat_dir(chat_id) / "backups")

    def create(self) -> str:
        """Create an empty project and return its collision-resistant ID."""
        for _ in range(10):
            chat_id = uuid.uuid4().hex[:12]
            chat_dir = self.chat_dir(chat_id)
            try:
                chat_dir.mkdir(parents=False)
            except FileExistsError:
                continue
            except OSError as exc:
                raise ChatStoreError("Nie udało się utworzyć katalogu projektu.") from exc

            try:
                self.workspace_path(chat_id).mkdir()
                now = _utc_now()
                self.save(
                    chat_id,
                    {
                        "name": DEFAULT_PROJECT_NAME,
                        "created": now,
                        "updated": now,
                        "messages": [],
                    },
                )
            except (ChatStoreError, OSError) as exc:
                shutil.rmtree(chat_dir, ignore_errors=True)
                if isinstance(exc, ChatStoreError):
                    raise
                raise ChatStoreError("Nie udało się zainicjalizować projektu.") from exc
            return chat_id

        raise ChatStoreError("Nie udało się utworzyć unikalnego identyfikatora projektu.")

    def load(self, chat_id: str) -> dict[str, Any] | None:
        """Load one project state, returning ``None`` when it does not exist."""
        try:
            state_path = self.state_path(chat_id)
            if not state_path.exists():
                return None
            if state_path.is_symlink():
                raise ChatStoreError("Plik stanu projektu nie może być dowiązaniem symbolicznym.")
            with state_path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ChatStoreError(f"Nie można odczytać stanu projektu {chat_id}.") from exc

        if not isinstance(state, dict):
            raise ChatStoreError(f"Stan projektu {chat_id} ma nieprawidłowy format.")
        if not isinstance(state.get("messages", []), list):
            raise ChatStoreError(f"Historia projektu {chat_id} ma nieprawidłowy format.")
        return state

    def save(self, chat_id: str, state: dict[str, Any]) -> None:
        """Atomically save JSON-serializable project state."""
        if not isinstance(state, dict):
            raise TypeError("Stan projektu musi być słownikiem.")

        chat_dir = self.chat_dir(chat_id)
        try:
            chat_dir.mkdir(parents=True, exist_ok=True)
            self.workspace_path(chat_id).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ChatStoreError(f"Nie można przygotować katalogu projektu {chat_id}.") from exc

        previous = self.load(chat_id) or {}
        payload = dict(state)
        payload.setdefault("name", previous.get("name", DEFAULT_PROJECT_NAME))
        payload.setdefault("created", previous.get("created", _utc_now()))
        payload.setdefault("messages", previous.get("messages", []))
        payload["updated"] = payload.get("updated") or _utc_now()

        try:
            serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as exc:
            raise ChatStoreError("Stan projektu zawiera dane, których nie można zapisać.") from exc

        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=chat_dir,
                prefix=".state-",
                suffix=".json.tmp",
                delete=False,
            ) as handle:
                temporary_path = handle.name
                handle.write(serialized)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.state_path(chat_id))
        except OSError as exc:
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)
            raise ChatStoreError(f"Nie można zapisać stanu projektu {chat_id}.") from exc

    def save_messages(
        self,
        chat_id: str,
        messages: list[dict[str, str]],
        *,
        name: str | None = None,
    ) -> None:
        """Update user-visible history without serializing runtime graph objects."""
        state = self.load(chat_id) or {}
        state.pop("graph_state", None)  # migrate legacy state files lazily
        state["messages"] = messages
        if name is not None:
            state["name"] = name
        state["updated"] = _utc_now()
        self.save(chat_id, state)

    def list(self) -> list[dict[str, str]]:
        """Return valid projects, ordered by most recent activity."""
        projects: list[dict[str, str]] = []
        try:
            children = list(self.root.iterdir())
        except OSError as exc:
            raise ChatStoreError("Nie można odczytać katalogu projektów.") from exc
        for child in children:
            if not child.is_dir() or child.is_symlink():
                continue
            try:
                state = self.load(child.name)
            except (ChatStoreError, InvalidChatId):
                continue
            if state is None:
                continue
            projects.append(
                {
                    "id": child.name,
                    "name": str(state.get("name") or DEFAULT_PROJECT_NAME),
                    "updated": str(state.get("updated") or ""),
                }
            )
        return sorted(
            projects,
            key=lambda item: _chronological_key(item["updated"], item["id"]),
            reverse=True,
        )

    def delete(self, chat_id: str) -> None:
        """Delete exactly one validated project directory."""
        chat_dir = self.chat_dir(chat_id)
        if not chat_dir.exists():
            return
        if chat_dir.is_symlink():
            raise ChatStoreError("Katalog projektu nie może być dowiązaniem symbolicznym.")
        try:
            shutil.rmtree(chat_dir)
        except OSError as exc:
            raise ChatStoreError(f"Nie można usunąć projektu {chat_id}.") from exc

    def create_backup(self, chat_id: str) -> str | None:
        """Snapshot a non-empty workspace and return the backup name."""
        staging_path = None
        try:
            workspace = self.workspace_path(chat_id)
            if not workspace.is_dir() or not any(workspace.iterdir()):
                return None

            backups_dir = self.backups_path(chat_id)
            backups_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            backup_name = f"backup_{timestamp}"
            backup_path = self._contained_path(backups_dir / backup_name)
            staging_path = self._contained_path(backups_dir / f".backup-staging-{uuid.uuid4().hex}")
            shutil.copytree(workspace, staging_path, symlinks=True)
            os.replace(staging_path, backup_path)
        except OSError as exc:
            if staging_path is not None and staging_path.exists():
                shutil.rmtree(staging_path, ignore_errors=True)
            raise ChatStoreError("Nie udało się utworzyć backupu projektu.") from exc
        return backup_name

    def list_backups(self, chat_id: str) -> list[str]:
        try:
            backups_dir = self.backups_path(chat_id)
            if not backups_dir.exists():
                return []
            backup_names = (
                path.name
                for path in backups_dir.iterdir()
                if path.is_dir()
                and not path.is_symlink()
                and _BACKUP_NAME_PATTERN.fullmatch(path.name)
            )
            return sorted(backup_names, key=_backup_sort_key, reverse=True)
        except OSError as exc:
            raise ChatStoreError("Nie można odczytać listy backupów projektu.") from exc

    def restore_latest_backup(self, chat_id: str) -> str | None:
        backups = self.list_backups(chat_id)
        if not backups:
            return None
        self.restore_backup(chat_id, backups[0])
        return backups[0]

    def restore_backup(self, chat_id: str, backup_name: str) -> None:
        """Restore a backup using same-filesystem renames for safe rollback."""
        if not _BACKUP_NAME_PATTERN.fullmatch(backup_name):
            raise ChatStoreError("Nieprawidłowa nazwa backupu.")

        workspace = None
        restored = None
        previous = None
        previous_moved = False

        try:
            chat_dir = self.chat_dir(chat_id)
            backup_path = self._contained_path(self.backups_path(chat_id) / backup_name)
            if not backup_path.is_dir() or backup_path.is_symlink():
                raise ChatStoreError(f"Backup {backup_name} nie istnieje.")

            workspace = self.workspace_path(chat_id)
            restored = self._contained_path(chat_dir / f".workspace-restore-{uuid.uuid4().hex}")
            previous = self._contained_path(chat_dir / f".workspace-previous-{uuid.uuid4().hex}")
            shutil.copytree(backup_path, restored, symlinks=True)
            if workspace.exists():
                os.replace(workspace, previous)
                previous_moved = True
            os.replace(restored, workspace)
        except OSError as exc:
            recovery_error = None
            if (
                previous_moved
                and workspace is not None
                and previous is not None
                and not workspace.exists()
                and previous.exists()
            ):
                try:
                    os.replace(previous, workspace)
                except OSError as recovery_exc:
                    recovery_error = recovery_exc
            if restored is not None and restored.exists():
                shutil.rmtree(restored, ignore_errors=True)
            if recovery_error is not None and previous is not None:
                raise ChatStoreError(
                    "Przywrócenie i automatyczny rollback nie powiodły się. "
                    f"Poprzedni workspace można odzyskać z: {previous}"
                ) from recovery_error
            raise ChatStoreError(f"Nie udało się przywrócić backupu {backup_name}.") from exc

        # Cleanup happens only after the restored workspace is in place.  A
        # stale recovery directory is harmless and must not turn a successful
        # rollback into a reported failure.
        if previous_moved and previous is not None:
            shutil.rmtree(previous, ignore_errors=True)

    def iter_workspace_files(self, chat_id: str) -> Iterable[tuple[Path, str]]:
        workspace = self.workspace_path(chat_id)
        if not workspace.exists():
            return
        for path in sorted(workspace.rglob("*")):
            if path.is_file() and not path.is_symlink():
                yield path, path.relative_to(workspace).as_posix()

    def build_zip(self, chat_id: str) -> bytes | None:
        """Create a project archive in memory, leaving no file in the repo."""
        files = list(self.iter_workspace_files(chat_id))
        if not files:
            return None

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, relative_name in files:
                archive.write(path, relative_name)
        return buffer.getvalue()
