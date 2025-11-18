from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState

# Używamy Llama3 do planowania (jest szybka i logiczna)
llm = ChatOllama(model="llama3", temperature=0)

def planner_node(state: AgentState):
    messages = state["messages"]
    
    # System Prompt dla Architekta
    sys_msg = SystemMessage(content="""
    Jesteś Głównym Architektem Oprogramowania (Tech Lead).
    Twoim zadaniem jest przeanalizowanie prośby użytkownika i stworzenie precyzyjnego planu implementacji.
    
    Twoja odpowiedź musi zawierać:
    1. Wybór technologii (Python, HTML, etc.).
    2. Listę plików do utworzenia.
    3. Krótki opis co ma być w każdym pliku.
    
    Nie pisz kodu, tylko PLAN. Bądź zwięzły.
    """)
    
    # Wywołanie modelu
    response = llm.invoke([sys_msg] + messages)
    
    # Aktualizacja stanu: zapisujemy plan i dodajemy wiadomość do historii
    return {
        "plan": response.content,
        "messages": [response]
    }