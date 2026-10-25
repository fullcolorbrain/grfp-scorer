#!/bin/bash
# Build an INTEL (x86_64) "GRFP Scorer.app" and .dmg. Works on either kind of Mac:
#   - on an Apple Silicon Mac (M1-M4) it builds under Rosetta 2, so you do not need an Intel Mac;
#   - on an Intel Mac it simply builds natively.
# Run from the grfp-scorer folder:
#     bash installer/build_mac_intel.sh
# Requires: Python 3.9+ from https://www.python.org/downloads/ (its macOS installer is
# "universal2": it contains both the Intel and the Apple Silicon interpreter, plus Tk).
# Homebrew's Python on an Apple Silicon Mac is arm64-only and cannot make an Intel build.
# To force a particular interpreter:   PYTHON=/path/to/python3 bash installer/build_mac_intel.sh
# Output goes to dist-intel/ so it never overwrites the Apple Silicon build in dist/.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
X86="arch -x86_64"                       # run a command as an Intel process (no-op on an Intel Mac)
VENV="$ROOT/.build-venv-intel"
DIST="$ROOT/dist-intel"; WORK="$ROOT/build-intel"
APP="$DIST/GRFP Scorer.app"; DMG="$DIST/GRFP Scorer (Intel).dmg"

[ "$(uname -s)" = "Darwin" ] || { echo "This script must be run on a Mac."; exit 1; }

echo "== Checking this Mac can run Intel code"
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = "1" ]; then
  if ! $X86 /usr/bin/true 2>/dev/null; then
    echo "Apple Silicon Mac without Rosetta 2. Install it (one minute), then rerun this script:"
    echo "    softwareupdate --install-rosetta --agree-to-license"
    exit 1
  fi
  echo "   Apple Silicon Mac with Rosetta 2: building the Intel app under Rosetta."
else
  echo "   Intel Mac: building natively."
fi

echo "== Finding a Python that can run as Intel and has Tk 8.6"
PROBE='import sys, platform, tkinter
assert platform.machine() == "x86_64", "not x86_64"
assert tkinter.TkVersion >= 8.6, "Tk too old"
assert sys.version_info >= (3, 9), "Python too old"
assert "conda" not in sys.prefix.lower(), "conda"'
CANDIDATES=()
[ -n "${PYTHON:-}" ] && CANDIDATES+=("$PYTHON")
# python.org framework builds, newest first
while IFS= read -r p; do [ -n "$p" ] && CANDIDATES+=("$p/bin/python3"); done < <(ls -d /Library/Frameworks/Python.framework/Versions/3.* 2>/dev/null | sort -t. -k3,3nr)
CANDIDATES+=("/usr/local/bin/python3")   # python.org symlink, or Intel Homebrew
command -v python3 >/dev/null 2>&1 && CANDIDATES+=("$(command -v python3)")
PY=""
for c in "${CANDIDATES[@]}"; do
  [ -x "$c" ] || continue
  [ "$c" = "/usr/bin/python3" ] && continue      # Apple's stub: old Tk 8.5, draws blank windows
  if $X86 "$c" -c "$PROBE" 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "No suitable Python found. An Intel build needs a Python that contains an x86_64 interpreter and Tk 8.6."
  echo "Install the macOS installer from https://www.python.org/downloads/ (it is universal2 and includes Tk),"
  echo "then rerun this script. Homebrew/conda Python on an Apple Silicon Mac will not work for this."
  exit 1
fi
echo "   Using $PY ($($X86 "$PY" -c 'import platform;print(platform.python_version(), platform.machine())'))"

if grep -q PASTE_DEPLOYMENT_ID register.py; then
  echo "WARNING: register.py still has the placeholder ENDPOINT; built apps will store registrations locally and never send them."
fi
echo "== Creating the Intel build environment (packages are downloaded as Intel wheels)"
rm -rf "$VENV" "$WORK" "$DIST"
$X86 "$PY" -m venv "$VENV"
VPY="$VENV/bin/python"                   # always call through $X86: the venv python is universal too
export ARCHFLAGS="-arch x86_64"          # in case any package has to compile from source
$X86 "$VPY" -m pip install --upgrade pip >/dev/null
# Prebuilt wheels only. If pip compiles a package here it links against THIS Mac's Homebrew libraries
# (seen with cryptography -> Homebrew OpenSSL), which then clash with Python's own inside the bundle and
# do not exist on students' Macs. --only-binary makes pip pick the newest version that has an Intel wheel.
PKGS=(-r requirements.txt pyinstaller tkinterdnd2)
if ! $X86 "$VPY" -m pip install --only-binary=:all: "${PKGS[@]}" >/dev/null 2>"$ROOT/.pip-intel.log"; then
  echo "   note: not every package has a wheel (details in .pip-intel.log); requiring wheels for the compiled ones only."
  $X86 "$VPY" -m pip install --only-binary=cryptography,cffi,lxml,pillow,pypdfium2,pydantic-core,jiter,charset-normalizer "${PKGS[@]}" >/dev/null
fi

echo "== Checking no package was compiled against Homebrew libraries"
SP="$($X86 "$VPY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
HB=0
while IFS= read -r -d '' f; do
  libs="$(otool -L "$f" 2>/dev/null || true)"
  case "$libs" in *"/usr/local/opt/"*|*"/usr/local/Cellar/"*|*"/opt/homebrew/"*) echo "   links to Homebrew: ${f#$SP/}"; HB=1 ;; esac
done < <(find "$SP" -type f \( -name "*.so" -o -name "*.dylib" \) -print0)
if [ "$HB" = "1" ]; then
  echo "The packages above were built on this Mac against Homebrew and will not work on other Macs. Not building."
  exit 1
fi
echo "   none."

# tkinterdnd2 ships a tkdnd library per platform; with --collect-all the arm64-only one would be
# swept into an x86_64 bundle and PyInstaller rejects it. Drop it from this throwaway venv.
TKDND="$($X86 "$VPY" -c 'import os, tkinterdnd2; print(os.path.join(os.path.dirname(tkinterdnd2.__file__), "tkdnd"))' 2>/dev/null || true)"
if [ -n "$TKDND" ] && [ -d "$TKDND" ]; then
  rm -rf "$TKDND"/osx-arm64*
  [ -d "$TKDND/osx-x64" ] || echo "   note: tkinterdnd2 has no osx-x64 library; the app will still work, without drag-and-drop."
fi

echo "== Building the app bundle (x86_64)"
$X86 "$VPY" -m PyInstaller --noconfirm --windowed --name "GRFP Scorer" \
  --target-arch x86_64 \
  --distpath "$DIST" --workpath "$WORK" --specpath "$WORK" \
  --add-data "$ROOT/rubric.md:." --add-data "$ROOT/LICENSE:." --add-data "$ROOT/DISCLAIMER.md:." --add-data "$ROOT/PRIVACY.md:." --add-data "$ROOT/installer/icon/grfp_icon.png:installer/icon" \
  --icon "$ROOT/installer/icon/grfp_icon.icns" \
  --collect-all tkinterdnd2 \
  --hidden-import anthropic --hidden-import docx --hidden-import pdfplumber \
  --collect-data certifi --hidden-import certifi \
  --collect-all pdfplumber --collect-all pdfminer --collect-all pypdfium2 --collect-all docx \
  "$ROOT/grfp_app.py"

echo "== Verifying every compiled file in the bundle is Intel"
BAD=0; N=0
while IFS= read -r -d '' f; do
  case "$(file -b "$f")" in *Mach-O*) ;; *) continue ;; esac
  N=$((N+1))
  archs="$(lipo -archs "$f" 2>/dev/null || true)"
  case " $archs " in *" x86_64 "*) ;; *) echo "   NOT Intel: ${f#$APP/}  ($archs)"; BAD=1 ;; esac
done < <(find "$APP" -type f \( -name "*.so" -o -name "*.dylib" -o -perm +111 \) -print0)
if [ "$BAD" = "1" ]; then
  echo "Some files above are not x86_64, so this app would fail on an Intel Mac. Not packaging it."
  echo "Usual cause: a package shipped an arm64-only library, or was installed by an arm64 pip."
  exit 1
fi
echo "   $N compiled files checked, all x86_64."

echo "== Smoke test: importing the app's dependencies as an Intel process"
$X86 "$VPY" - <<'EOF'
import platform, tkinter, anthropic, docx, pdfplumber, pypdfium2, certifi
assert platform.machine() == "x86_64"
print("   imports fine under", platform.machine())
EOF

echo "== Self-test of the finished app (loads every bundled library from inside the bundle)"
if ! "$APP/Contents/MacOS/GRFP Scorer" --selftest; then
  echo "The app was built but one of its libraries cannot load (see FAIL above). Not packaging it."
  exit 1
fi

echo "== Oldest macOS this build can run on"
$X86 "$VPY" - <<'EOF'
import glob, os, re, sysconfig
def ver(s): p = [int(x) for x in str(s).split(".")]; return (p[0], p[1] if len(p) > 1 else 0)
floor, why = ver(sysconfig.get_config_var("MACOSX_DEPLOYMENT_TARGET") or "10.9"), "Python itself"
for w in glob.glob(os.path.join(sysconfig.get_paths()["purelib"], "*.dist-info", "WHEEL")):
    tags = re.findall(r"macosx_(\d+)_(\d+)_(?:x86_64|universal2|intel)", open(w).read())
    if tags:
        need = min((int(a), int(b)) for a, b in tags)
        if need > floor: floor, why = need, os.path.basename(os.path.dirname(w)).split("-")[0]
print(f"   macOS {floor[0]}.{floor[1]} or newer (set by {why}). Users on older systems can run from source (see INSTALL.md).")
EOF

echo "== Packaging DMG"
STAGE="$(mktemp -d)"; cp -R "$APP" "$STAGE/"; ln -s /Applications "$STAGE/Applications"
cp "$ROOT/LICENSE" "$ROOT/DISCLAIMER.md" "$ROOT/PRIVACY.md" "$ROOT/USER_GUIDE.md" "$STAGE/"
hdiutil create -volname "GRFP Scorer (Intel)" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"
echo
echo "Done: ${DMG#$ROOT/}   (drag the app to Applications)"
echo "This build runs on Intel Macs, and also on Apple Silicon Macs through Rosetta; give Apple Silicon"
echo "users the native build from build_mac.sh instead, which starts faster."
echo "First launch (unsigned app): macOS 14 and earlier - right-click the app > Open, then Open again."
echo "  macOS 15 and later - double-click once, dismiss the warning, then System Settings >"
echo "  Privacy & Security > scroll down > Open Anyway."
echo "Local models: Ollama on an Intel Mac runs on the CPU only and a 14B model can take many minutes"
echo "  per statement. For Intel users, the Claude API key (or the offline mode) is the practical choice."
