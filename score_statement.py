#!/usr/bin/env python3
"""
score_statement.py — score an NSF GRFP personal statement against the ten-principle
rubric (rubric.md) and track progress across drafts.

Usage
    python score_statement.py STATEMENT.docx --student "Student"                       # Anthropic API
    python score_statement.py STATEMENT.docx --student "Student" --backend ollama      # local model, no API, no network
    python score_statement.py STATEMENT.pdf  --student "Student" --history scores.csv
    python score_statement.py STATEMENT.txt  --student "Student" --no-llm     # lexical checks only
    python score_statement.py --history scores.csv --progress "Student"       # show a student's trajectory

Requirements
    pip install anthropic python-docx pdfplumber
    export ANTHROPIC_API_KEY=...            (not needed with --no-llm)

What it does
    1. Extracts text from .docx / .pdf / .txt / .md.
    2. Runs deterministic checks that need no judgement: length, required headings,
       forecasted journal venues, dollar amounts, aspirational verbs, participation
       phrasing, "developed an interest" drift, disease/clinical vocabulary density.
    3. Sends the statement plus the rubric to Claude, which returns 0–2 sub-scores for
       the ten principles, the disease-centrality flag, one-line evidence per item, and
       the three highest-value revisions.
    4. Prints a report, and appends a row to a CSV so each student can see the trajectory
       of their drafts over time.
"""

import argparse, csv, datetime as dt, json, os, re, sys
from pathlib import Path
try:  # the built app has no system CA file; point OpenSSL/httpx at the bundled certifi one
    import certifi; os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except Exception: pass

RUBRIC_PATH = Path(__file__).with_name("rubric.md")
PRINCIPLES = [
    "P1 Outcomes stated plainly",
    "P2 Organizing question up front",
    "P3 Initiative and autonomy",
    "P4 Broader impacts as a concrete plan",
    "P5 Research tied to societal benefit",
    "P6 Explicit IM/BI framing",
    "P7 Narrative converted to evidence",
    "P8 One question, one finding per project",
    "P9 Obstacles narrated as method",
    "P10 Named graduate plan",
]
FOUR_ITEM = [0, 3, 6, 9]  # P1, P4, P7, P10
DEFAULT_MODEL = os.environ.get("GRFP_SCORER_MODEL", "claude-sonnet-5")

# ----------------------------------------------------------------------------- text extraction
def extract_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}\n  Looked in: {Path.cwd()}\n  Give the full path (drag the file into the terminal to paste it), or move the file into this folder.")
    suf = path.suffix.lower()
    if suf in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suf == ".docx":
        try:
            import docx  # python-docx
        except ImportError:
            raise RuntimeError("The .docx reader (python-docx) is not installed in this copy of the scorer. Run: pip install python-docx — or export the statement as PDF.")
        d = docx.Document(str(path))
        return "\n".join(p.text for p in d.paragraphs)
    if suf == ".pdf":
        try:
            import pdfplumber
        except ImportError as e:
            raise RuntimeError(f"The PDF reader (pdfplumber) could not be loaded in this copy of the scorer [{type(e).__name__}: {e}]. Export the statement as .docx for now, and report this message.")
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    raise RuntimeError(f"Unsupported file type {suf}: use .docx, .pdf, .txt or .md")

# ----------------------------------------------------------------------------- deterministic checks
JOURNALS = r"(Nature|Science|Cell|Neuron|PNAS|eLife|Nature Neuroscience|Nature Communications|Current Biology|Journal of Neuroscience|Biological Psychiatry|Movement Disorders|JAMA|Lancet|NEJM)"
FORECAST = re.compile(
    r"(in preparation for|to be submitted to|will be submitted to|preparing (a |the )?(manuscript|paper) for|submission to|targeting)\s+(the (academic )?journal\s+)?" + JOURNALS,
    re.I,
)
DOLLARS = re.compile(r"\$\s?\d[\d,]*(\.\d+)?|\b\d[\d,]*\s+dollars\b", re.I)
ASPIRATIONAL = re.compile(r"\b(strive[sd]?|striving|aspire[sd]?|aspiring|endeavor(s|ed|ing)?|hope[sd]? to|hoping to)\b", re.I)
PARTICIPATION = re.compile(
    r"\b(I (joined|assisted|helped|contributed to|participated in|was given the opportunity|had the opportunity|was fortunate to|was able to)|worked under|under the (guidance|supervision|mentorship) of)\b",
    re.I,
)
INTEREST_DRIFT = re.compile(r"\b(developed|sparked|piqued|grew|ignited|cemented|solidified)\b[^.]{0,40}\binterest", re.I)
CLINICAL = re.compile(
    r"\b(Parkinson|Alzheimer|dementia|schizophren|psychos[ie]s|depress(ion|ive)|anxiety|PTSD|autism|epilep|stroke|cancer|tumou?r|glioblastoma|addiction|opioid|cocaine|patients?|clinical|therap(y|ies|eutic)|treatment|cure|diagnos|disease|disorder|RDoC|NIH|NIMH|NIDA|NIAAA|gene therapy|trial)\w*",
    re.I,
)
HEADINGS = {
    "Intellectual Merit heading": re.compile(r"intellectual merit", re.I),
    "Broader Impacts heading": re.compile(r"broader impacts?", re.I),
}

def lexical_checks(text: str) -> dict:
    words = len(text.split())
    checks = {
        "word_count": words,
        "estimated_pages_12pt": round(words / 700, 2),
        "forecasted_venues": [m.group(0) for m in FORECAST.finditer(text)],
        "dollar_amounts": [m.group(0) for m in DOLLARS.finditer(text)],
        "aspirational_verbs": len(ASPIRATIONAL.findall(text)),
        "participation_phrases": len(PARTICIPATION.findall(text)),
        "interest_drift_phrases": len(INTEREST_DRIFT.findall(text)),
        "clinical_terms_per_1000_words": round(1000 * len(CLINICAL.findall(text)) / max(words, 1), 1),
    }
    for name, rx in HEADINGS.items():
        checks[name] = bool(rx.search(text))
    return checks

# ----------------------------------------------------------------------------- LLM scoring
SYSTEM_PROMPT = """You are scoring an NSF GRFP "Personal, Relevant Background and Future Goals" statement
against a fixed ten-principle rubric. You are a strict, consistent grader. Score only what is on the
page. Do not reward promises, intentions, or claims of skill without evidence. If the evidence for an item is
ambiguous, give the lower score; if the evidence is clearly present, do not under-score it. Return JSON only."""

EXAMPLE_PHRASES = re.compile(r"\"[^\"\n]{8,120}\"|“[^”\n]{8,120}”|\([^)\n]*e\.g\.[^)\n]*\)")

def rubric_for_local(rubric: str) -> str:
    """Remove quoted example phrases and e.g. parentheticals: small local models copy them as evidence."""
    return EXAMPLE_PHRASES.sub("", rubric)

def outcome_hints(text: str) -> str:
    """Sentences mentioning publications, presentations, or awards, handed to the model so P1 counts all of them."""
    hits = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if re.search(r"\b(publish|publication|co-?author|first[- ]author|manuscript|preprint|bioRxiv|PsyArXiv|in (?:review|press|preparation)|poster|presented|presentation|award|prize|fellowship|scholarship|grant)\b", x, re.I)]
    return "\n".join("- " + h[:220] for h in hits[:12]) or "- (none detected)"

def build_user_prompt(rubric: str, text: str, local: bool = False) -> str:
    if local:
        rubric = rubric_for_local(rubric)
        prepass = """
BEFORE SCORING, complete this inventory from the statement (copy phrases verbatim; write "none" if absent):
- Publications and preprints (with journal or server names): ...
- Presentations, posters, talks: ...
- Awards, fellowships, grants: ...
- The sentence in paragraph 1 or 2 that states the research question: ...
- Sentences beginning with "I" that describe designing, building, leading, founding, proposing, or securing something: ...
- Named outreach/mentoring programs, organizations, and any numbers of people reached: ...
- The stated result of each research project: ...
- Any sentence describing something that failed or went wrong and what the applicant did: ...
- The named lab, advisor, program, or techniques still to be learned: ...
Use ONLY this inventory as the source of evidence quotes below. Score P1, P4, P8 from the counts in the inventory, not from the first example you notice.
"""
    else:
        prepass = ""
    return f"""RUBRIC
{rubric}
{prepass}
SENTENCES IN THE STATEMENT THAT MENTION OUTCOMES (publications, presentations, awards). Count ALL of these for P1:
{outcome_hints(text)}

SCORING RULES
- Each principle P1–P10 is scored 0, 1, or 2 using the anchors above.
- D (disease/clinical centrality) is scored 0, 1, or 2 and is reported separately.
- For each item, the evidence MUST be a sentence copied VERBATIM from the statement between the <statement> tags.
  Never write a sentence of your own, never adapt an example from the rubric, and never fill a rubric example with
  names from the statement. If nothing in the statement supports the item, write exactly: NOT PRESENT — and score 0.
- A score of 1 or 2 requires a verbatim quote. A score of 0 requires NOT PRESENT.
- Check the whole statement before scoring P1 (all publications, preprints, presentations, awards), P6 (both headings),
  and P8 (every project's stated result). Do not stop at the first example.
- Then list the three revisions that would raise the four-item score (P1+P4+P7+P10) the most. Revisions must never
  recommend adding disease, patient, therapy, or treatment framing; NSF GRFP does not fund disease-oriented work.

Return exactly this JSON schema and nothing else:
{{
  "scores": {{"P1":0,"P2":0,"P3":0,"P4":0,"P5":0,"P6":0,"P7":0,"P8":0,"P9":0,"P10":0}},
  "evidence": {{"P1":"...","P2":"...","P3":"...","P4":"...","P5":"...","P6":"...","P7":"...","P8":"...","P9":"...","P10":"..."}},
  "disease_centrality": 0,
  "disease_evidence": "...",
  "top_revisions": ["...","...","..."]
}}

STATEMENT
<statement>
{text}
</statement>"""

def _salvage(raw: str) -> dict:
    """Pull scores, evidence, and revisions out of a JSON-like response by pattern when strict parsing fails."""
    out = {"scores": {}, "evidence": {}, "top_revisions": [], "disease_centrality": -1, "disease_evidence": ""}
    m = re.search(r'"scores"\s*:\s*\{(.*?)\}', raw, re.S)
    if m:
        for k, v in re.findall(r'"(P\d+)"\s*:\s*(\d)', m.group(1)): out["scores"][k] = int(v)
    m = re.search(r'"evidence"\s*:\s*\{(.*?)\n\s*\}', raw, re.S) or re.search(r'"evidence"\s*:\s*\{(.*)', raw, re.S)
    if m:
        for k, v in re.findall(r'"(P\d+)"\s*:\s*"((?:[^"\\]|\\.)*)"', m.group(1)): out["evidence"][k] = v.replace('\\"', '"')
    m = re.search(r'"disease_centrality"\s*:\s*(\d)', raw)
    if m: out["disease_centrality"] = int(m.group(1))
    m = re.search(r'"disease_evidence"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if m: out["disease_evidence"] = m.group(1)
    m = re.search(r'"top_revisions"\s*:\s*\[(.*?)\]', raw, re.S)
    if m: out["top_revisions"] = [x for x in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))]
    return out

def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        (CONFIG_DIR := Path.home() / ".grfp_scorer").mkdir(parents=True, exist_ok=True)
        (CONFIG_DIR / "last_raw_response.txt").write_text(raw, encoding="utf-8")
    except Exception:
        pass
    cleaned = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
    cleaned = cleaned.replace("\u00a0", " ").replace("\u200b", "")        # non-breaking / zero-width characters
    m = re.search(r"\{.*\}", cleaned, re.S)
    body = m.group(0) if m else cleaned
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        pass
    try:                                                              # lenient decoder shipped with the anthropic SDK
        import jiter
        return jiter.from_json(body.encode("utf-8"), partial_mode="trailing-strings")
    except Exception:
        pass
    sv = _salvage(body)
    if len(sv["scores"]) == 10:
        sv["parse_note"] = "response was not strict JSON; scores and evidence were recovered by pattern (raw text saved to ~/.grfp_scorer/last_raw_response.txt)"
        return sv
    raise RuntimeError("Model did not return usable JSON (raw text saved to ~/.grfp_scorer/last_raw_response.txt). First 800 characters:\n" + raw[:800])

def llm_score(text: str, model: str, backend: str = "claude", ollama_url: str = "http://localhost:11434") -> dict:
    rubric = RUBRIC_PATH.read_text(encoding="utf-8")
    prompt = build_user_prompt(rubric, text, local=(backend == "ollama"))
    if backend == "claude":
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("The anthropic package is not installed in this copy of the scorer (pip install anthropic), or use the Ollama/offline backend.")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("No Anthropic API key set. Add one in Settings (app) or export ANTHROPIC_API_KEY, or use the Ollama/offline backend.")
        # Short timeout and a single retry so a stalled connection surfaces as an error instead of a silent 30-minute wait.
        client = anthropic.Anthropic(timeout=float(os.environ.get("GRFP_CLAUDE_TIMEOUT", "150")), max_retries=1)
        # Current Claude models do not accept temperature/top_p/top_k (the API returns 400 and newer SDKs drop the
        # arguments), so none are sent; determinism is requested in the prompt instead. Ollama still honours temperature 0.
        # Current Claude models reason before answering and that reasoning counts against max_tokens, so the budget
        # must be far larger than the JSON itself; 2000 produced empty responses.
        kwargs = dict(model=model, max_tokens=int(os.environ.get("GRFP_CLAUDE_MAX_TOKENS", "12000")), system=SYSTEM_PROMPT,
                      messages=[{"role": "user", "content": prompt}])
        # If an SDK ever rejects another argument, strip it and retry rather than fail.
        for _ in range(3):
            try:
                msg = client.messages.create(**kwargs); break
            except TypeError as e:
                m = re.search(r"unexpected keyword argument '(\w+)'", str(e))
                if m and m.group(1) in kwargs: kwargs.pop(m.group(1))
                else: raise
        else:
            raise RuntimeError("Could not call the Anthropic API with this SDK version; try: pip install -U anthropic")
        text_out = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
        if not text_out.strip():
            stop = getattr(msg, "stop_reason", "?"); kinds = [getattr(b, "type", "?") for b in msg.content]
            if stop == "max_tokens":
                raise RuntimeError(f"Claude ran out of output budget before writing the scores (stop_reason=max_tokens; content blocks: {kinds}). Raise GRFP_CLAUDE_MAX_TOKENS above {kwargs['max_tokens']}.")
            raise RuntimeError(f"Claude returned no text (stop_reason={stop}; content blocks: {kinds}).")
        return _parse_json(text_out)
    if backend == "ollama":
        # Local open-weight model via Ollama (https://ollama.com). Nothing leaves the machine.
        # Install Ollama, then e.g.:  ollama pull llama3.1:8b    and run this script with --backend ollama --model llama3.1:8b
        import urllib.request
        body = json.dumps({"model": model, "system": SYSTEM_PROMPT, "prompt": prompt, "stream": False,
                           "format": "json", "keep_alive": "30m", "options": {"temperature": 0, "num_ctx": int(os.environ.get("GRFP_OLLAMA_CTX", "8192")), "num_predict": 3000}}).encode()
        req = urllib.request.Request(f"{ollama_url}/api/generate", data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return _parse_json(json.loads(r.read().decode())["response"])
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Could not reach Ollama at {ollama_url} ({e}). Is the Ollama app running, and is the model pulled?")
    raise RuntimeError(f"Unknown backend {backend}")

# ----------------------------------------------------------------------------- connection tests
def test_claude(model: str = None, timeout: float = 20.0) -> tuple:
    """Make the smallest possible API call. Returns (ok, message) with the real reason on failure."""
    try:
        import anthropic
    except ImportError:
        return False, "the anthropic package is not installed"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "no API key set"
    try:
        client = anthropic.Anthropic(timeout=timeout, max_retries=0)
        msg = client.messages.create(model=model or DEFAULT_MODEL, max_tokens=5, messages=[{"role": "user", "content": "Reply with OK."}])
        return True, f"Claude reachable ({model or DEFAULT_MODEL})"
    except Exception as e:  # noqa: BLE001
        name = type(e).__name__; text = str(e)
        if "401" in text or "authentication" in text.lower(): return False, "API key rejected (check it in Settings)"
        if "credit" in text.lower() or "billing" in text.lower(): return False, "Console account has no credit — add credit at console.anthropic.com"
        if "404" in text or "not_found" in text.lower(): return False, f"model id '{model or DEFAULT_MODEL}' not found — set a current model in Settings"
        if "timeout" in name.lower() or "timed out" in text.lower(): return False, f"connection timed out after {int(timeout)} s — network or firewall is blocking api.anthropic.com"
        if "connect" in name.lower() or "ssl" in text.lower() or "certificate" in text.lower(): return False, f"could not connect: {text[:160]}"
        return False, f"{name}: {text[:200]}"

def test_ollama(url: str = "http://localhost:11434", model: str = None, timeout: float = 5.0) -> tuple:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=timeout) as r:
            models = [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
    except Exception as e:  # noqa: BLE001
        return False, f"Ollama not reachable at {url} ({type(e).__name__}) — is the Ollama app running?"
    if not models: return False, "Ollama is running but has no models — run: ollama pull llama3.1:8b"
    if model and model not in models: return False, f"model '{model}' not pulled; available: {', '.join(models)}"
    return True, f"Ollama reachable with {', '.join(models)}"

# ----------------------------------------------------------------------------- verification
VENUE_RX = re.compile(r"\b(Nature|Science|Cell|Neuron|PNAS|eLife|Current Biology|Journal of [A-Z][a-z]+|J\. [A-Z][a-z]+|Biological Psychiatry|PLOS? (?:ONE|Biology)|bioRxiv|PsyArXiv|Frontiers in|Behavioral Neuroscience|Brain Connectivity|Developmental Biology|Conservation Genetics|Science Advances|Investigative Dermatology|Neurochemistry|eNeuro|Cerebral Cortex|Alzheimer's Disease)\b")
PUBSENT_RX = re.compile(r"\b(publish|publication|co-?author|first[- ]author|second[- ]author|manuscript|preprint|bioRxiv|PsyArXiv|in (?:review|press|preparation)|under review|submitted|et al)\b", re.I)
OUTCOME_RX = re.compile(r"\b(publish|publication|co-?author|first[- ]author|manuscript|preprint|poster|presented|presentation|award|prize|fellowship|scholarship|grant)\b", re.I)

def p1_floor(text: str) -> int:
    """Minimum defensible P1 from countable facts: venue-named publications and outcome sentences.
    Agrees with a human reader on 30 of 46 calibration statements and exceeds the reader on 1; otherwise it is lower."""
    sents = re.split(r"(?<=[.!?])\s+|\n", text)
    pubs_venue = sum(1 for x in sents if PUBSENT_RX.search(x) and VENUE_RX.search(x))
    outcomes = sum(1 for x in sents if OUTCOME_RX.search(x))
    f = 2 if (pubs_venue >= 2 or (pubs_venue >= 1 and outcomes >= 4)) else (1 if outcomes >= 2 else 0)
    if FORECAST.search(text) or DOLLARS.search(text): f = min(f, 1)
    return f

IM_HEAD_RX = re.compile(r"intellectual merit", re.I); BI_HEAD_RX = re.compile(r"broader impacts?", re.I)
DISEASE_ADVICE = re.compile(r"\b(treatment|therap|cure|disease|disorder|patient|clinical|addiction)\w*", re.I)

def _strip_label(ev: str) -> str:
    """Drop a leading 'Some label: ' that small models like to prepend to the quote."""
    m = re.match(r"^[^:\"“]{3,80}:\s+(?=\S)", ev)
    return ev[m.end():] if m else ev

def _in_text(quote: str, text: str) -> bool:
    """True if enough of the quote's 5-word windows occur verbatim in the statement (tolerates a few edits)."""
    norm = lambda t: re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()  # punctuation AND runs of spaces collapse to ONE space
    q, t = norm(_strip_label(quote)).split(), norm(text)
    q = [w for w in q if w]
    if len(q) < 5: return " ".join(q) in t
    wins = [" ".join(q[i:i + 5]) for i in range(0, len(q) - 4, 2)]
    return sum(w in t for w in wins) / len(wins) >= 0.5

def verify(result: dict, text: str) -> dict:
    """Flag fabricated evidence and score/evidence inconsistencies; adjust scores conservatively."""
    flags = []
    # P6 (headings present) is a structural fact; take it from the deterministic check, not the model
    heads = int(bool(IM_HEAD_RX.search(text))) + int(bool(BI_HEAD_RX.search(text)))
    if int(result["scores"].get("P6", 0)) != heads:
        flags.append(f"P6: set to {heads} from the heading check (model said {result['scores'].get('P6')})")
    result["scores"]["P6"] = heads; result["evidence"]["P6"] = f"{heads} of 2 required headings found by text check"
    # P1 has a countable floor: venue-named publications and outcome sentences
    fl = p1_floor(text)
    if int(result["scores"].get("P1", 0)) < fl:
        flags.append(f"P1: raised to {fl} from the outcome count (model said {result['scores'].get('P1')}; venue-named publications and outcomes are on the page)")
        result["scores"]["P1"] = fl
    for i in range(1, 11):
        k = f"P{i}"; ev = str(result["evidence"].get(k, "")).strip(); sc = int(result["scores"].get(k, 0))
        if k == "P6": continue
        absent = (not ev) or ("not present" in ev.lower()) or (_strip_label(ev).strip().lower() in ("none", "n/a", "absent"))
        if absent and sc > 0:
            flags.append(f"{k}: scored {sc} but no evidence given — set to 0"); result["scores"][k] = 0
        elif not absent and sc > 0 and not _in_text(ev, text):
            flags.append(f"{k}: evidence is not in the statement (model fabricated or paraphrased) — score untrusted, set to 0"); result["scores"][k] = 0
            result["evidence"][k] = "[UNVERIFIED] " + ev
        elif not absent and sc == 0:
            flags.append(f"{k}: quoted evidence but scored 0 — check this item")
    revs = [r for r in result.get("top_revisions", []) if not DISEASE_ADVICE.search(r)]
    if len(revs) < len(result.get("top_revisions", [])):
        flags.append("dropped a revision that recommended disease/treatment framing")
    result["top_revisions"] = revs
    if result.get("parse_note"): flags.append(result["parse_note"])
    result["verification_flags"] = flags
    return result

# ----------------------------------------------------------------------------- reporting
def summarise(scores: dict) -> dict:
    vals = [int(scores[f"P{i}"]) for i in range(1, 11)]
    return {
        "total": sum(vals),
        "four_item": sum(vals[i] for i in FOUR_ITEM),
        "vals": vals,
    }

def band(total: int, four: int) -> str:
    if total < 11:
        return "Below the floor seen in any funded reference statement; the essay itself is limiting."
    if four < 5:
        return "Total is competitive but the four discriminating items (P1, P4, P7, P10) are below every funded reference; focus there."
    if total < 14:
        return "At the lower edge of the funded reference range; outcome will depend on the rest of the application."
    return "Within the funded reference range; remaining gains are in the four-item score and in removing disease framing."

def print_report(student, path, lex, result):
    print("=" * 72)
    print(f"GRFP personal statement score — {student} — {path.name} — {dt.date.today()}")
    print("=" * 72)
    print("\nDeterministic checks")
    print(f"  Words: {lex['word_count']}  (~{lex['estimated_pages_12pt']} pages at 12 pt; target is 3.0)")
    print(f"  Intellectual Merit heading: {'yes' if lex['Intellectual Merit heading'] else 'MISSING'}"
          f" | Broader Impacts heading: {'yes' if lex['Broader Impacts heading'] else 'MISSING'}")
    print(f"  Forecasted journal venues: {lex['forecasted_venues'] or 'none'}")
    print(f"  Dollar amounts: {lex['dollar_amounts'] or 'none'}")
    print(f"  Aspirational verbs (strive/aspire/endeavor/hope to): {lex['aspirational_verbs']}")
    print(f"  Participation phrasing (joined/assisted/had the opportunity...): {lex['participation_phrases']}")
    print(f"  'Developed an interest' drift phrases: {lex['interest_drift_phrases']}")
    print(f"  Clinical/disease terms per 1,000 words: {lex['clinical_terms_per_1000_words']}"
          f"  (all six funded/HM neuroscience references were 4.0 or below)")
    if result is None:
        print("\n(LLM rubric scoring skipped: --no-llm)")
        return
    s = summarise(result["scores"])
    print("\nRubric sub-scores (0–2)")
    for name, v, ev in zip(PRINCIPLES, s["vals"], [result["evidence"].get(f"P{i}", "") for i in range(1, 11)]):
        print(f"  {v}  {name:44s} {ev}")
    print(f"\n  TOTAL {s['total']}/20    FOUR-ITEM (P1+P4+P7+P10) {s['four_item']}/8"
          f"    DISEASE CENTRALITY {result.get('disease_centrality', '?')}/2")
    print(f"  {result.get('disease_evidence', '')}")
    print(f"\n  Reading: {band(s['total'], s['four_item'])}")
    print("\nHighest-value revisions")
    for i, r in enumerate(result.get("top_revisions", []), 1):
        print(f"  {i}. {r}")
    if result.get("verification_flags"):
        print("\nVerification flags (evidence checked against the statement text)")
        for fl in result["verification_flags"]: print(f"  ! {fl}")
        print("  Small local models fabricate evidence more often; if several items are flagged, use a larger model or the offline self-check.")

def append_history(csv_path: Path, student, path, lex, result):
    new = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "student", "file", "words", "total", "four_item", "disease"]
                       + [f"P{i}" for i in range(1, 11)]
                       + ["forecast_venues", "dollar_amounts", "aspirational", "participation", "clinical_per_1000"])
        if result is None:
            s = {"total": "", "four_item": "", "vals": [""] * 10}; d = ""
        else:
            s = summarise(result["scores"]); d = result.get("disease_centrality", "")
        w.writerow([dt.date.today().isoformat(), student, path.name, lex["word_count"], s["total"], s["four_item"], d]
                   + s["vals"]
                   + [len(lex["forecasted_venues"]), len(lex["dollar_amounts"]), lex["aspirational_verbs"],
                      lex["participation_phrases"], lex["clinical_terms_per_1000_words"]])

def show_progress(csv_path: Path, student: str):
    if not csv_path.exists():
        sys.exit(f"No history file at {csv_path}")
    rows = [r for r in csv.DictReader(csv_path.open(encoding="utf-8")) if r["student"].lower() == student.lower()]
    if not rows:
        sys.exit(f"No rows for {student} in {csv_path}")
    print(f"Progress for {student}")
    print(f"{'date':10s} {'file':34s} {'total':>5s} {'four':>4s} {'dis':>3s}  " + " ".join(f"P{i:<2d}" for i in range(1, 11)))
    for r in rows:
        print(f"{r['date']:10s} {r['file'][:34]:34s} {r['total']:>5s} {r['four_item']:>4s} {r['disease']:>3s}  "
              + " ".join(f"{r[f'P{i}']:>3s}" for i in range(1, 11)))

# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("statement", nargs="?", help="personal statement (.docx, .pdf, .txt, .md)")
    ap.add_argument("--student", default="unnamed", help="student name used in the history file")
    ap.add_argument("--history", default="grfp_scores.csv", help="CSV file for tracking drafts over time")
    ap.add_argument("--no-llm", action="store_true", help="run deterministic checks only (no API call)")
    ap.add_argument("--model", default=None, help=f"model id (default {DEFAULT_MODEL} for claude, llama3.1:8b for ollama)")
    ap.add_argument("--backend", choices=["claude", "ollama"], default="claude", help="claude = Anthropic API; ollama = local open-weight model, no network")
    ap.add_argument("--ollama-url", default="http://localhost:11434")
    ap.add_argument("--progress", metavar="STUDENT", help="print a student's trajectory from the history file and exit")
    ap.add_argument("--json", action="store_true", help="also print the raw JSON result")
    ap.add_argument("--test", action="store_true", help="test the Claude and Ollama connections and exit")
    args = ap.parse_args()

    if args.test:
        ok, m = test_claude(args.model); print(("OK  " if ok else "FAIL") + "  Claude: " + m)
        ok, m = test_ollama(args.ollama_url, args.model if args.backend == "ollama" else None); print(("OK  " if ok else "FAIL") + "  Ollama: " + m); return
    if args.progress:
        show_progress(Path(args.history), args.progress); return
    if not args.statement:
        ap.error("a statement file is required unless --progress is used")

    path = Path(args.statement)
    model = args.model or (DEFAULT_MODEL if args.backend == "claude" else "llama3.1:8b")
    try:
        text = extract_text(path)
        if len(text.split()) < 200:
            raise RuntimeError("Extracted fewer than 200 words; check the file (scanned PDFs need to be exported as .docx).")
        lex = lexical_checks(text)
        result = None if args.no_llm else verify(llm_score(text, model, args.backend, args.ollama_url), text)
    except (RuntimeError, FileNotFoundError) as e:
        sys.exit(str(e))
    print_report(args.student, path, lex, result)
    append_history(Path(args.history), args.student, path, lex, result)
    print(f"\nLogged to {args.history}. View trajectory with: python score_statement.py --history {args.history} --progress \"{args.student}\"")
    if args.json and result:
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
