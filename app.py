import streamlit as st
import os
import time
import shutil
import json
import uuid
from datetime import datetime
from graph.workflow import app
from langchain_core.messages import HumanMessage
from tools.file_ops import list_files, read_file, get_all_file_paths, write_file

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="CodeFabric | AI Software House",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "CodeFabric - Autonomiczny zespół AI do tworzenia oprogramowania"
    }
)

# --- KONFIGURACJA CHATÓW ---
CHATS_DIR = "./chats"
os.makedirs(CHATS_DIR, exist_ok=True)

def get_chat_workspace(chat_id: str) -> str:
    """Zwraca ścieżkę do workspace danego chatu"""
    return os.path.join(CHATS_DIR, chat_id, "workspace")

def get_chat_state_file(chat_id: str) -> str:
    """Zwraca ścieżkę do pliku state danego chatu"""
    return os.path.join(CHATS_DIR, chat_id, "state.json")

def save_chat_state(chat_id: str, state: dict):
    """Zapisuje stan chatu do pliku"""
    os.makedirs(os.path.join(CHATS_DIR, chat_id), exist_ok=True)
    with open(get_chat_state_file(chat_id), 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)

def load_chat_state(chat_id: str) -> dict:
    """Wczytuje stan chatu z pliku"""
    state_file = get_chat_state_file(chat_id)
    if os.path.exists(state_file):
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def list_all_chats() -> list:
    """Zwraca listę wszystkich chatów (id, nazwa, data)"""
    chats = []
    if not os.path.exists(CHATS_DIR):
        return chats
    
    for chat_id in os.listdir(CHATS_DIR):
        state_file = get_chat_state_file(chat_id)
        if os.path.exists(state_file):
            state = load_chat_state(chat_id)
            chats.append({
                'id': chat_id,
                'name': state.get('name', 'Nowy projekt'),
                'updated': state.get('updated', '')
            })
    
    chats.sort(key=lambda x: x['updated'], reverse=True)
    return chats

def generate_chat_name(first_message: str) -> str:
    """Generuje nazwę chatu na podstawie pierwszego prompta"""
    name = first_message[:30].strip()
    name = ' '.join(name.split())
    return name if name else "Nowy projekt"

def create_new_chat() -> str:
    """Tworzy nowy chat i zwraca jego ID"""
    chat_id = str(uuid.uuid4())[:8]
    os.makedirs(get_chat_workspace(chat_id), exist_ok=True)
    
    save_chat_state(chat_id, {
        'name': 'Nowy projekt',
        'created': datetime.now().isoformat(),
        'updated': datetime.now().isoformat(),
        'messages': []
    })
    
    return chat_id

# --- DOSTĘPNE MODELE ---
AVAILABLE_MODELS = [
    "qwen3-coder:30b", "bielik2.6:11b", "mistral-small3.2:24b", "gemma3:27b", 
    "qwq:32b", "llama3.3:70b", "mistral:7b", "llama4:16x17b", "gpt-oss-safeguard:20b"
]

# --- CSS ---
def inject_custom_css():
    st.markdown("""
    <style>
        .main { background-color: #0E1117; }
        h1 {
            background: -webkit-linear-gradient(45deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
        .stButton>button {
            background: linear-gradient(90deg, #2b5876 0%, #4e4376 100%);
            color: white; border: none; border-radius: 8px; height: 45px; font-weight: 600;
            transition: all 0.3s ease;
        }
        .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        .stChatMessage { background-color: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 10px; margin-bottom: 10px; }
        .stStatusWidget { background-color: #0d1117; border: 1px solid #30363d; font-family: 'Courier New', monospace; color: #58a6ff; }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# === INICJALIZACJA AKTYWNEGO CHATU ===
if "active_chat_id" not in st.session_state:
    existing_chats = list_all_chats()
    if existing_chats:
        st.session_state["active_chat_id"] = existing_chats[0]['id']
    else:
        st.session_state["active_chat_id"] = create_new_chat()

# --- FUNKCJA BACKUP ---
def create_backup():
    """Tworzy backup workspace aktywnego chatu"""
    chat_id = st.session_state.get("active_chat_id")
    if not chat_id:
        return None
    
    chat_workspace = get_chat_workspace(chat_id)
    if os.path.exists(chat_workspace) and os.listdir(chat_workspace):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backups_dir = os.path.join(CHATS_DIR, chat_id, "backups")
        os.makedirs(backups_dir, exist_ok=True)
        backup_path = os.path.join(backups_dir, f"backup_{timestamp}")
        shutil.copytree(chat_workspace, backup_path)
        return backup_path
    return None

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=60)
    st.markdown("### **CodeFabric**")
    st.divider()
    
    # === SEKCJA: PROJEKTY ===
    st.markdown("#### 💬 Projekty")
    
    if st.button("➕ Nowy projekt", use_container_width=True, type="primary"):
        new_chat_id = create_new_chat()
        st.session_state["active_chat_id"] = new_chat_id
        st.session_state["messages"] = [{"role": "assistant", "content": "Cześć! Co dzisiaj budujemy?"}]
        st.session_state["current_chat_loaded"] = new_chat_id
        if "graph_state" in st.session_state:
            del st.session_state["graph_state"]
        st.session_state["pipeline_active"] = False
        st.rerun()
    
    # Lista chatów
    all_chats = list_all_chats()
    if all_chats:
        st.markdown("**Ostatnie:**")
        for chat in all_chats[:5]:
            is_active = chat['id'] == st.session_state["active_chat_id"]
            display_name = chat['name'][:30] + "..." if len(chat['name']) > 30 else chat['name']
            
            button_label = f"{'▶ ' if is_active else '○ '}{display_name}"
            
            if st.button(
                button_label,
                key=f"chat_{chat['id']}",
                use_container_width=True,
                disabled=is_active,
                type="primary" if is_active else "secondary"
            ):
                chat_state = load_chat_state(st.session_state["active_chat_id"])
                save_chat_state(st.session_state["active_chat_id"], {
                    'name': chat_state.get('name', 'Nowy projekt') if chat_state else 'Nowy projekt',
                    'updated': datetime.now().isoformat(),
                    'messages': st.session_state.get("messages", []),
                    'graph_state': st.session_state.get("graph_state", {})
                })
                
                st.session_state["active_chat_id"] = chat['id']
                st.session_state["current_chat_loaded"] = None
                if "graph_state" in st.session_state:
                    del st.session_state["graph_state"]
                st.rerun()
        
        # Delete button
        st.divider()
        if st.button("🗑️ Usuń aktywny projekt", use_container_width=True, key="delete_active"):
            active_id = st.session_state["active_chat_id"]
            shutil.rmtree(os.path.join(CHATS_DIR, active_id))
            remaining = [c for c in all_chats if c['id'] != active_id]
            if remaining:
                st.session_state["active_chat_id"] = remaining[0]['id']
            else:
                new_id = create_new_chat()
                st.session_state["active_chat_id"] = new_id
            st.session_state["current_chat_loaded"] = None
            if "graph_state" in st.session_state:
                del st.session_state["graph_state"]
            st.rerun()
    else:
        st.info("Brak projektów", icon="📝")
    
    st.divider()
    
    # === SEKCJA: MODELE ===
    st.markdown("#### 🧠 Wybór Modeli")
    chat_model = st.selectbox("Architekt/Manager", AVAILABLE_MODELS, index=1, help="Model do planowania")
    coder_model = st.selectbox("Programista", AVAILABLE_MODELS, index=0, help="Model do kodu")
    st.divider()

    # === SEKCJA: PLIKI ===
    st.markdown("#### 📂 Pliki")
    col1, col2 = st.columns(2)
    if col1.button("🔄 Odśwież", use_container_width=True):
        st.rerun()
    
    if col2.button("⏮️ Rollback", use_container_width=True):
        chat_workspace = get_chat_workspace(st.session_state["active_chat_id"])
        backups_dir = os.path.join(CHATS_DIR, st.session_state["active_chat_id"], "backups")
        
        backups = sorted([d for d in os.listdir(backups_dir) if d.startswith("backup_")], reverse=True) if os.path.exists(backups_dir) else []
        if backups:
            latest = os.path.join(backups_dir, backups[0])
            if os.path.exists(chat_workspace):
                shutil.rmtree(chat_workspace)
            shutil.copytree(latest, chat_workspace)
            st.success(f"Przywrócono: {backups[0]}")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Brak backupów")

    # Lista plików
    chat_workspace = get_chat_workspace(st.session_state["active_chat_id"])
    import tools.file_ops as file_ops_module
    original_workspace = file_ops_module.WORKSPACE_DIR
    file_ops_module.WORKSPACE_DIR = chat_workspace
    
    files_str = list_files()
    
    if "No files" not in files_str and files_str.strip():
        file_list = files_str.split(", ")
        selected_file = st.selectbox("Podgląd:", file_list, index=None)
        if selected_file:
            content = read_file(selected_file)
            st.code(content, language="python", line_numbers=True)
    else:
        st.info("Pusto.", icon="ℹ️")
    
    file_ops_module.WORKSPACE_DIR = original_workspace

    st.divider()
    
    # Backup info
    backups_dir = os.path.join(CHATS_DIR, st.session_state.get("active_chat_id", ""), "backups")
    if os.path.exists(backups_dir):
        backup_count = len([d for d in os.listdir(backups_dir) if d.startswith("backup_")])
        st.caption(f"💾 Backupy: {backup_count}")
    
    # ZIP download
    if st.button("📦 Pobierz ZIP", use_container_width=True):
        chat_workspace = get_chat_workspace(st.session_state["active_chat_id"])
        active_chat_state = load_chat_state(st.session_state["active_chat_id"])
        chat_name = active_chat_state.get('name', 'projekt') if active_chat_state else 'projekt'
        zip_name = chat_name.replace(' ', '_').replace('/', '_')
        
        if os.path.exists(chat_workspace) and os.listdir(chat_workspace):
            shutil.make_archive(zip_name, 'zip', chat_workspace)
            with open(f"{zip_name}.zip", "rb") as f:
                st.download_button("📥 Pobierz", f, f"{zip_name}.zip", "application/zip", use_container_width=True)
        else:
            st.warning("Brak plików do spakowania")

# --- GŁÓWNY CZAT ---
st.title("CodeFabric AI")
st.markdown("Twój autonomiczny zespół deweloperski.")
st.divider()

# Wczytaj stan aktywnego chatu
active_chat_id = st.session_state["active_chat_id"]
chat_state = load_chat_state(active_chat_id)

if "messages" not in st.session_state or st.session_state.get("current_chat_loaded") != active_chat_id:
    if chat_state and 'messages' in chat_state:
        st.session_state["messages"] = chat_state['messages']
    else:
        st.session_state["messages"] = [{"role": "assistant", "content": "Cześć! Co dzisiaj budujemy?"}]
    
    st.session_state["current_chat_loaded"] = active_chat_id
    st.session_state["pipeline_active"] = False

for msg in st.session_state["messages"]:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

user_input = st.chat_input("Opisz projekt który chcesz stworzyć...")

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(user_input)
    
    # Backup
    backup_path = create_backup()
    if backup_path:
        st.toast(f"💾 Backup utworzony", icon="✅")
    
    # Generuj nazwę z pierwszego prompta
    active_chat_state = load_chat_state(st.session_state["active_chat_id"])
    if active_chat_state and active_chat_state.get('name') == 'Nowy projekt':
        new_name = generate_chat_name(user_input)
        active_chat_state['name'] = new_name
        save_chat_state(st.session_state["active_chat_id"], active_chat_state)
    
    # Zapisz wiadomości
    if active_chat_state:
        active_chat_state['messages'] = st.session_state["messages"]
        active_chat_state['updated'] = datetime.now().isoformat()
        save_chat_state(st.session_state["active_chat_id"], active_chat_state)
    
    st.session_state["pipeline_active"] = True
    if "graph_state" in st.session_state: 
        del st.session_state["graph_state"]
    st.rerun()

# --- LOGIKA LANGGRAPH ---
if st.session_state.get("pipeline_active"):
    
    if "graph_state" not in st.session_state:
        chat_workspace = get_chat_workspace(st.session_state["active_chat_id"])
        
        import tools.file_ops as file_ops_module
        original_ws = file_ops_module.WORKSPACE_DIR
        file_ops_module.WORKSPACE_DIR = chat_workspace
        
        existing_files = get_all_file_paths()
        
        file_ops_module.WORKSPACE_DIR = original_ws
        
        st.session_state["graph_state"] = {
            "messages": [HumanMessage(content=st.session_state["messages"][-1]["content"])],
            "current_files": existing_files,
            "plan": None,
            "plan_approved": False,
            "feedback": None,
            "revision_count": 0,
            "next_node": "manager",
            "model_names": {"chat": chat_model, "coder": coder_model},
            "chat_workspace": chat_workspace
        }

    status_placeholder = st.empty()
    action_placeholder = st.empty()
    
    current_state = st.session_state["graph_state"]
    
    plan = current_state.get("plan")
    is_approved = current_state.get("plan_approved")
    feedback = current_state.get("feedback")
    next_node = current_state.get("next_node")

    # Decyzja: czy uruchamiać graf?
    should_run_graph = True
    
    if plan and not is_approved and not feedback:
        should_run_graph = False 

    if next_node == "end":
        should_run_graph = False
        
    if feedback and "APPROVE" in str(feedback).upper():
        should_run_graph = False

    # Uruchamianie grafu
    if should_run_graph:
        with status_placeholder.container():
            status = st.status("🚀 AI pracuje...", expanded=True)
            progress_bar = st.progress(0, text="Start...")
            step = 0
            
            try:
                for event in app.stream(current_state):
                    step += 1
                    prog = min(step / 8, 0.95)
                    
                    for node, new_state in event.items():
                        st.session_state["graph_state"].update(new_state)
                        current_state = st.session_state["graph_state"]
                        
                        if node == "planner":
                            progress_bar.progress(prog, "🧠 Architekt: Planuję...")
                            status.write("🧠 **Architekt:** Tworzę plan techniczny...")
                            if "plan" in new_state:
                                with st.expander("📜 Zobacz Plan", expanded=False):
                                    st.markdown(new_state["plan"])
                                    
                        elif node == "coder":
                            rev = new_state.get("revision_count", 0)
                            msg = "Piszę kod..." if rev == 0 else f"Poprawki (v{rev})..."
                            progress_bar.progress(prog, f"👨‍💻 {msg}")
                            status.write(f"👨‍💻 **Programista:** {msg}")
                            time.sleep(0.2)
                            
                        elif node == "reviewer":
                            progress_bar.progress(prog, "🔎 Recenzent: Sprawdzam...")
                            status.write("🔎 **Recenzent:** Weryfikacja jakości...")
                            if "feedback" in new_state:
                                with st.expander("📋 Raport", expanded=True):
                                    st.markdown(new_state["feedback"])
                
                status.update(label="Etap zakończony", state="running", expanded=False)
                progress_bar.empty()
                st.rerun()

            except Exception as e:
                status.update(label="Błąd", state="error")
                st.error(f"Błąd: {e}")
                st.session_state["pipeline_active"] = False

    # Interfejs decyzji
    plan = st.session_state["graph_state"].get("plan")
    is_approved = st.session_state["graph_state"].get("plan_approved")
    next_node = st.session_state["graph_state"].get("next_node")
    last_feedback = st.session_state["graph_state"].get("feedback", "")

    # Scenariusz A: Decyzja o planie
    if plan and not is_approved:
        with action_placeholder.container():
            st.info("🧠 **Architekt przygotował plan.**", icon="📋")
            with st.expander("📜 ZOBACZ PLAN", expanded=True):
                st.markdown(plan)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("✅ Zatwierdź i Rozpocznij Kodowanie", type="primary", use_container_width=True, key="btn_approve"):
                st.session_state["graph_state"]["plan_approved"] = True
                st.session_state["graph_state"]["feedback"] = None
                st.session_state["graph_state"]["next_node"] = "manager" 
                st.rerun()
            
            st.markdown("**Lub podaj uwagi do poprawy:**")
            user_feedback = st.text_area("Uwagi:", placeholder="Co chcesz zmienić w planie?", key="input_feedback")
            if st.button("🔄 Popraw Plan", use_container_width=True, key="btn_reject"):
                if user_feedback:
                    st.session_state["graph_state"]["feedback"] = user_feedback
                    st.session_state["graph_state"]["plan"] = None
                    st.session_state["graph_state"]["plan_approved"] = False
                    st.session_state["graph_state"]["next_node"] = "manager"
                    st.rerun()
                else:
                    st.warning("Wpisz uwagi do poprawy.")

    # Scenariusz B: Sukces
    elif next_node == "end":
        if not last_feedback or "APPROVE" in str(last_feedback).upper():
            st.session_state["pipeline_active"] = False
            
            with action_placeholder.container():
                st.success("✅ **Projekt gotowy!**")
                
                important_files = [f for f in get_all_file_paths() if any(f.endswith(ext) for ext in ['.py', '.js', '.html', '.md'])]
                if important_files:
                    st.markdown("**📦 Wygenerowane pliki:**")
                    for f in important_files:
                        st.markdown(f"- `{f}`")
                
                st.info("💬 Możesz teraz dodać kolejne funkcje - po prostu napisz co chcesz zmienić!", icon="✨")
                
                if st.button("🆕 Nowy projekt", key="btn_finish", use_container_width=True):
                    new_chat_id = create_new_chat()
                    st.session_state["active_chat_id"] = new_chat_id
                    st.session_state["messages"] = [{"role": "assistant", "content": "Cześć! Co dzisiaj budujemy?"}]
                    st.session_state["current_chat_loaded"] = new_chat_id
                    if "graph_state" in st.session_state:
                        del st.session_state["graph_state"]
                    st.session_state["pipeline_active"] = False
                    st.rerun()
        else:
            with action_placeholder.container():
                st.warning("⚠️ Proces zatrzymany z błędami.")
                st.markdown(f"**Ostatni feedback:**\n{last_feedback}")
                
                col1, col2 = st.columns(2)
                if col1.button("🔄 Spróbuj ponownie", key="btn_retry", use_container_width=True):
                    st.session_state["graph_state"]["revision_count"] = 0
                    st.session_state["graph_state"]["feedback"] = None
                    st.session_state["graph_state"]["next_node"] = "manager"
                    st.rerun()
                
                if col2.button("🗑️ Reset", key="btn_reset_err", use_container_width=True):
                    del st.session_state["graph_state"]
                    st.session_state["pipeline_active"] = False
                    st.rerun()