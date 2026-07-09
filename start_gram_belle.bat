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
echo [Gram Belle] Starting server in a new window (bound to 0.0.0.0 for phone access)...
start "Gram Belle Server" cmd /k ""%PYTHON_EXE%" -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [Gram Belle] Local Network URLs:
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /R /C:"IPv4 Address"') do (
    set "IP=%%i"
    set "IP=!IP:~1!"
    echo     http://!IP!:8000/
)
echo     http://127.0.0.1:8000/

echo.
echo [Gram Belle] Opening local frontend...
start "" "http://127.0.0.1:8000/"

echo [Gram Belle] Launched. Server is running on all interfaces.
echo [Gram Belle] Enter one of the network IP URLs shown above into your phone app.

endlocal
