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

for /f %%P in ('netstat -ano ^| findstr :8000') do (
  echo Port 8000 is already in use.
  echo Please stop the existing process and run run.bat again.
  exit /b 1
)

call python -m uv sync --extra dev
if errorlevel 1 exit /b 1

set "PYTHONPATH=%CD%\src"
start "" http://127.0.0.1:8000/
call python -m uvicorn --app-dir src game_survey_workbench.app:create_app --factory --host 127.0.0.1 --port 8000
