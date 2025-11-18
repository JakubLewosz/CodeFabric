import requests
import json
import os
import urllib3
from dotenv import load_dotenv

# --- KONFIGURACJA I WYCISZENIE OSTRZEŻEŃ SSL ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Konfiguracja
URL = os.getenv("OLLAMA_BASE_URL", "https://localhost:11434")
MODEL = os.getenv("MODEL_CODER", "llama3")
TOKEN = os.getenv("OLLAMA_TOKEN", "")

print(f"--- TEST BEZPOŚREDNI (RAW HTTP - NO SSL VERIFY) ---")
print(f"Cel: {URL}")
print(f"Model: {MODEL}")

headers = {"Content-Type": "application/json"}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"

payload = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "Napisz jedno krotkie zdanie."}],
    "stream": False 
}

try:
    # UWAGA: verify=False wyłącza sprawdzanie certyfikatu
    response = requests.post(
        f"{URL}/api/chat", 
        headers=headers, 
        json=payload, 
        timeout=120, 
        verify=False 
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        content = data.get("message", {}).get("content", "")
        print(f"\nODPOWIEDŹ:\n{content}")
        if not content:
            print("!!! PUSTA TREŚĆ W JSONIE !!!")
    else:
        print(f"BŁĄD HTTP: {response.text}")

except Exception as e:
    print(f"BŁĄD POŁĄCZENIA: {e}")