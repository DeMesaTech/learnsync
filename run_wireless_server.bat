@echo off
title LearnSync Launcher

REM Go to project folder
cd /d "%~dp0"

REM Start Cloudflare Tunnel in a separate window
start "LearnSync Tunnel" cmd /k "cloudflared tunnel --url http://localhost:8000"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Move to backend folder
cd backend

REM Run FastAPI with uvicorn
python -m uvicorn main:app --reload --log-config logging.conf


pause