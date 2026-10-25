# Installer folder

| File | Use |
|---|---|
| `run_from_source.sh` / `.bat` | Simplest: double-click (Windows) or `bash installer/run_from_source.sh` (macOS). Creates a Python environment on first run and launches the app. Needs Python installed. |
| `build_mac.sh` | Builds `GRFP Scorer.app` and `GRFP Scorer.dmg` in `dist/` for the kind of Mac it runs on (Apple Silicon or Intel). Run once on a Mac; then distribute the .dmg — recipients don't need Python. |
| `build_mac_intel.sh` | Builds the **Intel (x86_64)** app and `GRFP Scorer (Intel).dmg` in `dist-intel/`. Runs on an Intel Mac, or on an Apple Silicon Mac under Rosetta 2. Needs python.org (universal2) Python. |
| `build_windows.ps1` | Builds the portable `GRFP Scorer.exe` in `dist\` and, if Inno Setup 6 is installed, `Output\GRFP-Scorer-Setup-<version>.exe` from `grfp_scorer.iss` (shows the license and disclaimer before installing). |
| `grfp_scorer.iss` | Inno Setup script for the Windows installer. |
| `registration-Code.gs` | Google Apps Script that receives first-launch registrations (see INSTALL.md § 4). |
| `../.github/workflows/release.yml` | Runs all three builds on GitHub's runners when a `v*` tag is pushed. |

Binaries must be built on the platform they will run on (a .dmg on a Mac, an .exe on Windows).
A Mac app also matches the chip it was built on; `build_mac_intel.sh` is the exception, producing
the Intel build from either kind of Mac.
The built apps are unsigned; macOS and Windows will ask for confirmation on first launch.

All builds bundle `rubric.md`, `LICENSE`, `DISCLAIMER.md`, and `PRIVACY.md`; the self-test fails if any is missing.

## Backend behaviour (all versions)

On launch the app checks, in order: an Anthropic API key (environment variable or Settings) →
a running Ollama server with at least one model → offline. It reports which it chose and lets
you override it. With the API key, statement text is sent to Anthropic; the other two modes keep
everything on the computer.
