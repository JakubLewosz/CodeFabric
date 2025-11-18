import streamlit as st
import os
import time
import shutil
from graph.workflow import app
from langchain_core.messages import HumanMessage
from tools.file_ops import list_files, read_file

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="CodeFabric | AI Software House",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (STYLIZACJA) ---
def inject_custom_css():
    st.markdown("""
    <style>
        /* Główny kontener */
        .main {
            background-color: #0E1117;
        }
        
        /* Stylowanie tytułu */
        h1 {
            background: -webkit-linear-gradient(45deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700 !important;
        }
        
        /* Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #161b22;
            border-right: 1px solid #30363d;
        }
        
        /* Przyciski */
        .stButton>button {
            background: linear-gradient(90deg, #2b5876 0%, #4e4376 100%);
            color: white;
            border: none;
            border-radius: 8px;
            height: 45px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        
        /* Dymki czatu */
        .stChatMessage {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 10px;
            margin-bottom: 10px;
        }
        
        /* Status bar (terminal style) */
        .stStatusWidget {
            background-color: #0d1117;
            border: 1px solid #30363d;
            font-family: 'Courier New', Courier, monospace;
            color: #58a6ff;
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- SIDEBAR (PANEL STEROWANIA) ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=60)
    st.markdown("### **CodeFabric** \n *Local AI Software House*")
    st.divider()
    
    # Status Serwera
    st.markdown("#### 🖥️ System Status")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("🟢 **Ollama**\nOnline")
    with c2:
        st.markdown("🔒 **Privacy**\nLocalhost")
        
    st.divider()

    # Eksplorator Plików
    st.markdown("#### 📂 Workspace Explorer")
    
    if st.button("🔄 Odśwież pliki", use_container_width=True):
        st.rerun()

    files_str = list_files()
    if "No files" not in files_str and files_str.strip():
        file_list = files_str.split(", ")
        selected_file = st.selectbox("Wybierz plik do podglądu:", file_list, index=None)
        
        if selected_file:
            content = read_file(selected_file)
            st.markdown(f"**📄 Podgląd:** `{selected_file}`")
            st.code(content, language="python", line_numbers=True)
    else:
        st.info("Folder roboczy jest pusty.", icon="ℹ️")

    # --- NOWOŚĆ: EKSPORT DO ZIP ---
    st.divider()
    st.markdown("#### 📦 Eksport")
    
    # Przycisk generowania ZIP
    if st.button("Przygotuj plik ZIP", use_container_width=True):
        # Tworzymy archiwum z folderu workspace
        shutil.make_archive("projekt_codefabric", 'zip', "./workspace")
        
        with open("projekt_codefabric.zip", "rb") as fp:
            st.download_button(
                label="📥 Pobierz gotowy projekt (.zip)",
                data=fp,
                file_name="twoj_projekt.zip",
                mime="application/zip",
                use_container_width=True
            )

    st.divider()
    st.caption("v1.1.0 | Powered by LangGraph")

# --- GŁÓWNY CZAT ---

# Nagłówek
c1, c2 = st.columns([3, 1])
with c1:
    st.title("CodeFabric AI")
    st.markdown("Twój autonomiczny zespół deweloperski. Opisz zadanie, a my zajmiemy się resztą.")

# Inicjalizacja historii
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Cześć! Jestem Twoim Project Managerem. Co dzisiaj budujemy?"}
    ]

# Wyświetlanie wiadomości
for msg in st.session_state["messages"]:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🕵️‍♂️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# --- LOGIKA PRZETWARZANIA ---
user_input = st.chat_input("Np. Stwórz grę w węża w Pythonie...")

if user_input:
    # 1. Dodaj wiadomość użytkownika
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(user_input)
        
    # 2. Uruchomienie AI
    with st.chat_message("assistant", avatar="🕵️‍♂️"):
        
        # --- NOWOŚĆ: PASEK POSTĘPU ---
        progress_bar = st.progress(0, text="Inicjalizacja AI Team...")
        step_count = 0
        total_steps = 5 # Szacowana liczba kroków (Mgr -> Plan -> Mgr -> Code -> Mgr)

        # Kontener statusu (wygląda jak logi systemowe)
        status_container = st.status("🚀 Uruchamianie procedury...", expanded=True)
        
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "current_files": [],
            "plan": None
        }
        
        final_response = ""
        
        try:
            # Streamowanie kroków z grafu
            for event in app.stream(initial_state):
                step_count += 1
                # Aktualizacja paska postępu (max 95% przed końcem)
                prog_val = min(step_count / total_steps, 0.95)
                
                for node_name, node_state in event.items():
                    # Logi zależne od tego, kto pracuje
                    if node_name == "manager":
                        progress_bar.progress(prog_val, text="🕵️‍♂️ Manager: Zarządzam zespołem...")
                        status_container.write(f"🕵️‍♂️ **Manager:** Analizuję postępy...")
                        
                    elif node_name == "planner":
                        progress_bar.progress(prog_val, text="🧠 Architekt: Projektuję rozwiązanie...")
                        status_container.write(f"🧠 **Architekt:** Tworzę plan techniczny...")
                        # Pokaż plan w ładnym expanderze
                        if "plan" in node_state and node_state["plan"]:
                            with st.expander("📜 Zobacz Plan Projektu", expanded=False):
                                st.markdown(node_state["plan"])
                                
                    elif node_name == "coder":
                        progress_bar.progress(prog_val, text="👨‍💻 Programista: Piszę kod...")
                        status_container.write(f"👨‍💻 **Programista:** Piszę kod i tworzę pliki...")
                        time.sleep(0.5) # Małe opóźnienie dla efektu "pisania"
            
            # Sukces - 100% paska
            progress_bar.progress(1.0, text="✅ Gotowe!")
            time.sleep(0.5)
            progress_bar.empty() # Ukryj pasek po zakończeniu
            
            status_container.update(label="✅ Zadanie zakończone sukcesem!", state="complete", expanded=False)
            final_response = "Zrobione! Sprawdź wygenerowane pliki w panelu bocznym po lewej stronie."
            
        except Exception as e:
            status_container.update(label="❌ Błąd krytyczny", state="error")
            st.error(f"Wystąpił błąd połączenia: {str(e)}")
            final_response = "Przepraszam, wystąpił problem z połączeniem do lokalnego modelu AI."

        st.markdown(final_response)
        st.session_state["messages"].append({"role": "assistant", "content": final_response})

        # Wymuś odświeżenie, żeby pliki pojawiły się w sidebarze
        if "Zrobione" in final_response:
            time.sleep(1)
            st.rerun()