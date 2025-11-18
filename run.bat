@echo off
cls
echo ==========================================
echo      CODEFABRIC AI - SZYBKI START
echo ==========================================

:: 1. SPRAWDZANIE PYTHONA
echo.
echo [1/4] Sprawdzam Pythona...
python --version >nul 2>&1
if errorlevel 1 goto NoPython

:: 2. SPRAWDZANIE VENV
echo.
echo [2/4] Sprawdzam srodowisko venv...
if exist venv goto ActivateVenv
echo    -> Tworze folder venv...
python -m venv venv

:ActivateVenv
echo    -> Aktywuje venv...
call venv\Scripts\activate

:: 3. INSTALACJA BIBLIOTEK
echo.
echo [3/4] Instaluje biblioteki...
pip install -r requirements.txt

:: 4. URUCHOMIENIE
echo.
echo [4/4] Uruchamiam aplikacje...
echo ==========================================
streamlit run app.py
goto End

:: --- OBSLUGA BLEDOW ---
:NoPython
echo.
echo [BLAD] Nie wykryto polecenia 'python'.
echo Zainstaluj Python 3.10+ i zaznacz opcje "Add to PATH".
pause
exit

:End
pause