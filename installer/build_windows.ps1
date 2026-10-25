# Build "GRFP Scorer.exe" (portable) and, if Inno Setup 6 is installed, the GRFP-Scorer-Setup-<version>.exe
# installer with the license page. Run from the grfp-scorer folder in PowerShell:
#     powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1
# Requires: Python 3.9+ from python.org with "Add python.exe to PATH" ticked at install.
# Internet access is needed once, to install packages.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
Write-Host "== Checking Python has Tk"
python -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "This Python has no Tk support. Install Python from https://www.python.org/downloads/ (tick 'tcl/tk and IDLE' in Optional Features) and rerun."; exit 1 }
$Version = (Select-String -Path register.py -Pattern 'APP_VERSION\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
Write-Host "== Building GRFP Scorer $Version"
if (Select-String -Path register.py -Pattern "PASTE_DEPLOYMENT_ID" -Quiet) {
  Write-Warning "register.py still has the placeholder ENDPOINT; built apps will store registrations locally and never send them."
}
Write-Host "== Creating build environment"
python -m venv .build-venv
& .\.build-venv\Scripts\Activate.ps1
python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt pyinstaller tkinterdnd2 | Out-Null
Write-Host "== Building executable"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
pyinstaller --noconfirm --onefile --windowed --name "GRFP Scorer" `
  --add-data "rubric.md;." --add-data "LICENSE;." --add-data "DISCLAIMER.md;." --add-data "PRIVACY.md;." --add-data "installer/icon/grfp_icon.png;installer/icon" `
  --icon "installer/icon/grfp_icon.ico" `
  --collect-all tkinterdnd2 `
  --hidden-import anthropic --hidden-import docx --hidden-import pdfplumber `
  --collect-data certifi --hidden-import certifi `
  --collect-all pdfplumber --collect-all pdfminer --collect-all pypdfium2 --collect-all docx `
  grfp_app.py
Write-Host "== Self-test of the finished app"
& "dist\GRFP Scorer.exe" --selftest
if ($LASTEXITCODE -ne 0) { throw "Self-test failed: a bundled library or data file did not load." }
Write-Host "== Installer (Inno Setup)"
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
  $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($iscc) {
  & $iscc "/DAppVersion=$Version" installer\grfp_scorer.iss | Out-Null
  Write-Host "Done: installer\Output\GRFP-Scorer-Setup-$Version.exe   (installer with license page; distribute this)"
} else {
  Write-Host "Inno Setup not found (https://jrsoftware.org/isinfo.php); portable exe only."
}
Write-Host ""
Write-Host "Done: dist\GRFP Scorer.exe   (portable: copy it anywhere and double-click)"
Write-Host "If SmartScreen warns, choose More info > Run anyway (the app is unsigned)."
Write-Host "Optional local model: install Ollama from https://ollama.com and run:  ollama pull llama3.1:8b"
