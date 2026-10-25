# GRFP Scorer — User Guide

This guide is for using the GRFP Scorer app on your own drafts. You need the app (a `.dmg`
on macOS or an installer `.exe` on Windows, from the
[Releases page](https://github.com/fullcolorbrain/grfp-scorer/releases/latest)) and one of
three ways to read statements: your own Anthropic API key (best; a few cents a run), a free
local model via Ollama, or nothing at all for the offline checks. Nothing else needs to be
installed.

> The scores describe how closely a draft matches a writing rubric. They are not predictions
> of NSF outcomes, and the software is provided as is, without warranty. See DISCLAIMER.md.
> GRFP Scorer is not affiliated with or endorsed by the National Science Foundation.

## 1. What the app does

You drop a draft of your NSF GRFP personal statement onto the window. About a minute later
you get:

- a **total score** out of 20 across ten principles of a strong statement;
- a **four-item score** out of 8 on the four principles that most separated funded from
  unfunded statements in a study of past applications: outcomes stated plainly (P1), broader
  impacts as a concrete plan (P4), your story turned into evidence (P7), and a named
  graduate plan (P10);
- a **disease-centrality** flag (0–2) for how much a disease or patient group organizes your
  research narrative — a known risk with NSF reviewers;
- each of the ten sub-scores with **the sentence from your draft it rests on**;
- the **three revisions** most likely to raise your score;
- **mechanical checks**: length, required headings, forecasted journals, dollar amounts,
  hedging verbs, and clinical vocabulary;
- a **progress log** of every draft you have scored, so you can see the numbers move.

The scores are read by Claude against a fixed rubric, and every sentence it cites is checked
against your text. Read the total as a floor: every funded reference statement scored at
least 12 overall and 5 on the four items. Above that, the outcome is decided by your letters,
transcript, and research plan — the essay's job is to not lose points.

## 2. Install the app

**macOS.** There are two versions. Apple menu → **About This Mac** shows either
*Chip: Apple M…* (download the `…-macos-apple-silicon.dmg`) or *Processor: … Intel*
(download the `…-macos-intel.dmg`). Open the `.dmg` and drag *GRFP Scorer* into
Applications. The first time you open it, macOS asks once because the app is not signed by an
identified developer. On macOS 14 and earlier: right-click the app and choose **Open**, then
**Open** again. On macOS 15 and later: double-click it, dismiss the warning, then go to System
Settings → Privacy & Security, scroll down, and click **Open Anyway**.

**Windows.** Run `…-windows-setup.exe`; it shows the license, installs the app, and adds a
Start-menu entry. (The `…-windows-portable.exe` needs no installation — copy it anywhere and
double-click.) If a SmartScreen window appears, click **More info → Run anyway**.

If macOS says the app "is damaged", open Terminal and run
`xattr -dr com.apple.quarantine "/Applications/GRFP Scorer.app"`, then open it again.

## 3. First launch

The first time the app opens it walks you through three screens:

1. **License and terms.** Read the disclaimer and the Apache license and tick the box.
2. **How statements are read.** Choose one:
   - **Claude API** — the best reading. You need your own key from
     console.anthropic.com; the [five-minute setup guide](docs/API_KEY_SETUP.md) walks
     through creating an account, adding a few dollars of credit, setting a spend limit,
     and making a key. Paste it in and click **Test** — you should see *✓ Claude reachable*.
     A scoring run costs a few cents, billed to your account. The key is stored only on
     your computer.
   - **Ollama** — free, nothing leaves your computer. Install Ollama from ollama.com and
     pull a model (`ollama pull qwen2.5:14b` for a 16 GB machine, `llama3.1:8b` for 8 GB).
     Slower, and about a point lower on the judgement items.
   - **Offline** — the mechanical checks and rough proxies only.
3. **Registration.** Your name, email, and institution, so the author can count who uses
   the tool. Optionally tick the box to send an anonymous count after each run (no text,
   ever). See PRIVACY.md.

You can change the backend later under **Settings…**, and re-read the terms under
**About / License**.

**Privacy.** With a key set, the text of your statement is sent to Anthropic under your
key to be scored. With Ollama or offline it never leaves your computer. Score only your
own drafts — do not drop in anyone else's statement.

## 4. Score a draft

1. Type your name in **Student name**. Use the same spelling every time — it is how the
   progress log groups your drafts.
2. Leave **Backend** on *auto*.
3. Drop your `.docx` or `.pdf` onto the box, or click the box to browse for it. (Word and
   PDF are both fine; a scanned PDF with no selectable text will not work — export it from
   Word instead.)
4. Wait. The status line counts the seconds; a run typically takes 30–90 seconds. If
   something goes wrong, the reason appears in the **Checks** tab within about three minutes.

## 5. Read the results

**The three tiles.** Total /20 (navy), four-item /8 (gold), disease centrality /2. The
*Reading* box beside them says where you stand against the funded floors.

**Sub-scores.** Ten rows, each with a score chip (0, 1 or 2), the principle, and the sentence
from your draft the score rests on. The four gold rows are the ones that matter most. If a
row says *NOT PRESENT*, that is the revision: there is nothing in the draft for that
principle yet. Scroll the list to see all ten.

**Revisions tab.** The three changes most likely to raise your four-item score, then a
*Verification* section showing that the cited sentences were found in your draft and that
none of the advice steers you toward disease framing. If a line here starts with **!**, the
app has zeroed a score it could not verify — read that row with extra care.

**Checks tab.** Length against the three-page target, whether the *Intellectual Merit* and
*Broader Impacts* headings are present, any forecasted journals ("in preparation for
*Nature*"), dollar amounts, hedging verbs (*strive, aspire, hope to*), participation phrasing
(*I joined, I assisted, had the opportunity*), and clinical-term density. Funded reference
statements were all at or below 4 clinical terms per 1,000 words.

**Progress tab.** Every draft you have scored under your name, with its date, backend, total,
four-item score, and disease flag. **Show progress for this student** at the bottom jumps
here.

**Save report…** writes the full report as a text file, useful for sending to your mentor.

## 6. Revise and re-score

Work on the gold rows and the revisions first, then the checks. When you drop the next
draft, compare it with the previous one in the Progress tab. A single point of movement on
one sub-score can be noise — Claude's reading varies slightly from run to run — so if a change
matters, score the same draft twice before trusting it. Compare drafts scored with the same
backend; numbers from *claude*, *ollama*, and *offline* are not on the same scale.

What the numbers mean in practice:

| Total | Four-item | Read as |
|---|---|---|
| below 11 | any | The statement itself is limiting; rebuild the sections that score 0. |
| 11–14 | below 5 | Competitive total, but the four discriminating items are below every funded reference. |
| 12–14 | 5 or more | At the lower edge of the funded range. |
| 14 or more | 5 or more | Within the funded range; polish the four items and remove disease framing. |

## 7. If something goes wrong

| What you see | What to do |
|---|---|
| Status says *Claude unavailable: API key rejected* | Re-open Settings and re-paste the key; check for spaces at the ends. |
| *Console account has no credit* | Add prepaid credit under Billing at console.anthropic.com, or check your spend limit. |
| *connection timed out* | Check your internet connection; university VPNs sometimes block the API — try without the VPN. |
| The app fell back to *offline* | Any of the above. Offline scores are rough proxies for the judgement items; fix the connection and re-score before trusting them. |
| *Fewer than 200 words extracted* | The file is empty or a scanned image. Export it from Word as `.docx` or `.pdf`. |
| *File not found* / unsupported type | Use `.docx`, `.pdf`, `.txt` or `.md`. |
| Scores differ between two runs of the same draft | Normal within about a point. Re-score once before reading a change as real. |
| The window opens but a drop does nothing | Click the drop box to browse for the file instead. |

Your progress log and settings live in a hidden folder called `.grfp_scorer` in your home
directory; **Open history folder** opens it. Deleting that folder resets the app (you would
need to enter your key again and re-register).

## 8. What the app is not

It is not a predictor. It cannot see your letters, transcript, or research plan, and among
statements above the floor it ranks only weakly. It is a consistent reader that tells you
which sections are missing what, and whether a revision moved them. A human reader — your
mentor, your program's fellowship office — is still the final one.
