import os
import shutil
import time

# Katalog roboczy (może być zmieniony dynamicznie)
WORKSPACE_DIR = "./workspace"

def get_workspace_dir():
    """Zwraca aktualny workspace (może być podmieniony)"""
    return WORKSPACE_DIR

def write_file(filename: str, content: str) -> str:
    """Zapisuje treść do pliku, tworząc niezbędne podkatalogi."""
    try:
        workspace = get_workspace_dir()
        filename = filename.strip().replace("\\", "/")
        if filename.startswith("/"): 
            filename = filename[1:]
        
        full_path = os.path.abspath(os.path.join(workspace, filename))
        workspace_abs = os.path.abspath(workspace)

        if not full_path.startswith(workspace_abs):
            return f"Error: Próba zapisu poza workspace: {filename}"

        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"Successfully wrote to {filename}"

    except Exception as e:
        return f"Error writing file: {str(e)}"

def read_file(filename: str) -> str:
    """Odczytuje treść pliku z workspace."""
    try:
        workspace = get_workspace_dir()
        full_path = os.path.abspath(os.path.join(workspace, filename))
        workspace_abs = os.path.abspath(workspace)
        
        if not full_path.startswith(workspace_abs):
            return "Error: Security violation."

        if not os.path.exists(full_path):
            return ""
            
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def list_files(startpath=None) -> str:
    """Zwraca sformatowany string dla człowieka (do UI)."""
    if startpath is None:
        startpath = get_workspace_dir()
    files = get_all_file_paths(startpath)
    return ", ".join(files) if files else "No files in workspace."

def get_all_file_paths(startpath=None) -> list[str]:
    """
    Zwraca czystą listę ścieżek dla Agentów.
    Używane przez Codera do skanowania projektu.
    """
    if startpath is None:
        startpath = get_workspace_dir()
        
    file_list = []
    try:
        if not os.path.exists(startpath): 
            return []
        
        for root, dirs, files in os.walk(startpath):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
            
            for name in files:
                if name.startswith('.') or name == '.gitkeep': 
                    continue
                    
                absolute_path = os.path.join(root, name)
                relative_path = os.path.relpath(absolute_path, startpath)
                file_list.append(relative_path.replace("\\", "/"))
        
        return file_list
    except Exception:
        return []

# === NOWE FUNKCJE BACKUP ===

def create_backup(custom_name: str = None) -> str:
    """
    Tworzy backup obecnego workspace.
    Returns: ścieżka do backupu lub None jeśli workspace pusty
    """
    try:
        if not os.path.exists(WORKSPACE_DIR) or not os.listdir(WORKSPACE_DIR):
            return None
        
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        if custom_name:
            backup_path = os.path.join(BACKUP_DIR, custom_name)
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
        
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
        
        shutil.copytree(WORKSPACE_DIR, backup_path)
        return backup_path
        
    except Exception as e:
        print(f"⚠️ Błąd podczas tworzenia backupu: {e}")
        return None

def restore_backup(backup_name: str) -> bool:
    """
    Przywraca workspace z backupu.
    Returns: True jeśli sukces, False jeśli błąd
    """
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        if not os.path.exists(backup_path):
            print(f"⚠️ Backup {backup_name} nie istnieje.")
            return False
        
        if os.path.exists(WORKSPACE_DIR):
            shutil.rmtree(WORKSPACE_DIR)
        
        shutil.copytree(backup_path, WORKSPACE_DIR)
        print(f"✅ Przywrócono backup: {backup_name}")
        return True
        
    except Exception as e:
        print(f"⚠️ Błąd podczas przywracania backupu: {e}")
        return False

def list_backups() -> list[str]:
    """Zwraca listę dostępnych backupów (posortowane od najnowszych)."""
    try:
        if not os.path.exists(BACKUP_DIR):
            return []
        
        backups = [d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))]
        return sorted(backups, reverse=True)
        
    except Exception:
        return []

def delete_backup(backup_name: str) -> bool:
    """Usuwa określony backup."""
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
            print(f"🗑️ Usunięto backup: {backup_name}")
            return True
        return False
        
    except Exception as e:
        print(f"⚠️ Błąd podczas usuwania backupu: {e}")
        return False

def clean_old_backups(keep_last: int = 5):
    """
    Usuwa stare backupy, zachowując tylko N najnowszych.
    """
    try:
        backups = list_backups()
        
        if len(backups) <= keep_last:
            return
        
        to_delete = backups[keep_last:]
        for backup in to_delete:
            delete_backup(backup)
        
        print(f"🧹 Wyczyszczono {len(to_delete)} starych backupów.")
        
    except Exception as e:
        print(f"⚠️ Błąd podczas czyszczenia backupów: {e}")