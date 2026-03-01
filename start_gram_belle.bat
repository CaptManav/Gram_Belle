@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

echo [Gram Belle] Preparing launch...

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R "^[A-Za-z_][A-Za-z0-9_]*=" ".env"`) do (
        set "%%A=%%B"
    )
)

if "%GROQ_API_KEY%"=="" (
    echo [ERROR] GROQ_API_KEY is not set.
    echo Add GROQ_API_KEY in .env, then run this file again.
    pause
    exit /b 1
)

if "%XTTS_SPEED%"=="" set "XTTS_SPEED=1.35"
if "%XTTS_PRELOAD_ON_START%"=="" set "XTTS_PRELOAD_ON_START=1"

echo [Gram Belle] Using Python: %PYTHON_EXE%
echo [Gram Belle] XTTS speed: %XTTS_SPEED%
echo [Gram Belle] Starting server in a new window...
start "Gram Belle Server" cmd /k ""%PYTHON_EXE%" -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 2 /nobreak >nul

echo [Gram Belle] Opening frontend at http://127.0.0.1:8000/
start "" "http://127.0.0.1:8000/"

echo [Gram Belle] Launched. Server and frontend are running.
echo [Gram Belle] If you also want terminal mode, run: "%PYTHON_EXE%" agent_v1.py

endlocal
