@echo off
REM Run the app from source on Windows without building anything. First run installs packages.
cd /d "%~dp0\.."
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
python -c "import docx, pdfplumber" 2>NUL || pip install -r requirements.txt tkinterdnd2 >NUL
python grfp_app.py
