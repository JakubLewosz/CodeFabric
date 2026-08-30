"""Shared rules for project files that are safe to send to text models."""

from pathlib import PurePath

TEXT_FILE_EXTENSIONS = frozenset(
    {
        ".bash",
        ".bat",
        ".build",
        ".c",
        ".cfg",
        ".cmd",
        ".conf",
        ".cpp",
        ".cs",
        ".css",
        ".csv",
        ".dart",
        ".erl",
        ".ex",
        ".exs",
        ".gradle",
        ".go",
        ".gql",
        ".graphql",
        ".h",
        ".hpp",
        ".html",
        ".ini",
        ".java",
        ".js",
        ".json",
        ".jsonc",
        ".jsx",
        ".kt",
        ".kts",
        ".less",
        ".lock",
        ".lua",
        ".md",
        ".mdx",
        ".mjs",
        ".mod",
        ".php",
        ".proto",
        ".ps1",
        ".py",
        ".pyi",
        ".rb",
        ".rs",
        ".rst",
        ".sass",
        ".scss",
        ".sh",
        ".sql",
        ".svg",
        ".svelte",
        ".sum",
        ".swift",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".vue",
        ".xml",
        ".yaml",
        ".yml",
        ".zsh",
    }
)

TEXT_FILE_NAMES = frozenset(
    {
        ".dockerignore",
        ".editorconfig",
        ".env.example",
        ".env.sample",
        ".env.template",
        ".flake8",
        ".gitattributes",
        ".gitignore",
        "authors",
        "brewfile",
        "build",
        "changelog",
        "cname",
        "codeowners",
        "dockerfile",
        "gemfile",
        "gradlew",
        "jenkinsfile",
        "justfile",
        "license",
        "makefile",
        "mvnw",
        "notice",
        "pipfile",
        "podfile",
        "procfile",
        "rakefile",
        "tiltfile",
        "vagrantfile",
        "workspace",
    }
)
INTERNAL_ARTIFACT_NAMES = frozenset(
    {"error_log.txt", "error_report.txt", "failure_report.md", "review_report.md"}
)
SENSITIVE_FILE_NAMES = frozenset(
    {
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials",
        "credentials.json",
        "secrets.json",
        "secrets.toml",
        "secrets.yaml",
        "secrets.yml",
        "token.json",
    }
)
SENSITIVE_FILE_EXTENSIONS = frozenset({".jks", ".key", ".keystore", ".p12", ".pem", ".pfx"})
SAFE_ENV_EXAMPLES = frozenset({".env.example", ".env.sample", ".env.template"})


def is_internal_artifact(path: object) -> bool:
    """Return whether a file is a CodeFabric diagnostic, not project source."""
    if not isinstance(path, str) or not path.strip():
        return False
    name = PurePath(path).name.lower()
    return name in INTERNAL_ARTIFACT_NAMES or name.startswith("debug_diff_fail_")


def is_sensitive_file(path: object) -> bool:
    """Identify common credential files that must never enter an LLM prompt."""
    if not isinstance(path, str) or not path.strip():
        return False
    pure_path = PurePath(path.replace("\\", "/"))
    name = pure_path.name.lower()
    parts = {part.lower() for part in pure_path.parts}
    if name == ".env" or (name.startswith(".env.") and name not in SAFE_ENV_EXAMPLES):
        return True
    if name in SENSITIVE_FILE_NAMES or pure_path.suffix.lower() in SENSITIVE_FILE_EXTENSIONS:
        return True
    if ".ssh" in parts or ".aws" in parts:
        return True
    if ".streamlit" in parts and name.startswith("secrets."):
        return True
    if name.startswith("client_secret") and pure_path.suffix.lower() == ".json":
        return True
    return "service-account" in name and pure_path.suffix.lower() == ".json"


def is_text_file(path: object) -> bool:
    """Return whether a project path is a supported, model-readable text file."""
    if not isinstance(path, str) or not path.strip():
        return False
    name = PurePath(path).name.lower()
    if is_internal_artifact(path) or is_sensitive_file(path):
        return False
    return (
        name in TEXT_FILE_NAMES
        or name.startswith("dockerfile.")
        or PurePath(name).suffix.lower() in TEXT_FILE_EXTENSIONS
    )
