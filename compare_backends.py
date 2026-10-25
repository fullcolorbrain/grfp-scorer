#!/usr/bin/env python3
"""
compare_backends.py — score the same statements with the offline heuristic scorer and a local
Ollama model (and optionally the Claude API), and print them side by side with reader scores
and official outcomes if you supply them.

Usage
    python compare_backends.py manifest.csv                       # offline + ollama
    python compare_backends.py manifest.csv --backends offline ollama claude
    python compare_backends.py manifest.csv --model qwen2.5:14b --out comparison.csv

manifest.csv has one row per statement:
    file,label,outcome,reader_P1,...,reader_P10
where file is a path (.docx/.pdf/.txt), label is any short name (use "Applicant A" etc. if
the output will be shared), outcome is awarded / HM / not_listed / unknown, and the reader_
columns are optional 0–2 scores from a human reader. Only "file" and "label" are required.

Output: a table with total and four-item scores per backend, per-item agreement with the
reader where reader scores exist, and AUC (awarded+HM vs not_listed) per backend where at
least two outcomes of each kind are present.
"""
import argparse, csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import score_offline as so                                   # noqa: E402
import score_statement as ss                                 # noqa: E402

FOUR = [0, 3, 6, 9]

def run_offline(text):
    s, D = so.score(so.features(text)); return [s[f"P{i}"] for i in range(1, 11)], D

def run_llm(text, backend, model, url):
    r = ss.llm_score(text, model, backend, url); return [int(r["scores"][f"P{i}"]) for i in range(1, 11)], int(r.get("disease_centrality", -1))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest"); ap.add_argument("--backends", nargs="+", default=["offline", "ollama"], choices=["offline", "ollama", "claude"])
    ap.add_argument("--model", default=None, help="model for ollama/claude (defaults: llama3.1:8b / DEFAULT_MODEL in score_statement.py)")
    ap.add_argument("--ollama-url", default="http://localhost:11434"); ap.add_argument("--out", default=None, help="write the per-item results to this CSV")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.manifest, encoding="utf-8")))
    results = []
    for r in rows:
        text = ss.extract_text(Path(r["file"])); rec = {"label": r["label"], "outcome": r.get("outcome", "unknown")}
        rk = [r.get(f"reader_P{i}") for i in range(1, 11)]
        rec["reader"] = [int(x) for x in rk] if all(x not in (None, "") for x in rk) else None
        for b in a.backends:
            if b == "offline": rec[b] = run_offline(text)
            else:
                model = a.model or (ss.DEFAULT_MODEL if b == "claude" else "llama3.1:8b")
                rec[b] = run_llm(text, b, model, a.ollama_url)
            print(f"  scored {r['label']} with {b}", file=sys.stderr)
        results.append(rec)
    # table
    cols = ["reader"] + a.backends if any(x["reader"] for x in results) else a.backends
    print(f"\n{'label':16s} {'outcome':11s} " + " ".join(f"{c:>18s}" for c in cols)); print("-" * (28 + 19 * len(cols)))
    for x in results:
        cells = []
        for c in cols:
            v = x.get(c); vals = v if c == "reader" else (v[0] if v else None)
            cells.append("—" if not vals else f"{sum(vals):2d}/20  {sum(vals[i] for i in FOUR)}/8")
        print(f"{x['label']:16s} {x['outcome']:11s} " + " ".join(f"{c:>18s}" for c in cells))
    # agreement with reader
    withr = [x for x in results if x["reader"]]
    if withr:
        print("\nAgreement with reader (mean absolute difference on the four-item score; within 1 point):")
        for b in a.backends:
            d = [abs(sum(x["reader"][i] for i in FOUR) - sum(x[b][0][i] for i in FOUR)) for x in withr]
            print(f"  {b:8s} MAD {sum(d)/len(d):.2f}   within1 {sum(v <= 1 for v in d)/len(d):.2f}")
    # AUC
    pos = [x for x in results if x["outcome"] in ("awarded", "HM")]; neg = [x for x in results if x["outcome"] == "not_listed"]
    if len(pos) >= 2 and len(neg) >= 2:
        try:
            from sklearn.metrics import roc_auc_score
            y = [1] * len(pos) + [0] * len(neg); print("\nAUC (awarded+HM vs not_listed), four-item score:")
            for c in cols:
                sc = [sum((x[c] if c == "reader" else x[c][0])[i] for i in FOUR) for x in pos + neg]
                print(f"  {c:8s} {roc_auc_score(y, sc):.2f}")
        except ImportError:
            print("(install scikit-learn for AUC)")
    if a.out:
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["label", "outcome", "backend"] + [f"P{i}" for i in range(1, 11)] + ["total", "four_item", "disease"])
            for x in results:
                if x["reader"]: w.writerow([x["label"], x["outcome"], "reader"] + x["reader"] + [sum(x["reader"]), sum(x["reader"][i] for i in FOUR), ""])
                for b in a.backends: w.writerow([x["label"], x["outcome"], b] + x[b][0] + [sum(x[b][0]), sum(x[b][0][i] for i in FOUR), x[b][1]])
        print(f"\nWrote {a.out}")

if __name__ == "__main__":
    main()
