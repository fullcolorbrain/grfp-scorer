# Website copy for fullcolorbrain.com (Squarespace)

Two pages. Page 1 is public and holds the description, disclaimer, and the gate form.
Page 2 is unlinked (hidden from navigation and search) and holds the download buttons;
the form's post-submit redirect points at it.

---

## Page 1 — `/grfp-scorer` (public)

### GRFP Scorer

**Rubric-based feedback on your NSF GRFP personal statement, in about a minute.**

Drop in a draft and get a score on ten principles of a strong statement, the sentence in
your draft that each score rests on, the three revisions most likely to help, and a set of
mechanical checks (length, required headings, forecasted journals, dollar amounts). Score
every draft and watch the numbers move.

Free. Runs on your own Mac or Windows computer. Reads with Claude (using your own API key,
a few cents a run), with a free local model via Ollama, or fully offline.

**What the scores mean — and don't.** The rubric was built by comparing funded and
unfunded statements, and every funded reference scored at least 12/20 overall and 5/8 on
the four most discriminating principles. Treat that as a *floor to clear*, not a
prediction: above it, the outcome depends on your letters, transcript, and research plan.
GRFP Scorer is not affiliated with or endorsed by the National Science Foundation, and
the software is provided as is, without warranty of any kind.
[Full disclaimer](https://github.com/fullcolorbrain/grfp-scorer/blob/main/DISCLAIMER.md) ·
[Privacy notice](https://github.com/fullcolorbrain/grfp-scorer/blob/main/PRIVACY.md) ·
[Source code (Apache 2.0)](https://github.com/fullcolorbrain/grfp-scorer)

#### Get the app

*(Squarespace Form block — storage: Google Sheets, your personal account; post-submit:
redirect to the unlinked download page)*

| Field | Type | Required |
|---|---|---|
| Name | Text | yes |
| Email | Email | yes |
| Institution / university | Text | yes |
| Program or department | Text | no |
| I have read and accept the Disclaimer and Terms of Use and the Apache License 2.0 | Checkbox (single, required) | yes |

Small print under the form:

> We collect your name, email, and institution only to count who uses the tool and,
> occasionally, to announce a new version. Nothing is sold or shared. The app will ask
> you to confirm the same details on first launch. Your statement text never comes to us —
> with the Claude backend it goes to Anthropic under your own key; with Ollama or offline
> it never leaves your computer.

---

## Page 2 — `/grfp-scorer-download` (unlinked; hide from navigation and search engines)

### Download GRFP Scorer

Thanks for registering. Pick the build for your computer:

| | |
|---|---|
| **macOS — Apple Silicon** (M1 and later; Apple menu → About This Mac says *Chip: Apple M…*) | Button → `…-macos-apple-silicon.dmg` on the latest GitHub Release |
| **macOS — Intel** (*Processor: … Intel*) | Button → `…-macos-intel.dmg` |
| **Windows** | Button → `…-windows-setup.exe` (installer) · small link → `…-windows-portable.exe` |

Link each button to the asset on `https://github.com/fullcolorbrain/grfp-scorer/releases/latest`.
(The `/releases/latest` page itself is a stable URL; individual asset URLs change with
each version, so either update the buttons on each release or link the buttons to the
Releases page.)

**Opening an unsigned app.** macOS 14 and earlier: right-click the app → Open → Open.
macOS 15 and later: double-click, dismiss the warning, then System Settings → Privacy &
Security → *Open Anyway*. Windows: SmartScreen → *More info* → *Run anyway*.

#### First launch

1. Read and accept the license and disclaimer.
2. Choose how statements are read. **Claude** gives the best reading and needs your own
   API key — [five-minute setup guide](https://github.com/fullcolorbrain/grfp-scorer/blob/main/docs/API_KEY_SETUP.md)
   (a scoring run costs a few cents; set a spend limit). **Ollama** is free and keeps
   everything on your computer. **Offline** does the mechanical checks only.
3. Confirm your name, email, and institution.

Then type your name in the box, drop a `.docx` or `.pdf` of your statement onto the
window, and wait about a minute.

[User guide](https://github.com/fullcolorbrain/grfp-scorer/blob/main/USER_GUIDE.md) ·
[Report a problem](https://github.com/fullcolorbrain/grfp-scorer/issues)

---

## Squarespace settings checklist

- Form block → Storage → **Google Drive** (sign in with the personal Google account, not
  an Emory one) so submissions land in a Sheet you own.
- Form block → Advanced → **Post-submit redirect** → `/grfp-scorer-download`.
- Download page → Settings → **Hide from navigation**; SEO tab → **Hide from search
  results**. (Anyone with the URL can still reach it — the gate is a counter, not a wall.)
- Add the page to the site footer? No — keep it unlinked.
