#!/bin/bash
# Build "GRFP Scorer.app" and a .dmg on macOS. Run from the grfp-scorer folder:
#     bash installer/build_mac.sh
# Requires: Python 3.9+ from python.org (Homebrew Python also works), Xcode command-line tools
# (for hdiutil, already on macOS). Internet access is needed once, to install packages.
set -e
cd "$(dirname "$0")/.."
echo "== Checking Python has Tk (needed for the app window)"
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "This python3 ($(command -v python3)) has no Tk support, so the app window cannot be built."
  if command -v brew >/dev/null 2>&1; then
    PYV=$(python3 -c "import sys;print(f'{sys.version_info[0]}.{sys.version_info[1]}')")
    echo "Homebrew Python: run    brew install python-tk@${PYV}    then rerun this script."
  else
    echo "Install Python from https://www.python.org/downloads/ (it includes Tk), then rerun this script."
  fi
  exit 1
fi
if python3 -c "import sys; sys.exit(0 if 'anaconda' in sys.prefix.lower() or 'conda' in sys.prefix.lower() else 1)"; then
  echo "python3 is conda's ($(command -v python3)); PyInstaller + Tk is unreliable there. Run:  conda deactivate  and rerun."
  exit 1
fi
if grep -q PASTE_DEPLOYMENT_ID register.py; then
  echo "WARNING: register.py still has the placeholder ENDPOINT; built apps will store registrations locally and never send them."
fi
echo "== Creating build environment"
python3 -m venv .build-venv
source .build-venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt pyinstaller tkinterdnd2 >/dev/null
echo "== Building app bundle"
rm -rf build dist
pyinstaller --noconfirm --windowed --name "GRFP Scorer" \
  --add-data "rubric.md:." --add-data "LICENSE:." --add-data "DISCLAIMER.md:." --add-data "PRIVACY.md:." --add-data "installer/icon/grfp_icon.png:installer/icon" \
  --icon "installer/icon/grfp_icon.icns" \
  --collect-all tkinterdnd2 \
  --hidden-import anthropic --hidden-import docx --hidden-import pdfplumber \
  --collect-data certifi --hidden-import certifi \
  --collect-all pdfplumber --collect-all pdfminer --collect-all pypdfium2 --collect-all docx \
  grfp_app.py
echo "== Self-test of the finished app (loads every bundled library from inside the bundle)"
if ! "dist/GRFP Scorer.app/Contents/MacOS/GRFP Scorer" --selftest; then
  echo "The app was built but one of its libraries cannot load (see FAIL above). Not packaging it."
  exit 1
fi
echo "== Packaging DMG"
rm -f "dist/GRFP Scorer.dmg"
STAGE="$(mktemp -d)"; cp -R "dist/GRFP Scorer.app" "$STAGE/"; ln -s /Applications "$STAGE/Applications"
cp LICENSE DISCLAIMER.md PRIVACY.md USER_GUIDE.md "$STAGE/"
hdiutil create -volname "GRFP Scorer" -srcfolder "$STAGE" -ov -format UDZO "dist/GRFP Scorer.dmg" >/dev/null
rm -rf "$STAGE"
echo
echo "Done: dist/GRFP Scorer.dmg   (drag the app to Applications)"
echo "First launch (unsigned app): macOS 14 and earlier - right-click the app > Open, then Open again."
echo "  macOS 15 and later - double-click, dismiss the warning, then System Settings > Privacy & Security > Open Anyway."
echo "Intel Macs need the separate Intel build:  bash installer/build_mac_intel.sh"
echo "Optional local model: install Ollama from https://ollama.com and run:  ollama pull llama3.1:8b"
