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

call uv sync
if errorlevel 1 exit /b 1

start "" http://127.0.0.1:8000/
call uv run --with uvicorn uvicorn game_survey_workbench.app:create_app --factory --reload --host 127.0.0.1 --port 8000
