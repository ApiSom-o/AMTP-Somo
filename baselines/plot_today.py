#!/usr/bin/env python3
"""The 'today' figure set: one folder per experiment, PNG only, and the note under each figure lists only the
values that are held fixed.

    python3 plot_today.py --results ../new_result --old ../results_aws --out ../new_result/today

ex1_search     server time (search + proof) per query        run 2 (new_result)
ex2_verify     user verification time                        run 2
ex3_update     update time, AMTP vs Chen [40]                run 2 (update has no verification loop)
ex4_split_merge  static / global / AMTP, theta_max = 64      run 1 (results_aws, before the loop fix)
ex5_multidomain_scalability  end-to-end time vs domains      run 2
Statistics as plot_v4.py: median over queries (each the median of its runs), bars 25th-75th percentile.
"""
import argparse
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plot_v4 as v4  # noqa: E402
from plot_results import EXP4_STYLE, INK, INK2, KB, NAME, STYLE, SURFACE, AXIS, load, ok, paper_fig, plt, rq_axis  # noqa: E402,F401

SHAPES = {"AND": ("AND only", "A ∧ B ∧ …"), "OR": ("OR only", "A ∨ B ∨ …"),
          "AND_of_OR": ("AND of ORs", "(A ∨ B) ∧ (C ∨ D) …"), "OR_of_AND": ("OR of ANDs", "(A ∧ B) ∨ (C ∧ D) …")}
SHAPE_FILE = {"AND": "AND_only", "OR": "OR_only", "AND_of_OR": "AND_of_ORs", "OR_of_AND": "OR_of_ANDs"}


def save(fig, ax, path, title, xlabel, ylabel, fixed, log_y=True, ncol=2):
    """title, axes, legend on top, 'Fixed: …' under the plot, PNG only"""
    if log_y:
        ax.set_yscale("log")
    ax.set_title(title, fontsize=13, color=INK)
    ax.set_xlabel(xlabel, color=INK2, fontsize=12)
    ax.set_ylabel(ylabel, color=INK2, fontsize=12)
    handles = ax.get_legend_handles_labels()[0]
    lo, hi = ax.get_ylim()
    rows = -(-len(handles) // ncol)
    if ax.get_yscale() == "log":
        ax.set_ylim(lo, hi * (hi / lo) ** (0.12 * rows + 0.05))
    else:
        ax.set_ylim(lo, hi + (hi - lo) * (0.12 * rows + 0.05))
    if handles:
        ax.legend(loc="upper center", ncol=ncol, frameon=False, fontsize=9.5, handlelength=2.6, columnspacing=1.2)
    fig.text(0.01, 0.015, "Fixed: " + " · ".join(fixed), color=INK2, fontsize=8.5, wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(f"{path}.png", facecolor=SURFACE)
    plt.close(fig)
    print(f"-> {os.path.relpath(path)}.png")


def kfmt(ax):
    from matplotlib.ticker import FuncFormatter
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:g}k"))


def line(ax, s, rows, key, metric, xmap=int, label=None, **kw):
    pts = v4.agg(rows, [key], metric)
    v4.series(ax, "today", s, [(xmap(k[0]), m, e) for k, (m, e, _) in pts.items()], label, **kw)
    return {xmap(k[0]) for k in pts}


def suite(name, schemes, results):
    return {s: rows for s in schemes if (rows := load(s, name, results))}


# ---------------------------------------------------------------- ex1 search: server time
def ex1(a, out):
    d = os.path.join(out, "ex1_search")
    y = "Server time per query (ms)"
    data = suite("search_single", v4.SCHEMES, a.results)
    fig, ax = paper_fig()
    xs = set()
    for s, rows in data.items():
        xs |= line(ax, s, [r for r in rows if int(r["N"]) == a.fix], "kQ", "server_total_ms_median")
    rq_axis(ax, sorted(xs))
    save(fig, ax, os.path.join(d, "Search_1.1_single_domain_vary_keywords", "server_time_vs_kQ"),
         "Search 1.1 · single domain · vary keywords", "Keywords in the AND query $k_Q$", y,
         ["1 domain", f"{a.fix:,} files", "AND query"], ncol=4)
    fig, ax = paper_fig()
    xs = set()
    for s, rows in data.items():
        xs |= line(ax, s, [r for r in rows if int(r["kQ"]) == a.kq], "N", "server_total_ms_median")
    rq_axis(ax, sorted(xs))
    kfmt(ax)
    save(fig, ax, os.path.join(d, "Search_1.2_single_domain_vary_files", "server_time_vs_files"),
         "Search 1.2 · single domain · vary files", "Files in the domain", y,
         ["1 domain", f"$k_Q$ = {a.kq}", "AND query"], ncol=4)

    multi = suite("search_multi", ["amtp", "secollab"], a.results)
    for shape, (name, sym) in SHAPES.items():
        fig, ax = paper_fig()
        xs = set()
        for s, rows in multi.items():
            xs |= line(ax, s, [r for r in rows if r["shape"] == shape and int(r["N_per_domain"]) == a.fix],
                       "kQ", "server_total_ms_median")
        rq_axis(ax, sorted(xs))
        save(fig, ax, os.path.join(d, "Search_2.1_multi_domain_boolean", f"{SHAPE_FILE[shape]}_vs_kQ"),
             f"Search 2.1 · multi-domain · {name}  {sym}", "Keywords in the query $k_Q$", y,
             ["4 domains", f"{a.fix:,} files per domain", f"{name} query"])
        fig, ax = paper_fig()
        xs = set()
        for s, rows in multi.items():
            xs |= line(ax, s, [r for r in rows if r["shape"] == shape and int(r["kQ"]) == a.xkq],
                       "N_per_domain", "server_total_ms_median")
        rq_axis(ax, sorted(xs))
        kfmt(ax)
        save(fig, ax, os.path.join(d, "Search_2.1_multi_domain_boolean", f"{SHAPE_FILE[shape]}_vs_files"),
             f"Search 2.1 · multi-domain · {name}  {sym}", "Files per domain", y,
             ["4 domains", f"$k_Q$ = {a.xkq}", f"{name} query"])

    dom = suite("domains_scaling", ["amtp", "secollab"], a.results)
    n_total = max(int(r["N_total"]) for rows in dom.values() for r in ok(rows))
    for shape, (name, sym) in SHAPES.items():
        fig, ax = paper_fig()
        xs = set()
        for s, rows in dom.items():
            xs |= line(ax, s, [r for r in rows if r["shape"] == shape and int(r["kQ"]) == a.xkq],
                       "domains", "server_total_ms_median")
        rq_axis(ax, sorted(xs))
        save(fig, ax, os.path.join(d, "Search_2.2_multi_domain_vary_domains", f"{SHAPE_FILE[shape]}_vs_D"),
             f"Search 2.2 · multi-domain · vary domains · {name}", "Number of domains D", y,
             [f"{n_total:,} files in total (split over the D domains)", f"$k_Q$ = {a.xkq}", f"{name} query"])


# ---------------------------------------------------------------- ex2 verify: user verification time
def ex2(a, out):
    d = os.path.join(out, "ex2_verify")
    y = "User verification time (ms)"
    for multi, tag, title, folder, schemes in (
            (False, "verify_single", "Verify 1.1 · single domain · vary returned files",
             "Verify_1.1_single_domain_vary_results", v4.SCHEMES),
            (True, "verify_multi", "Verify 2.1 · multi-domain · vary returned files",
             "Verify_2.1_multi_domain_vary_results", ["amtp", "secollab"])):
        data = suite(tag, schemes, a.results)
        ncol = "N_per_domain" if multi else "N"
        by_target = {}
        for rows in data.values():
            for r in ok(rows):
                if int(r[ncol]) == a.fix and r.get("rQ") not in (None, ""):
                    by_target.setdefault(int(r["target_results"]), []).append(int(r["rQ"]))
        real = {t: statistics.median(v) for t, v in by_target.items()}
        fig, ax = paper_fig()
        for s, rows in data.items():
            rows = [r for r in rows if int(r[ncol]) == a.fix and r.get("proof_mode", "multi") in ("multi", "")]
            line(ax, s, rows, "target_results", "verify_total_ms_median", xmap=lambda k: real[int(k)])
        rq_axis(ax, sorted(real.values()))
        fixed = (["4 domains", f"{a.fix:,} files per domain", "one keyword found in every domain"] if multi else
                 ["1 domain", f"{a.fix:,} files", "one-keyword query"])
        save(fig, ax, os.path.join(d, folder, "verify_vs_rQ"), title,
             "Returned files $r_Q$", y, fixed, ncol=4 if not multi else 2)

    # Verify 1.2: the server modifies t of the returned files
    data = suite("tamper_detection", v4.SCHEMES, a.results)
    fig, ax = paper_fig()
    xs = set()
    for s, rows in data.items():
        rows = [r for r in rows if r.get("check_mode", "early") in ("early", "")]
        rk = [r for r in rows if r["tamper"] == "modify"]
        if rk and all(r["status"] == "N/A" for r in rk):           # Chen [40]: files are not returned
            base = v4.agg([r for r in rows if r["tamper"] == "none"], ["domain"], "verify_total_ms_median")
            if base:
                ym = statistics.median(m for m, _, _ in base.values())
                v4.series(ax, "today", s, [(t, ym, 0.0) for t in sorted(xs)],
                          NAME[s] + " (returns no files, nothing to check)", ls=":")
            continue
        xs |= line(ax, s, rk, "tampered", "verify_total_ms_median")
    rq_axis(ax, sorted(xs))
    rq = statistics.median(int(r["rQ"]) for r in ok(data["amtp"]) if r["tamper"] == "modify")
    save(fig, ax, os.path.join(d, "Verify_1.2_single_domain_vary_tampered", "verify_vs_modified"),
         "Verify 1.2 · single domain · vary tampered files", "Modified files t", y,
         ["1 domain", f"{a.fix:,} files", f"one keyword with ~{rq:,.0f} returned files"])

    dom = suite("domains_scaling", ["amtp", "secollab"], a.results)
    n_total = max(int(r["N_total"]) for rows in dom.values() for r in ok(rows))
    for shape, (name, sym) in SHAPES.items():
        fig, ax = paper_fig()
        xs = set()
        for s, rows in dom.items():
            xs |= line(ax, s, [r for r in rows if r["shape"] == shape and int(r["kQ"]) == a.xkq],
                       "domains", "verify_total_ms_median")
        rq_axis(ax, sorted(xs))
        save(fig, ax, os.path.join(d, "Verify_2.2_multi_domain_vary_domains", f"{SHAPE_FILE[shape]}_vs_D"),
             f"Verify 2.2 · multi-domain · vary domains · {name}", "Number of domains D", y,
             [f"{n_total:,} files in total (split over the D domains)", f"$k_Q$ = {a.xkq}", f"{name} query"])


# ---------------------------------------------------------------- ex3 update cost: AMTP vs Chen
def ex3(a, out):
    d = os.path.join(out, "ex3_update_cost")
    data = {s: ok(r) for s, r in suite("exp3_dynamic_update", ["amtp", "chen"], a.results).items()}
    for op in ("insert", "delete"):
        fig, ax = paper_fig()
        xs = set()
        for s, rows in data.items():
            pts = [(int(r["batch"]), float(r["update_ms_median"]), float(r["update_ms_std"] or 0))
                   for r in rows if r["op"] == op and int(r["N"]) == a.fix]
            xs |= {p[0] for p in pts}
            v4.series(ax, "today", s, pts)
        rq_axis(ax, sorted(xs))
        save(fig, ax, os.path.join(d, f"{op}_time_vs_files_updated"),
             f"Update cost · {op} · AMTP vs Chen [40]", f"Files {op}ed in one batch".replace("deleteed", "deleted"),
             "Update time per batch (ms)",
             [f"{a.fix:,} files in the index ({a.fix // 4:,} from each of the 4 domains, one index)"])
        # x = files in the index (10k .. 500k), one batch size per figure
        for b in (1, 100):
            fig, ax = paper_fig()
            xs = set()
            for s, rows in data.items():
                pts = [(int(r["N"]), float(r["update_ms_median"]), float(r["update_ms_std"] or 0))
                       for r in rows if r["op"] == op and int(r["batch"]) == b]
                xs |= {p[0] for p in pts}
                v4.series(ax, "today", s, pts)
            rq_axis(ax, sorted(xs))
            kfmt(ax)
            what = "one file" if b == 1 else f"a batch of {b} files"
            save(fig, ax, os.path.join(d, f"{op}_time_vs_index_size_batch{b}"),
                 f"Update cost · {op} {what} · AMTP vs Chen [40]", "Files in the index N",
                 "Update time per batch (ms)",
                 [f"{b} file{'s' if b > 1 else ''} per batch", "files taken equally from the 4 domains, one index"])


# ---------------------------------------------------------------- ex4 split / merge (run 1, theta 64)
def ex4(a, out):
    d = os.path.join(out, "ex4_split_merge")
    folder = os.path.join(a.old, "amtp", f"splitmerge_n100000_t{a.theta}")
    layout, queries, updates = (v4.read_csv(os.path.join(folder, n)) for n in ("layout.csv", "queries.csv", "updates.csv"))
    variants = [v for v in EXP4_STYLE if any(r["variant"] == v for r in layout)]
    fixed = [f"θ_max = {a.theta}, θ_min = {a.theta // 4}", "start 100,000 files",
             "1,000 batches of 100 inserts (95% into one hot group), then 65% of the hot group deleted"]
    for col, ylabel, name in (("max_partition", "Largest partition (files)", "max_partition"),
                              ("mean_partition", "Mean partition (files)", "mean_partition")):
        fig, ax = paper_fig()
        for v in variants:
            pts = v4.agg([r for r in layout if r["variant"] == v], ["batch"], col)
            v4.sm_line(ax, "today", v, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
        v4.phase_mark(ax, layout)
        save(fig, ax, os.path.join(d, name), f"Split / merge ablation · {ylabel.split(' (')[0].lower()}",
             "Batch (100 files each)", ylabel, fixed)
    fig, ax = paper_fig()
    for v in variants:
        pts = v4.agg([r for r in queries if r["variant"] == v], ["batch"], "verify_ms")
        v4.sm_line(ax, "today", v, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
    v4.phase_mark(ax, layout)
    save(fig, ax, os.path.join(d, "verify_time"), "Split / merge ablation · user verification",
         "Batch (100 files each)", "User verification time (ms)", fixed)
    every = 100
    fig, ax = paper_fig()
    for v in variants:
        rows = [dict(r, bin=str((int(r["batch"]) // every) * every + every - 1)) for r in updates if r["variant"] == v]
        pts = v4.agg(rows, ["bin"], "update_ms")
        v4.sm_line(ax, "today", v, [(int(k[0]), m, e) for k, (m, e, _) in pts.items()])
    v4.phase_mark(ax, layout)
    save(fig, ax, os.path.join(d, "update_time"), "Split / merge ablation · update cost",
         "Batch (100 files each)", "Update time per batch (ms)", fixed)


# ---------------------------------------------------------------- ex5 multi-domain scalability: end-to-end vs D
def ex5(a, out):
    d = os.path.join(out, "ex5_multidomain_scalability")
    dom = suite("domains_scaling", ["amtp", "secollab"], a.results)
    n_total = max(int(r["N_total"]) for rows in dom.values() for r in ok(rows))
    for shape, (name, sym) in SHAPES.items():
        fig, ax = paper_fig()
        xs = set()
        for s, rows in dom.items():
            xs |= line(ax, s, [r for r in rows if r["shape"] == shape and int(r["kQ"]) == a.xkq],
                       "domains", "end_to_end_ms_median")
        rq_axis(ax, sorted(xs))
        save(fig, ax, os.path.join(d, f"{SHAPE_FILE[shape]}_time_vs_D"),
             f"Multi-domain scalability · {name}  {sym}", "Number of domains D",
             "Total time per query (ms)",
             [f"{n_total:,} files in total (split over the D domains)", f"$k_Q$ = {a.xkq}", f"{name} query"])


# ---------------------------------------------------------------- AMTP vs Du [7]: the baseline with the same detection
def vs_du(a, out):
    d = os.path.join(out, "vs_du")
    pair = ["amtp", "du"]
    data = suite("search_single", pair, a.results)
    for col, ylabel, name in (("end_to_end", "End-to-end time per query (ms)", "end_to_end"),
                              ("server_total", "Server time per query (ms)", "server_time"),
                              ("verify_total", "User verification time (ms)", "verify_time")):
        for xname, key, sel, xlabel, fixed in (
                ("kQ", "kQ", lambda r: int(r["N"]) == a.fix, "Keywords in the AND query $k_Q$",
                 ["1 domain", f"{a.fix:,} files", "AND query"]),
                ("files", "N", lambda r: int(r["kQ"]) == a.kq, "Files in the domain",
                 ["1 domain", f"$k_Q$ = {a.kq}", "AND query"])):
            fig, ax = paper_fig()
            xs = set()
            for s, rows in data.items():
                xs |= line(ax, s, [r for r in rows if sel(r)], key, f"{col}_ms_median")
            rq_axis(ax, sorted(xs))
            if xname == "files":
                kfmt(ax)
            save(fig, ax, os.path.join(d, "search", f"{name}_vs_{xname}"),
                 f"AMTP vs Du [7] · search · {ylabel.split(' (')[0].lower()}", xlabel, ylabel, fixed)

    data = suite("verify_single", pair, a.results)
    by_target = {}
    for rows in data.values():
        for r in ok(rows):
            if int(r["N"]) == a.fix:
                by_target.setdefault(int(r["target_results"]), []).append(int(r["rQ"]))
    real = {t: statistics.median(v) for t, v in by_target.items()}
    for col, ylabel, name in (("end_to_end", "End-to-end time per query (ms)", "end_to_end"),
                              ("server_total", "Server time per query (ms)", "server_time"),
                              ("verify_total", "User verification time (ms)", "verify_time")):
        fig, ax = paper_fig()
        for s, rows in data.items():
            line(ax, s, [r for r in rows if int(r["N"]) == a.fix], "target_results", f"{col}_ms_median",
                 xmap=lambda k: real[int(k)])
        rq_axis(ax, sorted(real.values()))
        save(fig, ax, os.path.join(d, "vary_returned_files", f"{name}_vs_rQ"),
             f"AMTP vs Du [7] · vary returned files · {ylabel.split(' (')[0].lower()}", "Returned files $r_Q$",
             ylabel, ["1 domain", f"{a.fix:,} files", "one-keyword query"])

    data = suite("tamper_detection", pair, a.results)
    rq = statistics.median(int(r["rQ"]) for r in ok(data["amtp"]) if r["tamper"] == "modify")
    for kind, xlabel in (("modify", "Modified files t"), ("hide", "Hidden files t"),
                         ("inject", "Injected files t"), ("old_version", "Files sent as an old version t")):
        fig, ax = paper_fig()
        xs = set()
        for s, rows in data.items():
            xs |= line(ax, s, [r for r in rows if r["tamper"] == kind and r.get("check_mode", "early") in ("early", "")],
                       "tampered", "verify_total_ms_median")
        rq_axis(ax, sorted(xs))
        save(fig, ax, os.path.join(d, "cheating_server", f"verify_time_{kind}"),
             f"AMTP vs Du [7] · cheating server · {kind.replace('_', ' ')}", xlabel, "User verification time (ms)",
             ["1 domain", f"{a.fix:,} files", f"one keyword with ~{rq:,.0f} returned files"])
    # detection outcome, both schemes, measured
    rows_out = []
    for kind in ("modify", "hide", "inject", "old_version"):
        cells = [kind.replace("_", " ")]
        for s in pair:
            rs = [r for r in ok(data[s]) if r["tamper"] == kind and r.get("check_mode", "early") in ("early", "")]
            runs = sum(int(r["runs"]) for r in rs)
            det = sum(int(r["detected_runs"]) for r in rs)
            good = sum(int(r["result_ok_runs"] or 0) for r in rs if r.get("result_ok_runs") not in (None, ""))
            if det == runs:
                cells.append(f"detected {det}/{runs}")
            elif good == runs:
                cells.append(f"not reported, filtered out:\nresult correct {good}/{runs}")
            else:
                cells.append(f"detected {det}/{runs}")
        rows_out.append(cells)
    table_png(os.path.join(d, "cheating_server", "detection_outcome"),
              "AMTP vs Du [7] · what the user gets when the server cheats",
              ["Server attack", "AMTP", "Du [7]"], rows_out,
              ["1 domain", f"{a.fix:,} files", f"~{rq:,.0f} returned files",
               "t = 5, 10, 20, 40, 100, 1,000", "4 domains x 6 t x 30 runs = 720 runs per cell"])


def table_png(path, title, header, rows, fixed, col_w=None):
    fig, ax = plt.subplots(figsize=(10, 0.62 * (len(rows) + 1) + 1.4))
    ax.axis("off")
    t = ax.table(cellText=rows, colLabels=header, loc="center", cellLoc="center", colWidths=col_w)
    t.auto_set_font_size(False)
    t.set_fontsize(9.5)
    t.scale(1, 2.3)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor("#c9c9c9")
        txt = cell.get_text().get_text()
        if r == 0:
            cell.set_facecolor("#e8eef7")
            cell.get_text().set_weight("bold")
        elif c > 0 and (txt.startswith("✓") or txt.startswith("detected 720")):
            cell.get_text().set_color("#1a7f37")
        elif c > 0 and (txt.startswith("✗") or txt.startswith("detected 0")):
            cell.get_text().set_color("#b42318")
    ax.set_title(title, fontsize=13, color=INK, pad=12)
    fig.text(0.01, 0.015, "Fixed: " + " · ".join(fixed), color=INK2, fontsize=8.5, wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(f"{path}.png", facecolor=SURFACE, dpi=160)
    plt.close(fig)
    print(f"-> {os.path.relpath(path)}.png")


# ---------------------------------------------------------------- capability / security table (qualitative)
def capability(a, out):
    """features from each baseline's paper (see the header of each *_sim.py); attack rows measured in the tamper
    suite: ✓ = verification rejected in every run, ✗ = accepted in every run."""
    data = suite("tamper_detection", v4.SCHEMES, a.results)

    def attack(s, kind):
        rs = [r for r in data[s] if r["tamper"] == kind and r.get("check_mode", "early") in ("early", "")]
        if rs and all(r["status"] == "N/A" for r in rs):
            return "N/A\n(no files returned)"
        rs = ok(rs)
        runs = sum(int(r["runs"]) for r in rs)
        det = sum(int(r["detected_runs"]) for r in rs)
        good = sum(int(r["result_ok_runs"] or 0) for r in rs if r.get("result_ok_runs") not in (None, ""))
        if det == runs:
            return "✓"
        if det == 0 and good == runs:
            return "filtered out\n(not reported)"
        if det == 0:
            return "✗"
        return f"{det}/{runs}"

    feats = {"amtp": ["AND, OR, nested", "✓", "✓", "✓"],
             "du": ["AND only", "✗", "✗", "✓"],
             "chen": ["AND only", "✗", "✓", "✗ (bitmap)"],
             "secollab": ["AND, OR, nested", "✓", "✗", "✓"]}
    header = ["Scheme", "Boolean query", "Multi-domain", "Dynamic\nupdate", "Returns\nfiles",
              "Modified\nfile", "Hidden file\n(completeness)", "Injected\nfile", "Old version\n(freshness)"]
    rows = [[NAME[s]] + feats[s] + [attack(s, k) for k in ("modify", "hide", "inject", "old_version")]
            for s in v4.SCHEMES]
    fig, ax = plt.subplots(figsize=(13, 4.3))
    ax.axis("off")
    t = ax.table(cellText=rows, colLabels=header, loc="center", cellLoc="center",
                 colWidths=[0.11, 0.12, 0.09, 0.08, 0.08, 0.115, 0.12, 0.11, 0.115])
    t.auto_set_font_size(False)
    t.set_fontsize(9.5)
    t.scale(1, 3.0)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor("#c9c9c9")
        txt = cell.get_text().get_text()
        if r == 0:
            cell.set_facecolor("#e8eef7")
            cell.get_text().set_weight("bold")
        elif c >= 5:
            cell.set_facecolor("#f6f8fb")
        if r > 0 and txt.startswith("✓"):
            cell.get_text().set_color("#1a7f37")
        elif r > 0 and txt.startswith("✗"):
            cell.get_text().set_color("#b42318")
    ax.set_title("Capability and security comparison", fontsize=13, color=INK, pad=6)
    ax.text(0.725, 0.97, "server attack detected by the user (measured)", transform=ax.transAxes,
            ha="center", fontsize=9, color=INK2)
    fig.text(0.01, 0.02, "Fixed (attack columns): 1 domain · 100,000 files · ~2,000 returned files · "
             "t = 5 … 1,000 tampered files · 720 runs per cell (4 domains × 6 t × 30 runs) · "
             "✓ = rejected in every run, ✗ = accepted in every run", color=INK2, fontsize=8.5, wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    path = os.path.join(out, "capability_table", "capability_security_table")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(f"{path}.png", facecolor=SURFACE, dpi=160)
    plt.close(fig)
    print(f"-> {os.path.relpath(path)}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="run 2 results (new_result)")
    ap.add_argument("--old", required=True, help="run 1 results (results_aws), for split / merge")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fix", type=int, default=100_000)
    ap.add_argument("--kq", type=int, default=5)
    ap.add_argument("--xkq", type=int, default=4)
    ap.add_argument("--theta", type=int, default=64)
    a = ap.parse_args()
    for fn in (ex1, ex2, ex3, ex4, ex5, vs_du, capability):
        fn(a, a.out)


if __name__ == "__main__":
    main()
