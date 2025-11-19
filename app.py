import streamlit as st
import os
import time
import shutil
from graph.workflow import app
from langchain_core.messages import HumanMessage
from tools.file_ops import list_files, read_file, get_all_file_paths

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="CodeFabric | AI Software House",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DOSTĘPNE MODELE ---
AVAILABLE_MODELS = [
    "qwen3-coder:30b", "mistral-small3.2:24b", "gemma3:27b", 
    "qwq:32b", "bielik2.6:11b", "mistral:7b", "llama3.3:70b"
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

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=60)
    st.markdown("### **CodeFabric**")
    st.divider()
    
    # Wybór modeli
    st.markdown("#### 🧠 Wybór Mózgów")
    chat_model = st.selectbox("🗣️ Architekt/Manager", AVAILABLE_MODELS, index=4) # Bielik
    coder_model = st.selectbox("👨‍💻 Programista", AVAILABLE_MODELS, index=0) # Qwen
    st.divider()

    # Eksplorator
    st.markdown("#### 📂 Pliki")
    if st.button("🔄 Odśwież", use_container_width=True):
        st.rerun()

    files_str = list_files()
    if "No files" not in files_str and files_str.strip():
        file_list = files_str.split(", ")
        selected_file = st.selectbox("Podgląd:", file_list, index=None)
        if selected_file:
            content = read_file(selected_file)
            st.code(content, language="python", line_numbers=True)
    else:
        st.info("Pusto.", icon="ℹ️")

    # ZIP
    st.divider()
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

# Wyświetlanie historii
for msg in st.session_state["messages"]:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🕵️‍♂️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Input użytkownika
user_input = st.chat_input("Opis projektu...")

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(user_input)
    st.session_state["pipeline_active"] = True
    st.rerun()

# --- LOGIKA LANGGRAPH ---
if st.session_state.get("pipeline_active"):
    
    # 1. Inicjalizacja stanu (ładowanie pamięci tylko raz na cykl)
    if "graph_state" not in st.session_state:
        existing_files = get_all_file_paths()
        st.session_state["graph_state"] = {
            "messages": [HumanMessage(content=st.session_state["messages"][-1]["content"])],
            "current_files": existing_files,
            "plan": None,
            "plan_approved": False,
            "feedback": None,
            "revision_count": 0,
            "model_names": {"chat": chat_model, "coder": coder_model}
        }

    # Placeholder na status i przyciski (zapobiega duplikacji przy odświeżaniu)
    status_placeholder = st.empty()
    action_placeholder = st.empty()
    
    current_state = st.session_state["graph_state"]
    
    # Sprawdzamy czy mamy "zatrzymanie" (Plan gotowy, ale niezatwierdzony)
    plan = current_state.get("plan")
    is_approved = current_state.get("plan_approved")
    has_files = current_state.get("current_files")
    feedback = current_state.get("feedback")

    # Jeśli są uwagi (feedback), to znaczy że musimy puścić graf dalej (do Plannera), 
    # więc nie pokazujemy przycisków, tylko uruchamiamy pętlę.
    should_run_graph = True
    if plan and not is_approved and not feedback:
        should_run_graph = False # Zatrzymujemy się, by pokazać przyciski

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
                        # Aktualizacja stanu sesji
                        st.session_state["graph_state"].update(new_state)
                        current_state = st.session_state["graph_state"]
                        
                        if node == "planner":
                            progress_bar.progress(prog, "🧠 Architekt: Planuję...")
                            status.write("🧠 **Architekt:** Tworzę/Poprawiam plan...")
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
                
                # Po zakończeniu pętli - wymuszamy odświeżenie, żeby sprawdzić warunki UI
                st.rerun()

            except Exception as e:
                status.update(label="Błąd", state="error")
                st.error(f"Błąd: {e}")
                st.session_state["pipeline_active"] = False


    # --- INTERFEJS DECYZJI (POZA PĘTLĄ GRAFU) ---
    # To się wykona tylko gdy graf się zatrzymał (zwrócił END)
    
    # Odświeżamy zmienne po przebiegu grafu
    plan = st.session_state["graph_state"].get("plan")
    is_approved = st.session_state["graph_state"].get("plan_approved")
    has_files = st.session_state["graph_state"].get("current_files") # Czy doszły nowe pliki w tej sesji?
    
    # Scenariusz A: Czekamy na akceptację planu
    if plan and not is_approved:
        with action_placeholder.container():
            st.info("🧠 **Architekt przygotował plan.**")
            with st.expander("📜 ZOBACZ PLAN I ZATWIERDŹ", expanded=True):
                st.markdown(plan)
            
            c1, c2 = st.columns(2)
            # WAŻNE: key zapobiega duplikacji ID
            if c1.button("✅ Zatwierdź i Koduj", type="primary", use_container_width=True, key="btn_approve"):
                st.session_state["graph_state"]["plan_approved"] = True
                st.session_state["graph_state"]["feedback"] = None
                st.rerun()
            
            with c2:
                user_feedback = st.text_input("Uwagi do planu:", key="input_feedback")
                if st.button("❌ Popraw Plan", use_container_width=True, key="btn_reject"):
                    if user_feedback:
                        st.session_state["graph_state"]["feedback"] = user_feedback
                        st.rerun()
                    else:
                        st.warning("Wpisz uwagi.")

    # Scenariusz B: Sukces (Plan zatwierdzony i mamy pliki wynikowe)
    # Używamy len(current_files) > len(start_files) lub po prostu sprawdzamy czy Coder skończył
    elif is_approved and has_files:
        # Sprawdzamy czy nie ma REJECT w feedbacku (czyli czy proces zakończył się sukcesem)
        last_feedback = st.session_state["graph_state"].get("feedback", "")
        
        if not last_feedback or "APPROVE" in str(last_feedback):
            with action_placeholder.container():
                st.success("✅ **Projekt gotowy!** Pliki znajdziesz w panelu bocznym.")
                if st.button("Zakończ i zacznij nowy", key="btn_finish"):
                    final_msg = "Zadanie wykonane pomyślnie."
                    st.session_state["messages"].append({"role": "assistant", "content": final_msg})
                    del st.session_state["graph_state"]
                    st.session_state["pipeline_active"] = False
                    st.rerun()
        else:
            # Jeśli proces się skończył, ale feedback jest REJECT (np. limit poprawek)
            st.error("⚠️ Proces zakończony, ale mogą występować błędy (limit poprawek).")
            if st.button("Reset", key="btn_reset_err"):
                del st.session_state["graph_state"]
                st.session_state["pipeline_active"] = False
                st.rerun()