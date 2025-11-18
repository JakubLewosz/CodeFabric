graph TD
    %% Style definicje
    classDef ui fill:#ff9a9e,stroke:#333,stroke-width:2px;
    classDef ai fill:#a1c4fd,stroke:#333,stroke-width:2px;
    classDef storage fill:#f6d365,stroke:#333,stroke-width:2px;
    classDef external fill:#d4fc79,stroke:#333,stroke-width:2px;

    %% Węzły
    User((👤 Użytkownik)):::ui
    
    subgraph "Frontend (Streamlit)"
        UI[Interfejs Czat & Panel Boczny]:::ui
        Upload[Upload Plików]:::ui
    end

    subgraph "Core Logic (Python/LangChain)"
        Orchestrator{⚙️ Supervisor Graph}:::ai
        
        subgraph "Agenci (Wirtualny Zespół)"
            Planner[🧠 Agent Architekt\n(Planner)]:::ai
            Coder[👨‍💻 Agent Programista\n(Coder)]:::ai
            Reviewer[🕵️ Agent Recenzent\n(QA/Reviewer)]:::ai
        end
    end

    subgraph "Pamięć i Dane (Local Storage)"
        RAG_DB[(🗄️ ChromaDB\nVector Store)]:::storage
        FileSystem[📂 File System\n/workspace]:::storage
    end

    subgraph "Inference Engine (Localhost)"
        Ollama[🦙 Ollama Server]:::external
        LLM_Code[Model: DeepSeek Coder]:::external
        LLM_Chat[Model: Llama 3]:::external
    end

    %% Połączenia
    User -->|Prompt / Komenda| UI
    User -->|Dokumentacja PDF/TXT| Upload
    Upload -->|Embeddingi| RAG_DB
    
    UI <-->|Streaming Response| Orchestrator
    
    Orchestrator -->|1. Analiza| Planner
    Orchestrator -->|2. Generowanie| Coder
    Orchestrator -->|3. Weryfikacja| Reviewer
    
    Planner <-->|Kontekst RAG| RAG_DB
    Planner <-->|Zapytanie| LLM_Chat
    
    Coder -->|Zapis kodu| FileSystem
    Coder <-->|Generowanie kodu| LLM_Code
    Coder <-->|Odczyt przykładów| RAG_DB
    
    Reviewer -->|Odczyt plików| FileSystem
    Reviewer <-->|Analiza kodu| LLM_Code
    
    Ollama --- LLM_Code
    Ollama --- LLM_Chat
