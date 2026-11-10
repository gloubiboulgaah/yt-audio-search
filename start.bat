@echo off
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv || python -m venv .venv)
.venv\Scripts\python -m pip install -q -U -r requirements.txt
.venv\Scripts\python app.py
pause
