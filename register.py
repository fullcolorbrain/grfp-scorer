"""
register.py — configuration, first-launch registration, and optional usage counting
for GRFP Scorer.

Copyright 2025-2026 Vincent D. Costa
Licensed under the Apache License, Version 2.0 (see LICENSE).

This module owns the app's config file (~/.grfp_scorer/config.json) and the two
network events the app can send to the author:

    install  — once, after the user accepts the license and fills in the registration
               form: name, email, institution, OS, app version, random install id.
    score    — after each scoring run, ONLY if the user opted in: install id,
               statement type, summary score, app version. Never statement text.

No third-party dependencies. Every network call is best-effort: it never blocks the
UI for long and never crashes the app when offline. A registration that could not be
sent is stored locally and retried silently at the next launch.

ENDPOINT is the "Web app URL" shown after deploying installer/registration-Code.gs as a
Google Apps Script web app. APP_TOKEN is not a secret — this is open-source software,
so anyone can read it — it only stops accidental junk from reaching the sheet. Real
abuse protection is the dedupe-by-install-id and the daily cap in Code.gs.
"""

import json
import os
import platform
import sys
import threading
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

APP_VERSION = "1.1.1"          # keep in sync with CITATION.cff and the installer scripts
LICENSE_VERSION = "2026-10"    # bump when DISCLAIMER.md changes; users re-accept on next launch
ENDPOINT = "https://script.google.com/macros/s/AKfycbwDVrO02TkqP_GWbq1kELeYfCUdxPQpSFC0Sifoy3tzY6H7Z9hkCN6wsv13v31BW1MP1Q/exec"
APP_TOKEN = "grfp-scorer-public"

CONFIG_DIR = Path.home() / ".grfp_scorer"
CONFIG_PATH = CONFIG_DIR / "config.json"


# --------------------------------------------------------------------- config

def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg if isinstance(cfg, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)
    try:
        os.chmod(CONFIG_PATH, 0o600)   # the file also holds the user's API key
    except OSError:
        pass


def needs_registration(cfg: dict) -> bool:
    """True if the user hasn't accepted the current license text or hasn't registered."""
    return (
        cfg.get("license_accepted_version") != LICENSE_VERSION
        or not cfg.get("registered")
    )


def install_id(cfg: dict) -> str:
    if not cfg.get("install_id"):
        cfg["install_id"] = str(uuid.uuid4())
        save_config(cfg)
    return cfg["install_id"]


def registration_configured() -> bool:
    """False while ENDPOINT still holds the placeholder (e.g. running from a fresh clone)."""
    return "PASTE_DEPLOYMENT_ID" not in ENDPOINT


# --------------------------------------------------------------------- network

def _post(payload: dict, timeout: float = 8.0) -> bool:
    """POST JSON to the Apps Script endpoint. Returns True if the sheet accepted it."""
    if not registration_configured():
        return False
    payload = dict(payload, token=APP_TOKEN)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={"Content-Type": "application/json", "User-Agent": f"GRFP-Scorer/{APP_VERSION}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "ignore")
            try:
                return json.loads(body).get("status") == 200
            except (ValueError, AttributeError):
                return resp.status == 200
    except Exception:
        return False


def _post_async(payload: dict) -> None:
    threading.Thread(target=_post, args=(payload,), daemon=True).start()


def _env() -> dict:
    return {
        "os": platform.system(),
        "os_version": platform.release(),
        "arch": platform.machine(),
        "python": sys.version.split()[0],
        "app_version": APP_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------- registration

def accept_license(cfg: dict) -> None:
    """Record acceptance of the current LICENSE + DISCLAIMER text, with a timestamp."""
    cfg["license_accepted_version"] = LICENSE_VERSION
    cfg["license_accepted_at"] = datetime.now(timezone.utc).isoformat()
    save_config(cfg)


def _install_payload(cfg: dict) -> dict:
    return {
        "event": "install",
        "install_id": install_id(cfg),
        "name": cfg.get("name", ""),
        "email": cfg.get("email", ""),
        "institution": cfg.get("institution", ""),
        "usage_opt_in": bool(cfg.get("usage_opt_in", False)),
        **_env(),
    }


def register_install(cfg: dict, name: str, email: str, institution: str,
                     usage_opt_in: bool) -> bool:
    """
    Call once the user has accepted the license and filled in the registration form.
    Stores the registration locally, then posts it. Returns True if the post succeeded.
    The local record is written either way so the user isn't asked again; a failed
    post is retried at later launches by retry_pending().
    """
    cfg.update({
        "registered": True,
        "name": name.strip(),
        "email": email.strip(),
        "institution": institution.strip(),
        "usage_opt_in": bool(usage_opt_in),
    })
    install_id(cfg)
    ok = _post(_install_payload(cfg))
    cfg["registration_sent"] = ok
    save_config(cfg)
    return ok


def retry_pending(cfg: dict) -> None:
    """Call at startup. Re-sends a registration that failed to post earlier (offline install)."""
    if cfg.get("registered") and not cfg.get("registration_sent") and registration_configured():
        payload = _install_payload(cfg)

        def _run():
            if _post(payload):
                cfg["registration_sent"] = True
                save_config(cfg)

        threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------- usage

def record_usage(cfg: dict, statement_type: str = "personal", total=None, four=None,
                 disease=None, backend: str = "", model: str = "", words=None) -> None:
    """
    Call after each scoring run. Sends nothing unless the user opted in at registration.
    Sends only the install id, the statement type, the scores (total, four-item, disease
    flag), which backend/model read it, the word count, and the app version — never
    statement text, file names, or student names.
    """
    if not cfg.get("usage_opt_in"):
        return
    _post_async({
        "event": "score",
        "install_id": install_id(cfg),
        "statement_type": statement_type,
        "backend": backend,
        "model": model,
        "words": words,
        "total": total,
        "four": four,
        "disease": disease,
        **_env(),
    })


# ----------------------------------------------------------------- legal text

def legal_text(base_dir: Path) -> str:
    """LICENSE + DISCLAIMER.md as one plain-text block for the first-run dialog.
    Falls back to a short notice if the files were not bundled."""
    parts = []
    for fname, title in (("DISCLAIMER.md", "DISCLAIMER AND TERMS OF USE"), ("LICENSE", "APACHE LICENSE, VERSION 2.0")):
        p = Path(base_dir) / fname
        try:
            txt = p.read_text(encoding="utf-8")
        except OSError:
            txt = (f"[{fname} was not found next to the application. The current text is at\n"
                   f" https://github.com/fullcolorbrain/grfp-scorer/blob/main/{fname} ]")
        parts.append("=" * 78 + f"\n{title}\n" + "=" * 78 + "\n\n" + txt.strip() + "\n")
    return "\n\n".join(parts)
