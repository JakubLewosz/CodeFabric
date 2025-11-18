# Plik: app.py
import streamlit as st
from graph.workflow import app
from langchain_core.messages import HumanMessage
from tools.file_ops import list_files, read_file
import os

# --- Konfiguracja Strony ---
st.set_page_config(page_title="CodeFabric Local", page_icon="🏗️", layout="wide")

st.title("🏗️ CodeFabric: Local AI Software House")
st.markdown("Using: **Ollama (DeepSeek/Llama3)** | Privacy: **100% Local**")

# --- Panel Boczny (Pliki) ---
with st.sidebar:
    st.header("📂 Workspace Files")
    if st.button("🔄 Refresh Files"):
        pass # Przeładowanie strony
    
    # Wyświetlanie listy plików
    files_str = list_files()
    if "No files" not in files_str:
        file_list = files_str.split(", ")
        selected_file = st.selectbox("Select file to view:", file_list)
        
        if selected_file:
            content = read_file(selected_file)
            st.code(content)
    else:
        st.info("Workspace is empty.")

# --- Inicjalizacja Historii Czatu ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Wyświetlanie historii na ekranie
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Logika Czatu ---
user_input = st.chat_input("Co mam dla Ciebie zbudować?")

if user_input:
    # 1. Wyświetl wiadomość użytkownika
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    # 2. Uruchom AI (LangGraph)
    with st.chat_message("assistant"):
        status_container = st.status("AI Team is working...", expanded=True)
        
        # Przygotuj stan początkowy
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "current_files": [],
            "plan": None
        }
        
        # Uruchomienie grafu (streamowanie kroków)
        final_response = "Proces zakończony."
        
        try:
            # Streamujemy zdarzenia z grafu
            for event in app.stream(initial_state):
                for node_name, node_state in event.items():
                    status_container.write(f"👉 **{node_name.upper()}** zakończył pracę.")
                    
                    # Jeśli planner coś wymyślił, pokaż to
                    if "plan" in node_state and node_state["plan"]:
                        with st.expander("Zobacz Plan Architekta"):
                            st.markdown(node_state["plan"])
            
            final_response = "Zadanie wykonane! Sprawdź pliki w panelu bocznym."
            status_container.update(label="Gotowe!", state="complete", expanded=False)
            
        except Exception as e:
            st.error(f"Błąd połączenia z Ollama: {str(e)}")
            final_response = "Wystąpił błąd. Upewnij się, że Ollama działa."

        st.markdown(final_response)
        st.session_state["messages"].append({"role": "assistant", "content": final_response})