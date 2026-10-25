"""
firstrun.py — first-launch wizard for GRFP Scorer (Tk).

Copyright 2025-2026 Vincent D. Costa
Licensed under the Apache License, Version 2.0 (see LICENSE).

Three steps, shown once (and again only when DISCLAIMER.md changes):

    1. License and disclaimer — scrollable text, "I have read and accept" checkbox.
    2. Scoring backend — your own Anthropic API key (with a Test button), a local
       Ollama model, or offline mode. Explains cost and privacy of each.
    3. Registration — name, email, institution (required), optional usage ping.

run(root, cfg, base_dir) returns True when the user completed the wizard, False if
they closed it. The app exits on False: no acceptance, no use. The wizard runs inside
root.mainloop() (Tk 8.6 on macOS does not map windows from a nested wait_window loop
before the main loop has started) and ends it with root.quit(), after which the app
builds its main window and enters mainloop() again.
show_about(root, cfg, base_dir) re-displays the license text and registration info.
"""

import sys
import threading
import webbrowser
from pathlib import Path

import register

API_KEY_DOC = "https://github.com/fullcolorbrain/grfp-scorer/blob/main/docs/API_KEY_SETUP.md"
PRIVACY_DOC = "https://github.com/fullcolorbrain/grfp-scorer/blob/main/PRIVACY.md"
OLLAMA_URL = "https://ollama.com/download"

NAVY, INK, MID, BG, WHITE = "#1E2761", "#23272F", "#5B6270", "#ECEEF1", "#FFFFFF"


def _log(msg: str) -> None:
    """Append a line to ~/.grfp_scorer/launch.log (best effort) so a silent failure can be diagnosed."""
    try:
        import datetime
        register.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(register.CONFIG_DIR / "launch.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} firstrun: {msg}\n")
    except Exception:
        pass


def _fonts():
    ui = "Helvetica" if sys.platform == "darwin" else "Segoe UI"
    mono = "Menlo" if sys.platform == "darwin" else "Consolas"
    return ui, mono


def _text_box(parent, content, height=18):
    import tkinter as tk
    from tkinter import ttk
    ui, mono = _fonts()
    f = tk.Frame(parent, bg=WHITE, highlightbackground="#D2D6DC", highlightthickness=1)
    sb = ttk.Scrollbar(f, orient="vertical")
    t = tk.Text(f, wrap="word", font=(mono, 9), bg=WHITE, fg=INK, relief="flat",
                padx=10, pady=8, height=height, yscrollcommand=sb.set)
    t.insert("1.0", content)
    t.configure(state="disabled")
    sb.configure(command=t.yview)
    sb.pack(side="right", fill="y")
    t.pack(side="left", fill="both", expand=True)
    return f


def run(root, cfg: dict, base_dir: Path) -> bool:
    """Show the wizard modally. Returns True if completed, False if the user closed it."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    ui, mono = _fonts()
    done = {"ok": False}

    win = tk.Toplevel(root)
    win.title("GRFP Scorer — first launch")
    win.configure(bg=BG)
    win.geometry("760x640")
    win.minsize(680, 560)
    # Not transient: with Tk 8.6 on macOS a transient of a not-yet-mapped master never appears.
    win.lift()
    win.attributes("-topmost", True)
    win.after(500, lambda: win.attributes("-topmost", False))
    win.focus_force()
    def _grab():
        try: win.grab_set()
        except tk.TclError: pass
    win.after(200, _grab)

    # Background threads must not touch Tk (RuntimeError: main thread is not in main loop
    # while wait_window is running). They put a callable on this queue; the UI thread polls it.
    import queue
    results = queue.Queue()
    def _poll():
        try:
            while True: results.get_nowait()()
        except queue.Empty: pass
        if win.winfo_exists(): win.after(100, _poll)
    win.after(100, _poll)

    header = tk.Frame(win, bg=NAVY, padx=22, pady=14)
    header.pack(fill="x")
    title_var = tk.StringVar()
    tk.Label(header, textvariable=title_var, bg=NAVY, fg=WHITE, font=(ui, 16, "bold"), anchor="w").pack(fill="x")
    step_var = tk.StringVar()
    tk.Label(header, textvariable=step_var, bg=NAVY, fg="#CADCFC", font=(ui, 11), anchor="w").pack(fill="x")

    body = tk.Frame(win, bg=BG, padx=22, pady=14)
    body.pack(fill="both", expand=True)

    footer = tk.Frame(win, bg=BG, padx=22, pady=12)
    footer.pack(fill="x")
    back_btn = ttk.Button(footer, text="Back")
    next_btn = ttk.Button(footer, text="Next")
    back_btn.pack(side="left")
    next_btn.pack(side="right")
    status_var = tk.StringVar(value="")
    tk.Label(footer, textvariable=status_var, bg=BG, fg=MID, font=(ui, 10), wraplength=440, justify="left").pack(side="right", padx=(0, 14))

    steps = []
    current = {"i": 0}

    # ------------------------------------------------------------ step 1: license
    s1 = tk.Frame(body, bg=BG)
    tk.Label(s1, text="Please read the terms below. The scores this tool produces describe how closely a draft "
                      "matches a writing rubric. They are not predictions of fellowship outcomes, and the software "
                      "is provided without warranty of any kind.",
             bg=BG, fg=INK, font=(ui, 11), wraplength=700, justify="left").pack(anchor="w", pady=(0, 8))
    _text_box(s1, register.legal_text(base_dir)).pack(fill="both", expand=True)
    accept_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(s1, text="I have read and accept the Disclaimer and Terms of Use and the Apache License 2.0",
                    variable=accept_var).pack(anchor="w", pady=(10, 0))

    # ------------------------------------------------------------ step 2: backend
    s2 = tk.Frame(body, bg=BG)
    tk.Label(s2, text="How should statements be read?", bg=BG, fg=INK, font=(ui, 12, "bold")).pack(anchor="w")
    backend_var = tk.StringVar(value="claude" if cfg.get("anthropic_api_key") else "")
    key_var = tk.StringVar(value=cfg.get("anthropic_api_key", ""))

    def option(value, title, lines):
        f = tk.Frame(s2, bg=WHITE, highlightbackground="#D2D6DC", highlightthickness=1, padx=12, pady=10)
        f.pack(fill="x", pady=(8, 0))
        ttk.Radiobutton(f, text=title, value=value, variable=backend_var).pack(anchor="w")
        tk.Label(f, text=lines, bg=WHITE, fg=MID, font=(ui, 10), wraplength=660, justify="left").pack(anchor="w", padx=(22, 0))
        return f

    f_claude = option("claude", "Claude API — best reading (recommended)",
                      "Uses YOUR OWN Anthropic API key, which you create and pay for. A scoring run is roughly "
                      "9,000 tokens; set a monthly spend limit on your account. Your statement text is sent to "
                      "Anthropic under your key — never to the author of this tool.")
    kf = tk.Frame(f_claude, bg=WHITE)
    kf.pack(fill="x", padx=(22, 0), pady=(6, 0))
    tk.Label(kf, text="API key:", bg=WHITE, fg=INK, font=(ui, 10)).pack(side="left")
    key_entry = ttk.Entry(kf, textvariable=key_var, width=44, show="•")
    key_entry.pack(side="left", padx=6)
    key_test_var = tk.StringVar(value="")

    def test_key():
        k = key_var.get().strip()
        if not k:
            key_test_var.set("Enter a key first."); return
        key_test_var.set("Testing… (up to 20 s)")
        import os
        os.environ["ANTHROPIC_API_KEY"] = k
        model = cfg.get("claude_model")   # read Tk/config state here, on the UI thread

        def work():
            try:
                import score_statement as ss
                ok, msg = ss.test_claude(model or ss.DEFAULT_MODEL)
            except Exception as e:  # noqa: BLE001
                ok, msg = False, str(e)
            results.put(lambda: key_test_var.set(("✓ " if ok else "✗ ") + msg))
        threading.Thread(target=work, daemon=True).start()

    ttk.Button(kf, text="Test", command=test_key).pack(side="left")
    tk.Label(f_claude, textvariable=key_test_var, bg=WHITE, fg=NAVY, font=(ui, 10), wraplength=640, justify="left").pack(anchor="w", padx=(22, 0))
    link = tk.Label(f_claude, text="How to create a key and set a spend limit (opens in browser)", bg=WHITE, fg="#1A56DB", font=(ui, 10, "underline"), cursor="hand2")
    link.pack(anchor="w", padx=(22, 0), pady=(4, 0))
    link.bind("<Button-1>", lambda e: webbrowser.open(API_KEY_DOC))

    option("ollama", "Local model via Ollama — free, nothing leaves your computer",
           "Install Ollama (ollama.com) and pull a model, e.g.  ollama pull qwen2.5:14b  (needs ~16 GB RAM; "
           "llama3.1:8b for 8 GB). Slower and about a point lower on judgement items than Claude. "
           "The app detects a running Ollama automatically.")
    option("offline", "Offline checks only — no model",
           "Mechanical checks and lexical proxies. Good for length, headings, and forbidden content; "
           "weak for the judgement items. Always available as a fallback.")
    tk.Label(s2, text="You can change this later under Settings…", bg=BG, fg=MID, font=(ui, 10)).pack(anchor="w", pady=(10, 0))

    # ------------------------------------------------------------ step 3: register
    s3 = tk.Frame(body, bg=BG)
    tk.Label(s3, text="Register this copy", bg=BG, fg=INK, font=(ui, 12, "bold")).pack(anchor="w")
    tk.Label(s3, text="The tool is free. In return, the author asks who is using it, so that the number of users and "
                      "institutions can be counted. Your statement text is never sent to the author.",
             bg=BG, fg=INK, font=(ui, 11), wraplength=700, justify="left").pack(anchor="w", pady=(4, 10))
    form = tk.Frame(s3, bg=BG)
    form.pack(anchor="w")
    name_var = tk.StringVar(value=cfg.get("name", ""))
    email_var = tk.StringVar(value=cfg.get("email", ""))
    inst_var = tk.StringVar(value=cfg.get("institution", ""))
    for i, (lab, var) in enumerate((("Name", name_var), ("Email", email_var), ("Institution / university", inst_var))):
        tk.Label(form, text=lab + ":", bg=BG, fg=INK, font=(ui, 11)).grid(row=i, column=0, sticky="e", pady=4, padx=(0, 8))
        ttk.Entry(form, textvariable=var, width=46).grid(row=i, column=1, sticky="w", pady=4)
    optin_var = tk.BooleanVar(value=bool(cfg.get("usage_opt_in", False)))
    ttk.Checkbutton(s3, text="Also send an anonymous record after each scoring run (installation id, statement type, "
                             "scores, backend used, word count — never any text). Optional; helps the author report how the tool is used.",
                    variable=optin_var).pack(anchor="w", pady=(12, 0))
    plink = tk.Label(s3, text="Privacy notice (opens in browser)", bg=BG, fg="#1A56DB", font=(ui, 10, "underline"), cursor="hand2")
    plink.pack(anchor="w", pady=(8, 0))
    plink.bind("<Button-1>", lambda e: webbrowser.open(PRIVACY_DOC))

    steps = [("License and terms", s1), ("Scoring backend", s2), ("Registration", s3)]

    # ------------------------------------------------------------ navigation
    def show(i):
        for _, fr in steps:
            fr.pack_forget()
        current["i"] = i
        name, fr = steps[i]
        fr.pack(fill="both", expand=True)
        title_var.set(name)
        step_var.set(f"Step {i + 1} of {len(steps)}")
        back_btn.configure(state="normal" if i > 0 else "disabled")
        next_btn.configure(text="Finish" if i == len(steps) - 1 else "Next")
        status_var.set("")

    def validate_and_advance():
        i = current["i"]
        if i == 0:
            if not accept_var.get():
                status_var.set("Tick the box to accept the terms, or close this window to quit."); return
            register.accept_license(cfg)
        elif i == 1:
            b = backend_var.get()
            if not b:
                status_var.set("Choose one of the three options."); return
            if b == "claude":
                k = key_var.get().strip()
                if not k:
                    status_var.set("Enter your API key, or choose Ollama or offline."); return
                cfg["anthropic_api_key"] = k
                import os
                os.environ["ANTHROPIC_API_KEY"] = k
            else:
                cfg["anthropic_api_key"] = ""
            cfg["preferred_backend"] = b
            register.save_config(cfg)
        elif i == 2:
            n, e, ins = name_var.get().strip(), email_var.get().strip(), inst_var.get().strip()
            if not n or not ins or "@" not in e or "." not in e.split("@")[-1]:
                status_var.set("Name, a valid email address, and institution are required."); return
            next_btn.configure(state="disabled"); back_btn.configure(state="disabled")
            status_var.set("Registering…")
            opt_in = optin_var.get()   # read on the UI thread; the worker must not touch Tk

            def work():
                ok = register.register_install(cfg, n, e, ins, opt_in)
                def finish():
                    if not ok and register.registration_configured():
                        status_var.set("Could not reach the registration service; saved locally and will retry later.")
                    done["ok"] = True
                    win.after(600 if not ok else 0, close_wizard)
                results.put(finish)
            threading.Thread(target=work, daemon=True).start()
            return
        show(i + 1)

    next_btn.configure(command=validate_and_advance)
    back_btn.configure(command=lambda: show(max(0, current["i"] - 1)))

    def close_wizard():
        try: win.grab_release()
        except tk.TclError: pass
        win.destroy()
        root.quit()          # ends the mainloop started below; run() then returns

    def on_close():
        if messagebox.askyesno("Quit GRFP Scorer?", "The app cannot be used until the terms are accepted and the copy is registered. Quit?", parent=win):
            close_wizard()
    win.protocol("WM_DELETE_WINDOW", on_close)

    show(0)
    _log("wizard shown")
    root.mainloop()      # returns when close_wizard() calls root.quit()
    _log(f"wizard finished ok={done['ok']}")
    return done["ok"]


def show_about(root, cfg: dict, base_dir: Path):
    """About box: version, registration summary, and the full license/disclaimer text."""
    import tkinter as tk
    from tkinter import ttk
    ui, mono = _fonts()
    win = tk.Toplevel(root)
    win.title("About GRFP Scorer")
    win.configure(bg=BG)
    win.geometry("720x600")
    win.lift(); win.focus_force()
    top = tk.Frame(win, bg=BG, padx=22, pady=14)
    top.pack(fill="x")
    tk.Label(top, text=f"GRFP Scorer {register.APP_VERSION}", bg=BG, fg=NAVY, font=(ui, 16, "bold")).pack(anchor="w")
    reg = f"Registered to {cfg.get('name', '—')} ({cfg.get('email', '—')}), {cfg.get('institution', '—')}." if cfg.get("registered") else "Not registered."
    acc = f"Terms (version {cfg.get('license_accepted_version', '—')}) accepted {str(cfg.get('license_accepted_at', '—'))[:10]}."
    opt = "Usage counting: on." if cfg.get("usage_opt_in") else "Usage counting: off."
    tk.Label(top, text="\n".join([reg, acc, opt, "Copyright 2025-2026 Vincent D. Costa. Apache License 2.0. Not affiliated with NSF or Emory University."]),
             bg=BG, fg=INK, font=(ui, 10), justify="left", wraplength=680).pack(anchor="w", pady=(6, 0))
    links = tk.Frame(top, bg=BG)
    links.pack(anchor="w", pady=(6, 0))
    for text, url in (("Project page", "https://github.com/fullcolorbrain/grfp-scorer"), ("Privacy notice", PRIVACY_DOC), ("API key setup", API_KEY_DOC)):
        l = tk.Label(links, text=text, bg=BG, fg="#1A56DB", font=(ui, 10, "underline"), cursor="hand2")
        l.pack(side="left", padx=(0, 14))
        l.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
    body = tk.Frame(win, bg=BG, padx=22)
    body.pack(fill="both", expand=True, pady=(0, 14))
    _text_box(body, register.legal_text(base_dir), height=20).pack(fill="both", expand=True)
    ttk.Button(body, text="Close", command=win.destroy).pack(anchor="e", pady=(10, 0))
