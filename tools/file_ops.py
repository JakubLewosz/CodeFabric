# Plik: tools/file_ops.py
import os

# Ustalmy na sztywno katalog roboczy dla bezpieczeństwa
WORKSPACE_DIR = "./workspace"

def write_file(filename: str, content: str) -> str:
    """Zapisuje treść do pliku w katalogu workspace."""
    try:
        # Zabezpieczenie: usuń ewentualne próby wyjścia z katalogu (..)
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(WORKSPACE_DIR, safe_filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {safe_filename}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def read_file(filename: str) -> str:
    """Odczytuje treść pliku z katalogu workspace."""
    try:
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(WORKSPACE_DIR, safe_filename)
        
        if not os.path.exists(file_path):
            return "Error: File does not exist."
            
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def list_files() -> str:
    """Zwraca listę plików w workspace."""
    try:
        files = os.listdir(WORKSPACE_DIR)
        return ", ".join(files) if files else "No files in workspace."
    except Exception as e:
        return f"Error listing files: {str(e)}"