import streamlit as st
import os
import time
import shutil
from graph.workflow import app
from langchain_core.messages import HumanMessage
from tools.file_ops import list_files, read_file

st.set_page_config(page_title="CodeFabric | AI Software House", page_icon="🏗️", layout="wide")

# --- LISTA TWOICH MODELI ---
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

# ... (CSS bez zmian, pomijam dla czytelności - wklej swój CSS tutaj) ...

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=60)
    st.markdown("### **CodeFabric**")
    st.divider()
    
    # --- WYBÓR MODELI ---
    st.markdown("#### 🧠 Wybór Mózgów")
    
    # Domyślnie: Bielik do gadania (bo Polski), Qwen do kodowania
    selected_chat_model = st.selectbox(
        "🗣️ Model: Manager/Planista", 
        AVAILABLE_MODELS, 
        index=4 # Index 4 to Bielik
    )
    
    selected_coder_model = st.selectbox(
        "👨‍💻 Model: Programista", 
        AVAILABLE_MODELS, 
        index=0 # Index 0 to Qwen (Best for code)
    )
    st.divider()
    
    # ... (Reszta sidebaru: Eksplorator plików, Zip - bez zmian) ...
    # Poniżej wklejam resztę logiki obsługi plików
    st.markdown("#### 📂 Workspace Explorer")
    if st.button("🔄 Odśwież pliki", use_container_width=True):
        st.rerun()
    files_str = list_files()
    if "No files" not in files_str:
        selected_file = st.selectbox("Podgląd:", files_str.split(", "), index=None)
        if selected_file:
            st.code(read_file(selected_file))
            
    st.divider()
    if st.button("📦 Pobierz ZIP", use_container_width=True):
        shutil.make_archive("projekt", 'zip', "./workspace")
        with open("projekt.zip", "rb") as f:
            st.download_button("📥 Pobierz", f, "projekt.zip", "application/zip")

# --- GŁÓWNY CZAT ---
st.title("CodeFabric AI")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "Gotowy do pracy!"}]

for msg in st.session_state["messages"]:
    st.chat_message(msg["role"]).write(msg["content"])

user_input = st.chat_input("Co robimy?")

if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)
    
    with st.chat_message("assistant"):
        status = st.status("🚀 Start...", expanded=True)
        
        # PRZEKAZUJEMY WYBRANE MODELE DO STANU
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "current_files": [],
            "plan": None,
            "model_names": {
                "chat": selected_chat_model,
                "coder": selected_coder_model
            }
        }
        
        try:
            for event in app.stream(initial_state):
                for node, state in event.items():
                    if node == "planner":
                        status.write(f"🧠 **Architekt ({selected_chat_model}):** Planuję...")
                    elif node == "coder":
                        status.write(f"👨‍💻 **Programista ({selected_coder_model}):** Piszę kod...")
                    elif node == "reviewer":
                        status.write(f"🔎 **Recenzent:** Sprawdzam...")
            
            status.update(label="Gotowe!", state="complete", expanded=False)
            final_msg = "Zrobione! Sprawdź pliki."
            st.markdown(final_msg)
            st.session_state["messages"].append({"role": "assistant", "content": final_msg})
            
        except Exception as e:
            st.error(f"Błąd: {e}")