#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ -n "${CODEFABRIC_PYTHON:-}" ]]; then
    codefabric_python="$CODEFABRIC_PYTHON"
elif [[ -x ".venv/bin/python" ]]; then
    codefabric_python=".venv/bin/python"
elif command -v python >/dev/null 2>&1; then
    codefabric_python="python"
else
    codefabric_python="python3"
fi

if ! "$codefabric_python" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "CodeFabric wymaga Python 3.10+. Usuń stare .venv lub ustaw CODEFABRIC_PYTHON." >&2
    exit 2
fi

"$codefabric_python" -m compileall -q app.py state.py agents graph tools debug_raw.py
"$codefabric_python" -m ruff format --check .
"$codefabric_python" -m ruff check .
"$codefabric_python" -m pytest
