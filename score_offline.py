#!/usr/bin/env python3
"""
score_offline.py — score an NSF GRFP personal statement against the ten-principle rubric
WITHOUT any API or model. Every sub-score is a proxy computed from measurable text features,
calibrated against 46 hand-scored statements. It is deliberately conservative: it catches
the mechanical and structural problems reliably and approximates the judgement items.

Usage
    python score_offline.py STATEMENT.docx --student "Name"
    python score_offline.py STATEMENT.pdf  --student "Name" --history offline_scores.csv
    python score_offline.py --history offline_scores.csv --progress "Name"
    python score_offline.py STATEMENT.txt --explain        # show the feature counts behind each score
    python score_offline.py STATEMENT.docx --self-check    # audit the five judgement items yourself

Requires only python-docx (for .docx) and pdfplumber (for .pdf). No network access.

How to read it
    This tool is reliable for the mechanical checks (length, headings, venue forecasts, dollar
    amounts, aspirational verbs, participation phrasing, clinical-term density) and for P4
    (broader-impacts concreteness) and P6 (framing). P1 and P3 are fair. The remaining items
    are weak proxies: on the 46-statement calibration set the offline four-item score agrees
    with a human reader's four-item score to within one point 63% of the time (Spearman 0.33),
    and its AUC against official NSF outcomes in the neuroscience pool was 0.61 versus 0.81
    for the human-scored four-item score. Use it to track direction between drafts and to
    catch the mechanical problems; use score_statement.py (API) or a reader for the judgement.
"""
import argparse, csv, datetime as dt, json, re, sys
from pathlib import Path

PRINCIPLES = ["P1 Outcomes stated plainly", "P2 Organizing question up front", "P3 Initiative and autonomy",
              "P4 Broader impacts as a concrete plan", "P5 Research tied to societal benefit", "P6 Explicit IM/BI framing",
              "P7 Narrative converted to evidence", "P8 One question, one finding per project", "P9 Obstacles narrated as method",
              "P10 Named graduate plan"]
FOUR = [0, 3, 6, 9]

# --------------------------------------------------------------------------- text extraction
def extract_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}\n  Looked in: {Path.cwd()}\n  Give the full path (drag the file into the terminal to paste it), or move the file into this folder.")
    s = path.suffix.lower()
    if s in (".txt", ".md"): return path.read_text(encoding="utf-8", errors="ignore")
    if s == ".docx":
        try:
            import docx
        except ImportError:
            raise RuntimeError("The .docx reader (python-docx) is not installed in this copy of the scorer. Run: pip install python-docx — or export the statement as PDF.")
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    if s == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("The PDF reader (pdfplumber) is not installed in this copy of the scorer. Run: pip install pdfplumber — or export the statement as .docx.")
        with pdfplumber.open(str(path)) as pdf: return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    raise RuntimeError(f"Unsupported file type {s}: use .docx, .pdf, .txt or .md")

# --------------------------------------------------------------------------- lexicons
W = lambda pat: re.compile(r"\b(?:" + pat + r")\b", re.I)
JOURNALS = W(r"Nature|Science|Cell|Neuron|PNAS|eLife|Current Biology|J(?:ournal)? of [A-Z][a-z]+(?: [A-Z][a-z]+)*|Biological Psychiatry|PLOS? (?:ONE|Biology)|bioRxiv|PsyArXiv|Frontiers in [A-Z][a-z]+|Molecular [A-Z][a-z]+|Behavioral Neuroscience|Brain Connectivity|Developmental Biology|Conservation Genetics|Science Advances")
PUB = W(r"published|publication|co-?author(?:ship|ed)?|first[- ]author(?:ship|ed)?|second[- ]author|manuscript|preprint|in (?:review|press|preparation)|under review|submitted")
PRESENT = W(r"poster|presented|presentation|talk|symposium|conference|meeting|SfN|Society for Neuroscience")
AWARD = W(r"award(?:ed)?|prize|fellowship|scholarship|grant|honou?rs|dean'?s list|summa|magna|cum laude|distinction|editor'?s choice")
FORECAST = re.compile(r"(?:in preparation for|to be submitted to|will be submitted to|preparing (?:a |the )?(?:manuscript|paper) for|submission to|targeting)\s+(?:the (?:academic )?journal\s+)?(?:Nature|Science|Cell|Neuron|PNAS|eLife|Lancet|NEJM|JAMA)\b", re.I)
DOLLARS = re.compile(r"\$\s?\d[\d,]*")
AGENT = W(r"I (?:designed|built|developed|led|co-?founded|founded|created|initiated|proposed|spearheaded|wrote|secured|established|organized|taught|trained|pioneered|engineered|automated|implemented|devised|launched|coordinated|managed|recruited|mentored|approached|contacted|applied for|was awarded|won|discovered|identified|demonstrated|showed|found|tested|hypothesized)")
PARTICIP = W(r"I (?:joined|assisted|helped|contributed to|participated in|was given the opportunity|had the opportunity|was fortunate|was able to|was exposed to|gained experience|learned (?:how )?to)|worked under|under the (?:guidance|supervision|mentorship) of|had the chance")
ASPIRE = W(r"strive[sd]?|striving|aspire[sd]?|aspiring|endeavou?r(?:s|ed|ing)?|hope[sd]? to|hoping to|I hope")
QUESTION = re.compile(r"\?|\b(?:my (?:core |central |overarching |guiding )?(?:question|goal|aim) (?:is|was)|I (?:want|aim|seek|set out) to (?:understand|know|determine|uncover|explain|answer)|how (?:does|do|can|the)|why (?:does|do|is|are)|what (?:are|is) the)\b", re.I)
FINDING = W(r"(?:we|I) (?:found|showed|discovered|demonstrated|observed|identified|concluded)|(?:this|these|our|my) (?:results?|findings?|data|work) (?:showed?|suggest(?:ed|s)?|indicat(?:ed|es)|revealed?|demonstrat(?:ed|es))|suggesting that|indicating that|revealed that|consistent with|surprisingly|unexpectedly|contrary to")
TECHNIQUE = W(r"PCR|qPCR|Western blot(?:ting)?|immunohistochemistry|IHC|immunofluorescence|ELISA|flow cytometry|FACS|sequencing|RNA-?seq|single-?(?:cell|nucle[iu]s)|CRISPR|optogenetic(?:s)?|chemogenetic(?:s)?|DREADDs?|electrophysiolog(?:y|ical)|patch[- ]clamp|fMRI|MRI|EEG|MEG|DTI|calcium imaging|two-?photon|2-?photon|fiber photometry|stereotaxic|surger(?:y|ies)|MATLAB|Python|R\b|machine learning|deep learning|confocal|microscopy|cloning|transfection|viral vectors?|AAV|histolog(?:y|ical)|cryostat|tractography|GLM|regression")
OBSTACLE = W(r"fail(?:ed|ure|ing)?|did not (?:work|produce|yield)|didn'?t work|unexpected(?:ly)?|troubleshoot(?:ing)?|setback|obstacle|scooped|null (?:result|effect)|no (?:significant )?(?:effect|difference)|negative results?|rejected|rejection|struggl(?:e|ed|ing)|broke|inadequate|confound|artifact|redesign(?:ed)?|rebuilt|adapted|persist(?:ed|ence)|from scratch|trial and error")
RESOLVE = W(r"so I|instead,? I|to (?:overcome|solve|address|surmount) this|I (?:redesigned|rebuilt|built|adapted|optimized|developed a (?:new|novel)|reanalyzed|re-ran|ran several more|identified the (?:problem|confound|source)|figured out)")
PLAN = W(r"I will|I plan to|I intend to|I propose|I am (?:now )?(?:working|focusing|studying|investigating)|my (?:thesis|dissertation|proposed) (?:work|project|research)|during (?:my|graduate)|(?:next|first|second) (?:year|rotation)|rotation")
LAB = re.compile(r"\b(?:Dr\.|Professor|Prof\.)\s+[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?(?:'s)?\s+(?:lab|laboratory|group)|(?:lab|laboratory) of (?:Dr\.|Professor)\s+[A-Z][\w'-]+|(?:rotat(?:ing|ed|ion) (?:in|with)|joined|working with|under the (?:guidance|mentorship|direction) of|my (?:advisor|mentor|PI),?|co-?advised by|collaborat(?:e|ing|ion) with)\s+(?:Dr\.|Professor|Prof\.)\s+[A-Z][\w'-]+|(?:Neuroscience|Biology|Psychology|Bioengineering)\s+(?:Graduate|PhD|Ph\.D\.)\s+Program|(?:PhD|Ph\.D\.|doctoral) (?:program|student|studies) (?:at|in) [A-Z]", re.I)
TRAIN = W(r"learn(?:ing)? (?:to|how to|new)|new techniques?|techniques? (?:still|I will|I need|to learn)|training in|will (?:gain|acquire|develop|learn)|workshop|course")
FELLOW = W(r"(?:the )?(?:NSF|GRFP|fellowship|GRF)\b.{0,60}\b(?:would|will) (?:allow|enable|give|provide|let|support|free|afford)")
SOCIETY = W(r"society|societal|public (?:health|policy|understanding|good|literacy)|policy(?:makers)?|communit(?:y|ies)|patients?|clinicians?|farmers?|conservation|agricultur(?:e|al)|economic|quality of life|inform (?:the )?(?:design|treatment|management|decisions?)|benefit(?:s|ing)? (?:society|the public|people)|real[- ]world|translat(?:e|ional|ion)")
BI_NUMBER = re.compile(r"\b(?:\d{1,3}(?:,\d{3})*|\d+)\+?\s*(?:students?|kids|children|girls|boys|attendees|participants|members|volunteers|teachers|schools|classrooms|mentees|undergraduates|people|employees|copies|views|hours|sessions|events|workshops|visits)\b", re.I)
PROGRAM = re.compile(r"\b(?:[A-Z][\w'&-]+\s+){1,4}(?:Program|Programme|Initiative|Club|Society|Chapter|Fellowship|Festival|Fair|Bee|Camp|Academy|Institute|Center|Centre|Project|Network|Alliance|Association|Outreach|Journal|Newsletter|Seminar|Committee|Foundation|Museum|Hospital|Clinic|YMCA|REU|SACNAS|ABRCMS)\b")
FUTURE_BI = re.compile(r"\b(?:I will|I plan to|I intend to|I am (?:working|committed) to|I have (?:already )?(?:begun|started|signed|applied|joined))\b[^.]{0,120}\b(?:mentor|teach|outreach|volunteer|tutor|Brain Bee|festival|chapter|program|workshop|panel|K-12|high school|undergraduate)", re.I)
PERSONAL = W(r"my (?:mother|mom|father|dad|parents|family|grandmother|grandfather|grandpa|grandma|sister|brother|cousin|hometown|childhood|upbringing)|first[- ]generation|immigrant(?:s)?|as a child|growing up|when I was (?:\d+|a child|young|seven|eight|twelve)|in (?:high|middle|elementary) school|non-?traditional|gap year|veteran|Air Force|Peace Corps")
CONVERT = W(r"taught me|showed me|gave me (?:the|a)|prepared me|instilled|I learned (?:that|to|the)|this (?:experience|lesson|shift)|which (?:is|was) why|that is why|which led me to|convinced me|confirmed my|forced me to|made me (?:realize|aware)|drives my|shaped my|informs my|I now (?:understand|realize|see)|the same (?:skills|lesson|principles)")
IM_HEAD = re.compile(r"intellectual merit", re.I)
BI_HEAD = re.compile(r"broader impacts?", re.I)
CLINICAL = re.compile(r"\b(?:Parkinson|Alzheimer|dementia|schizophren|psychos[ie]s|depress(?:ion|ive)|anxiety|PTSD|autism|epilep|stroke|cancer|tumou?r|glioblastoma|addiction|opioid|cocaine|patients?|clinical|therap(?:y|ies|eutic)|treatment|cure|diagnos|disease|disorder|RDoC|NIH|NIMH|NIDA|NIAAA|gene therapy|trial)\w*", re.I)

# --------------------------------------------------------------------------- feature extraction
FIRST_PERSON_ACT = re.compile(r"\bI (?:had to|redesigned|rebuilt|built|adapted|optimized|ran|re-?ran|tested|tried|spent|identified|figured|learned|taught myself|went back|returned|repeated|switched|changed|developed|found|realized|noticed)\b", re.I)
MENTOR_CTX = re.compile(r"\b(?:taught me|showed me|she|he|they|my mentor|Dr\.)\b", re.I)
def obstacle_episodes(text):
    n = 0
    for sent in re.split(r"(?<=[.!?])\s+", text):
        if OBSTACLE.search(sent) and FIRST_PERSON_ACT.search(sent) and not (MENTOR_CTX.search(sent) and not re.search(r"\bI\b", sent)):
            n += 1
    return n
def paragraphs(text):
    ps = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[A-Z])", text) if len(p.split()) > 25]
    return ps if ps else [text]

def bi_section(text):
    m = BI_HEAD.search(text)
    if m:
        seg = text[m.start():]
        e = re.search(r"\b(?:Future Goals?|Intellectual Merit|References?)\b", seg[20:], re.I)
        return seg[: 20 + e.start()] if e else seg
    return text[int(len(text) * 0.6):]

def features(text):
    words = len(text.split()); k = max(words, 1) / 1000.0
    ps = paragraphs(text); opening = " ".join(ps[:2])[:1500]; body = text
    op_words = [w.lower() for w in re.findall(r"[A-Za-z][a-z]{5,}", opening)]
    stop = set("during through research science because experience program university college graduate student students".split())
    key = [w for w in dict.fromkeys(op_words) if w not in stop][:12]
    later = ps[2:] if len(ps) > 3 else ps
    coherence = (sum(any(kw in p.lower() for kw in key) for p in later) / max(len(later), 1)) if key else 0
    bi = bi_section(text); bi_words = max(len(bi.split()), 1)
    f = dict(
        words=words, pages=round(words / 700, 2),
        pubs=len(PUB.findall(text)), journals=len(JOURNALS.findall(text)), presents=len(PRESENT.findall(text)), awards=len(AWARD.findall(text)),
        forecast=len(FORECAST.findall(text)), dollars=len(DOLLARS.findall(text)),
        question_open=len(QUESTION.findall(opening)), coherence=round(coherence, 2),
        agent=len(AGENT.findall(text)), particip=len(PARTICIP.findall(text)), aspire=len(ASPIRE.findall(text)),
        bi_numbers=len(BI_NUMBER.findall(bi)), bi_programs=len(set(m.strip() for m in PROGRAM.findall(bi))), bi_future=len(FUTURE_BI.findall(bi)), bi_aspire=len(ASPIRE.findall(bi)), bi_share=round(bi_words / max(words, 1), 2),
        society=len(SOCIETY.findall(text)),
        im_head=bool(IM_HEAD.search(text)), bi_head=bool(BI_HEAD.search(text)),
        personal=len(PERSONAL.findall(text)), convert=len(CONVERT.findall(text)),
        findings=len(FINDING.findall(text)), techniques=len(TECHNIQUE.findall(text)),
        obstacle=len(OBSTACLE.findall(text)), obstacle_episodes=obstacle_episodes(text), resolve=len(RESOLVE.findall(text)),
        plan=len(PLAN.findall(text)), lab=len(LAB.findall(text)), train=len(TRAIN.findall(text)), fellow=len(FELLOW.findall(text)),
        clinical_per_1000=round(len(CLINICAL.findall(text)) / k, 1),
    )
    return f

# --------------------------------------------------------------------------- scoring rules
# Each proxy is a continuous index cut into 0/1/2 at thresholds chosen to maximise agreement with
# 46 hand-scored statements. RELIABILITY is the Spearman correlation with the hand score on that set:
# treat items marked "weak" as suggestions, not measurements.
CUTS = {"P1": (3.75, 13.5), "P2": (0.5, 2.29), "P3": (0.11, 3.32), "P4": (0.0, 1.53), "P5": (3.13, 8.08),
        "P6": (0.75, 1.0), "P7": (0.5, 9.35), "P8": (-3.85, 0.86), "P9": (0.0, 0.71), "P10": (1.5, 3.25)}
RELIABILITY = {"P1": "fair (0.45)", "P2": "weak (0.28)", "P3": "fair (0.46)", "P4": "good (0.61)", "P5": "weak (0.33)",
               "P6": "good (0.66)", "P7": "weak (0.21)", "P8": "weak (0.26)", "P9": "weak (0.28)", "P10": "fair (0.38)"}

def proxies(f):
    W = max(f["words"] / 1000.0, 0.5)
    return {
        "P1": f["pubs"] + f["journals"] + 0.5 * f["awards"] - 2 * (f["forecast"] + f["dollars"]),
        "P2": f["question_open"] + 2 * f["coherence"],
        "P3": f["agent"] / max(f["agent"] + f["particip"], 1) * 10 - f["aspire"],
        "P4": (2 * f["bi_numbers"] + f["bi_programs"] + f["bi_future"]) / W,
        "P5": f["society"] / W,
        "P6": int(f["im_head"]) + int(f["bi_head"]),
        "P7": f["personal"] + f["convert"] / W,
        "P8": f["findings"] / max(f["findings"] + 0.5 * f["techniques"], 1) * 10 - f["particip"],
        "P9": f["obstacle"] / W + 2 * f["resolve"],
        "P10": (2 if f["lab"] >= 1 else 0) + (1 if f["plan"] >= 3 else 0) + (1 if f["train"] >= 2 else 0) + (1 if f["fellow"] >= 1 else 0) - 0.5 * f["aspire"],
    }

def band(x, lo, hi): return 0 if x < lo else (1 if x < hi else 2)

def score(f):
    px = proxies(f)
    s = {k: band(px[k], *CUTS[k]) for k in CUTS}
    D = band(f["clinical_per_1000"], 4.0, 8.0)
    return s, D


# --------------------------------------------------------------------------- guided self-check for the judgement items
SELF_CHECK = [
    ("P2", "Paste the sentence from your FIRST paragraph that states the question you want to answer."),
    ("P7", "Paste the sentence where your personal story is turned into evidence of something reviewers score (independence, persistence, leadership)."),
    ("P8", "For your MAIN project, paste the sentence that states what you found and what it means."),
    ("P9", "Paste the sentence describing something that went wrong in your research and what YOU did about it."),
    ("P10", "Paste the sentence naming the lab or advisor, the project, and a technique you still need to learn."),
]
def self_check(text):
    """Ask the student to locate the evidence for each judgement item. A pasted sentence that appears in the
    statement earns 1; an empty answer earns 0; the student assigns 2 only if the sentence also contains the
    specific detail the rubric asks for. This replaces the weak proxies with the student's own audit."""
    print("\nSelf-check for the judgement items (the offline proxies for these are unreliable).")
    print("For each, paste the sentence from your statement, or press Enter if there isn't one.\n")
    norm = re.sub(r"\s+", " ", text).lower(); out = {}
    for item, prompt in SELF_CHECK:
        ans = input(f"{item}: {prompt}\n> ").strip()
        if not ans: out[item] = 0; print("   -> 0 (nothing to point to; that is the revision)\n"); continue
        found = re.sub(r"\s+", " ", ans).lower()[:80] in norm
        if not found: print("   (that sentence is not in the statement as uploaded)")
        spec = input("   Does it contain the specific detail the rubric asks for — a name, a number, a result, an action? [y/N] ").strip().lower() == "y"
        out[item] = 2 if (found and spec) else (1 if found else 0); print(f"   -> {out[item]}\n")
    return out

# --------------------------------------------------------------------------- reporting / history
def report(student, path, f, s, D, explain=False):
    vals = [s[f"P{i}"] for i in range(1, 11)]; total = sum(vals); four = sum(vals[i] for i in FOUR)
    print("=" * 72); print(f"OFFLINE rubric score — {student} — {path.name} — {dt.date.today()}"); print("=" * 72)
    print(f"Words {f['words']} (~{f['pages']} pages)   IM heading: {'yes' if f['im_head'] else 'MISSING'}   BI heading: {'yes' if f['bi_head'] else 'MISSING'}")
    print(f"Forecasted venues: {f['forecast']}   Dollar amounts: {f['dollars']}   Aspirational verbs: {f['aspire']}   Participation phrasing: {f['particip']}   Clinical terms/1000: {f['clinical_per_1000']}")
    print("\nSub-scores (proxy, 0–2)")
    for i,(name, v) in enumerate(zip(PRINCIPLES, vals)): print(f"  {v}  {name:44s} reliability {RELIABILITY[f'P{i+1}']}")
    print(f"\n  TOTAL {total}/20    FOUR-ITEM {four}/8    DISEASE-CENTRALITY {D}/2")
    if total < 11: msg = "Below the floor of any funded reference statement."
    elif four < 5: msg = "Total competitive; the four discriminating items are below every funded reference."
    elif total < 14: msg = "Lower edge of the funded reference range."
    else: msg = "Within the funded reference range."
    print(f"  Reading: {msg}")
    if explain:
        print("\nFeature counts:"); print("  " + json.dumps(f))
    return total, four

def append_history(csv_path, student, path, f, s, D, total, four):
    new = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new: w.writerow(["date", "student", "file", "words", "total", "four_item", "disease"] + [f"P{i}" for i in range(1, 11)] + ["forecast", "dollars", "aspire", "particip", "clinical_per_1000"])
        w.writerow([dt.date.today().isoformat(), student, path.name, f["words"], total, four, D] + [s[f"P{i}"] for i in range(1, 11)] + [f["forecast"], f["dollars"], f["aspire"], f["particip"], f["clinical_per_1000"]])

def show_progress(csv_path, student):
    rows = [r for r in csv.DictReader(csv_path.open(encoding="utf-8")) if r["student"].lower() == student.lower()]
    if not rows: sys.exit(f"No rows for {student}")
    print(f"{'date':10s} {'file':34s} {'total':>5s} {'four':>4s} {'dis':>3s}  " + " ".join(f"P{i:<2d}" for i in range(1, 11)))
    for r in rows: print(f"{r['date']:10s} {r['file'][:34]:34s} {r['total']:>5s} {r['four_item']:>4s} {r['disease']:>3s}  " + " ".join(f"{r[f'P{i}']:>3s}" for i in range(1, 11)))

def calibrate(dirpath):
    """Compare proxy scores with hand scores in <dir>/hand.json (name -> 10 scores)."""
    from scipy.stats import spearmanr
    hand = json.load(open(Path(dirpath) / "hand.json"))
    H, M = [], []
    for name, hv in hand.items():
        p = Path(dirpath) / f"{name}.txt"
        if not p.exists(): continue
        s, D = score(features(extract_text(p))); H.append(hv); M.append([s[f"P{i}"] for i in range(1, 11)])
    import numpy as np; H = np.array(H); M = np.array(M)
    print(f"n = {len(H)}"); print("item   spearman  exact  within1")
    for i in range(10):
        r = spearmanr(H[:, i], M[:, i])[0] if len(set(M[:, i])) > 1 else float("nan")
        print(f"P{i+1:<3d}  {r:7.2f}   {np.mean(H[:,i]==M[:,i]):.2f}   {np.mean(abs(H[:,i]-M[:,i])<=1):.2f}")
    ht, mt = H.sum(1), M.sum(1); hf, mf = H[:, FOUR].sum(1), M[:, FOUR].sum(1)
    print(f"TOTAL spearman {spearmanr(ht, mt)[0]:.2f}  mean abs diff {np.mean(abs(ht-mt)):.2f}")
    print(f"FOUR  spearman {spearmanr(hf, mf)[0]:.2f}  mean abs diff {np.mean(abs(hf-mf)):.2f}  within1 {np.mean(abs(hf-mf)<=1):.2f}")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("statement", nargs="?"); ap.add_argument("--student", default="unnamed"); ap.add_argument("--history", default="offline_scores.csv")
    ap.add_argument("--progress", metavar="STUDENT"); ap.add_argument("--explain", action="store_true"); ap.add_argument("--calibrate", metavar="DIR")
    ap.add_argument("--self-check", action="store_true", help="after the proxy scores, walk through the five judgement items interactively and replace the proxies with your own audited scores")
    a = ap.parse_args()
    if a.calibrate: calibrate(a.calibrate); return
    if a.progress: show_progress(Path(a.history), a.progress); return
    if not a.statement: ap.error("statement file required")
    path = Path(a.statement)
    try:
        text = extract_text(path)
    except (RuntimeError, FileNotFoundError) as e:
        sys.exit(str(e))
    if len(text.split()) < 200: sys.exit("Fewer than 200 words extracted; check the file (scanned PDFs need to be exported as .docx).")
    f = features(text); s, D = score(f)
    if a.self_check:
        s.update(self_check(text)); print("\nRe-scored with self-check answers:")
    total, four = report(a.student, path, f, s, D, a.explain)
    append_history(Path(a.history), a.student, path, f, s, D, total, four)
    print(f"\nLogged to {a.history}.")

if __name__ == "__main__": main()
