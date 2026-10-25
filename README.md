# GRFP Scorer

**Rubric-based formative feedback for NSF Graduate Research Fellowship statements.**

Project page: [fullcolorbrain.com/grfp-scorer](https://fullcolorbrain.com/grfp-scorer) ·
Downloads: [Releases](https://github.com/fullcolorbrain/grfp-scorer/releases/latest) ·
Questions and problems: [Issues](https://github.com/fullcolorbrain/grfp-scorer/issues)

Drop a draft of your GRFP personal statement onto the app. About a minute later you get a
score on each of ten principles of a strong statement, the sentence in your draft that
each score rests on, the three revisions most likely to help, a set of mechanical checks
(length, required headings, forecasted journals, dollar amounts, clinical vocabulary), and
a log of every draft you have scored so you can watch the numbers move.

> **Read this first.** The scores describe how closely a draft matches a writing rubric.
> They are **not** predictions of NSF outcomes: a high score does not mean an application
> will be funded, a low score does not mean it won't. The software is provided as is,
> without warranty of any kind. See [DISCLAIMER.md](DISCLAIMER.md). This project is not
> affiliated with or endorsed by the National Science Foundation.

## Download

Installers for Windows and macOS (Apple Silicon and Intel) are on the
[Releases page](https://github.com/fullcolorbrain/grfp-scorer/releases/latest).
They are unsigned: on macOS, right-click → Open (macOS 14) or allow it under System
Settings → Privacy & Security (macOS 15+); on Windows, SmartScreen → More info → Run anyway.

On first launch the app shows the license and disclaimer, asks how statements should be
read (below), and asks you to register the copy — name, email, institution — so the
author can count users and institutions. Your statement text is never sent to the author.
See [PRIVACY.md](PRIVACY.md).

## Three ways to read a statement

| Backend | Needs | Quality | Where your text goes |
|---|---|---|---|
| **Claude API** (recommended) | Your own Anthropic API key — [setup guide](docs/API_KEY_SETUP.md). A run is ~9,000 tokens; set a spend limit on your account. | Best. Designed to match a human reader on the four-item score. | To Anthropic, under your key. Never to the author. |
| **Local model via Ollama** | [Ollama](https://ollama.com) and a pulled model, e.g. `ollama pull qwen2.5:14b` (~16 GB RAM) | About a point low on judgement items; quotes real sentences. 8B models are not reliable. | Nowhere. Stays on your computer. |
| **Offline** | Nothing | Mechanical checks and lexical proxies only; weak on judgement items. | Nowhere. |

**The author does not provide API keys.** The Claude backend costs you roughly 5–10 cents
per scoring run at current Sonnet-tier pricing, billed to your own account.

## What the numbers mean

The rubric ([rubric.md](rubric.md)) was calibrated on statements across ecology,
psychology, and neuroscience, and where possible matched to NSF's official award and
honorable mention lists. The **four-item score** (P1 + P4 + P7 + P10) separated funded from
unfunded references better than the ten-item total (nested cross-validated AUC 0.76 vs
0.66). Treat both as a *floor*: every funded reference scored 12 or higher overall and 5
or higher on the four items. Above that, the outcome depends on letters, transcript, and
research plan — the essay's job is to not lose points. The calibration set is small and
mostly life-science; relevance to other fields is not established. Full numbers are in
[calibration/](calibration/).

## Run from source

    git clone https://github.com/fullcolorbrain/grfp-scorer.git
    cd grfp-scorer
    python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python grfp_app.py

Command-line tools (`score_statement.py`, `score_offline.py`, `compare_backends.py`) are
described in [INSTALL.md](INSTALL.md) § 7, and the student-facing walkthrough is
[USER_GUIDE.md](USER_GUIDE.md).

## Building the installers

`installer/build_windows.ps1` and `installer/build_mac.sh` build on their own platform;
pushing a tag such as `v1.1.0` runs [.github/workflows/release.yml](.github/workflows/release.yml),
which builds all three and attaches them to a GitHub Release. See [INSTALL.md](INSTALL.md).

## Registration back end

The first-run registration posts to a Google Apps Script web app backed by a private
Google Sheet. `installer/registration-Code.gs` is that script; deploy it once and paste
the resulting URL into `ENDPOINT` in `register.py` before building. Until then,
registrations are stored locally and never sent.

## Citing

If you use GRFP Scorer in teaching or research, please cite it — see
[CITATION.cff](CITATION.cff), or use the "Cite this repository" button at the top of the
GitHub page.

## License

Copyright 2025–2026 Vincent D. Costa. Licensed under the
[Apache License, Version 2.0](LICENSE). The rubric and calibration data are part of the
work and carry the same license. Not a product of Emory University; developed
independently with personal resources.
