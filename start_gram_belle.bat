@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

echo [Gram Belle] Preparing launch...

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
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

echo [Gram Belle] Using Python: %PYTHON_EXE%
echo [Gram Belle] Opening UI at http://127.0.0.1:8000/
start "" "http://127.0.0.1:8000/"

echo [Gram Belle] Starting server... Press Ctrl+C to stop.
"%PYTHON_EXE%" -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start server.
    echo Ensure dependencies are installed in your current environment.
    pause
    exit /b 1
)

endlocal
