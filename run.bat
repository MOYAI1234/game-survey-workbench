@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example.
  echo Please edit .env and finish a real LLM configuration before running again.
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  set "key=%%A"
  set "value=%%B"
  if not "!key!"=="" if not "!key:~0,1!"=="#" set "!key!=!value!"
)

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "FALLBACK_VENV_PYTHON=%CD%\..\..\.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" set "VENV_PYTHON=%FALLBACK_VENV_PYTHON%"
if not exist "%VENV_PYTHON%" (
  echo Missing project virtual environment at %VENV_PYTHON%.
  exit /b 1
)

set "PORT=8000"
set "PORT_CANDIDATES=8000 8014 8015 8016 8017 8018"
for %%P in (%PORT_CANDIDATES%) do (
  netstat -ano | findstr :%%P >nul
  if errorlevel 1 (
    set "PORT=%%P"
    goto port_selected
  )
  echo Port %%P is already in use, trying the next port.
)

echo Could not find an available port.
exit /b 1

:port_selected

call python -m uv sync --extra dev
if errorlevel 1 exit /b 1

set "PYTHONPATH=%CD%\src"
echo Starting server on http://127.0.0.1:!PORT!/
start "" http://127.0.0.1:!PORT!/
call "%VENV_PYTHON%" -m uvicorn --app-dir src game_survey_workbench.app:create_app --factory --host 127.0.0.1 --port !PORT!
