#!/bin/bash
# Run the app from source on macOS/Linux without building anything. First run installs packages.
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -c "import docx, pdfplumber" 2>/dev/null || pip install -r requirements.txt tkinterdnd2 >/dev/null
python grfp_app.py
