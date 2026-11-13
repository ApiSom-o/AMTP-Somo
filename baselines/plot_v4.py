"""
plot_v4.py
============================================================================
Figures for the advisor's plan on dataset-v4: the suites of scripts/aws_run_all.sh
(search1, verify1, tamper, xsearch, xverify, xdomains) and the split / merge runs of bench.ablation
(results/amtp/splitmerge_*/). Same colours, markers and layout as the compare_* figures of plot_results.py.

  python3 plot_v4.py                                   # every figure whose CSVs exist -> results/figures_v4/
  python3 plot_v4.py --results <dir> --out <dir> --note "AWS r7i.4xlarge"

Each point = median over the queries (or keywords) of that point, where each query's value is already the median of
--reps runs (<metric>_ms_median). Error bars = 25th-75th percentile across those queries (a point with one query:
+-1 std over its runs). Every plotted number is also written to <out>/figure_points.csv, and the tamper outcome
to <out>/tamper_summary.csv, so the text of the paper can quote the numbers from a file.
Verify 1.2 draws, as the plan asks, one figure (x = modified files t) and one detected / not-detected table;
--tamper-detail adds the hide / inject / old_version figures and the 4 x 4 detection matrix.
============================================================================
"""

import argparse
import csv
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from plot_results import (AXIS, EXP4_STYLE, INK, INK2, KB, NAME, STYLE, SURFACE, load, new_fig,  # noqa: E402
                          ok, paper_fig, paper_finish, paper_line, plt, rq_axis)

SCHEMES = ["amtp", "chen", "du", "secollab"]
KINDS = ["modify", "hide", "inject", "old_version"]
KIND_LABEL = {"modify": "modified files", "hide": "hidden files", "inject": "injected files",
              "old_version": "old versions of files"}
SHAPE_LABEL = {"AND": "A ∧ B ∧ …", "OR": "A ∨ B ∨ …", "AND_of_OR": "(A ∨ B) ∧ (C ∨ D) …",
               "OR_of_AND": "(A ∧ B) ∨ (C ∧ D) …"}
POINTS = []                                        # rows of figure_points.csv


# ============================================================================
# helpers
# ============================================================================
def agg(rows, keys, metric, scale=1.0):
    """{key tuple: (median, (down, up), n_queries)} of `metric` over the rows of each key.
    Bars: 25th-75th percentile across the queries; one query -> +-1 std over its runs (timings only)."""
    groups = {}
    for r in ok(rows):
        if r.get(metric) in (None, ""):
            continue
        groups.setdefault(tuple(r[k] for k in keys), []).append(r)
    out = {}
    for k, g in groups.items():
        xs = [float(r[metric]) / scale for r in g]
        m = statistics.median(xs)
        if len(xs) > 1:
            q1, _, q3 = statistics.quantiles(xs, n=4, method="inclusive")
            e = (m - q1, q3 - m)
        else:
            std = g[0].get(metric.replace("_ms_median", "_ms_std")) if metric.endswith("_ms_median") else None
            e = float(std) / scale if std not in (None, "") else 0.0
        out[k] = (m, e, len(xs))
    return out


def series(ax, fig, scheme, pts, label=None, variant=False, ls=None, style=None):
    """pts = [(x, y, err)]; draws one line in the scheme's colour and records it in figure_points.csv"""
    if not pts:
        return False
    pts = sorted(pts, key=lambda p: p[0])
    color, marker = style or STYLE[scheme]
    label = label or NAME[scheme]
    paper_line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], color,
               "x" if variant else marker, label, ls or ("--" if variant else "-"))
    for x, y, e in pts:
        lo, hi = e if isinstance(e, tuple) else (e, e)
        POINTS.append({"figure": fig, "series": label, "x": x, "y": round(y, 6),
                       "err_down": round(lo, 6), "err_up": round(hi, 6)})
    return True


def pick(values, want):
    """`want` if present, else the largest value"""
    values = sorted(values)
    return want if want in values else values[-1]


def note_of(a, setting):
    return (f"dataset-v4 (arXiv) · {setting} · median over queries (each: median of {a.reps} runs), "
            f"bars: 25th–75th percentile across queries · {a.note}")


# the advisor's plan: item -> (folder under --out, heading on every figure of that item)
PLAN = {
    "S1.1": ("Search_1.1_single_domain_vary_keywords", "Search 1.1 · single domain · vary keywords"),
    "S1.2": ("Search_1.2_single_domain_vary_files", "Search 1.2 · single domain · vary files"),
    "V1.1": ("Verify_1.1_single_domain_vary_results", "Verify 1.1 · single domain · vary returned files"),
    "V1.2": ("Verify_1.2_single_domain_vary_tampered", "Verify 1.2 · single domain · vary tampered files"),
    "S2.1": ("Search_2.1_multi_domain_boolean", "Search 2.1 · multi-domain · Boolean AND / OR"),
    "V2.1": ("Verify_2.1_multi_domain_vary_results", "Verify 2.1 · multi-domain · vary returned files"),
    "S2.2": ("Search_2.2_multi_domain_vary_domains", "Search 2.2 · multi-domain · vary domains"),
    "V2.2": ("Verify_2.2_multi_domain_vary_domains", "Verify 2.2 · multi-domain · vary domains"),
    "SM": ("Split_merge", "Split / merge"),
    "UPD": ("Update", "Update · insert / delete batches"),
    "TH": ("Theta", "θ sweep · partition size θ_max"),
    "SB": ("Boolean_single_domain", "Boolean search · single domain"),
    "SELF": ("way3_ourself", "AMTP vs itself"),
}
# --by-experiment: one folder per experiment; ex1_search is split into normal / boolean / multi-domain / self
EXPERIMENT = {"S1.1": "ex1_search/normal_search", "S1.2": "ex1_search/normal_search",
              "S2.1": "ex1_search/multi_domain", "S2.2": "ex1_search/multi_domain",
              "SB": "ex1_search/boolean_search", "SELF": "ex1_search/way3_ourself",
              "V1.1": "ex2_verify", "V1.2": "ex2_verify", "V2.1": "ex2_verify", "V2.2": "ex2_verify",
              "UPD": "ex3_update", "TH": "ex4_theta", "SM": "ex5_split_merge"}
BY_EXPERIMENT = False
# --search-metric: what the Search figures plot (Verify figures always plot the user's verification)
SEARCH_METRICS = {"end_to_end": ("end_to_end", "End-to-end search time"),
                  "server": ("server_total", "Server search time (search + proof)")}
SEARCH_COL = SEARCH_METRICS["end_to_end"]
_LETTER = {}


def plan_dir(out, plan):
    if BY_EXPERIMENT:
        ex = EXPERIMENT[plan]
        sub = plan in ("S1.1", "S1.2", "S2.1", "S2.2", "V1.1", "V1.2", "V2.1", "V2.2")
        path = os.path.join(out, ex, PLAN[plan][0]) if sub else os.path.join(out, ex)
    else:
        path = os.path.join(out, PLAN[plan][0])
    os.makedirs(path, exist_ok=True)
    return path


def done(fig, ax, plan, sub, xlabel, ylabel, note, out, name, log_y=True):
    """save into <out>/<plan folder>/<name>; title = plan heading + what this figure shows; panels lettered per item"""
    if log_y:
        ax.set_yscale("log")
    _LETTER[plan] = _LETTER.get(plan, 0) + 1
    paper_finish(fig, ax, "abcdefghijklmnopqrstuvwxyz"[_LETTER[plan] - 1], f"{PLAN[plan][1]}\n{sub}", xlabel, ylabel,
                 note, os.path.join(plan_dir(out, plan), name))


# ============================================================================
# Search 1.1 / 1.2 (search1): single domain, x = kQ or files per domain
# ============================================================================
def figs_search1(data, a, out):
    ns = {int(r["N"]) for rows in data.values() for r in ok(rows)}
    kqs = {int(r["kQ"]) for rows in data.values() for r in ok(rows)}
    if not ns:
        return
    n_fix, kq = pick(ns, a.fix), pick(kqs, a.kq)
    for metric, ylabel, name in ((f"{SEARCH_COL[0]}_ms_median", f"{SEARCH_COL[1]} (ms)", "time"),
                                 ("verify_total_ms_median", "User verification time (ms)", "verify")):
        fig, ax = paper_fig()
        for s, rows in data.items():
            pts = agg([r for r in rows if int(r["N"]) == n_fix], ["kQ"], metric)
            series(ax, f"search1_{name}_vs_kQ", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
        rq_axis(ax, sorted(kqs))
        what = {"verify": "User verification", "time": SEARCH_COL[1]}[name]
        done(fig, ax, "S1.1", f"{what} vs $k_Q$ ({n_fix:,} files)",
             "Keywords in the AND query $k_Q$", ylabel,
             note_of(a, f"one domain, {n_fix:,} files, AND queries (queries_search_single.jsonl)"),
             out, f"{name}_vs_kQ")
        fig, ax = paper_fig()
        for s, rows in data.items():
            pts = agg([r for r in rows if int(r["kQ"]) == kq], ["N"], metric)
            series(ax, f"search1_{name}_vs_N", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
        rq_axis(ax, sorted(ns))
        done(fig, ax, "S1.2", f"{what} vs files ($k_Q$ = {kq})",
             "Files in the domain", ylabel,
             note_of(a, f"one domain, AND queries with k_Q = {kq} (queries_search_single.jsonl)"),
             out, f"{name}_vs_files")
    fig, ax = paper_fig()
    for s, rows in data.items():
        pts = agg([r for r in rows if int(r["N"]) == n_fix], ["kQ"], "response_bytes", KB)
        series(ax, "search1_response_vs_kQ", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
    rq_axis(ax, sorted(kqs))
    done(fig, ax, "S1.1", f"data returned vs $k_Q$ ({n_fix:,} files)", "Keywords in the AND query $k_Q$",
         "Response size (KB, 1 KB = 1000 B)", note_of(a, f"one domain, {n_fix:,} files; results + proof"),
         out, "response_vs_kQ")


# ============================================================================
# Verify 1.1 (verify1) and Verify 2.1 (xverify): x = target result size
# ============================================================================
def figs_verify(data, a, out, multi):
    ncol = "N_per_domain" if multi else "N"
    ns = {int(r[ncol]) for rows in data.values() for r in ok(rows)}
    if not ns:
        return
    n_fix = pick(ns, a.fix)
    tag, title = ("xverify", "Verify 2.1") if multi else ("verify1", "Verify 1.1")
    where = f"4 domains, {n_fix:,} files each, keywords found in every domain" if multi else \
        f"one domain, {n_fix:,} files, real keywords"
    # x = the real result size: the median r_Q of the keywords in each target group. The targets are not
    # always reachable (in one domain the largest keywords return ~2,000-5,000 files, not 10,000), so plotting
    # at the target would place a point at a result size that was never measured.
    by_target = {}
    for rows in data.values():
        for r in ok(rows):
            if int(r[ncol]) == n_fix and r.get("rQ") not in (None, ""):
                by_target.setdefault(int(r["target_results"]), []).append(int(r["rQ"]))
    real_rq = {t: statistics.median(v) for t, v in by_target.items()}
    targets = sorted(real_rq.values())
    for metric, ylabel, name, scale in (("verify_total_ms_median", "User verification time (ms)", "verify", 1.0),
                                        ("end_to_end_ms_median", "End-to-end search time (ms)", "time", 1.0),
                                        ("response_bytes", "Response size (KB, 1 KB = 1000 B)", "response", KB)):
        fig, ax = paper_fig()
        for s, rows in data.items():
            rows = [r for r in rows if int(r[ncol]) == n_fix]
            modes = sorted({r.get("proof_mode", "") for r in rows})
            for mode in modes:
                pts = agg([r for r in rows if r.get("proof_mode", "") == mode], ["target_results"], metric, scale)
                label = NAME[s] + (f" ({'multiproof' if mode == 'multi' else 'per-path'})" if len(modes) > 1 else "")
                series(ax, f"{tag}_{name}_vs_rQ", s,
                       [(real_rq[int(k[0])], m, e) for k, (m, e, _) in pts.items()], label,
                       variant=len(modes) > 1 and mode == "multi")
        rq_axis(ax, targets)
        what = {"verify": "User verification", "time": "End-to-end search time", "response": "Data returned"}[name]
        done(fig, ax, "V2.1" if multi else "V1.1", f"{what} vs returned files",
             "Result size $r_Q$ (median of the real result sizes per group)", ylabel,
             note_of(a, f"{where}, 5 keywords per target{'' if multi else ' and domain'} (verify_keywords.csv)")
             .replace("across queries", "across keywords"), out, f"{name}_vs_rQ")


# ============================================================================
# Verify 1.2 (tamper)
# ============================================================================
def tamper_rows(data):
    """[(scheme, check, label, variant, rows)]: AMTP early + full check, SE-COLLAB early + full, Chen, Du"""
    out = []
    for s, rows in data.items():
        if s == "amtp":
            out.append((s, "early", "AMTP", False, rows, "verify_total"))
            out.append((s, "full", "AMTP: full check", True, rows, "full_check"))
        elif s == "secollab":
            out.append((s, "early", "SE-COLLAB [37]", False,
                        [r for r in rows if r.get("check_mode", "early") == "early"], "verify_total"))
            full = [r for r in rows if r.get("check_mode") == "full"]
            if full:
                out.append((s, "full", "SE-COLLAB [37]: per-path", True, full, "verify_total"))
        else:
            out.append((s, "early", NAME[s], False, rows, "verify_total"))
    return out


def figs_tamper(data, a, out):
    """Verify 1.2 as the advisor's plan asks: "t files are modified, what happens".
    Default: ONE figure (x = modified files t, y = normal user verification time, 4 schemes) and ONE small table
    (detected or not, can the user name the wrong files). --tamper-detail also draws the hide / inject /
    old_version figures and the 4 x 4 detection matrix. tamper_summary.csv always keeps every kind and t."""
    sets = tamper_rows(data)
    summary = []
    for s, check, label, variant, rows, metric in sets:          # full outcome table: every (scheme, check, kind, t)
        for r in rows:
            row = {"scheme": NAME[s], "check": check, "domain": r["domain"], "tamper": r["tamper"],
                   "tampered": int(r["tampered"]), "status": r["status"]}
            if r["status"] == "ok":
                row.update(detected_runs=int(r["detected_runs"]), runs=int(r["runs"]),
                           # AMTP's normal verification stops at the first fault; its row's localized is the full check's
                           localized="" if (s == "amtp" and check == "early") else r.get("localized", ""), result_ok_runs=r.get("result_ok_runs", ""),
                           failed_check=r.get("failed_check", "") if check == "early" else "",
                           time_ms=round(float(r[f"{metric}_ms_median"]), 4))
            summary.append(row)
    if not summary:
        return
    cols = ["scheme", "check", "domain", "tamper", "tampered", "status", "detected_runs", "runs", "localized",
            "result_ok_runs", "failed_check", "time_ms"]
    with open(os.path.join(plan_dir(out, "V1.2"), "tamper_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(summary)
    fig_modify(data, sets, summary, a, out)
    figs_security(summary, a, plan_dir(out, "V1.2"))
    if a.tamper_detail:
        fig_tamper_kinds(data, sets, a, out)
        fig_tamper_matrix(summary, a, plan_dir(out, "V1.2"))


def fig_modify(data, sets, summary, a, out):
    """one figure: x = modified files t, y = normal verification time of every scheme; plus the small table.
    Chen returns only a result bitmap, never the files, so a modified file never reaches its verification:
    its line is its verification time on the same query (the untampered run, t = 0), marked as not checking files."""
    fig, ax = paper_fig()
    ts = set()
    for s, check, label, variant, rows, metric in sets:
        if check != "early":                                      # the normal verification of every scheme only
            continue
        rk = [r for r in rows if r["tamper"] == "modify"]
        if rk and all(r["status"] == "N/A" for r in rk):          # Chen: files are not returned
            base = agg([r for r in rows if r["tamper"] == "none"], ["domain"], f"{metric}_ms_median")
            if not base:
                continue
            y = statistics.median(m for m, _, _ in base.values())
            xs = sorted({int(r["tampered"]) for rows_ in data.values() for r in ok(rows_) if r["tamper"] == "modify"})
            series(ax, "tamper_modify", s, [(t, y, 0.0) for t in xs], label + " (files not returned, not checked)",
                   ls=":")
            continue
        pts = agg(rk, ["tampered"], f"{metric}_ms_median")
        ts |= {int(k[0]) for k in pts}
        det = sum(int(r["detected_runs"]) for r in ok(rk))
        series(ax, "tamper_modify", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()],
               label + ("" if det else " (missed)"))
    if not ts:
        plt.close(fig)
        return
    rq_axis(ax, sorted(ts))
    dom = sorted({r["domain"] for rows in data.values() for r in ok(rows)})
    n = max(int(r["N"]) for rows in data.values() for r in ok(rows))
    done(fig, ax, "V1.2", "User verification time when t returned files are modified", "Modified files t",
         "User verification time (ms)",
         f"dataset-v4 (arXiv) · {', '.join(dom)}, {n:,} files each, one keyword with ~2,000 results per domain "
         f"(tamper_sets.jsonl) · the server changes t returned files · normal verification of each scheme · median "
         f"over domains (each: median of {a.reps} runs), bars: 25th–75th percentile across domains · {a.note}",
         out, "verify_vs_modified")
    table_modify(summary, a, plan_dir(out, "V1.2"))


def table_modify(summary, a, out):
    """small table: does the user detect the modified files, and can the user name them"""
    order = ["AMTP", NAME["chen"], NAME["du"], NAME["secollab"]]
    lines = []
    for sname in order:
        rows = [r for r in summary if r["scheme"] == sname and r["tamper"] == "modify" and r["tampered"] > 0]
        if not rows:
            continue
        if all(r["status"] == "N/A" for r in rows):
            lines.append((sname, "N/A (files not returned)", "N/A"))
            continue
        early = [r for r in rows if r["check"] == "early" and r["status"] == "ok"]
        full = [r for r in rows if r["check"] == "full" and r["status"] == "ok"]
        det, runs = sum(r["detected_runs"] for r in early), sum(r["runs"] for r in early)
        detected = "yes" if det == runs else ("no" if det == 0 else "partly")
        detected += f" ({det}/{runs})"

        def names(rs):
            return [int(r["localized"]) == r["tampered"] for r in rs if str(r["localized"]).lstrip("-").isdigit()]
        own = names(early)
        if own and all(own):
            named = "yes"
        elif full and names(full) and all(names(full)):
            named = "yes (full check)" if sname == "AMTP" else "yes (per-path check)"
        else:
            named = "no"
        lines.append((sname, detected, named))
    if not lines:
        return
    with open(os.path.join(out, "detection_table.md"), "w", encoding="utf-8") as f:
        f.write("| Scheme | Modified files detected? | Can the user name the modified files? |\n|---|---|---|\n")
        for row in lines:
            f.write("| " + " | ".join(row) + " |\n")
    with open(os.path.join(out, "detection_table.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scheme", "detected", "names_files"])
        w.writerows(lines)
    fig, ax = new_fig(6.4, 0.8 + 0.42 * (len(lines) + 1))
    ax.axis("off")
    tab = ax.table(cellText=[list(r) for r in lines],
                   colLabels=["Scheme", "Modified files detected?", "Names the modified files?"],
                   loc="center", cellLoc="center", colWidths=[0.26, 0.37, 0.37])
    tab.auto_set_font_size(False)
    tab.set_fontsize(9)
    tab.scale(1, 1.6)
    for (i, j), cell in tab.get_celld().items():
        cell.set_edgecolor("#d9d8d4")
        if i == 0:
            cell.set_text_props(fontweight="bold", color=INK)
            cell.set_facecolor("#f0efeb")
        elif j == 1:
            txt = cell.get_text().get_text()
            cell.set_facecolor("#bfe3cf" if txt.startswith("yes") else "#d9d8d4" if txt.startswith("N/A")
                               else "#f3c0b5")
    ax.set_title(f"{PLAN['V1.2'][1]}\nmodified files: detected or not (all domains, t, runs)",
                 fontsize=11, color=INK, loc="left")
    fig.text(0.01, 0.02, f"dataset-v4 (arXiv) · tamper_sets.jsonl · {a.note}", color=AXIS, fontsize=6.6)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out, f"detection_table.{ext}"), facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print(f"-> {os.path.relpath(os.path.join(out, 'detection_table'))}.png / .pdf / .md")


SEC_ORDER = [("amtp", "AMTP"), ("chen", NAME["chen"]), ("du", NAME["du"]), ("secollab", NAME["secollab"])]


def security_values(summary):
    """per scheme and tamper kind, over every domain, t > 0 and run (tamper_summary rows):
    wrong = % of tampered responses after which the user keeps a wrong result: not detected, and (Du) not corrected
            by its own filtering (result_ok_runs);
    named = % of the tampered files the user can point to, with the scheme's best check (AMTP / SE-COLLAB: full /
            per-path check; Chen, Du: their verification); a rejected proof (localized = -1) names no file.
    None = N/A (the scheme does not return the files)."""
    out = {}
    for s, sname in SEC_ORDER:
        for kind in KINDS:
            rows = [r for r in summary if r["scheme"] == sname and r["tamper"] == kind and r["tampered"] > 0]
            if not rows:
                continue
            if all(r["status"] == "N/A" for r in rows):
                out[(s, kind)] = (None, None, "")
                continue
            early = [r for r in rows if r["check"] == "early" and r["status"] == "ok"]
            full = [r for r in rows if r["check"] == "full" and r["status"] == "ok"] or early
            runs = sum(r["runs"] for r in early)
            det = sum(r["detected_runs"] for r in early)
            fixed = sum(int(r["result_ok_runs"]) for r in early
                        if str(r.get("result_ok_runs", "")).isdigit() and r["detected_runs"] == 0)
            wrong = 100.0 * (runs - det - fixed) / runs if runs else None
            note = "filtered, not reported" if det == 0 and fixed else ""
            named_rows = [r for r in full if str(r["localized"]).lstrip("-").isdigit()]
            named = (100.0 * sum(max(0, min(int(r["localized"]), r["tampered"])) for r in named_rows)
                     / sum(r["tampered"] for r in named_rows)) if named_rows else None
            out[(s, kind)] = (wrong, named, note)
    return out


def bars(ax, vals, idx, ylabel, fmt):
    """grouped bars: x = tamper kind, one bar per scheme; N/A bars drawn hatched at a small height"""
    width = 0.2
    for i, (s, sname) in enumerate(SEC_ORDER):
        color = STYLE[s][0]
        ax.bar(0, 0, 0, color=color, label=sname)                # legend entry even if the first kind is N/A
        for j, kind in enumerate(KINDS):
            if (s, kind) not in vals:
                continue
            v, note = vals[(s, kind)][idx], vals[(s, kind)][2]
            x = j + (i - 1.5) * width
            if v is None:
                ax.bar(x, 3, width, color="none", edgecolor=AXIS, hatch="///", linewidth=0.8)
                ax.text(x, 5, "N/A", ha="center", va="bottom", fontsize=7, color=INK2, rotation=90)
                continue
            ax.bar(x, max(v, 0.6), width, color=color)
            ax.text(x, max(v, 0.6) + 2, fmt(v) + ("*" if note and idx == 0 else ""), ha="center", va="bottom",
                    fontsize=7, color=INK, rotation=90)
    ax.set_xticks(range(len(KINDS)))
    ax.set_xticklabels([k.replace("_", " ") for k in KINDS])
    ax.set_ylim(0, 125)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.grid(axis="x", visible=False)
    handles, labels = ax.get_legend_handles_labels()
    seen = dict(zip(labels, handles))
    ax.legend(seen.values(), seen.keys(), loc="upper center", ncol=4, frameon=False, fontsize=9,
              bbox_to_anchor=(0.5, 1.0))


def figs_security(summary, a, out):
    """Verify 1.2, without time: (a) wrong results the user keeps after tampering, (b) tampered files the user can name"""
    vals = security_values(summary)
    if not vals:
        return
    with open(os.path.join(out, "security_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scheme", "tamper", "wrong_result_kept_pct", "files_named_pct", "note"])
        for (s, kind), (wrong, named, note) in vals.items():
            w.writerow([NAME[s], kind, "N/A" if wrong is None else round(wrong, 2),
                        "N/A" if named is None else round(named, 2), note])
    tail = (f"dataset-v4 (arXiv) · every domain, t = 5…1,000 and run (tamper_sets.jsonl) · N/A: the scheme does not "
            f"return the files · {a.note}")
    for idx, name, sub, ylabel, note in (
            (0, "wrong_result_kept", "Tampered responses the user still accepts (lower is better)",
             "Wrong results accepted (%)",
             "accepted = not detected and not corrected · * Du: injected files filtered out, cheating not reported"),
            (1, "files_named", "Tampered files the user can point to (higher is better)", "Tampered files named (%)",
             "best check of each scheme (AMTP full check, SE-COLLAB per-path, Chen and Du their verification)")):
        fig, ax = paper_fig()
        bars(ax, vals, idx, ylabel, lambda v: f"{v:.0f}%")
        _LETTER["V1.2"] = _LETTER.get("V1.2", 0) + 1
        ax.set_title(f"({'abcdefgh'[_LETTER['V1.2'] - 1]}) {PLAN['V1.2'][1]}\n{sub}", fontsize=12, color=INK)
        ax.set_xlabel("What the server does", color=INK2, fontsize=11)
        ax.set_ylabel(ylabel, color=INK2, fontsize=11)
        fig.text(0.01, 0.012, f"{note} · {tail}", color=AXIS, fontsize=6.4, wrap=True)
        fig.tight_layout(rect=(0, 0.06, 1, 1))
        for ext in ("png", "pdf"):
            fig.savefig(os.path.join(out, f"{name}.{ext}"), facecolor=SURFACE)
        plt.close(fig)
        print(f"-> {os.path.relpath(os.path.join(out, name))}.png / .pdf")


def fig_tamper_kinds(data, sets, a, out):
    """--tamper-detail: one figure per tamper kind (modify / hide / inject / old_version), early + full checks"""
    for kind in KINDS:
        fig, ax = paper_fig()
        ts, na, missed = set(), [], []
        for s, check, label, variant, rows, metric in sets:
            rk = [r for r in rows if r["tamper"] == kind]
            if rk and all(r["status"] == "N/A" for r in rk):
                na.append(NAME[s])
                continue
            pts = agg(rk, ["tampered"], f"{metric}_ms_median")
            ts |= {int(k[0]) for k in pts}
            det = sum(int(r["detected_runs"]) for r in ok(rk))
            if ok(rk) and det == 0 and check == "early":
                missed.append(NAME[s])
            series(ax, f"tamper_{kind}", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()],
                   label + ("" if det or not ok(rk) else " (missed)"), variant=variant)
        if ts:
            rq_axis(ax, sorted(ts))
            dom = sorted({r["domain"] for rows in data.values() for r in ok(rows)})
            n = max(int(r["N"]) for rows in data.values() for r in ok(rows))
            tail = (f" · N/A: {', '.join(na)}" if na else "") + (f" · not detected: {', '.join(missed)}" if missed else "")
            done(fig, ax, "V1.2", f"User verification with {KIND_LABEL[kind]}", "Tampered files t",
                 "User verification time (ms)",
                 f"dataset-v4 (arXiv) · {', '.join(dom)}, {n:,} files each, one keyword with ~2,000 results per "
                 f"domain (tamper_sets.jsonl) · median over domains (each: median of {a.reps} runs), bars: "
                 f"25th–75th percentile across domains · full check = check every file and name the wrong ones · "
                 f"{a.note}" + tail,
                 out, f"{kind}_vs_t")
        else:
            plt.close(fig)


def outcome(rows):
    """(text, colour) of one scheme x kind cell over every domain and t"""
    if not rows or all(r["status"] == "N/A" for r in rows):
        return "N/A\n(not returned)", "#d9d8d4"
    rows = [r for r in rows if r["status"] == "ok"]
    det, runs = sum(r["detected_runs"] for r in rows), sum(r["runs"] for r in rows)
    names = [(int(r["localized"]) if str(r["localized"]).lstrip("-").isdigit() else None, r["tampered"]) for r in rows]
    fails = [r["failed_check"] for r in rows if r.get("failed_check")]
    if all(n is None for n, _ in names) and fails:
        named = "rejected at check '" + max(set(fails), key=fails.count) + "'"
    elif all(n == t for n, t in names):
        named = "names all t files"
    elif all(not n or n < 0 for n, _ in names):
        named = "names no file"
    else:
        named = "names " + ", ".join(f"{n}/{t}" for n, t in sorted(names, key=lambda p: p[1]) if n is not None)
    if det == runs:
        good = named == "names all t files" or named.startswith("rejected at")
        return f"detected {det}/{runs}\n{named}", "#bfe3cf" if good else "#f6e3a6"
    filt = [r for r in rows if str(r.get("result_ok_runs", "")).isdigit()]
    if det == 0 and filt and sum(int(r["result_ok_runs"]) for r in filt) == runs:
        return f"not flagged {det}/{runs}\nfiltered out, result correct", "#f6e3a6"
    return f"detected {det}/{runs}", "#f3c0b5" if det == 0 else "#f6e3a6"


def fig_tamper_matrix(summary, a, out):
    """grid: one row per scheme (+ check), one column per tamper kind"""
    rows = []
    for label in dict.fromkeys(f"{r['scheme']}|{r['check']}" for r in summary):
        s, check = label.split("|")
        rows.append((f"{s}\n({'full check' if check == 'full' else 'normal verify'})"
                     if any(r["scheme"] == s and r["check"] == "full" for r in summary) else s, s, check))
    fig, ax = new_fig(8.4, 0.9 + 0.75 * len(rows))
    ax.grid(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_xlim(0, len(KINDS) + 1.2)
    ax.set_ylim(len(rows), -0.8)
    ax.set_xticks([])
    ax.set_yticks([])
    for j, kind in enumerate(KINDS):
        ax.text(1.2 + j + 0.5, -0.4, kind.replace("_", " "), ha="center", va="center", fontsize=10.5, color=INK,
                fontweight="bold")
    for i, (label, s, check) in enumerate(rows):
        ax.text(0.05, i + 0.5, label, ha="left", va="center", fontsize=9.5, color=INK)
        for j, kind in enumerate(KINDS):
            cell = [r for r in summary if r["scheme"] == s and r["check"] == check and r["tamper"] == kind
                    and r["tampered"] > 0]
            text, colour = outcome(cell)
            ax.add_patch(plt.Rectangle((1.2 + j + 0.03, i + 0.04), 0.94, 0.92, color=colour, lw=0))
            ax.text(1.2 + j + 0.5, i + 0.5, text, ha="center", va="center", fontsize=7.6, color=INK)
    ax.set_title(f"{PLAN['V1.2'][1]}\nwhat each scheme catches (every t, every run)", fontsize=12.5, color=INK,
                 loc="left")
    fig.text(0.01, 0.012, f"dataset-v4 (arXiv) · tamper_sets.jsonl · names = files the user can point to as wrong · "
             f"{a.note}", color=AXIS, fontsize=6.6)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out, f"detection_matrix.{ext}"), facecolor=SURFACE)
    plt.close(fig)
    print(f"-> {os.path.relpath(os.path.join(out, 'detection_matrix'))}.png / .pdf")
    with open(os.path.join(out, "tamper_summary.md"), "w", encoding="utf-8") as f:
        f.write("| scheme | " + " | ".join(KINDS) + " |\n|---|" + "---|" * len(KINDS) + "\n")
        for label, s, check in rows:
            cells = [outcome([r for r in summary if r["scheme"] == s and r["check"] == check and r["tamper"] == k
                              and r["tampered"] > 0])[0].replace("\n", ", ") for k in KINDS]
            f.write(f"| {label.replace(chr(10), ' ')} | " + " | ".join(cells) + " |\n")


# ============================================================================
# Search 2.1 (xsearch): Boolean shapes over 4 domains, x = kQ
# ============================================================================
def figs_xsearch(data, a, out):
    ns = {int(r["N_per_domain"]) for rows in data.values() for r in ok(rows)}
    if not ns:
        return
    n_fix = pick(ns, a.fix)
    for shape in SHAPE_LABEL:
        fig, ax = paper_fig()
        kqs = set()
        for s, rows in data.items():
            rows = [r for r in rows if r["shape"] == shape and int(r["N_per_domain"]) == n_fix]
            pts = agg(rows, ["kQ"], f"{SEARCH_COL[0]}_ms_median")
            kqs |= {int(k[0]) for k in pts}
            series(ax, f"xsearch_{shape}", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
        if not kqs:
            plt.close(fig)
            continue
        rq_axis(ax, sorted(kqs))
        done(fig, ax, "S2.1", f"{SHAPE_LABEL[shape]} over 4 domains ({n_fix:,} files each)",
             "Keywords in the query $k_Q$", f"{SEARCH_COL[1]} (ms)", note_of(a, f"4 domains, {n_fix:,} files each, one query per domain, times summed "
                                     f"(queries_boolean_multi.jsonl)"), out, f"{shape}_vs_kQ")


# ============================================================================
# Search 2.2 / Verify 2.2 (xdomains): x = number of domains D
# ============================================================================
def figs_xdomains(data, a, out):
    kqs = {int(r["kQ"]) for rows in data.values() for r in ok(rows)}
    if not kqs:
        return
    kq = pick(kqs, a.xkq)
    n = max(int(r["N_total"]) for rows in data.values() for r in ok(rows))
    for plan, metric, ylabel in (("S2.2", SEARCH_COL[0], f"{SEARCH_COL[1]} (ms)"),
                                 ("V2.2", "verify_total", "User verification time (ms)")):
        for shape in SHAPE_LABEL:
            fig, ax = paper_fig()
            ds = set()
            for s, rows in data.items():
                rows = [r for r in rows if r["shape"] == shape and int(r["kQ"]) == kq]
                pts = agg(rows, ["domains"], f"{metric}_ms_median")
                ds |= {int(k[0]) for k in pts}
                series(ax, f"{plan}_{shape}", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
            if not ds:
                plt.close(fig)
                continue
            rq_axis(ax, sorted(ds))
            done(fig, ax, plan, f"{SHAPE_LABEL[shape]} vs domains ($k_Q$ = {kq})", "Number of domains D", ylabel,
                 note_of(a, f"the same {n:,} files split into D domains (domain_groups.csv), one query per domain")
                 .replace(f"median of {a.reps} runs", f"median of {a.xdomains_reps} runs"),
                 out, f"{shape}_vs_D")


# ============================================================================
# Split / merge (bench.ablation folders results/amtp/splitmerge_*/)
# ============================================================================
def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sm_line(ax, fig, v, pts, label=None, ls=None):
    color, marker, vls = EXP4_STYLE[v]
    return series(ax, fig, None, pts, label or v, ls=ls or vls, style=(color, marker))


def phase_mark(ax, layout):
    """vertical line where the hot-group deletes start"""
    last_ins = max((int(r["batch"]) for r in layout if r.get("phase") == "insert"), default=None)
    if last_ins is not None and any(r.get("phase") == "hot_delete" for r in layout):
        ax.axvline(last_ins + 0.5, color=AXIS, lw=1, ls=":")
        ax.text(last_ins + 0.5, 1.0, " deletes start", transform=ax.get_xaxis_transform(), color=INK2,
                fontsize=8, va="top")


def figs_splitmerge(a, out):
    folders = sorted(glob.glob(os.path.join(a.results, "amtp", "splitmerge_*", "")))
    per_theta = []
    for folder in folders:
        layout, queries, updates = (read_csv(os.path.join(folder, n)) for n in ("layout.csv", "queries.csv", "updates.csv"))
        if not layout:
            continue
        args = {}
        if os.path.exists(os.path.join(folder, "manifest.json")):
            with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
                args = json.load(f).get("args", {})
        tag = os.path.basename(os.path.normpath(folder))
        theta = args.get("theta_max")
        setup = (f"start {args['n']:,} files, +{args['batches'] * args['batch_size']:,} inserts "
                 f"({float(str(args['skews']).split()[0].split(',')[0]) * 100:g}% into one hot group), then delete "
                 f"{args.get('hot_delete_frac', 0) * 100:g}% of it · θ = {args['theta_max']}/{args['theta_min']} · "
                 f"{args['runs']} run(s)") if args else tag
        note = f"dataset-v4 (arXiv) · {setup} · median over runs · {a.note}"
        variants = [v for v in EXP4_STYLE if any(r["variant"] == v for r in layout)]
        for col, ylabel, name in (("max_partition", "Largest partition (files)", "max_partition"),
                                  ("mean_partition", "Mean partition (files)", "mean_partition")):
            fig, ax = paper_fig()
            for v in variants:
                pts = agg([r for r in layout if r["variant"] == v], ["batch"], col)
                sm_line(ax, f"{tag}_{name}", v, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
            phase_mark(ax, layout)
            done(fig, ax, "SM", f"{ylabel.split(' (')[0]} over time (θ = {theta})",
                 "Batch (100 files each)", ylabel, note, out, f"{tag}_{name}")
        if queries:
            fig, ax = paper_fig()
            for v in variants:
                pts = agg([r for r in queries if r["variant"] == v], ["batch"], "verify_ms")
                sm_line(ax, f"{tag}_verify", v, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
            phase_mark(ax, layout)
            done(fig, ax, "SM", f"User verification over time (θ = {theta})",
                 "Batch (100 files each)", "User verification time (ms)",
                 note.replace("median over runs", "median over queries and runs, bars 25th–75th percentile"),
                 out, f"{tag}_verify")
        if updates:
            every = int(args.get("query_every") or 0) or 50
            fig, ax = paper_fig()
            for v in variants:
                rows = [dict(r, bin=str((int(r["batch"]) // every) * every + every - 1)) for r in updates
                        if r["variant"] == v]
                pts = agg(rows, ["bin"], "update_ms")
                sm_line(ax, f"{tag}_update", v, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
            phase_mark(ax, layout)
            done(fig, ax, "SM", f"Update cost per batch (θ = {theta})", "Batch (100 files each)",
                 "Update time per batch (ms)",
                 note.replace("median over runs", f"median over each {every} batches and runs, bars 25th–75th"),
                 out, f"{tag}_update")
        if theta:
            per_theta.append((int(theta), args, layout, queries, updates))
    if len(per_theta) < 2:
        return
    per_theta.sort(key=lambda p: p[0])
    thetas = [p[0] for p in per_theta]
    end_note = (f"dataset-v4 (arXiv) · start {per_theta[0][1]['n']:,} files, same workload per θ, θ_min = θ_max / 4 · "
                f"median over runs · {a.note}")
    for name, ylabel, fn in (
            ("final_max_partition", "Largest partition at the end (files)",
             lambda lay, q, u, v: [float(r["max_partition"]) for r in lay if r["variant"] == v
                                   and int(r["batch"]) == max(int(x["batch"]) for x in lay)]),
            ("final_mean_partition", "Mean partition at the end (files)",
             lambda lay, q, u, v: [float(r["mean_partition"]) for r in lay if r["variant"] == v
                                   and int(r["batch"]) == max(int(x["batch"]) for x in lay)]),
            ("update", "Update time per batch (ms)",
             lambda lay, q, u, v: [float(r["update_ms"]) for r in u if r["variant"] == v]),
            ("final_verify", "User verification at the end (ms)",
             lambda lay, q, u, v: [float(r["verify_ms"]) for r in q if r["variant"] == v
                                   and int(r["batch"]) == max(int(x["batch"]) for x in q)])):
        fig, ax = paper_fig()
        for v in EXP4_STYLE:
            pts = []
            for th, args, lay, q, u in per_theta:
                xs = fn(lay, q, u, v)
                if xs:
                    m = statistics.median(xs)
                    if len(xs) > 1:
                        q1, _, q3 = statistics.quantiles(xs, n=4, method="inclusive")
                        pts.append((th, m, (m - q1, q3 - m)))
                    else:
                        pts.append((th, m, 0.0))
            sm_line(ax, f"splitmerge_{name}_vs_theta", v, pts)
        rq_axis(ax, thetas)
        done(fig, ax, "SM", f"{ylabel.split(' (')[0]} vs θ", "θ_max (files per partition)",
             ylabel, end_note, out, f"{name}_vs_theta")


# ============================================================================
# Update (exp3): insert / delete batches, AMTP vs Chen
# ============================================================================
def figs_update(data, a, out):
    rows = {s: ok(r) for s, r in data.items()}
    ns = sorted({int(r["N"]) for rs in rows.values() for r in rs})
    batches = sorted({int(r["batch"]) for rs in rows.values() for r in rs})
    if not ns:
        return
    n_fix = pick(set(ns), a.fix)
    note = (f"dataset-v4 (arXiv) · insert from the insert pool, delete the same files · median of {a.reps} runs, "
            f"bars: ±1 std · {a.note}")
    for op in ("insert", "delete"):
        # (1) time per file vs N, one file per batch
        fig, ax = paper_fig()
        for s, rs in rows.items():
            pts = [(int(r["N"]), float(r["update_ms_median"]), float(r["update_ms_std"] or 0))
                   for r in rs if r["op"] == op and int(r["batch"]) == 1]
            series(ax, f"update_{op}_b1_vs_N", s, pts)
        rq_axis(ax, ns)
        done(fig, ax, "UPD", f"{op.capitalize()} one file vs files in the index", "Files in the index N",
             "Update time (ms)", note, out, f"{op}_one_file_vs_N")
        # (2) time per file vs batch size, N fixed
        fig, ax = paper_fig()
        for s, rs in rows.items():
            pts = [(int(r["batch"]), float(r["update_ms_median"]) / int(r["batch"]),
                    float(r["update_ms_std"] or 0) / int(r["batch"]))
                   for r in rs if r["op"] == op and int(r["N"]) == n_fix]
            series(ax, f"update_{op}_per_file_vs_batch", s, pts)
        rq_axis(ax, batches)
        done(fig, ax, "UPD", f"{op.capitalize()} time per file vs batch size (N = {n_fix:,})",
             "Files per batch", "Update time per file (ms)", note, out, f"{op}_per_file_vs_batch")


# ============================================================================
# θ sweep (theta): AMTP only, x = θ_max
# ============================================================================
TH_STYLE = (("#2a78d6", "o", "-"), ("#2a78d6", "s", "--"), ("#2a78d6", "^", ":"))


def figs_theta(rows, a, out):
    rows = sorted(ok(rows), key=lambda r: int(r["theta_max"]))
    if len(rows) < 2:
        return
    thetas = [int(r["theta_max"]) for r in rows]
    n = int(rows[0]["N"])
    note = (f"dataset-v4 (arXiv) · {n:,} files, one domain, θ_min = θ_max / 4 · median over queries / runs "
            f"({a.reps} runs) · {a.note}")
    for name, ylabel, lines in (
            ("query_vs_theta", "Time per query (ms)",
             (("End-to-end search", "query_end_to_end_ms_median"), ("User verification", "query_verify_total_ms_median"),
              ("Server (search + proof)", "query_server_total_ms_median"))),
            ("insert_vs_theta", "Insert time per file (ms)",
             (("Batch of 1 file", "insert_b1_per_doc_ms"), ("Batch of 100 files", "insert_b100_per_doc_ms")))):
        fig, ax = paper_fig()
        for (label, col), (color, marker, ls) in zip(lines, TH_STYLE):
            series(ax, f"theta_{name}_{col}", "amtp", [(int(r["theta_max"]), float(r[col]), 0.0) for r in rows],
                   label, ls=ls, style=(color, marker))
        rq_axis(ax, thetas)
        done(fig, ax, "TH", f"{ylabel.split(' (')[0]} vs θ_max", "θ_max (files per partition)", ylabel, note, out, name)


# ============================================================================
# Search 2.1 vs files: multi-domain Boolean queries at 10k..125k files per domain
# ============================================================================
def figs_xsearch_files(data, a, out):
    ns = sorted({int(r["N_per_domain"]) for rows in data.values() for r in ok(rows)})
    if len(ns) < 2:
        return
    for shape in SHAPE_LABEL:
        fig, ax = paper_fig()
        for s, rows in data.items():
            rows = [r for r in rows if r["shape"] == shape and int(r["kQ"]) == a.xkq]
            pts = agg(rows, ["N_per_domain"], f"{SEARCH_COL[0]}_ms_median")
            series(ax, f"xsearch_files_{shape}", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
        rq_axis(ax, ns)
        done(fig, ax, "S2.1", f"{SHAPE_LABEL[shape]} over 4 domains vs files ($k_Q$ = {a.xkq})",
             "Files per domain", f"{SEARCH_COL[1]} (ms)",
             note_of(a, f"4 domains, one query per domain, times summed (queries_boolean_multi.jsonl)"),
             out, f"{shape}_vs_files")


# ============================================================================
# Boolean search, single domain (exp1 queries): AND / OR / mixed, x = k_Q or files
# ============================================================================
EXP1_SHAPE = {"single": "one keyword", "conjunctive": "A ∧ B ∧ …", "disjunctive": "A ∨ B ∨ …",
              "or_and_or": "(A ∨ B) ∧ (C ∨ D) …", "and_or_and": "(A ∧ B) ∨ (C ∧ D) …"}
EXP1_STYLE = {"single": ("#5b6b7c", "x", "-"), "conjunctive": ("#2a78d6", "o", "-"),
              "disjunctive": ("#7a4fd0", "s", "--"), "or_and_or": ("#1b9aaa", "^", "-."),
              "and_or_and": ("#c2410c", "D", ":")}


def figs_boolean(data, a, out):
    """vs SE-COLLAB only (the one baseline with OR). One figure per shape and x axis."""
    ns = sorted({int(r["N"]) for rows in data.values() for r in ok(rows)})
    kqs = sorted({int(r["kQ"]) for rows in data.values() for r in ok(rows)})
    if not ns:
        return
    n_fix = pick(set(ns), a.fix)
    base = "one domain (all N files in it), queries of exp1_queries.json (20 per point)"
    for metric, ylabel, name in ((f"{SEARCH_COL[0]}_ms_median", f"{SEARCH_COL[1]} (ms)", "time"),
                                 ("verify_total_ms_median", "User verification time (ms)", "verify")):
        for shape in [s for s in EXP1_SHAPE if s != "single"]:
            fig, ax = paper_fig()
            for s, rows in data.items():
                rs = [r for r in rows if int(r["N"]) == n_fix and (r["shape"] == shape or r["shape"] == "single")]
                pts = agg(rs, ["kQ"], metric)
                series(ax, f"bool_{name}_{shape}_vs_kQ", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
            rq_axis(ax, kqs)
            done(fig, ax, "SB", f"{EXP1_SHAPE[shape]} vs $k_Q$ ({n_fix:,} files)", "Keywords in the query $k_Q$",
                 ylabel, note_of(a, f"{base}; k_Q = 1 is the one-keyword query"), out, f"{name}_{shape}_vs_kQ")
        for shape in EXP1_SHAPE:
            kq = 1 if shape == "single" else a.bkq
            fig, ax = paper_fig()
            for s, rows in data.items():
                pts = agg([r for r in rows if r["shape"] == shape and int(r["kQ"]) == kq], ["N"], metric)
                series(ax, f"bool_{name}_{shape}_vs_N", s, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
            rq_axis(ax, ns)
            done(fig, ax, "SB", f"{EXP1_SHAPE[shape]} vs files ($k_Q$ = {kq})", "Files in the domain", ylabel,
                 note_of(a, base), out, f"{name}_{shape}_vs_files")


def figs_self_boolean(rows, a, out):
    """way3_ourself: AMTP's Boolean shapes against AND (conjunctive) on the same files and k_Q."""
    rows = ok(rows)
    if not rows:
        return
    ns = sorted({int(r["N"]) for r in rows})
    kqs = sorted({int(r["kQ"]) for r in rows})
    n_fix = pick(set(ns), a.fix)
    note = (f"dataset-v4 (arXiv) · AMTP only · one domain, exp1_queries.json (20 queries per point), the same files "
            f"for every shape · median over queries, bars: 25th–75th percentile · {a.reps} runs per query · {a.note}")
    for metric, ylabel, name in ((f"{SEARCH_COL[0]}_ms_median", f"{SEARCH_COL[1]} (ms)", "time"),
                                 ("rQ", "Returned files r_Q", "results")):
        for xname, xs, sel, xlabel in (
                ("kQ", kqs, lambda r: int(r["N"]) == n_fix, "Keywords in the query $k_Q$"),
                ("files", ns, lambda r: int(r["kQ"]) in (1, a.bkq), "Files in the domain")):
            fig, ax = paper_fig()
            for shape, (color, marker, ls) in EXP1_STYLE.items():
                if shape == "single" and xname == "kQ":
                    continue
                rs = [r for r in rows if sel(r) and (r["shape"] == shape or (xname == "kQ" and r["shape"] == "single"))]
                if xname == "files":
                    rs = [r for r in rs if int(r["kQ"]) == (1 if shape == "single" else a.bkq)]
                pts = agg(rs, ["kQ" if xname == "kQ" else "N"], metric)
                series(ax, f"self_bool_{name}_vs_{xname}_{shape}", "amtp",
                       [(int(k[0]), m, e) for k, (m, e, _) in pts.items()], EXP1_SHAPE[shape], ls=ls,
                       style=(color, marker))
            rq_axis(ax, xs)
            fixed = f"{n_fix:,} files" if xname == "kQ" else f"$k_Q$ = {a.bkq} (one keyword: 1)"
            done(fig, ax, "SELF", f"Boolean vs AND: {ylabel.split(' (')[0].lower()} vs "
                 f"{'$k_Q$' if xname == 'kQ' else 'files'} ({fixed})", xlabel, ylabel, note, out,
                 f"boolean_vs_and_{name}_vs_{xname}")


# ============================================================================
# way3_ourself: AMTP against itself (same files, same queries)
# ============================================================================
SHAPE_STYLE = {"AND": ("#2a78d6", "o", "-"), "OR": ("#7a4fd0", "s", "--"),
               "AND_of_OR": ("#1b9aaa", "^", "-."), "OR_of_AND": ("#5b6b7c", "D", ":")}


def figs_self_domains(rows, a, out):
    """single domain (D = 1) vs multi domain (D > 1): the same 400,000 files and the same queries, split into D
    domains (xdomains). Per query: time at D / time at D = 1, then the median over queries."""
    rows = ok(rows)
    if not rows:
        return
    ds = sorted({int(r["domains"]) for r in rows})
    if 1 not in ds:
        return
    by_q = {(r["query_id"], int(r["domains"])): r for r in rows}
    n = max(int(r["N_total"]) for r in rows)
    note = (f"dataset-v4 (arXiv) · AMTP only · the same {n:,} files and the same queries split into D domains "
            f"(xdomains), every k_Q · per query: value at D / value at D = 1, median over queries, "
            f"bars: 25th–75th percentile · {a.xdomains_reps} runs per query · {a.note}")
    for metric, ylabel, name in (("end_to_end_ms_median", "End-to-end time relative to D = 1", "time"),
                                 ("verify_total_ms_median", "User verification relative to D = 1", "verify"),
                                 ("proof_bytes", "Proof size relative to D = 1", "proof")):
        fig, ax = paper_fig()
        for shape, (color, marker, ls) in SHAPE_STYLE.items():
            pts = []
            for d in ds:
                v = [float(by_q[(q, d)][metric]) / float(r[metric])
                     for (q, d1), r in by_q.items() if d1 == 1 and r["shape"] == shape and (q, d) in by_q
                     and float(r[metric]) > 0]
                if v:
                    m = statistics.median(v)
                    q1, _, q3 = statistics.quantiles(v, n=4, method="inclusive") if len(v) > 1 else (m, m, m)
                    pts.append((d, m, (m - q1, q3 - m)))
            series(ax, f"self_{name}_vs_D_{shape}", "amtp", pts, SHAPE_LABEL[shape], ls=ls, style=(color, marker))
        ax.axhline(1, color=INK2, linewidth=1, linestyle=":")
        rq_axis(ax, ds)
        done(fig, ax, "SELF", f"Single domain (D = 1) vs multi domain: {ylabel.split(' relative')[0].lower()}",
             "Number of domains D (same files, same queries)", ylabel, note, out, f"single_vs_multi_domain_{name}",
             log_y=False)


# ============================================================================
# main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="figures for the dataset-v4 suites (advisor's plan)")
    ap.add_argument("--results", default=os.path.join(HERE, "results"), help="folder with <scheme>/ inside")
    ap.add_argument("--out", default=None, help="figure folder (default <results>/figures_v4)")
    ap.add_argument("--reps", type=int, default=30, help="runs per query (written in the note)")
    ap.add_argument("--xdomains-reps", type=int, default=10,
                    help="runs per query of the xdomains suite (Search / Verify 2.2; written in the note)")
    ap.add_argument("--fix", type=int, default=100_000, help="files per domain where the size is fixed")
    ap.add_argument("--kq", type=int, default=5, help="Search 1.2: k_Q of the files-per-domain figure")
    ap.add_argument("--xkq", type=int, default=4, help="Search 2.2 / 2.1 vs files: k_Q of the figure")
    ap.add_argument("--bkq", type=int, default=4, help="Boolean single domain: k_Q of the files figures")
    ap.add_argument("--note", default="AWS r7i.4xlarge", help="note at the bottom of every figure")
    ap.add_argument("--tamper-detail", action="store_true",
                    help="Verify 1.2: also the hide / inject / old_version figures and the 4 x 4 detection matrix")
    ap.add_argument("--search-metric", choices=list(SEARCH_METRICS), default="end_to_end",
                    help="Search figures: end-to-end time (query + server + user verification) or server time only")
    ap.add_argument("--by-experiment", action="store_true",
                    help="folders ex1_search / ex2_verify / ex3_update / ex4_theta / ex5_split_merge, "
                         "and the update and θ-sweep figures")
    a = ap.parse_args()
    global BY_EXPERIMENT, SEARCH_COL
    BY_EXPERIMENT = a.by_experiment
    SEARCH_COL = SEARCH_METRICS[a.search_metric]
    out = a.out or os.path.join(a.results, "figures_v4")
    os.makedirs(out, exist_ok=True)

    def suite(name, schemes=SCHEMES):
        return {s: rows for s in schemes if (rows := load(s, name, a.results))}

    for name, fn in (("search_single", lambda d: figs_search1(d, a, out)),
                     ("verify_single", lambda d: figs_verify(d, a, out, multi=False)),
                     ("tamper_detection", lambda d: figs_tamper(d, a, out)),
                     ("search_multi", lambda d: figs_xsearch(d, a, out)),
                     ("verify_multi", lambda d: figs_verify(d, a, out, multi=True)),
                     ("domains_scaling", lambda d: figs_xdomains(d, a, out))):
        d = suite(name)
        if d:
            print(f"[{name}] {', '.join(NAME[s] for s in d)}")
            fn(d)
    if a.by_experiment:
        d = suite("exp3_dynamic_update", ["amtp", "chen"])
        if d:
            print(f"[exp3_dynamic_update] {', '.join(NAME[s] for s in d)}")
            figs_update(d, a, out)
        th = load("amtp", "theta_sweep", a.results)
        if th:
            print("[theta_sweep] AMTP")
            figs_theta(th, a, out)
        xd = load("amtp", "domains_scaling", a.results)
        if xd:
            print("[way3_ourself] AMTP single vs multi domain")
            figs_self_domains(xd, a, out)
        d = suite("search_multi", ["amtp", "secollab"])
        if d:
            print("[search_multi vs files] " + ", ".join(NAME[s] for s in d))
            figs_xsearch_files(d, a, out)
        d = suite("exp1_boolean_scalability", ["amtp", "secollab"])
        if d:
            print("[boolean single domain] " + ", ".join(NAME[s] for s in d))
            figs_boolean(d, a, out)
            if "amtp" in d:
                figs_self_boolean(d["amtp"], a, out)
    figs_splitmerge(a, out)
    if POINTS:
        with open(os.path.join(out, "figure_points.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, list(POINTS[0]))
            w.writeheader()
            w.writerows(POINTS)
        print(f"-> {os.path.relpath(os.path.join(out, 'figure_points.csv'))} ({len(POINTS)} points)")


if __name__ == "__main__":
    main()
