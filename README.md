# 🚀 CodeFabric v2.0 - Instrukcja Instalacji

## 📦 Co Jest w Paczce?

Ten folder zawiera **poprawione pliki** gotowe do zainstalowania w Twoim projekcie CodeFabric.

```
codefabric_v2/
├── agents/
│   ├── __init__.py
│   ├── coder.py          ← Diff-editing + smart truncate
│   ├── manager.py        ← Diagnostyka + failure reports
│   ├── planner.py        ← Kontekst-aware prompty
│   └── reviewer.py       ← Lepszy checklist + raporty
│
├── tools/
│   ├── __init__.py
│   ├── file_ops.py       ← System backup/restore
│   └── llm_factory.py    ← Monitoring tokenów
│
├── graph/
│   ├── __init__.py
│   └── workflow.py       ← Bez zmian
│
├── state.py              ← Bez zmian
├── app.py                ← UI z rollback + fixy
│
└── INSTALL_README.md     ← Ten plik
```

---

## ⚡ Instalacja - Krok po Kroku

### Opcja 1: Automatyczna (Zalecana dla Linux/Mac)

```bash
# 1. Przejdź do swojego katalogu CodeFabric
cd ~/CodeFabric

# 2. Stwórz backup (dla bezpieczeństwa)
cp -r . ../CodeFabric_backup

# 3. Skopiuj wszystkie pliki
cp -r /ścieżka/do/codefabric_v2/* .

# 4. Upewnij się że struktura katalogów istnieje
mkdir -p backups workspace

# 5. Uruchom
streamlit run app.py
```

---

### Opcja 2: Ręczna (Windows lub jeśli wolisz kontrolę)

#### Krok 1: Backup
```bash
# PowerShell
Copy-Item -Path "C:\CodeFabric" -Destination "C:\CodeFabric_backup" -Recurse

# Lub ręcznie skopiuj cały folder
```

#### Krok 2: Zastąp pliki agents/

```bash
# Usuń stare (opcjonalnie przemianuj)
Rename-Item agents\coder.py agents\coder_old.py
Rename-Item agents\manager.py agents\manager_old.py
Rename-Item agents\planner.py agents\planner_old.py
Rename-Item agents\reviewer.py agents\reviewer_old.py

# Skopiuj nowe
Copy-Item codefabric_v2\agents\*.py agents\
```

#### Krok 3: Zastąp pliki tools/

```bash
Rename-Item tools\file_ops.py tools\file_ops_old.py
Rename-Item tools\llm_factory.py tools\llm_factory_old.py

Copy-Item codefabric_v2\tools\*.py tools\
```

#### Krok 4: Zastąp app.py

```bash
Rename-Item app.py app_old.py
Copy-Item codefabric_v2\app.py .
```

#### Krok 5: Stwórz folder backups

```bash
New-Item -ItemType Directory -Path "backups" -Force
```

#### Krok 6: Uruchom

```bash
streamlit run app.py
```

---

## 🧪 Weryfikacja Instalacji

Po uruchomieniu sprawdź:

1. **Sidebar** - Czy widzisz przycisk "⏮️ Rollback"
2. **Wybór modeli** - Czy lista zawiera `qwen2.5-coder:32b`
3. **Logi w konsoli** - Powinny być emoji (🧠, 💻, 🔎, etc.)

---

## 🔧 Konfiguracja

W pliku `.env` możesz ustawić:

```env
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TOKEN=
VERIFY_SSL=False

# Domyślne modele (opcjonalne)
MODEL_PLANNER=mistral:7b
MODEL_CODER=qwen2.5-coder:32b
MODEL_REVIEWER=llama3.3:70b
```

---

## 📊 Główne Zmiany

### ✨ Nowe Funkcje

1. **Diff-Based Editing** - Coder edytuje tylko zmieniane fragmenty (nie przepisuje całości)
2. **System Backup** - Automatyczny backup przed każdą zmianą
3. **Rollback** - 1 kliknięcie = przywrócenie poprzedniej wersji
4. **Smart Truncate** - Zachowuje początek i koniec długich plików
5. **Diagnostyka** - Raporty `FAILURE_REPORT.md` i `review_report.md`

### 🔧 Poprawki

1. **UI freeze** - Naprawione zawieszanie przy odrzuceniu planu
2. **Amnezja LLM** - Rozwiązana utrata kontekstu przy dużych plikach
3. **Manager logic** - Priorytet sukcesu nad limitem prób

---

## 🆘 Troubleshooting

### Problem: "ImportError: cannot import name 'manager_node'"
**Rozwiązanie:**
```bash
# Upewnij się że __init__.py istnieje
touch agents/__init__.py
touch tools/__init__.py
touch graph/__init__.py
```

### Problem: "Brak folderu backups"
**Rozwiązanie:**
```bash
mkdir -p backups
chmod 755 backups
```

### Problem: "Coder nadal przepisuje całe pliki"
**Rozwiązanie:**
- Upewnij się że używasz modelu `qwen2.5-coder:32b`
- Sprawdź czy projekt ma >3 pliki (diff włącza się automatycznie)
- Zobacz logi - powinno być "TRYB ROZWOJU (REFACTORING)" lub "TRYB NAPRAWY"

### Problem: "TypeError: 'NoneType' object is not subscriptable"
**Rozwiązanie:**
```bash
# Sprawdź czy state.py jest poprawny
cat state.py | grep "plan_approved"
# Powinno być: plan_approved: bool
```

---

## 📈 Test Przed i Po

### Test 1: Edycja istniejącego projektu
```
Prompt: "Dodaj licznik kliknięć w prawym górnym rogu"
```

**v1.0:** Przepisze cały plik main.py (może zgubić logikę)  
**v2.0:** Użyje SEARCH/REPLACE tylko dla funkcji draw()

---

### Test 2: Rollback po błędzie
```
1. Wygeneruj prostą grę Snake
2. Poproś o dodanie licznika punktów
3. Jeśli się zepsuje → Kliknij "⏮️ Rollback"
```

**v1.0:** Musisz ręcznie przywracać z Git  
**v2.0:** 2 sekundy = przywrócona poprzednia wersja

---

## 🎯 Zalecane Modele

| Zadanie | Model | Dlaczego? |
|---------|-------|-----------|
| **Kodowanie** | `qwen2.5-coder:32b` | Najlepszy dla diff-editing, duży kontekst |
| **Planowanie** | `mistral:7b` | Szybki, precyzyjny, dobry dla instrukcji |
| **Recenzja** | `llama3.3:70b` | Rozumie złożoną logikę |

---

## 📞 Co Jeśli Coś Nie Działa?

1. **Sprawdź logi** w konsoli (gdzie uruchomiłeś `streamlit run app.py`)
2. **Sprawdź raporty:**
   - `workspace/FAILURE_REPORT.md` (jeśli proces się zawiesił)
   - `workspace/review_report.md` (jeśli kod został odrzucony)
3. **Przywróć backup:**
   ```bash
   rm -rf ~/CodeFabric
   cp -r ~/CodeFabric_backup ~/CodeFabric
   ```

---

## 🎉 Gotowe!

Jeśli wszystko działa:
1. Usuń backup po kilku dniach: `rm -rf ~/CodeFabric_backup`
2. Usuń stare pliki: `rm agents/*_old.py tools/*_old.py app_old.py`
3. Ciesz się nową wersją! 🚀

---

**Wersja:** 2.0  
**Data:** 2024-11-24  
**Kompatybilność:** Python 3.10+, LangGraph 0.0.20+, Ollama