#!/usr/bin/env python3
"""Verify 1.2 as accuracy: how correct is what the user accepts WITHOUT a warning when the server cheats.

    python3 old/plot_accuracy.py --results ../new_result --out <folder>

Per run of the tamper suite (the server changes t of the ~2,000 results r):
  * the check fails (detected_runs)            -> the user is warned and accepts nothing wrong silently: 100 %
  * not detected, but the final result is right
    (Du filters injected files: result_ok_runs) -> 100 %
  * not detected and wrong                     -> what the user silently accepts:
        hide t          recall    = (r - t) / r          (matching files the user got)
        inject t        precision = r / (r + t)          (accepted files that really match)
        modify / old t  precision = (r - t) / r          (accepted files with the right content)
Chen [40] returns no files, so modify / old_version are N/A for it. Value = mean over runs, median over the 4 domains.
Writes accuracy_<kind>.png/.pdf and accuracy_summary.csv.
"""
import argparse
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # baselines/ (this script now lives in baselines/old/)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "old"))
from plot_results import NAME, STYLE, load, paper_fig, paper_finish, paper_line, rq_axis  # noqa: E402

KINDS = {"hide": ("Server hides t files", "Recall of the accepted result (%)"),
         "inject": ("Server injects t files", "Precision of the accepted result (%)"),
         "modify": ("Server modifies t files", "Precision of the accepted result (%)"),
         "old_version": ("Server returns old versions of t files", "Precision of the accepted result (%)")}


def silent_value(kind, r, t):
    if kind == "hide":
        return (r - t) / r
    if kind == "inject":
        return r / (r + t)
    return (r - t) / r


def row_value(row):
    """accuracy (0..1) of what the user accepts without a warning, averaged over the runs of this row"""
    if row.get("status") != "ok" or row.get("runs") in (None, ""):
        return None
    runs = int(row["runs"])
    det = int(row["detected_runs"] or 0)
    ok_runs = int(row["result_ok_runs"]) if row.get("result_ok_runs") not in (None, "") else 0
    good = min(runs, max(det, ok_runs))           # warned, or silently but correct
    bad = runs - good
    r, t = int(row["rQ"]), int(row["tampered"])
    return (good + bad * silent_value(row["tamper"], r, t)) / runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--note", default="AWS r7i.4xlarge")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    summary = []
    letter = iter("abcdefgh")
    for kind, (title, ylabel) in KINDS.items():
        fig, ax = paper_fig()
        ts_all = set()
        perfect = []
        for s in ("secollab", "du", "chen", "amtp"):          # AMTP last, so it is drawn on top
            rows = load(s, "tamper_detection", a.results) or []
            rows = [x for x in rows if x["tamper"] == kind and x.get("check_mode", "early") in ("early", "")]
            by_t = {}
            for x in rows:
                v = row_value(x)
                if v is not None:
                    by_t.setdefault(int(x["tampered"]), []).append(v)
            pts = sorted((t, 100 * statistics.median(v)) for t, v in by_t.items())
            for t, v in pts:
                summary.append({"scheme": NAME[s], "tamper": kind, "t": t, "accuracy_pct": round(v, 3),
                                "metric": "recall" if kind == "hide" else "precision"})
            if not pts:
                summary.append({"scheme": NAME[s], "tamper": kind, "t": "", "accuracy_pct": "N/A",
                                "metric": "files not returned"})
                continue
            ts_all |= {t for t, _ in pts}
            if all(v >= 99.9995 for _, v in pts):
                perfect.append(NAME[s])
            color, marker = STYLE[s]
            paper_line(ax, [p[0] for p in pts], [p[1] for p in pts], [0.0] * len(pts), color, marker, NAME[s])
        rq_axis(ax, sorted(ts_all))
        ax.set_ylim(-5, 105)
        if len(perfect) > 1:
            ax.text(0.02, 0.08, "100 % at every t (lines on top of each other): " + ", ".join(reversed(perfect)),
                    transform=ax.transAxes, fontsize=9, color=STYLE["amtp"][0])
        note = ("dataset-v4 (arXiv) · one keyword with ~2,000 results per domain (tamper_sets.jsonl), D1–D4 · "
                "accuracy of what the user accepts without a warning: a detected run counts 100 % · "
                f"mean over 30 runs, median over domains · Chen [40] returns no files (modify / old: N/A) · {a.note}")
        paper_finish(fig, ax, next(letter), f"Verify 1.2 · accuracy under a cheating server\n{title}",
                     "Tampered files t", ylabel, note, os.path.join(a.out, f"accuracy_{kind}"), ncol=4)
    with open(os.path.join(a.out, "accuracy_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["scheme", "tamper", "metric", "t", "accuracy_pct"])
        w.writeheader()
        w.writerows(summary)


if __name__ == "__main__":
    main()
