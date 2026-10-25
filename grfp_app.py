#!/usr/bin/env python3
"""
grfp_app.py — desktop app for the GRFP personal statement rubric.

Copyright 2025-2026 Vincent D. Costa
Licensed under the Apache License, Version 2.0 (see LICENSE). Provided "AS IS", without
warranty; scores describe rubric fit only and are not predictions of fellowship outcomes
(see DISCLAIMER.md).

Drop a .docx or .pdf onto the window (or click Open). The app picks the best available
backend automatically:
    1. Claude API      if an Anthropic API key is set (environment or saved in Settings).
                       The key is the user's own — see docs/API_KEY_SETUP.md.
    2. Local model     if Ollama is running on this machine with at least one model pulled
    3. Offline         always available: lexical checks + proxy sub-scores
You can override the choice in the Backend menu. Every run is appended to a history file in
your home folder (~/.grfp_scorer/history.csv) so you can watch drafts improve.

On first launch the app shows the license and disclaimer, asks which backend to use, and
registers the copy (name, email, institution) — see firstrun.py, register.py, PRIVACY.md.

Run from source:   python grfp_app.py
Build an app:      installer/build_mac.sh, build_mac_intel.sh, build_windows.ps1, or the GitHub
                   Actions workflow in .github/workflows/release.yml
"""
import csv, datetime as dt, json, os, sys, threading, urllib.request
from pathlib import Path

# --- locate bundled resources (PyInstaller) or the source folder --------------------------------
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(BASE))
import score_offline as so          # noqa: E402
import score_statement as ss        # noqa: E402
import register                     # noqa: E402  config file, first-run registration, usage ping

CONFIG_DIR = register.CONFIG_DIR
CONFIG = register.CONFIG_PATH
HISTORY = CONFIG_DIR / "history.csv"
FOUR = [0, 3, 6, 9]

# --- backend detection (no GUI dependency; testable) -------------------------------------------
load_config = register.load_config
save_config = register.save_config

def claude_available(cfg: dict) -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY") or cfg.get("anthropic_api_key")
    if not key: return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    os.environ["ANTHROPIC_API_KEY"] = key
    return True

def ollama_models(url="http://localhost:11434") -> list:
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=2) as r:
            return [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
    except Exception:
        return []

def detect_backend(cfg: dict, live_check: bool = True) -> tuple:
    """Return (backend, model, reason). With live_check, actually call the API so a bad key, no credit,
    or a blocked network is reported here instead of as a stall later."""
    if claude_available(cfg):
        model = cfg.get("claude_model") or ss.DEFAULT_MODEL
        if not live_check: return "claude", model, "Anthropic API key found"
        ok, msg = ss.test_claude(model)
        if ok: return "claude", model, msg
        note = f"Claude unavailable: {msg}"
        models = ollama_models(cfg.get("ollama_url", "http://localhost:11434"))
        if models:
            pref = cfg.get("ollama_model"); m = pref if pref in models else models[0]
            return "ollama", m, note + f" — using Ollama ({m})"
        return "offline", "", note + " — using offline"
    models = ollama_models(cfg.get("ollama_url", "http://localhost:11434"))
    if models:
        pref = cfg.get("ollama_model")
        model = pref if pref in models else models[0]
        return "ollama", model, f"Ollama running with {len(models)} model(s); no API key"
    return "offline", "", "no API key and Ollama not running"

# --- scoring dispatch (no GUI dependency; testable) --------------------------------------------
def run_scoring(path: Path, student: str, backend: str, model: str, cfg: dict) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    text = ss.extract_text(path)
    if len(text.split()) < 200:
        raise ValueError("Fewer than 200 words extracted — is this the right file? Scanned PDFs need to be exported to .docx first.")
    lex = ss.lexical_checks(text)
    out = {"file": path.name, "student": student, "backend": backend, "model": model, "lex": lex, "date": dt.date.today().isoformat()}
    if backend == "offline":
        f = so.features(text); s, D = so.score(f)
        out["scores"] = [s[f"P{i}"] for i in range(1, 11)]; out["disease"] = D
        out["evidence"] = [f"proxy — reliability {so.RELIABILITY[f'P{i}']}" for i in range(1, 11)]
        out["revisions"] = offline_revisions(out["scores"], lex, D)
    else:
        r = ss.verify(ss.llm_score(text, model, backend, cfg.get("ollama_url", "http://localhost:11434")), text)
        out["scores"] = [int(r["scores"][f"P{i}"]) for i in range(1, 11)]
        out["disease"] = int(r.get("disease_centrality", -1))
        out["evidence"] = [r["evidence"].get(f"P{i}", "") for i in range(1, 11)]
        out["revisions"] = r.get("top_revisions", [])
        out["disease_evidence"] = r.get("disease_evidence", "")
        out["flags"] = r.get("verification_flags", [])
    out["total"] = sum(out["scores"]); out["four"] = sum(out["scores"][i] for i in FOUR)
    return out

def offline_revisions(scores, lex, D) -> list:
    tips = []
    names = ["state every publication, presentation, and award plainly with its venue",
             "state the research question in the first paragraph and carry it through",
             "narrate initiative as specific acts, not 'I joined' / 'I assisted'",
             "build broader impacts from named programs, partners, headcounts, and future commitments",
             "add one sentence on who outside the field benefits if the work succeeds",
             "keep the Intellectual Merit and Broader Impacts headings and argue each",
             "turn the opening story into evidence of independence, persistence, or leadership",
             "give each project a question, a finding, and its meaning in plain language",
             "narrate one concrete obstacle and what you did about it",
             "name the lab, the project, the techniques still to learn, and what the fellowship enables"]
    order = sorted(range(10), key=lambda i: (scores[i], -1 if i in FOUR else 0))
    for i in order:
        if scores[i] < 2 and len(tips) < 3: tips.append(f"P{i+1}: {names[i]}")
    if lex["forecasted_venues"]: tips.insert(0, "remove forecasted journal venues: " + ", ".join(lex["forecasted_venues"]))
    if lex["dollar_amounts"]: tips.insert(0, "remove dollar amounts: " + ", ".join(lex["dollar_amounts"]))
    if D == 2: tips.insert(0, "the research narrative is organized around a disease or patient population; reframe as a mechanism question")
    if lex["estimated_pages_12pt"] < 2.6: tips.insert(0, f"only ~{lex['estimated_pages_12pt']} pages — use all three")
    return tips[:5]

def append_history(out: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True); new = not HISTORY.exists()
    with HISTORY.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new: w.writerow(["date", "student", "file", "backend", "model", "words", "total", "four_item", "disease"] + [f"P{i}" for i in range(1, 11)])
        w.writerow([out["date"], out["student"], out["file"], out["backend"], out["model"], out["lex"]["word_count"], out["total"], out["four"], out["disease"]] + out["scores"])

def format_report(out: dict) -> str:
    lex = out["lex"]; L = []
    L.append(f"{out['student']} — {out['file']} — {out['date']}")
    L.append(f"Backend: {out['backend']}" + (f" ({out['model']})" if out["model"] else ""))
    L.append("")
    L.append("MECHANICAL CHECKS")
    L.append(f"  Words {lex['word_count']} (~{lex['estimated_pages_12pt']} pages at 12 pt; target 3.0)")
    L.append(f"  Intellectual Merit heading: {'yes' if lex['Intellectual Merit heading'] else 'MISSING'}   Broader Impacts heading: {'yes' if lex['Broader Impacts heading'] else 'MISSING'}")
    L.append(f"  Forecasted journal venues: {', '.join(lex['forecasted_venues']) or 'none'}")
    L.append(f"  Dollar amounts: {', '.join(lex['dollar_amounts']) or 'none'}")
    L.append(f"  Aspirational verbs: {lex['aspirational_verbs']}   Participation phrasing: {lex['participation_phrases']}   Clinical terms/1000 words: {lex['clinical_terms_per_1000_words']} (funded references ≤ 4)")
    L.append("")
    L.append("RUBRIC SUB-SCORES (0–2)")
    for name, v, ev in zip(ss.PRINCIPLES, out["scores"], out["evidence"]):
        L.append(f"  {v}  {name}"); 
        if ev: L.append(f"       {ev}")
    L.append("")
    L.append(f"TOTAL {out['total']}/20     FOUR-ITEM (P1+P4+P7+P10) {out['four']}/8     DISEASE CENTRALITY {out['disease']}/2")
    if out.get("disease_evidence"): L.append(f"  {out['disease_evidence']}")
    L.append(f"  {ss.band(out['total'], out['four'])}")
    L.append("")
    L.append("HIGHEST-VALUE REVISIONS")
    for i, t in enumerate(out["revisions"], 1): L.append(f"  {i}. {t}")
    if out.get("flags"):
        L.append(""); L.append("VERIFICATION FLAGS (evidence checked against the statement)")
        for fl in out["flags"]: L.append(f"  ! {fl}")
    if out["backend"] == "offline":
        L.append(""); L.append("Note: offline sub-scores for P2, P5, P7, P8, P9 are weak proxies. For a real reading, set an API key in Settings or start Ollama.")
    return "\n".join(L)

def progress_text(student: str) -> str:
    if not HISTORY.exists(): return "No history yet."
    rows = [r for r in csv.DictReader(HISTORY.open(encoding="utf-8")) if r["student"].strip().lower() == student.strip().lower()]
    if not rows: return f"No runs logged for {student}."
    L = [f"{'date':10s} {'file':28s} {'backend':8s} {'total':>5s} {'four':>4s} {'dis':>3s}  " + " ".join(f"P{i:<2d}" for i in range(1, 11))]
    for r in rows: L.append(f"{r['date']:10s} {r['file'][:28]:28s} {r['backend']:8s} {r['total']:>5s} {r['four_item']:>4s} {r['disease']:>3s}  " + " ".join(f"{r[f'P{i}']:>3s}" for i in range(1, 11)))
    L.append(""); L.append("Compare runs made with the same backend; the numbers are not interchangeable across backends.")
    return "\n".join(L)

# --- GUI ---------------------------------------------------------------------------------------
NAVY, GOLD, INK, MID, PALE, LINE, GREEN, BG, WHITE, STAR_BG = "#1E2761", "#D9A441", "#23272F", "#5B6270", "#EEF3FB", "#D2D6DC", "#2E8B57", "#ECEEF1", "#FFFFFF", "#FDF8EC"
FOUR_SET = {0, 3, 6, 9}

def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk(); dnd = True
    except Exception:
        root = tk.Tk(); dnd = False
    root.title("GRFP Personal Statement Scorer"); root.geometry("1240x860"); root.minsize(1000, 700); root.configure(bg=BG)
    try:
        icon_png = BASE / "installer" / "icon" / "grfp_icon.png"
        if icon_png.exists(): root.iconphoto(True, tk.PhotoImage(file=str(icon_png)))
    except Exception:
        pass
    mono = "Menlo" if sys.platform == "darwin" else "Consolas"
    ui = "Helvetica" if sys.platform == "darwin" else "Segoe UI"
    style = ttk.Style(); style.configure("TNotebook", background=BG); style.configure("TFrame", background=BG)
    cfg = load_config()

    # ---- first launch: license + disclaimer, backend choice, registration (firstrun.py)
    if register.needs_registration(cfg):
        _launch_log("first launch: starting wizard")
        try:
            import firstrun
            ok = firstrun.run(root, cfg, BASE)   # runs root.mainloop() itself; returns when the wizard closes
        except Exception:
            import traceback
            tb = traceback.format_exc(); _launch_log("wizard crashed:\n" + tb)
            try: messagebox.showerror("GRFP Scorer", "The first-launch setup failed to open.\n\n" + tb[-1500:] + f"\n\nDetails were written to {CONFIG_DIR / 'launch.log'}.")
            except Exception: pass
            root.destroy(); return
        if not ok:
            _launch_log("wizard declined; exiting"); root.destroy(); return
    _launch_log("building main window")
    register.retry_pending(cfg)
    backend, model, reason = detect_backend(cfg)

    # ---- top controls
    top = tk.Frame(root, bg=BG, padx=22, pady=12); top.pack(fill="x")
    tk.Label(top, text="Student name:", bg=BG, fg=INK, font=(ui, 13)).grid(row=0, column=0, sticky="w")
    student_var = tk.StringVar(value=cfg.get("last_student") or cfg.get("name", ""))
    tk.Entry(top, textvariable=student_var, width=28, font=(ui, 13)).grid(row=0, column=1, sticky="w", padx=(6, 18))
    tk.Label(top, text="Backend:", bg=BG, fg=INK, font=(ui, 13)).grid(row=0, column=2, sticky="w")
    backend_var = tk.StringVar(value="offline" if cfg.get("preferred_backend") == "offline" else "auto")
    ttk.Combobox(top, textvariable=backend_var, values=["auto", "claude", "ollama", "offline"], width=9, state="readonly").grid(row=0, column=3, sticky="w", padx=6)
    ttk.Button(top, text="Settings…", command=lambda: settings_dialog()).grid(row=0, column=4, padx=(18, 0))
    status_var = tk.StringVar(value=f"Auto-detected: {backend} — {reason}")
    tk.Label(top, textvariable=status_var, bg=BG, fg=MID, font=(ui, 12), anchor="w", wraplength=1180, justify="left").grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

    # ---- drop zone
    drop = tk.Label(root, text="Drop a .docx or .pdf here, or click to choose a file" + ("" if dnd else "   (drag-and-drop unavailable — click to open)"),
                    relief="solid", bd=1, bg="#F4F6F8", fg=INK, font=(ui, 14), pady=14); drop.pack(fill="x", padx=22, pady=(0, 14))

    # ---- headline tiles
    head = tk.Frame(root, bg=BG, padx=22); head.pack(fill="x")
    for c in range(4): head.grid_columnconfigure(c, weight=1, uniform="tiles")
    def tile(col, bg, fg, sub_fg, label):
        f = tk.Frame(head, bg=bg, padx=12, pady=14, highlightbackground=LINE, highlightthickness=1 if bg == WHITE else 0)
        f.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 8 if col < 3 else 0))
        n = tk.Label(f, text="—", bg=bg, fg=fg, font=(ui, 40, "bold")); n.pack()
        tk.Label(f, text=label, bg=bg, fg=sub_fg, font=(ui, 11)).pack(pady=(6, 0))
        return n
    total_lbl = tile(0, NAVY, WHITE, "#CADCFC", "TOTAL — ten principles")
    four_lbl = tile(1, GOLD, NAVY, NAVY, "FOUR-ITEM — P1 + P4 + P7 + P10")
    dis_lbl = tile(2, WHITE, INK, MID, "DISEASE CENTRALITY")
    rf = tk.Frame(head, bg=PALE, padx=14, pady=12); rf.grid(row=0, column=3, sticky="nsew")
    tk.Label(rf, text="Reading", bg=PALE, fg=NAVY, font=(ui, 13, "bold"), anchor="w").pack(fill="x")
    reading_lbl = tk.Label(rf, text="Drop a statement to score it.", bg=PALE, fg=INK, font=(ui, 11), justify="left", anchor="nw", wraplength=280); reading_lbl.pack(fill="both", expand=True, pady=(4, 0))

    # ---- main area: sub-scores (left) and tabs (right)
    main_area = tk.Frame(root, bg=BG, padx=22, pady=14); main_area.pack(fill="both", expand=True)
    main_area.grid_columnconfigure(0, weight=3); main_area.grid_columnconfigure(1, weight=2); main_area.grid_rowconfigure(0, weight=1)
    left = tk.Frame(main_area, bg=WHITE, highlightbackground=LINE, highlightthickness=1, padx=14, pady=12); left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
    hdr = tk.Frame(left, bg=WHITE); hdr.pack(fill="x")
    tk.Label(hdr, text="Sub-scores (0–2)", bg=WHITE, fg=NAVY, font=(ui, 14, "bold")).pack(side="left")
    tk.Label(hdr, text="gold = the four discriminating principles", bg=WHITE, fg=MID, font=(ui, 11)).pack(side="right")
    lc = tk.Frame(left, bg=WHITE); lc.pack(fill="both", expand=True, pady=(8, 0))
    canvas = tk.Canvas(lc, bg=WHITE, highlightthickness=0, bd=0); vsb = ttk.Scrollbar(lc, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set); vsb.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
    rows_frame = tk.Frame(canvas, bg=WHITE); rows_frame.grid_columnconfigure(1, weight=1)
    rows_win = canvas.create_window((0, 0), window=rows_frame, anchor="nw")
    ev_labels = []
    def on_canvas_resize(e):
        canvas.itemconfigure(rows_win, width=e.width)
        for lbl in ev_labels: lbl.configure(wraplength=max(200, e.width - 90))
    def on_rows_resize(e): canvas.configure(scrollregion=canvas.bbox("all"))
    canvas.bind("<Configure>", on_canvas_resize); rows_frame.bind("<Configure>", on_rows_resize)
    def _wheel(e, target):
        if sys.platform == "darwin": target.yview_scroll(-1 * int(e.delta), "units")
        else: target.yview_scroll(-1 * int(e.delta / 120), "units")
    def bind_wheel(widget, target):
        widget.bind("<Enter>", lambda e: (root.bind_all("<MouseWheel>", lambda ev: _wheel(ev, target)), root.bind_all("<Button-4>", lambda ev: target.yview_scroll(-1, "units")), root.bind_all("<Button-5>", lambda ev: target.yview_scroll(1, "units"))))
        widget.bind("<Leave>", lambda e: (root.unbind_all("<MouseWheel>"), root.unbind_all("<Button-4>"), root.unbind_all("<Button-5>")))
    bind_wheel(canvas, canvas)
    row_widgets = []
    for i, name in enumerate(ss.PRINCIPLES):
        star = i in FOUR_SET; bg = STAR_BG if star else WHITE
        rf_ = tk.Frame(rows_frame, bg=bg); rf_.grid(row=i, column=0, columnspan=2, sticky="ew", pady=1); rf_.grid_columnconfigure(1, weight=1)
        chip = tk.Label(rf_, text="–", bg=GOLD if star else NAVY, fg=WHITE, font=(ui, 14, "bold"), width=3, pady=3); chip.grid(row=0, column=0, rowspan=2, padx=(6, 10), pady=4)
        nm = tk.Label(rf_, text=name, bg=bg, fg=INK, font=(ui, 12, "bold"), anchor="w"); nm.grid(row=0, column=1, sticky="w")
        ev = tk.Label(rf_, text="", bg=bg, fg=MID, font=(ui, 10), anchor="w", justify="left", wraplength=420); ev.grid(row=1, column=1, sticky="w", pady=(0, 4)); ev_labels.append(ev)
        tk.Frame(rows_frame, bg=LINE, height=1).grid(row=i, column=0, columnspan=2, sticky="sew")
        row_widgets.append((chip, ev))

    right = tk.Frame(main_area, bg=WHITE, highlightbackground=LINE, highlightthickness=1, padx=10, pady=10); right.grid(row=0, column=1, sticky="nsew")
    nb = ttk.Notebook(right); nb.pack(fill="both", expand=True)
    def text_tab(title):
        f = tk.Frame(nb, bg=WHITE); nb.add(f, text=title)
        sb = ttk.Scrollbar(f, orient="vertical"); sb.pack(side="right", fill="y")
        t = tk.Text(f, wrap="word", font=(ui, 11), bg=WHITE, fg=INK, relief="flat", padx=8, pady=8, state="disabled", yscrollcommand=sb.set); t.pack(side="left", fill="both", expand=True)
        sb.configure(command=t.yview); bind_wheel(t, t)
        t.tag_configure("h", font=(ui, 13, "bold"), foreground=NAVY, spacing1=8, spacing3=4)
        t.tag_configure("ok", foreground=GREEN); t.tag_configure("warn", foreground="#B45309"); t.tag_configure("mono", font=(mono, 10))
        return t
    checks_txt = text_tab("Checks"); revs_txt = text_tab("Revisions")
    prog_frame = tk.Frame(nb, bg=WHITE); nb.add(prog_frame, text="Progress")
    prog_cols = ("date", "file", "backend", "total", "four", "dis")
    prog = ttk.Treeview(prog_frame, columns=prog_cols, show="headings", height=14)
    for c, w, txt in zip(prog_cols, (90, 170, 70, 50, 50, 40), ("Date", "File", "Backend", "Total", "Four", "Dis")):
        prog.heading(c, text=txt); prog.column(c, width=w, anchor="center" if c not in ("file",) else "w")
    psb = ttk.Scrollbar(prog_frame, orient="vertical", command=prog.yview); prog.configure(yscrollcommand=psb.set)
    psb.pack(side="right", fill="y", pady=4); prog.pack(side="left", fill="both", expand=True, padx=4, pady=4); bind_wheel(prog, prog)
    tk.Label(prog_frame, text="Compare runs made with the same backend; the numbers are not interchangeable across backends.", bg=WHITE, fg=MID, font=(ui, 10), wraplength=400, justify="left").pack(anchor="w", padx=6, pady=(0, 6))

    # ---- bottom buttons
    bottom = tk.Frame(root, bg=BG, padx=22, pady=12); bottom.pack(fill="x")
    ttk.Button(bottom, text="Show progress for this student", command=lambda: (render_progress(), nb.select(2))).pack(side="left")
    ttk.Button(bottom, text="Open history folder", command=lambda: open_folder(CONFIG_DIR)).pack(side="left", padx=8)
    ttk.Button(bottom, text="About / License", command=lambda: __import__("firstrun").show_about(root, cfg, BASE)).pack(side="left", padx=8)
    ttk.Button(bottom, text="Save report…", command=lambda: save_report()).pack(side="right")
    last = {"out": None}

    # ---- helpers
    def set_text(widget, parts):
        widget.configure(state="normal"); widget.delete("1.0", "end")
        for text, tag in parts: widget.insert("end", text, tag) if tag else widget.insert("end", text)
        widget.configure(state="disabled")
    def open_folder(p):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin": os.system(f'open "{p}"')
        elif os.name == "nt": os.startfile(p)  # type: ignore[attr-defined]
        else: os.system(f'xdg-open "{p}"')
    def save_report():
        if not last["out"]: messagebox.showinfo("Nothing to save", "Score a statement first."); return
        p = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")], initialfile=f"{last['out']['student']}_{last['out']['date']}_rubric.txt")
        if p: Path(p).write_text(format_report(last["out"]), encoding="utf-8")
    def render_progress():
        for r in prog.get_children(): prog.delete(r)
        student = (student_var.get() or "unnamed").strip().lower()
        if HISTORY.exists():
            for r in csv.DictReader(HISTORY.open(encoding="utf-8")):
                if r["student"].strip().lower() == student:
                    prog.insert("", "end", values=(r["date"], r["file"][:28], r["backend"], r["total"], r["four_item"], r["disease"]))
    def render(out):
        last["out"] = out; lex = out["lex"]
        total_lbl.configure(text=f"{out['total']} / 20"); four_lbl.configure(text=f"{out['four']} / 8"); dis_lbl.configure(text=f"{out['disease']} / 2")
        reading_lbl.configure(text=ss.band(out["total"], out["four"]) + (f"  Clinical-term density {lex['clinical_terms_per_1000_words']} per 1,000 words (funded references ≤ 4)." if lex["clinical_terms_per_1000_words"] > 4 else ""))
        for (chip, ev), sc, evid in zip(row_widgets, out["scores"], out["evidence"]):
            chip.configure(text=str(sc)); ev.configure(text=(evid or ""))
        parts = [("Mechanical checks\n", "h"),
                 (f"Words {lex['word_count']:,} (~{lex['estimated_pages_12pt']} pages; target 3.0)\n", None),
                 (f"IM heading {'✓' if lex['Intellectual Merit heading'] else '✗ MISSING'}    BI heading {'✓' if lex['Broader Impacts heading'] else '✗ MISSING'}\n", None),
                 (f"Forecasted venues: {', '.join(lex['forecasted_venues']) or 'none'}\n", "warn" if lex["forecasted_venues"] else None),
                 (f"Dollar amounts: {', '.join(lex['dollar_amounts']) or 'none'}\n", "warn" if lex["dollar_amounts"] else None),
                 (f"Aspirational verbs {lex['aspirational_verbs']}    Participation phrasing {lex['participation_phrases']}\n", None),
                 (f"Clinical terms / 1,000 words: {lex['clinical_terms_per_1000_words']}  (funded references ≤ 4)\n", "warn" if lex["clinical_terms_per_1000_words"] > 4 else None),
                 ("\nBackend\n", "h"), (f"{out['backend']}{' (' + out['model'] + ')' if out['model'] else ''}\n", None)]
        if out.get("disease_evidence"): parts += [("\nDisease-centrality evidence\n", "h"), (out["disease_evidence"] + "\n", None)]
        set_text(checks_txt, parts)
        rp = [("Highest-value revisions\n", "h")] + [(f"{i}. {r}\n\n", None) for i, r in enumerate(out.get("revisions", []), 1)]
        rp.append(("Verification\n", "h"))
        flags = out.get("flags", [])
        if out["backend"] == "offline":
            rp.append(("Offline proxies: P4 and P6 are good, P1, P3 and P10 fair; P2, P5, P7, P8, P9 are weak. Use a reader backend for those.\n", "warn"))
        elif not flags:
            rp += [("✓ All evidence quotes found in the statement\n", "ok"), ("✓ P6 confirmed by heading check\n", "ok"), ("✓ No revision recommends disease framing\n", "ok")]
        else:
            for fl in flags: rp.append((("✓ " if "set to 2" in fl or "raised" in fl else "! ") + fl + "\n", "ok" if ("set to 2" in fl or "raised" in fl) else "warn"))
        set_text(revs_txt, rp); render_progress(); nb.select(1)

    def score_file(path_str):
        path = Path(path_str.strip().strip("{}"))
        if path.suffix.lower() not in (".docx", ".pdf", ".txt", ".md"):
            messagebox.showerror("Unsupported file", "Please drop a .docx, .pdf, .txt or .md file."); return
        student = student_var.get().strip() or "unnamed"; cfg["last_student"] = student; save_config(cfg)
        choice = backend_var.get()
        if choice == "auto": b, m, r = detect_backend(cfg)
        else:
            b, r = choice, "manual"
            m = {"claude": cfg.get("claude_model") or ss.DEFAULT_MODEL, "ollama": cfg.get("ollama_model") or (ollama_models(cfg.get("ollama_url", "http://localhost:11434")) or [""])[0], "offline": ""}[choice]
            if b == "claude" and not claude_available(cfg): messagebox.showwarning("No API key", "No Anthropic API key found; add one in Settings or choose another backend."); return
            if b == "ollama" and not m: messagebox.showwarning("Ollama not available", "Ollama is not running or has no models."); return
        set_text(checks_txt, [("Scoring… typically 30–90 seconds with Claude, a few minutes with a local model.\n", None)]); set_text(revs_txt, [("Scoring…\n", None)]); nb.select(0)
        t0 = dt.datetime.now(); running = {"on": True}
        def tick():
            if running["on"]:
                status_var.set(f"Scoring with {b}{' (' + m + ')' if m else ''} … {int((dt.datetime.now() - t0).total_seconds())} s"); root.after(1000, tick)
        tick()
        def work():
            try:
                res = run_scoring(path, student, b, m, cfg); append_history(res); running["on"] = False
                register.record_usage(cfg, statement_type="personal", total=res["total"], four=res["four"], disease=res["disease"],
                                      backend=res["backend"], model=res["model"], words=res["lex"]["word_count"])   # only if the user opted in
                root.after(0, lambda: (render(res), status_var.set(f"Done — {b}{' (' + m + ')' if m else ''} in {int((dt.datetime.now() - t0).total_seconds())} s. Logged to {HISTORY}")))
            except BaseException as e:  # noqa: BLE001
                running["on"] = False; msg = str(e) or type(e).__name__
                root.after(0, lambda: (set_text(checks_txt, [("Error\n", "h"), (msg + "\n\nUse Settings… → Test connections to check the backends.\n", "warn")]), nb.select(0), status_var.set("Error")))
        threading.Thread(target=work, daemon=True).start()

    def choose():
        p = filedialog.askopenfilename(filetypes=[("Statements", "*.docx *.pdf *.txt *.md"), ("All files", "*.*")])
        if p: score_file(p)
    drop.bind("<Button-1>", lambda e: choose())
    if dnd:
        drop.drop_target_register(DND_FILES); drop.dnd_bind("<<Drop>>", lambda e: score_file(e.data.split("} {")[0] if e.data.startswith("{") else e.data.split()[0]))

    def settings_dialog():
        win = tk.Toplevel(root); win.title("Settings"); win.resizable(False, False); frm = ttk.Frame(win, padding=12); frm.pack()
        key_var = tk.StringVar(value=cfg.get("anthropic_api_key", "")); cm_var = tk.StringVar(value=cfg.get("claude_model", ss.DEFAULT_MODEL))
        ou_var = tk.StringVar(value=cfg.get("ollama_url", "http://localhost:11434")); om_var = tk.StringVar(value=cfg.get("ollama_model", "llama3.1:8b"))
        rows = [("Your Anthropic API key (blank = use Ollama/offline):", key_var, True), ("Claude model id:", cm_var, False), ("Ollama URL:", ou_var, False), ("Ollama model:", om_var, False)]
        for i, (lab, var, secret) in enumerate(rows):
            ttk.Label(frm, text=lab).grid(row=i, column=0, sticky="w", pady=3); ttk.Entry(frm, textvariable=var, width=46, show="•" if secret else "").grid(row=i, column=1, pady=3, padx=6)
        ttk.Label(frm, text="The API key is your own (console.anthropic.com) and its usage is billed to you; see About / License → API key setup. With a key, statement text is sent to Anthropic. Ollama and offline keep everything on this computer.", foreground="#666", wraplength=460).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 4))
        test_var = tk.StringVar(value=""); ttk.Label(frm, textvariable=test_var, foreground=NAVY, wraplength=460).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))
        def apply():
            cfg.update(anthropic_api_key=key_var.get().strip(), claude_model=cm_var.get().strip(), ollama_url=ou_var.get().strip(), ollama_model=om_var.get().strip()); save_config(cfg)
            if cfg.get("anthropic_api_key"): os.environ["ANTHROPIC_API_KEY"] = cfg["anthropic_api_key"]
        def run_test():
            apply(); test_var.set("Testing… (up to 20 seconds)")
            cm, ou, om = cfg.get("claude_model") or ss.DEFAULT_MODEL, cfg.get("ollama_url", "http://localhost:11434"), cfg.get("ollama_model") or None
            box = {"msg": None}
            def work():
                okc, mc = ss.test_claude(cm)
                oko, mo = ss.test_ollama(ou, om)
                box["msg"] = ("✓ " if okc else "✗ ") + mc + "\n" + ("✓ " if oko else "✗ ") + mo
            def poll():
                if box["msg"] is not None: test_var.set(box["msg"])
                elif win.winfo_exists(): win.after(200, poll)
            threading.Thread(target=work, daemon=True).start(); win.after(200, poll)
        def ok():
            apply(); b, m, r = detect_backend(cfg); status_var.set(f"Auto-detected: {b} — {r}"); win.destroy()
        ttk.Button(frm, text="Test connections", command=run_test).grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Button(frm, text="Save", command=ok).grid(row=5, column=1, sticky="e", pady=(6, 0))

    missing = []
    for mod, what in (("docx", ".docx reader (python-docx)"), ("pdfplumber", "PDF reader (pdfplumber)")):
        try: __import__(mod)
        except ImportError: missing.append(what)
    intro = [("Ready\n", "h"), (f"Backend auto-detected: {backend} — {reason}.\n\nSet a student name so runs are logged under it, then drop a statement onto the box above or click it to choose a file.\n", None)]
    if missing: intro.append(("\nWARNING: this copy of the app is missing the " + " and ".join(missing) + ". Those file types will not open. Rebuild the app, or pip install the package if running from source.\n", "warn"))
    set_text(checks_txt, intro); set_text(revs_txt, [("Revisions appear here after scoring.\n", None)]); render_progress()
    root.mainloop()

def _launch_log(msg: str) -> None:
    """Append to ~/.grfp_scorer/launch.log (best effort)."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_DIR / "launch.log", "a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} app: {msg}\n")
    except Exception:
        pass

def selftest() -> int:
    """`GRFP Scorer --selftest`: load every bundled dependency and exit. The build scripts run this on the
    finished app, so a library that is present but cannot load is caught at build time, not by a student."""
    import importlib
    bad = 0
    for mod in ("tkinter", "docx", "pdfplumber", "pypdfium2", "cryptography.hazmat.bindings._rust", "anthropic", "certifi", "ssl"):
        try:
            importlib.import_module(mod); print(f"  ok    {mod}")
        except Exception as e:
            bad += 1; print(f"  FAIL  {mod}: {type(e).__name__}: {str(e)[:300]}")
    try:
        import certifi, ssl
        ssl.create_default_context(cafile=certifi.where()); print("  ok    CA certificates load")
    except Exception as e:
        bad += 1; print(f"  FAIL  CA certificates: {e}")
    for fname in ("rubric.md", "LICENSE", "DISCLAIMER.md"):
        if (BASE / fname).exists(): print(f"  ok    {fname} bundled")
        else: bad += 1; print(f"  FAIL  {fname} missing from the bundle (check --add-data in the build script)")
    if "PASTE_DEPLOYMENT_ID" in register.ENDPOINT: print("  warn  register.ENDPOINT is still the placeholder; registrations stay local")
    return bad

if __name__ == "__main__":
    if "--selftest" in sys.argv: sys.exit(1 if selftest() else 0)
    main()
