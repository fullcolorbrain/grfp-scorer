# Calibration data

`hand_scores_and_features.csv` — one row per calibration statement, anonymised with sequential IDs.
Columns: corpus, official outcome where known (awarded / HM / not_listed / funded_or_HM /
unknown), the ten reader-assigned sub-scores P1–P10, total, four-item score, and the
feature counts computed by `score_offline.py` (prefixed `feat_`). No statement text or
names are included, and the word count is rounded to the nearest 100 so that no row can be
matched to an individual statement.

Uses:
- Recalibrate the offline thresholds if you add more hand-scored statements
  (`score_offline.py --calibrate` expects a directory of `.txt` files plus `hand.json`;
  the scores here can seed that file).
- Check a future run of `score_statement.py` against the reader baseline: score the same
  drafts and compare sub-scores; agreement within one point on the four-item score is the
  expectation.
- Reproduce the AUC figures in the report from the neuroscience rows.
