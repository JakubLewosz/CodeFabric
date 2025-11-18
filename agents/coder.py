import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from state import AgentState
from tools.file_ops import write_file

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN")
MODEL_NAME = os.getenv("MODEL_CODER", "deepseek-coder-v2") # Tu używamy modelu kodującego!
VERIFY_SSL = os.getenv("VERIFY_SSL", "False").lower() == "true"

llm = ChatOllama(
    model=MODEL_NAME,
    base_url=OLLAMA_URL,
    temperature=0.2,
    client_kwargs={
        "verify": VERIFY_SSL,
        "headers": {
            "Authorization": f"Bearer {OLLAMA_TOKEN}"
        }
    }
)

def coder_node(state: AgentState):
    plan = state["plan"]
    sys_msg = SystemMessage(content=f"""
    Jesteś Senior Developerem. Napisz kod na podstawie PLANU.
    PLAN: {plan}
    """)
    response = llm.invoke([sys_msg])
    
    # Symulacja zapisu (MVP)
    write_file("README_AI.md", f"PLAN:\n{plan}\n\nKOD:\n{response.content}")
    
    return {"current_files": ["README_AI.md"], "messages": [response]}