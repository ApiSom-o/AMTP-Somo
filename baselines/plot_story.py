"""Story figures for the paper, from one merged run folder (default: the γ-with-v cloud run).

    .venv/bin/python baselines/plot_story.py                     # -> results/new_amtp_result/graph_op/
    .venv/bin/python baselines/plot_story.py --run <dir> --out <dir>

  1. attack_detection    which scheme detects which attack, over every run (tamper_detection CSVs)
  2. proof_size_vs_rq    proof size against the number of returned files r_Q (verify_single CSVs)
  3. e2e_breakdown       where the end-to-end time of one query goes, per scheme (search_single CSVs)
  4. amtp_verify_checks  AMTP's verification time split over its checks (same point as 3)
  5. proof_size_vs_rq_4domains   proof size against r_Q, query over 4 domains (verify_multi CSVs)
  6. e2e_vs_rq                   end-to-end time against r_Q, with the AMTP / SE-COLLAB crossover
  7. query_vs_domains            query time against the number of deployed domains (exp5_domains)
  8. update_vs_domains           AMTP update of one domain against the number of domains (exp5_domains)
  9. max_partition_vs_batch      largest partition over the update stream, AMTP vs Static-MT (θ_max = 64)
 10. update_vs_batch             update time over the same stream, AMTP vs Static-MT

Statistics as plot_paper.py: each query's value is the median of its timed runs; a point is the median
over its queries. Sizes in KB = 1000 B. Colours and markers of the schemes come from plot_results.py.
"""
import argparse
import collections
import csv
import glob
import math
import os
import statistics
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from plot_results import (AXIS, EXP4_STYLE, INK, INK2, KB, NAME, STYLE, SURFACE, FixedLocator,
                          FuncFormatter, new_fig, plt, rq_axis)  # noqa: E402

SCHEMES = ("amtp", "chen", "du", "secollab")
ATTACKS = [("none", "Honest response\n(no false alarm)"), ("modify", "Modified file"),
           ("hide", "Hidden result"), ("inject", "Injected result"), ("old_version", "Old file version")]
CHECK_NAME = {"ct": "ct", "comp": "comp", "papc": "papc", "part": "part", "idx": "idx", "anchor": "anchor",
              "ctx": "ctx"}
GOOD, BAD, NA = "#d9efe3", "#f8dcd8", "#ecebe7"          # cell fills; the ✓ / ✗ / N/A text carries the meaning


def rows(run, scheme, suite):
    path = os.path.join(run, scheme, f"{scheme}_{suite}.csv")
    with open(path) as f:
        return list(csv.DictReader(f))


def med(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def num(x, col):
    v = x.get(col + "_median") or x.get(col)
    return float(v) if v not in (None, "") else None


def save(fig, ax, out, name, title, fixed, note_below=False):
    """wrapped title; the fixed values under the title, or under the plot when the top holds column labels"""
    h = fig.get_figheight() * 72                                  # figure height in points
    t_lines = textwrap.wrap(title, 62, break_on_hyphens=False)
    s_lines = textwrap.wrap("fixed: " + fixed, 110 if note_below else 96, break_on_hyphens=False)
    t_h = (len(t_lines) * 12.5 * 1.3 + 10) / h                     # title block, as a figure fraction
    s_h = (len(s_lines) * 8.5 * 1.35 + 8) / h                      # fixed-values block
    top = 1 - t_h - (0 if note_below else s_h) - (0.03 if note_below else 0)
    fig.tight_layout(rect=(0, s_h + 0.01 if note_below else 0, 1, top))
    fig.text(0.02, 0.985, "\n".join(t_lines), fontsize=12.5, color=INK, va="top", ha="left")
    sub = "\n".join(s_lines)
    if note_below:
        fig.text(0.02, 0.012, sub, fontsize=8.5, color=INK2, va="bottom", ha="left")
    else:
        fig.text(0.02, 0.985 - t_h, sub, fontsize=8.5, color=INK2, va="top", ha="left")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, name + ".png")
    fig.savefig(path, facecolor=SURFACE, dpi=200)
    plt.close(fig)
    print("->", os.path.relpath(path))


# ---------------------------------------------------------------- 1. attack detection
def attack_detection(run, out, points):
    table = {}
    for s in SCHEMES:
        agg = collections.defaultdict(lambda: {"det": 0, "runs": 0, "na": False, "checks": set(), "dom": set()})
        for x in rows(run, s, "tamper_detection"):
            a = agg[x["tamper"]]
            a["dom"].add(x["domain"])
            if x["status"] != "ok":
                a["na"] = True
                continue
            a["det"] += int(x["detected_runs"] or 0)
            a["runs"] += int(x["runs"] or 0)
            if x.get("failed_check"):
                a["checks"].add(x["failed_check"])
        table[s] = agg
    fig, ax = new_fig(7.6, 5.2)
    ax.grid(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_xlim(-0.5, len(SCHEMES) - 0.5)
    ax.set_ylim(len(ATTACKS) - 0.5, -0.5)
    for j, s in enumerate(SCHEMES):
        for i, (key, _) in enumerate(ATTACKS):
            a = table[s].get(key)
            if a is None or (a["na"] and not a["runs"]):
                fill, text = NA, "N/A"
            elif key == "none":                                   # honest: the good outcome is "nothing flagged"
                false = a["det"]
                fill, text = (GOOD, f"✓ 0 / {a['runs']}") if false == 0 else (BAD, f"✗ {false} / {a['runs']}")
            else:
                rate = a["det"] / a["runs"]
                mark = "✓" if rate == 1 else "✗"
                fill = GOOD if rate == 1 else BAD
                text = f"{mark} {rate:.0%}"
                if a["checks"]:
                    text += "\ncheck: " + ", ".join(sorted(CHECK_NAME.get(c, c) for c in a["checks"]))
            ax.add_patch(plt.Rectangle((j - 0.47, i - 0.44), 0.94, 0.88, facecolor=fill, edgecolor=SURFACE,
                                       linewidth=2))
            ax.text(j, i, text, ha="center", va="center", fontsize=10, color=INK)
            points.append(("attack_detection", NAME[s], key, text.replace("\n", " ")))
    ax.set_xticks(range(len(SCHEMES)))
    ax.set_xticklabels([NAME[s] for s in SCHEMES], fontsize=10.5, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(ATTACKS)))
    ax.set_yticklabels([lab for _, lab in ATTACKS], fontsize=10, color=INK)
    ax.tick_params(length=0)
    runs = table["amtp"]["modify"]["runs"]
    save(fig, ax, out, "attack_detection", "Only AMTP detects every attack, with no false alarm",
         f"one domain of 100,000 files · keyword with 2,021 results · t = 5…1000 files changed · "
         f"domains D1–D4 · {runs} attacked responses per cell · ✓ = detected in every run; "
         f"N/A = Chen returns no files, so a file cannot be modified or replaced", note_below=True)


# ---------------------------------------------------------------- 2. proof size
def proof_size(run, out, points):
    fig, ax = new_fig(6.6, 5.0)
    ticks = []
    last = {}
    for s in ("amtp", "secollab", "du"):
        by = collections.defaultdict(lambda: ([], []))
        for x in rows(run, s, "verify_single"):
            if x.get("proof_bytes") and x.get("status", "ok") == "ok":
                rq, pb = by[int(x["target_results"])]
                rq.append(float(x["rQ"]))
                pb.append(float(x["proof_bytes"]))
        xs = [med(by[k][0]) for k in sorted(by)]
        ys = [med(by[k][1]) / KB for k in sorted(by)]
        color, marker = STYLE[s]
        ax.plot(xs, ys, color=color, marker=marker, markersize=7, markeredgecolor="white", linewidth=2.2,
                label=NAME[s])
        ticks = xs
        last[s] = (xs[-1], ys[-1])
        points.extend(("proof_size_vs_rq", NAME[s], x, y) for x, y in zip(xs, ys))
    for s, (x, y) in last.items():                       # direct labels on the last point only
        ax.annotate(f"{y:,.0f} KB", (x, y), xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=9, color=INK2)
    ax.set_yscale("log")
    rq_axis(ax, [round(t) for t in ticks])
    ax.set_xlim(ticks[0] * 0.7, ticks[-1] * 2.2)
    ax.set_xlabel("Returned files $r_Q$ (median per target group)", color=INK2, fontsize=11.5)
    ax.set_ylabel("Proof size (KB)", color=INK2, fontsize=11.5)
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    a, se, du = last["amtp"][1], last["secollab"][1], last["du"][1]
    save(fig, ax, out, "proof_size_vs_rq",
         f"At {last['amtp'][0]:,.0f} results, AMTP's proof is {se / a:.1f}× smaller than SE-COLLAB's "
         f"and {du / a:.0f}× smaller than Du's",
         "single keyword · one domain of 100,000 files · median over domains D1–D4 · "
         "Chen [40] records no separate proof object (0 B), so it is not shown")


# ---------------------------------------------------------------- 3. end-to-end breakdown
PARTS = [("query_gen_ms", "Query generation (DU)", "#c9c6bf"),
         ("server_total_ms", "Search + proof (server)", "#8a8985"),
         ("verify_total_ms", "Verification (DU)", "#2a78d6"),
         ("du_decrypt_ms", "Decrypt / decode (DU)", "#dcd9d2")]


def point_rows(run, s, kq="5", n="100000"):
    return [x for x in rows(run, s, "search_single") if x["kQ"] == kq and x["N"] == n
            and x.get("status", "ok") == "ok"]


def e2e_breakdown(run, out, points):
    order = ["du", "chen", "secollab", "amtp"]                # bottom → top: AMTP on top
    fig, ax = new_fig(7.4, 4.4)
    ax.grid(axis="y", visible=False)
    totals = {}
    for i, s in enumerate(order):
        sel = point_rows(run, s)
        left = 0.0
        for col, label, color in PARTS:
            v = med([num(x, col) for x in sel]) if sel and col + "_median" in sel[0] else None
            if not v:
                continue
            ax.barh(i, v, left=left, height=0.56, color=color, edgecolor=SURFACE, linewidth=2,
                    label=label if i == len(order) - 1 or label not in ax.get_legend_handles_labels()[1] else None)
            points.append(("e2e_breakdown", NAME[s], label, v))
            left += v
        total = med([num(x, "end_to_end_ms") for x in sel])
        totals[s] = total
        ax.text(max(left, total) + 0.15, i, f"{total:.1f} ms", va="center", fontsize=9.5, color=INK)
        points.append(("e2e_breakdown", NAME[s], "end_to_end", total))
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([NAME[s] for s in order], fontsize=10.5, color=INK)
    ax.set_xlim(0, max(totals.values()) * 1.18)
    ax.set_xlabel("Time per query (ms)", color=INK2, fontsize=11.5)
    handles, labels = ax.get_legend_handles_labels()
    uniq = dict(zip(labels, handles))
    ax.legend(uniq.values(), uniq.keys(), frameon=False, fontsize=9, loc="lower right")
    amtp = point_rows(run, "amtp")
    v = med([num(x, "verify_total_ms") for x in amtp])
    save(fig, ax, out, "e2e_breakdown",
         f"{v / totals['amtp']:.0%} of AMTP's query time is verification — the checks that prove completeness",
         "conjunctive query, k_Q = 5 · one domain of 100,000 files · median over 80 queries (4 domains × 20) · "
         "AMTP's verification covers every posting of every query key, not only the returned files")


# ---------------------------------------------------------------- 4. AMTP verification by check
CHECKS = [("verify_part_ms", "part — partition positions\n(multiproofs)"),
          ("verify_papc_ms", "papc — rebuild every\nposting commitment"),
          ("verify_idx_ms", "idx — Index Merkle Tree"),
          ("verify_ct_ms", "ct — ciphertext hashes"),
          ("verify_comp_ms", "comp — exact Boolean result")]


def amtp_checks(run, out, points):
    sel = point_rows(run, "amtp")
    vals = [(label, med([num(x, col) for x in sel])) for col, label in CHECKS]
    total = med([num(x, "verify_total_ms") for x in sel])
    fig, ax = new_fig(7.2, 4.3)
    ax.grid(axis="y", visible=False)
    ys = list(range(len(vals)))[::-1]
    for y, (label, v) in zip(ys, vals):
        ax.barh(y, v, height=0.56, color=STYLE["amtp"][0], edgecolor=SURFACE, linewidth=2)
        ax.text(v + total * 0.01, y, f"{v:.2f} ms ({v / total:.0%})", va="center", fontsize=9.5, color=INK)
        points.append(("amtp_verify_checks", "AMTP", label.split(" —")[0], v))
    ax.set_yticks(ys)
    ax.set_yticklabels([label for label, _ in vals], fontsize=9.5, color=INK)
    ax.set_xlim(0, max(v for _, v in vals) * 1.35)
    ax.set_xlabel("Time per query (ms)", color=INK2, fontsize=11.5)
    save(fig, ax, out, "amtp_verify_checks",
         "Most of AMTP's verification authenticates where every posting lives",
         f"same queries as the breakdown figure · total verification {total:.2f} ms · ctx and anchor "
         "checks take under 0.01 ms and are not shown")


# ---------------------------------------------------------------- line figures (one story each)
def series(xs_rows, xkey, ycol, scale=1.0):
    """median of ycol per x value (each row's own value is already the median of its timed runs)"""
    by = collections.defaultdict(list)
    for x in xs_rows:
        v = num(x, ycol)
        if v is not None:
            by[xkey(x)].append(v)
    ks = sorted(by)
    return ks, [med(by[k]) / scale for k in ks]


def lines(ax, data, styles, points, fig_name, fmt, label_pad=6, label_dy=None):
    """data: {series: (xs, ys)}; a legend plus a direct value label on each line's last point"""
    label_dy = label_dy or {}
    for s, (xs, ys) in data.items():
        color, marker, ls = styles[s]
        ax.plot(xs, ys, color=color, marker=marker, linestyle=ls, markersize=7, markeredgecolor="white",
                linewidth=2.2, label=s)
        ax.annotate(fmt(ys[-1]), (xs[-1], ys[-1]), xytext=(label_pad, label_dy.get(s, 0)),
                    textcoords="offset points", va="center", fontsize=9, color=INK2)
        points.extend((fig_name, s, x, y) for x, y in zip(xs, ys))
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")


def labels(ax, x, y):
    ax.set_xlabel(x, color=INK2, fontsize=11.5)
    ax.set_ylabel(y, color=INK2, fontsize=11.5)


def scheme_styles(*schemes):
    return {NAME[s]: STYLE[s] + ("-",) for s in schemes}


def ok_rows(run, s, suite, keep=lambda x: True):
    return [x for x in rows(run, s, suite) if x.get("status", "ok") == "ok" and keep(x)]


# 5. proof size against r_Q when the query spans 4 domains
def proof_size_multi(run, out, points):
    fig, ax = new_fig(6.6, 5.0)
    data = {}
    for s in ("amtp", "secollab"):
        rs = ok_rows(run, s, "verify_multi")
        xs, _ = series(rs, lambda x: int(x["target_results"]), "rQ")
        rq = [med([float(x["rQ"]) for x in rs if int(x["target_results"]) == k]) for k in xs]
        _, ys = series(rs, lambda x: int(x["target_results"]), "proof_bytes", KB)
        data[NAME[s]] = (rq, ys)
    lines(ax, data, scheme_styles("amtp", "secollab"), points, "proof_size_vs_rq_4domains",
          lambda y: f"{y:,.0f} KB")
    ax.set_yscale("log")
    ticks = data[NAME["amtp"]][0]
    rq_axis(ax, [round(t) for t in ticks])
    ax.set_xlim(ticks[0] * 0.7, ticks[-1] * 2.6)
    labels(ax, "Returned files $r_Q$ over 4 domains (median per target group)", "Proof size (KB)")
    a, se = data[NAME["amtp"]][1][-1], data[NAME["secollab"]][1][-1]
    save(fig, ax, out, "proof_size_vs_rq_4domains",
         f"Across 4 domains, AMTP's proof is {se / a:.1f}× smaller than SE-COLLAB's at "
         f"{data[NAME['amtp']][0][-1]:,.0f} results",
         "below ~100 results SE-COLLAB's proof is a few KB smaller · single keyword · 4 domains of 100,000 files each · 5 keywords per target group · "
         "Du [7] and Chen [40] have no multi-domain setting")


# 6. end-to-end time against r_Q (crossover with SE-COLLAB)
def e2e_vs_rq(run, out, points):
    fig, ax = new_fig(6.6, 5.0)
    data = {}
    for s in ("amtp", "secollab", "du", "chen"):
        rs = ok_rows(run, s, "verify_single")
        ks, ys = series(rs, lambda x: int(x["target_results"]), "end_to_end_ms")
        rq = [med([float(x["rQ"]) for x in rs if int(x["target_results"]) == k]) for k in ks]
        data[NAME[s]] = (rq, ys)
    lines(ax, data, scheme_styles("amtp", "secollab", "du", "chen"), points, "e2e_vs_rq",
          lambda y: f"{y:,.1f} ms" if y < 10 else f"{y:,.0f} ms")
    ax.set_yscale("log")
    ax.set_xscale("log")
    (xa, ya), ys = data[NAME["amtp"]], data[NAME["secollab"]][1]
    cross = None
    for i in range(len(xa) - 1):                              # log-log interpolation of AMTP = SE-COLLAB
        d0, d1 = math.log(ya[i] / ys[i]), math.log(ya[i + 1] / ys[i + 1])
        if d0 < 0 <= d1:
            t = d0 / (d0 - d1)
            cross = math.exp(math.log(xa[i]) + t * (math.log(xa[i + 1]) - math.log(xa[i])))
    if cross:
        ax.axvline(cross, color=AXIS, linewidth=1, linestyle=(0, (3, 3)))
        ax.text(cross * 1.06, ax.get_ylim()[0] * 1.3, f"AMTP faster ← {cross:,.0f} files → SE-COLLAB faster",
                rotation=90, ha="left", va="bottom", fontsize=8.5, color=INK2)
        points.append(("e2e_vs_rq", "crossover AMTP = SE-COLLAB", cross, None))
    rq_axis(ax, [round(t) for t in xa])
    ax.set_xlim(xa[0] * 0.7, xa[-1] * 2.4)
    labels(ax, "Returned files $r_Q$ (median per target group)", "End-to-end time per query (ms)")
    small = ys[0] / ya[0]
    du = data[NAME["du"]][1][-1] / ya[-1]
    save(fig, ax, out, "e2e_vs_rq",
         f"AMTP answers small queries {small:.0f}× faster than SE-COLLAB, and is always faster than Du "
         f"({du:.1f}× at {xa[-1]:,.0f} results)",
         f"single keyword · one domain of 100,000 files · median over D1–D4 · end-to-end = query generation "
         f"+ server + verification + decryption · Chen [40] is fastest but cannot detect a modified or "
         f"old-version file (it returns no files)")


EX5_FIXED = "query on one domain of 5,000 files while 1–32 domains are deployed · mixed query shapes"


# 7. query cost against the number of domains
def query_vs_domains(run, out, points):
    fig, ax = new_fig(6.6, 5.0)
    data = {}
    for s in ("amtp", "secollab"):
        rs = ok_rows(run, s, "exp5_domains", lambda x: x["op"] == "query")
        data[NAME[s]] = series(rs, lambda x: int(x["domains"]), "end_to_end_ms")
    lines(ax, data, scheme_styles("amtp", "secollab"), points, "query_vs_domains",
          lambda y: f"{y:,.1f} ms")
    ds = data[NAME["amtp"]][0]
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_locator(FixedLocator(ds))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlim(ds[0] * 0.8, ds[-1] * 1.9)
    ax.set_ylim(0, max(max(y) for _, y in data.values()) * 1.35)
    labels(ax, "Domains deployed", "End-to-end time per query (ms)")
    a, se = data[NAME["amtp"]][1], data[NAME["secollab"]][1]
    save(fig, ax, out, "query_vs_domains",
         f"Adding domains does not slow AMTP down: {a[0]:.1f} ms with 1 domain, {a[-1]:.1f} ms with "
         f"{ds[-1]} — {se[-1] / a[-1]:.1f}× faster than SE-COLLAB",
         EX5_FIXED + " · median over the queries")


# 8. update cost of one domain against the number of domains
def update_vs_domains(run, out, points):
    fig, ax = new_fig(6.6, 5.0)
    rs = ok_rows(run, "amtp", "exp5_domains", lambda x: x["op"] == "update_one_domain")
    data = {NAME["amtp"]: series(rs, lambda x: int(x["domains"]), "update_ms")}
    lines(ax, data, scheme_styles("amtp"), points, "update_vs_domains", lambda y: f"{y:,.0f} ms")
    ax.get_legend().remove()                                  # one series: the title names it
    ds, ys = data[NAME["amtp"]]
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_locator(FixedLocator(ds))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlim(ds[0] * 0.8, ds[-1] * 1.9)
    ax.set_ylim(0, max(ys) * 1.35)
    labels(ax, "Domains deployed", "AMTP update of one domain (ms)")
    save(fig, ax, out, "update_vs_domains",
         f"Updating one domain costs AMTP {min(ys):.0f}–{max(ys):.0f} ms whether 1 or {ds[-1]} domains exist",
         "one update batch on one domain of 5,000 files · the other domains' roots are untouched · "
         "SE-COLLAB has no per-domain update in this experiment")


# 9 and 10. split/merge over the update stream (θ_max = 64)
SM_VARIANTS = ("AMTP", "Static-MT")                           # Global-MT here is unversioned: not comparable


def sm_rows(run, name):
    d = glob.glob(os.path.join(run, "amtp", "splitmerge_*_t64"))
    with open(os.path.join(d[0], name)) as f:
        return list(csv.DictReader(f))


def sm_axes(ax, rs, run):
    switch = min(int(x["batch"]) for x in sm_rows(run, "updates.csv") if x["phase"] == "hot_delete")
    ax.axvline(switch, color=AXIS, linewidth=1, linestyle=(0, (3, 3)))
    top = ax.get_ylim()[1]
    ax.text(switch * 0.5, top, "insert phase", ha="center", va="top", fontsize=8.5, color=INK2)
    ax.text((switch + max(int(x["batch"]) for x in rs)) / 2, top, "hot-key delete phase", ha="center",
            va="top", fontsize=8.5, color=INK2)


def max_partition(run, out, points):
    rs = [x for x in sm_rows(run, "layout.csv") if x["variant"] in SM_VARIANTS and x["run"] == "0"]
    fig, ax = new_fig(6.6, 5.0)
    data = {}
    for v in SM_VARIANTS:
        r = sorted((int(x["batch"]), float(x["max_partition"])) for x in rs if x["variant"] == v)
        data[v] = ([b for b, _ in r], [m for _, m in r])
    lines(ax, data, {v: EXP4_STYLE[v] for v in SM_VARIANTS}, points, "max_partition_vs_batch",
          lambda y: f"{y:,.0f}")
    ax.axhline(64, color=AXIS, linewidth=1)
    ax.text(300, 64 + 12, r"$\theta_{\max}$ = 64", va="bottom", fontsize=9, color=INK2)
    ax.set_ylim(0, max(max(y) for _, y in data.values()) * 1.18)
    labels(ax, "Update batch", "Largest partition (posting components)")
    ax.legend(frameon=False, fontsize=9.5, loc="upper left", bbox_to_anchor=(0, 0.93))
    sm_axes(ax, rs, run)
    peak = max(data["Static-MT"][1])
    save(fig, ax, out, "max_partition_vs_batch",
         f"AMTP keeps every partition within $\\theta_{{\\max}}$ = 64; Static-MT's largest grows to {peak:,.0f}",
         "100,000 files · Zipf-skewed keywords (s = 0.95) · b = 100 files per batch · "
         "Static-MT = AMTP's initial layout, frozen")


def update_vs_batch(run, out, points, window=50):
    rs = [x for x in sm_rows(run, "updates.csv") if x["variant"] in SM_VARIANTS and x["run"] == "0"]
    fig, ax = new_fig(6.6, 5.0)
    data = {}
    for v in SM_VARIANTS:
        r = sorted((int(x["batch"]), float(x["update_ms"]) / 1000) for x in rs if x["variant"] == v)
        bs = [b for b, _ in r][window - 1::window]
        ys = [med([u for _, u in r[i - window + 1:i + 1]]) for i in range(window - 1, len(r), window)]
        data[v] = (bs, ys)
    lines(ax, data, {v: EXP4_STYLE[v] for v in SM_VARIANTS}, points, "update_vs_batch",
          lambda y: f"{y:,.1f} s")
    for (_, line) in zip(SM_VARIANTS, ax.get_lines()):
        line.set_markersize(0)
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator([2, 3, 5, 10, 20, 40]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    labels(ax, "Update batch", "Update time per batch (s)")
    ax.legend(frameon=False, fontsize=9.5, loc="upper left", bbox_to_anchor=(0, 0.93))
    ax.set_ylim(ax.get_ylim()[0], ax.get_ylim()[1] * 1.6)
    sm_axes(ax, rs, run)
    allm = {v: med([float(x["update_ms"]) for x in rs if x["variant"] == v]) for v in SM_VARIANTS}
    save(fig, ax, out, "update_vs_batch",
         f"By splitting hot partitions, AMTP updates {allm['Static-MT'] / allm['AMTP']:.1f}× faster than "
         f"Static-MT over the whole stream",
         f"100,000 files · Zipf s = 0.95 · b = 100 · θ_max = 64 · γ with v · each point = median of {window} "
         f"batches · ratio = medians over all {len(rs) // len(SM_VARIANTS):,} batches")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=os.path.join(HERE, "results", "new_amtp_result", "gamma_with_v"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "new_amtp_result", "graph_op"))
    a = ap.parse_args()
    points = []
    attack_detection(a.run, a.out, points)
    proof_size(a.run, a.out, points)
    e2e_breakdown(a.run, a.out, points)
    amtp_checks(a.run, a.out, points)
    for fn in (proof_size_multi, e2e_vs_rq, query_vs_domains, update_vs_domains, max_partition,
               update_vs_batch):
        fn(a.run, a.out, points)
    with open(os.path.join(a.out, "figure_points.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["figure", "series", "x", "value"])
        w.writerows(points)
    print(len(points), "points ->", os.path.relpath(os.path.join(a.out, "figure_points.csv")))


if __name__ == "__main__":
    main()
