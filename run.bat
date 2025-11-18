@echo off
title CodeFabric Launcher
cls

echo ==================================================
echo      ROCKET LAUNCHER: CODEFABRIC AI
echo ==================================================

:: 1. Sprawdzenie czy Python istnieje
echo [1/5] Sprawdzam instalacje Pythona...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 4
    echo [BLAD] Nie wykryto Pythona! 
    echo Zainstaluj Python 3.10+ ze strony python.org lub Microsoft Store.
    pause
    exit
)
echo [OK] Python wykryty.

:: 2. Tworzenie/Aktywacja VENV
echo.
echo [2/5] Konfiguracja srodowiska wirtualnego...
if not exist venv (
    echo    -> Tworzenie folderu venv (to potrwa chwile)...
    python -m venv venv
) else (
    echo    -> Venv juz istnieje, pomijam tworzenie.
)

call venv\Scripts\activate

:: 3. Instalacja bibliotek
echo.
echo [3/5] Aktualizacja bibliotek (requirements.txt)...
pip install -r requirements.txt


:: 5. Start
echo.
echo [5/5] Wszystko gotowe! Odpalam aplikacje...
echo ==================================================
streamlit run app.py

pause