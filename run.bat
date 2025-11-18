@echo off
title CodeFabric Launcher
cls

echo ==================================================
echo      CODEFABRIC AI - SZYBKI START
echo ==================================================

:: 1. Sprawdzenie czy Python istnieje
echo [1/4] Sprawdzam Pythona...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 4
    echo [BLAD] Nie znaleziono polecenia 'python'.
    echo Upewnij sie, ze Python jest dodany do zmiennych srodowiskowych (PATH).
    pause
    exit
)

:: 2. Konfiguracja VENV
echo.
echo [2/4] Sprawdzam srodowisko wirtualne...
if not exist venv (
    echo    -> Tworze folder venv...
    python -m venv venv
)

echo    -> Aktywuje venv...
call venv\Scripts\activate

:: 3. Instalacja bibliotek
echo.
echo [3/4] Sprawdzam biblioteki...
pip install -r requirements.txt

:: 4. Start Aplikacji (Bez pobierania modeli)
echo.
echo [4/4] Uruchamianie Streamlit...
echo ==================================================
streamlit run app.py

pause