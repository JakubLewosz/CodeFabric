import os

# Katalog roboczy
WORKSPACE_DIR = "./workspace"

def write_file(filename: str, content: str) -> str:
    """
    Zapisuje treść do pliku, tworząc niezbędne podkatalogi.
    """
    try:
        # 1. Normalizacja ścieżki (zamiana \ na / dla spójności)
        filename = filename.strip().replace("\\", "/")
        
        # Usuwamy ewentualny ukośnik na początku, żeby os.path.join działał poprawnie
        if filename.startswith("/"):
            filename = filename[1:]

        # 2. Budowanie pełnej ścieżki
        full_path = os.path.abspath(os.path.join(WORKSPACE_DIR, filename))
        workspace_abs = os.path.abspath(WORKSPACE_DIR)

        # 3. ZABEZPIECZENIE (Sandbox)
        # Sprawdzamy, czy plik nadal ląduje wewnątrz workspace
        if not full_path.startswith(workspace_abs):
            return f"Error: Próba zapisu poza workspace: {filename}"

        # 4. Tworzenie folderów (jeśli nie istnieją)
        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"DEBUG: Utworzono katalog: {directory}")

        # 5. Zapis pliku
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"Successfully wrote to {filename}"

    except Exception as e:
        return f"Error writing file: {str(e)}"

def read_file(filename: str) -> str:
    """Odczytuje treść pliku z workspace."""
    try:
        full_path = os.path.abspath(os.path.join(WORKSPACE_DIR, filename))
        workspace_abs = os.path.abspath(WORKSPACE_DIR)
        
        if not full_path.startswith(workspace_abs):
            return "Error: Security violation."

        if not os.path.exists(full_path):
            return "Error: File does not exist."
            
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def list_files(startpath=WORKSPACE_DIR) -> str:
    """
    Rekurencyjnie listuje pliki, pokazując strukturę folderów.
    """
    try:
        file_list = []
        for root, dirs, files in os.walk(startpath):
            for name in files:
                # Tworzymy ścieżkę relatywną (np. css/style.css)
                absolute_path = os.path.join(root, name)
                relative_path = os.path.relpath(absolute_path, startpath)
                file_list.append(relative_path.replace("\\", "/"))
                
        return ", ".join(file_list) if file_list else "No files in workspace."
    except Exception as e:
        return f"Error listing files: {str(e)}"