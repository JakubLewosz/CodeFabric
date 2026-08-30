"""Explicit workspace access without mutating module-level configuration."""

from typing import Optional

from tools.file_ops import (
    get_all_file_paths_strict,
    get_workspace_dir,
    read_file_strict,
    write_file,
)


class WorkspaceReadError(RuntimeError):
    """Raised when an existing workspace file cannot be read safely as text."""


class WorkspaceListError(RuntimeError):
    """Raised when the workspace cannot be listed completely."""


class WorkspaceFiles:
    """Read and write one explicitly selected project workspace."""

    def __init__(self, root: Optional[str] = None):
        self.root = get_workspace_dir(root)

    def read(self, filename: str) -> str:
        try:
            return self.read_strict(filename)
        except WorkspaceReadError as exc:
            print(f"⚠️ Nie udało się odczytać {filename}: {exc}")
            return ""

    def read_strict(self, filename: str) -> str:
        """Read text while preserving the distinction between empty and failed."""
        try:
            return read_file_strict(filename, workspace_dir=self.root)
        except Exception as exc:
            raise WorkspaceReadError(str(exc)) from exc

    def write(self, filename: str, content: str) -> bool:
        result = write_file(filename, str(content), workspace_dir=self.root)
        if result.startswith("Successfully wrote to "):
            return True
        print(f"⚠️ Nie udało się zapisać {filename}: {result}")
        return False

    def list(self) -> list[str]:
        """Return a stable, complete snapshot or fail closed."""
        try:
            return get_all_file_paths_strict(workspace_dir=self.root)
        except Exception as exc:
            raise WorkspaceListError(str(exc)) from exc
