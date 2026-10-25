# GRFP Scorer — Build and Administration Manual

This manual is for whoever builds and releases the app — the maintainer, or a program that
wants its own build. End users need only the installer from the Releases page and
*USER_GUIDE.md*.

## 1. What is in the repository

| Item | Purpose |
|---|---|
| `grfp_app.py` | The desktop app: drop a `.docx` or `.pdf`, get scores, evidence, revisions, checks, and a progress log. |
| `firstrun.py` | The first-launch wizard: license/disclaimer acceptance, backend choice (own API key / Ollama / offline), registration. |
| `register.py` | Config file handling, registration and optional usage events, app and license version numbers. |
| `LICENSE`, `NOTICE`, `DISCLAIMER.md`, `PRIVACY.md` | Apache 2.0 license, attribution, terms of use shown in the app, privacy notice. `LICENSE` and `DISCLAIMER.md` are bundled into the app. |
| `CITATION.cff`, `.zenodo.json` | Citation metadata; Zenodo mints a DOI per GitHub release when the repo is linked. |
| `installer/registration-Code.gs` | Google Apps Script that receives registrations into a private Sheet (§ 4). |
| `.github/workflows/release.yml` | Builds Windows + macOS (both architectures) on a `v*` tag and attaches them to a GitHub Release. |
| `score_statement.py` | The scoring engine the app calls: reads the file, runs the deterministic checks, sends the rubric and statement to Claude (or a local Ollama model), verifies every quoted sentence against the text, and applies the countable floors for P1 and P6. Also a command-line tool. |
| `score_offline.py` | Rubric proxies with no model at all; command-line only. |
| `compare_backends.py` | Scores a set of statements with several backends side by side, with agreement and AUC. |
| `rubric.md` | The ten principles, anchors, and calibration ranges — embedded in the prompt sent to the model. |
| `calibration/` | Anonymised reader scores, outcomes, and feature counts for the calibration statements, and a manifest template for blind test cases. |
| `installer/` | `build_mac.sh`, `build_mac_intel.sh`, `build_windows.ps1`, the Inno Setup script `grfp_scorer.iss`, run-from-source launchers, the icon folder. |
| `USER_GUIDE.md`, `INSTALL.md`, `README.md`, `docs/` | The user guide, this manual, the public readme, the API-key setup guide and website copy. |

## 2. Build the app

**The easy way: GitHub Actions.** Push a version tag and the workflow builds all three
installers on GitHub's own Windows and macOS runners and attaches them to a Release:

    # bump APP_VERSION in register.py and version in CITATION.cff first
    git tag v1.1.0 && git push origin v1.1.0

Ten to fifteen minutes later the Release holds `…-windows-setup.exe`, `…-windows-portable.exe`,
`…-macos-apple-silicon.dmg`, and `…-macos-intel.dmg`. The Actions tab shows progress and any
failure. You can also run the workflow by hand (*Run workflow*) to test a build without
tagging.

**Before the first release**, deploy the registration script (§ 4) and paste its URL into
`ENDPOINT` in `register.py`; otherwise the built apps store registrations locally and never
send them (the build scripts warn about this).

**Building locally.** PyInstaller only builds for the platform it runs on. Each build takes
5–10 minutes and needs internet once, to fetch packages. The result is around 150–250 MB
unpacked; the `.dmg` about 60–100 MB. No model or key is inside it.

### macOS

Requirements: Python 3.9 or newer **with Tk**. Homebrew's Python ships without Tk — run
`brew install python-tk@3.14` (match your Python version). Python from python.org includes
Tk. Apple's command-line tools are needed for `hdiutil`; `xcode-select --install` if
missing. Build with conda deactivated, since PyInstaller and Tk are unreliable under conda's
Python.

    cd grfp-scorer
    conda deactivate            # if a (base) prompt is showing
    bash installer/build_mac.sh

Output: `dist/GRFP Scorer.app` and `dist/GRFP Scorer.dmg`. The script checks for Tk and conda
first and stops with the fix if either is wrong, bundles `rubric.md`, `LICENSE`, and
`DISCLAIMER.md` into the app, and finishes by running the built app with `--selftest`.

To rebuild after changing any file:

    rm -rf build dist .build-venv "GRFP Scorer.spec"
    bash installer/build_mac.sh

### macOS — Intel Macs

`build_mac.sh` builds for the kind of Mac it runs on, so an app built on an Apple Silicon Mac
(M1 and later) will not open on an Intel Mac. `build_mac_intel.sh`
makes the Intel (x86_64) version, and it runs on either kind of Mac — on Apple Silicon it
builds under Rosetta 2, so no Intel Mac is needed. (The GitHub workflow builds Intel on an
Intel runner, which is simpler still.)

Requirements: Python 3.9 or newer **from python.org** (its installer is *universal2*: it
contains the Intel and the Apple Silicon interpreter, and Tk). Homebrew or conda Python on an
Apple Silicon Mac is arm64-only and cannot produce an Intel build. On Apple Silicon, Rosetta 2:
`softwareupdate --install-rosetta --agree-to-license` if it has never been installed.

    cd grfp-scorer
    bash installer/build_mac_intel.sh

Output: `dist-intel/GRFP Scorer.app` and `dist-intel/GRFP Scorer (Intel).dmg`. It uses its own
folders (`.build-venv-intel`, `build-intel`, `dist-intel`), so it never disturbs the Apple
Silicon build in `dist/`. Before packaging, the script checks that every compiled file in the
bundle is x86_64 and stops if one is not, and it prints the oldest macOS version the build
will run on, which is set by Python and the bundled packages. Building with an older
python.org Python generally lowers it:

    PYTHON=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 bash installer/build_mac_intel.sh

The script installs prebuilt packages only and refuses to continue if any package was compiled
on the build Mac against Homebrew libraries: such a package (seen with `cryptography` and
Homebrew's OpenSSL) clashes with Python's own libraries inside the bundle and breaks PDF
reading. Both macOS build scripts finish by running the packaged app with `--selftest`, which
loads every bundled library from inside the bundle and stops the build if one fails.

Which file to give whom: Apple Silicon students get `dist/GRFP Scorer.dmg`; Intel students
get `dist-intel/GRFP Scorer (Intel).dmg`. (Apple menu → About This Mac shows "Chip: Apple M…"
or "Processor: … Intel".) The Intel build also runs on Apple Silicon through Rosetta, so it
is a safe fallback when you do not know, but the native build starts faster.

Local models on Intel Macs: Ollama runs on the CPU only there, and a 14B model can take many
minutes per statement. For Intel students the API key, or offline mode, is the practical
choice.

### Windows

Requirements: Python 3.9 or newer from python.org, installed with **"Add python.exe to
PATH"** ticked and *tcl/tk and IDLE* selected under Optional Features. In PowerShell:

    cd grfp-scorer
    powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1

Output: `dist\GRFP Scorer.exe`, a single portable file, and — if
[Inno Setup 6](https://jrsoftware.org/isinfo.php) is installed —
`installer\Output\GRFP-Scorer-Setup-<version>.exe`, an installer that shows the license
(must be accepted) and the disclaimer before installing. Distribute the installer; keep
the portable exe as the fallback for locked-down machines.

### Signing (optional)

The apps are unsigned. On macOS 14 and earlier the user right-clicks → Open once; on macOS 15
and later they double-click, dismiss the warning, and choose **Open Anyway** under System
Settings → Privacy & Security; Windows shows a
SmartScreen prompt. An Apple Developer ID or a Windows code-signing certificate removes the
prompts; PyInstaller's documentation covers both. Unsigned is adequate for now; a signing
certificate becomes worth it once SmartScreen complaints outnumber the cost.

## 3. Distribute

Builds live on the GitHub Releases page; the website (`docs/WEBSITE_COPY.md`) fronts it with
a registration form whose post-submit redirect leads to the download buttons. Each app
additionally registers itself on first launch, which is the count that reflects actual
installs rather than downloads.

**License acceptance happens three times**, deliberately: the website form checkbox, the
Windows installer's license page (the macOS `.dmg` ships the files alongside the app), and
the in-app first-launch screen, which records the accepted version and timestamp in the
user's config file. The in-app one is the binding record, because it covers copies obtained
from anywhere.

## 4. API keys and the registration back end

### Users bring their own API key

The Claude backend needs an Anthropic Console key (console.anthropic.com; separate from a
claude.ai subscription). **The public release does not provide keys** — the first-launch
screen and `docs/API_KEY_SETUP.md` walk users through creating their own account, adding a
few dollars of credit, setting a spend limit, and creating a key. Nothing about a key is
ever embedded in the app, and the maintainer never sees users' keys.

### Registration back end (Google Apps Script)

First-launch registrations and optional usage events post to a small Google Apps Script
web app that appends rows to a private Google Sheet and emails a daily digest. Setup, once:

1. In a **personal** Google account, create a Sheet with two tabs, `installs` and `usage`.
2. Extensions → Apps Script; paste `installer/registration-Code.gs`; check `NOTIFY_EMAIL`.
3. Deploy → New deployment → Web app; *Execute as: Me*; *Who has access: Anyone*. Copy the
   Web app URL.
4. Paste it into `ENDPOINT` in `register.py`, commit, and build. Run `installDigestTrigger()`
   once from the editor to schedule the daily email.

What arrives: name, email, institution, OS, app version, and a random install id per
registration; and, only for users who opted in, an install id + statement type + four-item
score per scoring run. Never statement text. `PRIVACY.md` is the public description and
must stay accurate if you change what is sent. The sheet's distinct-institution count and
the usage tab are the numbers for reporting adoption.

### Cohort arrangement (optional)

A program that wants to cover students' API costs can still do so the old way — one
Console account it owns, with one key per student, revoked after the deadline:

1. Sign up at console.anthropic.com and add prepaid credit under **Billing**. A scoring run
   is roughly 4–5,000 tokens in and a few thousand out; at Sonnet-tier pricing that is on the
   order of 5–10 cents a run, so a few dollars covers a student's whole application season.
   Check the Console's usage page after the first runs to confirm the per-run cost.
2. Under **API Keys**, create one key per student, named for them. Copy each key when it is
   created — the full value is shown only once.
3. Give each student their key privately (not in a shared document). The user guide tells
   them to paste it into the app's Settings once and to keep it private.
4. Watch **Usage** by key if you want to see who is scoring, and **revoke** keys after the
   deadline from the same page. A leaked key costs a click to replace.

The key is stored on the user's computer in `~/.grfp_scorer/config.json` (owner-only
permissions), never in the app bundle. With a key, statement text is sent to Anthropic;
users are told to score only their own drafts.

## 5. Optional: a local model instead of the API

If a student cannot use the API — no key, a network that blocks it, or a statement that must
not leave the machine — the app can use an open-weight model through Ollama, with nothing
sent anywhere.

1. Install Ollama from https://ollama.com/download and open it (the menu-bar icon must be
   running when scoring).
2. Pull a model: `ollama pull qwen2.5:14b` (≈9 GB; needs 16 GB of RAM) or
   `ollama pull llama3.1:8b` (≈5 GB; 8 GB of RAM). On a Mac, the `ollama` command appears after
   the app is first opened; until then use `/Applications/Ollama.app/Contents/Resources/ollama`.
3. In the app's Settings, enter the model name under **Ollama model** and Save. The app
   selects Ollama automatically whenever no API key is set.

What to expect, from the calibration runs: the 14B model orders funded and unfunded
statements correctly and quotes real sentences, but scores about a point low on the
judgement items — totals run 3–6 points under a human reader. The 8B model is not reliable;
it fabricated evidence and recommended disease framing before the verification step was
added. Treat a local model as a second opinion for tracking drafts, not as the final read.

## 6. Running from source

Anyone with Python can run the app without building it:

    cd grfp-scorer
    python3 -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python grfp_app.py

`installer/run_from_source.sh` (macOS) and `installer/run_from_source.bat` (Windows) do the
same in one step. Homebrew Python refuses `pip install` outside a virtual environment, which
is why the `.venv` step is not optional there.

## 7. Command-line tools

All three tools read `.docx`, `.pdf`, `.txt`, and `.md`. Paths are relative to the
`grfp-scorer` folder; drag a file into the terminal to paste its full path.

    export ANTHROPIC_API_KEY=sk-ant-...                       # once per terminal
    python score_statement.py draft.docx --student "Name"     # Claude
    python score_statement.py draft.pdf  --student "Name" --backend ollama --model qwen2.5:14b
    python score_statement.py --test                          # check both connections
    python score_statement.py --history grfp_scores.csv --progress "Name"
    python score_offline.py  draft.docx --student "Name" --self-check
    python compare_backends.py calibration/test_cases_manifest.csv --backends offline ollama claude

The comparison script needs the four file paths in the manifest edited to real locations;
it prints reader, offline, and model scores side by side with agreement and AUC, and writes
a CSV with `--out`.

## 8. How the scoring works, briefly

The model receives the rubric (with its worked examples stripped, because small models copy
them as evidence), an inventory of every sentence in the statement that mentions a
publication, presentation, or award, and the statement. It must return a 0–2 score per
principle with a verbatim sentence as evidence, or NOT PRESENT and a 0. The app then checks
each quoted sentence against the text and zeroes any score it cannot verify; sets P6 from
its own heading check; raises P1 to a floor computed from venue-named publications and
outcome sentences; and discards any recommended revision that would add disease or treatment
framing. Everything it changed is listed as a flag in the Revisions tab.

Current Claude models do not accept a temperature setting, so two runs of the same draft can
differ by a point on a sub-score. Ollama runs at temperature 0 and is deterministic.

## 9. Troubleshooting the build

| Symptom | Fix |
|---|---|
| `No module named '_tkinter'` or "tkinter installation is broken" | Python lacks Tk. Homebrew: `brew install python-tk@3.14`; or install python.org Python. |
| Build stops saying python3 is conda's | `conda deactivate`, then rerun. |
| `externally-managed-environment` from pip | Use the virtual environment in Section 6; do not pass `--break-system-packages`. |
| App opens but says a reader is missing | The build did not collect `pdfplumber` or `python-docx`; rebuild after `rm -rf .build-venv`. |
| App shows *Claude unavailable* at launch | The status line says why: key rejected, no credit, wrong model id, or a blocked network. Settings → Test connections repeats the check. |
| `Messages.create() got an unexpected keyword argument` | An old `score_statement.py`; the current one sends no sampling parameters. Rebuild. |
| Model returns no text or invalid JSON | An old `score_statement.py`; the current one has a 12,000-token budget and a three-tier parser that saves the raw response to `~/.grfp_scorer/last_raw_response.txt`. |
| Ollama slow, `ollama ps` shows part CPU | Context window too large for mthe program; the current script uses 8,192 and keeps the model loaded for 30 minutes. |

## 10. Files the app writes

Everything lives in `~/.grfp_scorer/` on the user's machine: `config.json` (key, model
choices, last student name, registration details, accepted license version and timestamp,
install id), `history.csv` (one row per scoring run), and
`last_raw_response.txt` (the model's most recent raw output, for diagnosis). Deleting the
folder resets the app. Nothing is written anywhere else, and nothing is sent anywhere except
the statement text to the chosen backend, the registration details to the maintainer's
sheet (§ 4), and — only if opted in — the per-run usage event.

## 11. Releasing a new version

1. Bump `APP_VERSION` in `register.py` and `version`/`date-released` in `CITATION.cff`.
   If `DISCLAIMER.md` changed, also bump `LICENSE_VERSION` so existing users re-accept.
2. Commit, then `git tag vX.Y.Z && git push origin main vX.Y.Z`.
3. Watch the Actions tab; the Release appears with all four files attached when the three
   build jobs finish. Edit the release notes if the auto-generated ones need context.
4. If the repository is linked to Zenodo (zenodo.org → GitHub → toggle this repo on,
   done once), a DOI is minted automatically; add it to the README.
5. Update the download buttons on the website if they point at versioned asset URLs.
