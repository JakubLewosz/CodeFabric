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
Zero chmury. 100% prywatności.

[Demo (Wkrótce)] • [Dokumentacja] • [Zgłoś Błąd]

</div>

---

## 💡 O Projekcie

CodeFabric to platforma typu **Autonomous Agentic Workflow**, która automatyzuje proces wytwarzania oprogramowania. W odróżnieniu od zwykłych asystentów (jak ChatGPT), CodeFabric nie tylko "rozmawia", ale **fizycznie wykonuje pracę**: planuje strukturę, tworzy pliki, pisze kod i samodzielnie go naprawia.

### Dlaczego CodeFabric?
* **🔐 Private Cloud on Localhost:** Działa na modelach Open Source (Llama 3, DeepSeek) poprzez Ollama. Żadne dane nie opuszczają Twojego komputera.
* **🔄 Self-Healing Code:** Dzięki pętlom zwrotnym w LangGraph, system potrafi wykryć błąd w wygenerowanym kodzie i go poprawić bez ingerencji człowieka.
* **🧠 Menedżer AI:** Nad wszystkim czuwa nadrzędny agent (Supervisor), który dynamicznie przydziela zadania, zapobiegając utknięciu procesu w martwym punkcie.

---

## 🧠 Architektura: Hierarchiczny System Agentów

Projekt wykorzystuje wzorzec **Supervisor (Nadzorca)**. Centralny Menedżer decyduje, który agent powinien działać w danym momencie.

```mermaid
stateDiagram-v2
    %% Style Definitions
    classDef manager fill:#2d2d2d,stroke:#fff,stroke-width:4px,color:#fff;
    classDef worker fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000;
    classDef user fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;

    User_Input: 👤 Użytkownik (Prompt)
    Final_Output: 🚀 Gotowy Projekt (/workspace)
    
    state "🕵️‍♂️ AI PROJECT MANAGER" as Manager:::manager
    
    %% Worker Agents
    state "🧠 Architekt (Planner)" as Planner:::worker
    state "👨‍💻 Programista (Coder)" as Coder:::worker
    state "🔎 Tester (Reviewer)" as Reviewer:::worker

    [*] --> User_Input
    User_Input --> Manager: Nowe zadanie

    %% Workflow
    Manager --> Planner: 1. Potrzebny plan
    Planner --> Manager: Strategia gotowa

    Manager --> Coder: 2. Napisz kod
    Coder --> Manager: Pliki utworzone

    Manager --> Reviewer: 3. Sprawdź jakość
    Reviewer --> Manager: Raport błędów

    %% Logic Routing
    state Decyzja <<Choice>>
    Manager --> Decyzja
    
    Decyzja --> Coder: ❌ Błędy (Fix Loop)
    Decyzja --> Planner: ❌ Zły plan (Re-plan)
    Decyzja --> Final_Output: ✅ Sukces
