@echo off

REM Go to project folder (optional if already there)
cd /d %~dp0

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Move to backend folder
cd backend

REM Run FastAPI with uvicorn
python -m uvicorn main:app --reload

pause