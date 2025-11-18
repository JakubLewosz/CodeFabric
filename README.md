<div align="center">

# 🏗️ CodeFabric
### Local AI Software House & Autonomous Agent System

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black?logo=ollama&logoColor=white)
![LangChain](https://img.shields.io/badge/LangGraph-Orchestration-E10098?logo=langchain&logoColor=white)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

**CodeFabric to Twój prywatny zespół deweloperski działający na localhost.**
Projekt symuluje pracę software house'u, w którym wyspecjalizowane agenty AI (Architekt, Programista, Tester) zarządzane są przez AI Menedżera.

**Zero chmury. 100% prywatności.**

[Zgłoś Błąd] • [Wiki] • [Roadmapa]

</div>

---

## 💡 O Projekcie

CodeFabric to platforma typu **Autonomous Agentic Workflow**, która automatyzuje proces wytwarzania oprogramowania. W odróżnieniu od zwykłych asystentów (jak ChatGPT), CodeFabric nie tylko "rozmawia", ale **fizycznie wykonuje pracę**: planuje strukturę, tworzy pliki, pisze kod i samodzielnie go naprawia.

### Kluczowe Wartości
* **🔐 Private Cloud on Localhost:** Działa na modelach Open Source (DeepSeek/Llama3) via **Ollama**. Idealne dla danych wrażliwych.
* **🔄 Self-Healing Code:** Dzięki pętlom zwrotnym w LangGraph, system potrafi wykryć błąd w wygenerowanym kodzie i go poprawić bez ingerencji człowieka.
* **🧠 Menedżer AI:** Nad wszystkim czuwa nadrzędny agent (Supervisor), który dynamicznie przydziela zadania, zapobiegając utknięciu procesu w martwym punkcie.
* **📚 RAG Context:** Możliwość douczania agenta na własnej dokumentacji (PDF/TXT).

---

## 🗺️ Koncepcja (Mindmap)

Szybki rzut oka na cele i strukturę projektu.

```mermaid
mindmap
  root((CodeFabric))
    Cele
      Prywatność (Localhost)
      Automatyzacja (End-to-End)
      Samonaprawianie (Self-Healing)
    Agenci
      Supervisor (Manager)
      Planner (Architekt)
      Coder (Programista)
      Reviewer (Tester)
    Tech Stack
      LangGraph (Orkiestracja)
      Ollama (AI Backend)
      ChromaDB (Pamięć RAG)
      Streamlit (UI)
