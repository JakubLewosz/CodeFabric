@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo      CODEFABRIC AI - SZYBKI START
echo ==========================================

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1 || goto :no_python
    set "PYTHON_CMD=python"
)

echo.
echo [1/4] Sprawdzam Python 3.10+...
%PYTHON_CMD% -c "import sys; raise SystemExit(sys.version_info ^< (3, 10))"
if errorlevel 1 goto :bad_python

echo.
echo [2/4] Przygotowuje srodowisko .venv...
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(sys.version_info ^< (3, 10))"
if errorlevel 1 goto :bad_venv

echo.
echo [3/4] Instaluje zaleznosci...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo [4/4] Uruchamiam aplikacje...
echo ==========================================
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto :failed
goto :end

:no_python
echo.
echo [BLAD] Nie wykryto Pythona. Zainstaluj Python 3.10 lub nowszy.
goto :failed

:bad_python
echo.
echo [BLAD] CodeFabric wymaga Python 3.10 lub nowszego.
goto :failed

:bad_venv
echo.
echo [BLAD] Istniejacy katalog .venv uzywa Pythona starszego niz 3.10.
echo Usun .venv, a nastepnie uruchom run.bat ponownie.
goto :failed

:failed
echo.
echo Uruchomienie nie powiodlo sie.
pause
exit /b 1

:end
endlocal
