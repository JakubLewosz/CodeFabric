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

# --- DOSTĘPNE MODELE (Z TWOJEJ LISTY) ---
AVAILABLE_MODELS = [
    "qwen3-coder:30b",       # Najlepszy do kodu
    "mistral-small3.2:24b",  # Dobry ogólny
    "gemma3:27b",            # Nowy Google
    "qwq:32b",               # Reasoning (dobre do planowania)
    "bielik2.6:11b",         # Polski!
    "mistral:7b",            # Szybki
    "llama3.3:70b",          # Potwór (może być wolny)
    "llama4:16x17b"          # Eksperymentalny?
]

# --- CUSTOM CSS (STYLIZACJA) ---
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

# --- SIDEBAR (PANEL STEROWANIA) ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=60)
    st.markdown("### **CodeFabric** \n *Local AI Software House*")
    st.divider()
    
    # --- WYBÓR MODELI ---
    st.markdown("#### 🧠 Wybór Mózgów")
    
    # Domyślnie: Bielik do gadania (bo Polski), Qwen do kodowania
    selected_chat_model = st.selectbox(
        "🗣️ Architekt/Manager", 
        AVAILABLE_MODELS, 
        index=4 # Bielik
    )
    
    selected_coder_model = st.selectbox(
        "👨‍💻 Programista", 
        AVAILABLE_MODELS, 
        index=0 # Qwen
    )
    
    st.divider()

    # --- EKSPLORATOR PLIKÓW ---
    st.markdown("#### 📂 Workspace Explorer")
    if st.button("🔄 Odśwież pliki", use_container_width=True):
        st.rerun()

    files_str = list_files()
    if "No files" not in files_str and files_str.strip():
        file_list = files_str.split(", ")
        selected_file = st.selectbox("Podgląd:", file_list, index=None)
        if selected_file:
            content = read_file(selected_file)
            st.markdown(f"**📄 {selected_file}**")
            st.code(content, language="python", line_numbers=True)
    else:
        st.info("Folder roboczy jest pusty.", icon="ℹ️")

    # --- EKSPORT DO ZIP ---
    st.divider()
    if st.button("📦 Pobierz ZIP", use_container_width=True):
        shutil.make_archive("projekt_codefabric", 'zip', "./workspace")
        with open("projekt_codefabric.zip", "rb") as fp:
            st.download_button(
                label="📥 Pobierz (.zip)",
                data=fp,
                file_name="projekt.zip",
                mime="application/zip",
                use_container_width=True
            )

    st.divider()
    st.caption("v2.0.0 | Powered by LangGraph")

# --- GŁÓWNY CZAT ---

c1, c2 = st.columns([3, 1])
with c1:
    st.title("CodeFabric AI")
    st.markdown("Twój autonomiczny zespół deweloperski.")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Cześć! Co dzisiaj budujemy?"}
    ]
    st.session_state["pipeline_active"] = False

# Wyświetlanie historii
for msg in st.session_state["messages"]:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🕵️‍♂️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# --- INPUT UŻYTKOWNIKA ---
user_input = st.chat_input("Np. Stwórz kalkulator w Pythonie...")

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(user_input)
    st.session_state["pipeline_active"] = True
    st.rerun()

# --- SILNIK LANGGRAPH (PROCES GŁÓWNY) ---
if st.session_state.get("pipeline_active"):
    
    # 1. Inicjalizacja stanu (tylko na początku procesu)
    if "graph_state" not in st.session_state:
        # Pamięć Projektu: Ładujemy pliki, które już są na dysku
        existing_files = get_all_file_paths()
        
        st.session_state["graph_state"] = {
            "messages": [HumanMessage(content=st.session_state["messages"][-1]["content"])],
            "current_files": existing_files, # <-- AI widzi co już jest!
            "plan": None,
            "plan_approved": False,
            "feedback": None,
            "revision_count": 0,
            "model_names": {
                "chat": selected_chat_model,
                "coder": selected_coder_model
            }
        }

    status_container = st.status("🚀 AI pracuje...", expanded=True)
    progress_bar = st.progress(0, text="Inicjalizacja...")
    
    # Szacunkowa liczba kroków do paska postępu
    step_count = 0
    total_steps = 7 
    
    current_state = st.session_state["graph_state"]
    
    try:
        # Uruchamiamy graf. Dzięki logice w manager.py, graf sam się zatrzyma (zwróci END),
        # gdy dojdzie do momentu "Czekam na zatwierdzenie planu".
        for event in app.stream(current_state):
            step_count += 1
            prog_val = min(step_count / total_steps, 0.95)
            
            for node_name, new_state in event.items():
                # Aktualizujemy stan w sesji Streamlit na bieżąco
                st.session_state["graph_state"].update(new_state)
                current_state = st.session_state["graph_state"]
                
                if node_name == "manager":
                    progress_bar.progress(prog_val, text="🕵️‍♂️ Manager: Koordynuję...")
                    status_container.write(f"🕵️‍♂️ **Manager:** Analiza stanu...")
                    
                elif node_name == "planner":
                    progress_bar.progress(prog_val, text="🧠 Architekt: Projektuję...")
                    status_container.write(f"🧠 **Architekt:** Tworzę plan techniczny...")
                    if "plan" in new_state and new_state["plan"]:
                        with st.expander("📜 Zobacz Wstępny Plan", expanded=False):
                            st.markdown(new_state["plan"])
                            
                elif node_name == "coder":
                    rev = new_state.get("revision_count", 0)
                    msg = "Piszę kod..." if rev == 0 else f"Wprowadzam poprawki (v{rev})..."
                    progress_bar.progress(prog_val, text=f"👨‍💻 Programista: {msg}")
                    status_container.write(f"👨‍💻 **Programista:** {msg}")
                    time.sleep(0.5)

                elif node_name == "reviewer":
                    progress_bar.progress(prog_val, text="🔎 Recenzent: Sprawdzam...")
                    status_container.write(f"🔎 **Recenzent:** Analiza jakości i dokumentacji...")
                    if "feedback" in new_state:
                        with st.expander("📋 Raport Testera", expanded=True):
                            st.markdown(new_state["feedback"])

        # --- PO ZAKOŃCZENIU STRUMIENIOWANIA SPRAWDZAMY STAN ---
        
        plan = current_state.get("plan")
        is_approved = current_state.get("plan_approved")
        files_created = current_state.get("current_files")

        status_container.update(label="Oczekiwanie na decyzję...", state="running")

        # SCENARIUSZ A: Mamy plan, ale nie jest zatwierdzony -> HUMAN IN THE LOOP
        if plan and not is_approved:
            status_container.update(label="🛑 Wymagana akcja człowieka", state="error")
            progress_bar.empty()
            
            st.info("🧠 **Architekt przedstawił plan.** Sprawdź go poniżej i zdecyduj.")
            
            with st.expander("📜 PEŁNY PLAN PROJEKTU", expanded=True):
                st.markdown(plan)
            
            col1, col2 = st.columns(2)
            
            # Przycisk 1: Zatwierdź
            if col1.button("✅ Zatwierdź Plan i Koduj", type="primary", use_container_width=True):
                st.session_state["graph_state"]["plan_approved"] = True
                st.session_state["graph_state"]["feedback"] = None 
                st.rerun() # Restartujemy, Manager puści teraz Codera
            
            # Przycisk 2: Popraw
            with col2:
                user_feedback = st.text_input("Lub zgłoś uwagi:", placeholder="Np. Dodaj plik requirements.txt...")
                if st.button("❌ Popraw Plan", use_container_width=True):
                    if user_feedback:
                        st.session_state["graph_state"]["feedback"] = user_feedback
                        st.rerun() # Restartujemy, Manager wyśle do Plannera
                    else:
                        st.warning("Wpisz treść uwag.")

        # SCENARIUSZ B: Proces zakończony sukcesem (pliki są gotowe i zatwierdzone)
        # Sprawdzamy też czy Manager nie zakończył procesu przedwcześnie (np. błąd pętli)
        elif is_approved and files_created:
            status_container.update(label="✅ Zadanie zakończone!", state="complete")
            progress_bar.progress(1.0, text="✅ Gotowe!")
            time.sleep(0.5)
            progress_bar.empty()
            
            final_msg = "Projekt gotowy! Pliki znajdziesz w panelu bocznym."
            st.markdown(final_msg)
            st.session_state["messages"].append({"role": "assistant", "content": final_msg})
            
            # Sprzątamy sesję grafu, żeby można było zacząć nowy projekt
            del st.session_state["graph_state"] 
            st.session_state["pipeline_active"] = False
            
            # Odświeżamy UI, żeby pokazać nowe pliki w sidebarze
            time.sleep(2)
            st.rerun()

    except Exception as e:
        status_container.update(label="❌ Błąd krytyczny", state="error")
        st.error(f"Wystąpił błąd: {str(e)}")