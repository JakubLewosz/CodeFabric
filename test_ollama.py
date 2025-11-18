# Plik: test_ollama.py
from langchain_ollama import ChatOllama
import time

print("--- ROZPOCZYNAM TEST OLLAMA ---")

# 1. Próba na localhost
print("1. Próba połączenia z http://localhost:11434 ...")
try:
    llm = ChatOllama(model="llama3", base_url="http://localhost:11434", temperature=0)
    response = llm.invoke("Powiedz tylko słowo TEST")
    print(f"   SUKCES! Odpowiedź: {response.content}")
except Exception as e:
    print(f"   BŁĄD: {e}")

print("-" * 30)

# 2. Próba na 127.0.0.1 (częsty błąd Windowsa)
print("2. Próba połączenia z http://127.0.0.1:11434 ...")
try:
    llm = ChatOllama(model="llama3", base_url="http://127.0.0.1:11434", temperature=0)
    response = llm.invoke("Powiedz tylko słowo TEST")
    print(f"   SUKCES! Odpowiedź: {response.content}")
except Exception as e:
    print(f"   BŁĄD: {e}")

print("--- KONIEC TESTU ---")