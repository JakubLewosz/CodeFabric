import streamlit as st
import os
import time
import shutil
from graph.workflow import app
from langchain_core.messages import HumanMessage
from tools.file_ops import list_files, read_file, get_all_file_paths, write_file

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="CodeFabric | AI Software House",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# --- FUNKCJA BACKUP ---
def create_backup():
    """Tworzy backup aktualnego workspace przed zmianami"""
    if os.path.exists("./workspace") and os.listdir("./workspace"):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = f"./backups/backup_{timestamp}"
        os.makedirs("./backups", exist_ok=True)
        shutil.copytree("./workspace", backup_path)
        return backup_path
    return None

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=60)
    st.markdown("### **CodeFabric**")
    st.divider()
    
    st.markdown("#### 🧠 Wybór Mózgów")
    chat_model = st.selectbox("🗣️ Architekt/Manager", AVAILABLE_MODELS, index=1)  # bielik2.6:11b
    coder_model = st.selectbox("👨‍💻 Programista", AVAILABLE_MODELS, index=0)  # qwen3-coder:30b
    st.divider()

    st.markdown("#### 📂 Pliki")
    col1, col2 = st.columns(2)
    if col1.button("🔄 Odśwież", use_container_width=True):
        st.rerun()
    
    # NOWOŚĆ: Przycisk Rollback
    if col2.button("⏮️ Rollback", use_container_width=True):
        backups = sorted([d for d in os.listdir("./backups") if d.startswith("backup_")], reverse=True) if os.path.exists("./backups") else []
        if backups:
            latest = f"./backups/{backups[0]}"
            shutil.rmtree("./workspace")
            shutil.copytree(latest, "./workspace")
            st.success(f"Przywrócono: {backups[0]}")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Brak backupów")

    files_str = list_files()
    if "No files" not in files_str and files_str.strip():
        file_list = files_str.split(", ")
        selected_file = st.selectbox("Podgląd:", file_list, index=None)
        if selected_file:
            content = read_file(selected_file)
            st.code(content, language="python", line_numbers=True)
    else:
        st.info("Pusto.", icon="ℹ️")

    st.divider()
    
    # NOWOŚĆ: Informacja o backupach
    if os.path.exists("./backups"):
        backup_count = len([d for d in os.listdir("./backups") if d.startswith("backup_")])
        st.caption(f"💾 Backupy: {backup_count}")
    
    if st.button("📦 Pobierz ZIP", use_container_width=True):
        shutil.make_archive("projekt", 'zip', "./workspace")
        with open("projekt.zip", "rb") as f:
            st.download_button("📥 Pobierz", f, "projekt.zip", "application/zip", use_container_width=True)

# --- GŁÓWNY CZAT ---
c1, c2 = st.columns([3, 1])
with c1:
    st.title("CodeFabric AI")
    st.markdown("Twój autonomiczny zespół deweloperski.")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "Cześć! Co dzisiaj budujemy?"}]
    st.session_state["pipeline_active"] = False

for msg in st.session_state["messages"]:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🕵️‍♂️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

user_input = st.chat_input("Opis projektu...")

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(user_input)
    
    # NOWOŚĆ: Twórz backup przed każdą nową iteracją
    backup_path = create_backup()
    if backup_path:
        st.toast(f"💾 Backup utworzony", icon="✅")
    
    st.session_state["pipeline_active"] = True
    if "graph_state" in st.session_state: 
        del st.session_state["graph_state"]
    st.rerun()

# --- LOGIKA LANGGRAPH ---
if st.session_state.get("pipeline_active"):
    
    if "graph_state" not in st.session_state:
        existing_files = get_all_file_paths()
        st.session_state["graph_state"] = {
            "messages": [HumanMessage(content=st.session_state["messages"][-1]["content"])],
            "current_files": existing_files,
            "plan": None,
            "plan_approved": False,
            "feedback": None,
            "revision_count": 0,
            "next_node": "manager",
            "model_names": {"chat": chat_model, "coder": coder_model}
        }

    status_placeholder = st.empty()
    action_placeholder = st.empty()
    
    current_state = st.session_state["graph_state"]
    
    plan = current_state.get("plan")
    is_approved = current_state.get("plan_approved")
    feedback = current_state.get("feedback")
    next_node = current_state.get("next_node")

    # --- DECYZJA: CZY URUCHAMIAĆ GRAF? ---
    should_run_graph = True
    
    if plan and not is_approved and not feedback:
        should_run_graph = False 

    if next_node == "end":
        should_run_graph = False
        
    if feedback and "APPROVE" in str(feedback).upper():
        should_run_graph = False

    # --- URUCHAMIANIE GRAFU ---
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

    # --- INTERFEJS ---
    plan = st.session_state["graph_state"].get("plan")
    is_approved = st.session_state["graph_state"].get("plan_approved")
    next_node = st.session_state["graph_state"].get("next_node")
    last_feedback = st.session_state["graph_state"].get("feedback", "")

    # Scenariusz A: Decyzja o planie
    if plan and not is_approved:
        with action_placeholder.container():
            st.info("🧠 **Architekt przygotował plan.**")
            with st.expander("📜 ZOBACZ PLAN", expanded=True):
                st.markdown(plan)
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Zatwierdź i Koduj", type="primary", use_container_width=True, key="btn_approve"):
                st.session_state["graph_state"]["plan_approved"] = True
                st.session_state["graph_state"]["feedback"] = None
                st.session_state["graph_state"]["next_node"] = "manager" 
                st.rerun()
            
            with c2:
                user_feedback = st.text_input("Uwagi:", key="input_feedback")
                if st.button("❌ Popraw Plan", use_container_width=True, key="btn_reject"):
                    if user_feedback:
                        st.session_state["graph_state"]["feedback"] = user_feedback
                        st.session_state["graph_state"]["plan"] = None
                        st.session_state["graph_state"]["plan_approved"] = False
                        st.session_state["graph_state"]["next_node"] = "manager"
                        st.rerun()
                    else:
                        st.warning("Wpisz uwagi.")

    # Scenariusz B: Sukces
    elif next_node == "end":
        if not last_feedback or "APPROVE" in str(last_feedback).upper():
            with action_placeholder.container():
                st.success("✅ **Projekt gotowy!**")
                
                important_files = [f for f in get_all_file_paths() if any(f.endswith(ext) for ext in ['.py', '.js', '.html', '.md'])]
                if important_files:
                    with st.expander("📁 Wygenerowane pliki", expanded=True):
                        for f in important_files:
                            st.markdown(f"- `{f}`")
                
                col1, col2 = st.columns(2)
                if col1.button("🆕 Nowy projekt", key="btn_finish", use_container_width=True):
                    st.session_state["messages"].append({"role": "assistant", "content": "Zadanie zakończone."})
                    del st.session_state["graph_state"]
                    st.session_state["pipeline_active"] = False
                    st.rerun()
                
                if col2.button("🔄 Kontynuuj pracę", key="btn_continue", use_container_width=True):
                    # Nie usuwamy graph_state - zachowujemy pliki i context
                    st.session_state["graph_state"]["plan_approved"] = False
                    st.session_state["graph_state"]["feedback"] = None
                    st.session_state["graph_state"]["next_node"] = "manager"
                    st.session_state["graph_state"]["plan"] = None  # Reset planu
                    st.session_state["pipeline_active"] = False
                    st.toast("Możesz dodać kolejne funkcje!", icon="✨")
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