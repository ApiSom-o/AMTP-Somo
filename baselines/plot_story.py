"""Story figures for the paper, from one merged run folder (default: the γ-with-v cloud run). Line charts only.

    .venv/bin/python baselines/plot_story.py                     # -> results/new_amtp_result/graph_op/
    .venv/bin/python baselines/plot_story.py --run <dir> --out <dir>

graph_op/main/    the paper's story: AMTP against every scheme the figure compares
  detection_vs_tampered      attack types detected against the number of tampered files (tamper_detection)
  proof_size_vs_rq           proof size against r_Q, one domain (verify_single)
  proof_size_vs_rq_4domains  proof size against r_Q, query over 4 domains (verify_multi)
  query_vs_domains           query time against the number of deployed domains (exp5_domains)
  update_vs_domains          AMTP update of one domain against the number of domains (exp5_domains)
  max_partition_vs_batch     largest partition over the update stream, AMTP vs Static-MT (θ_max = 64)
  update_vs_batch            update time over the same stream, AMTP vs Static-MT
graph_op/limits/  where a baseline is faster (for the discussion), each labelled with what that baseline misses
  e2e_vs_rq                  end-to-end time against r_Q, with the AMTP / SE-COLLAB crossover
  e2e_vs_files               end-to-end time against N (search_single)
  server_vs_files            server time against N (search_single)
  e2e_vs_kq                  end-to-end time against k_Q at N = 100,000 (search_single)

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

SCHEMES = ("amtp", "secollab", "du", "chen")


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


# ---------------------------------------------------------------- proof size
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
    cross = crossover(xa, ya, ys, logx=True)
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


def crossover(xa, ya, yb, logx):
    """x where series a stops being below series b (interpolated on log y, and on log x if logx)"""
    fx = math.log if logx else (lambda v: v)
    gx = math.exp if logx else (lambda v: v)
    for i in range(len(xa) - 1):
        d0, d1 = math.log(ya[i] / yb[i]), math.log(ya[i + 1] / yb[i + 1])
        if d0 < 0 <= d1:
            t = d0 / (d0 - d1)
            return gx(fx(xa[i]) + t * (fx(xa[i + 1]) - fx(xa[i])))
    return None


ATTACK_SHORT = {"modify": "modified", "hide": "hidden", "inject": "injected", "old_version": "old-version"}


def missed(run, s):
    """the attacks a scheme does not detect in every run, or cannot be tested on (N/A)"""
    det = collections.defaultdict(lambda: [0, 0])
    for x in rows(run, s, "tamper_detection"):
        if x["tamper"] == "none":
            continue
        d = det[x["tamper"]]
        if x["status"] == "ok":
            d[0] += int(x["detected_runs"] or 0)
            d[1] += int(x["runs"] or 0)
    return [ATTACK_SHORT[a] for a in ATTACK_SHORT if det[a][1] == 0 or det[a][0] < det[a][1]]


def search_rows(run, s, **fix):
    return ok_rows(run, s, "search_single",
                   lambda x: x.get("shape", "AND") == "AND" and all(x[k] == v for k, v in fix.items()))


def miss_labels(ax, run, data, keys, fmt):
    """at each line's end: its value and the attacks it misses, so speed is read next to what it buys"""
    ends = sorted(((data[NAME[s]][1][-1], s) for s in keys))
    lo, hi = (math.log(v) for v in ax.get_ylim())
    prev = None
    for y, s in ends:                                         # keep labels ≥ 7% of the axis height apart
        ly = math.log(y)
        if prev is not None and (ly - prev) / (hi - lo) < 0.07:
            ly = prev + 0.07 * (hi - lo)
        prev = ly
        m = missed(run, s)
        text = fmt(y) + "  ·  " + ("detects every attack" if not m else "misses " + ", ".join(m))
        ax.annotate(text, (data[NAME[s]][0][-1], math.exp(ly)), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=INK2)


# 11. end-to-end time against the number of files, with what each scheme misses
def e2e_vs_files(run, out, points):
    fig, ax = new_fig(7.6, 5.0)
    keys = ("amtp", "secollab", "du", "chen")
    data = {NAME[s]: series(search_rows(run, s, kQ="5"), lambda x: int(x["N"]), "end_to_end_ms") for s in keys}
    for s in keys:
        xs, ys = data[NAME[s]]
        color, marker = STYLE[s]
        ax.plot(xs, ys, color=color, marker=marker, markersize=7, markeredgecolor="white", linewidth=2.2,
                label=NAME[s])
        points.extend(("e2e_vs_files", NAME[s], x, y) for x, y in zip(xs, ys))
    ax.set_yscale("log")
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    (xa, ya), ys = data[NAME["amtp"]], data[NAME["secollab"]][1]
    cross = crossover(xa, ya, ys, logx=False)
    ax.set_xlim(0, xa[-1] * 1.75)
    ax.set_ylim(0.2, 60)
    ax.xaxis.set_major_locator(FixedLocator(xa))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:,.0f}k"))
    ax.yaxis.set_major_locator(FixedLocator([0.3, 1, 3, 10, 30]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    if cross:
        ax.axvline(cross, color=AXIS, linewidth=1, linestyle=(0, (3, 3)))
        ax.text(cross - 1500, 0.24, f"AMTP faster ← {cross / 1000:,.0f}k files", ha="right", va="bottom",
                fontsize=8.5, color=INK2)
        points.append(("e2e_vs_files", "crossover AMTP = SE-COLLAB", cross, None))
    miss_labels(ax, run, data, keys, lambda y: f"{y:,.1f} ms")
    labels(ax, "Files in the domain", "End-to-end time per query (ms)")
    save(fig, ax, out, "e2e_vs_files",
         f"SE-COLLAB only overtakes AMTP above ~{cross / 1000:,.0f}k files — and it misses hidden and "
         f"injected results",
         "AND query with k_Q = 5 keywords · one domain · 80 queries per point · right-hand labels: the "
         "attacks a scheme does not detect (attack_detection.png)")


# 12. server time against the number of files
def server_vs_files(run, out, points):
    fig, ax = new_fig(7.6, 5.0)
    keys = ("amtp", "secollab", "du", "chen")
    data = {NAME[s]: series(search_rows(run, s, kQ="5"), lambda x: int(x["N"]), "server_total_ms") for s in keys}
    for s in keys:
        xs, ys = data[NAME[s]]
        color, marker = STYLE[s]
        ax.plot(xs, ys, color=color, marker=marker, markersize=7, markeredgecolor="white", linewidth=2.2,
                label=NAME[s])
        points.extend(("server_vs_files", NAME[s], x, y) for x, y in zip(xs, ys))
    ax.set_yscale("log")
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    xa = data[NAME["amtp"]][0]
    ax.set_xlim(0, xa[-1] * 1.75)
    ax.set_ylim(0.012, 40)
    ax.xaxis.set_major_locator(FixedLocator(xa))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:,.0f}k"))
    ax.yaxis.set_major_locator(FixedLocator([0.01, 0.03, 0.1, 0.3, 1, 3, 10]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    miss_labels(ax, run, data, keys, lambda y: f"{y:,.2f} ms" if y < 1 else f"{y:,.1f} ms")
    labels(ax, "Files in the domain", "Server time per query (ms)")
    a, se = data[NAME["amtp"]][1], data[NAME["secollab"]][1]
    lo, hi = min(s / x for s, x in zip(se, a)), max(s / x for s, x in zip(se, a))
    save(fig, ax, out, "server_vs_files",
         f"AMTP's server answers {lo:.1f}–{hi:.0f}× faster than SE-COLLAB's at every size",
         "AND query with k_Q = 5 keywords · one domain · server = search + proof generation · Chen [40] "
         "and Du [7] do less server work but miss attacks (right-hand labels)")


# 13. end-to-end time against the number of query keywords
def e2e_vs_kq(run, out, points):
    fig, ax = new_fig(7.6, 5.0)
    keys = ("amtp", "secollab", "du", "chen")
    data = {NAME[s]: series(search_rows(run, s, N="100000"), lambda x: int(x["kQ"]), "end_to_end_ms")
            for s in keys}
    for s in keys:
        xs, ys = data[NAME[s]]
        color, marker = STYLE[s]
        ax.plot(xs, ys, color=color, marker=marker, markersize=7, markeredgecolor="white", linewidth=2.2,
                label=NAME[s])
        points.extend(("e2e_vs_kq", NAME[s], x, y) for x, y in zip(xs, ys))
    ax.set_yscale("log")
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    (xa, ya), ys = data[NAME["amtp"]], data[NAME["secollab"]][1]
    cross = crossover(xa, ya, ys, logx=False)
    ax.set_xlim(0, xa[-1] * 1.75)
    ax.set_ylim(0.2, 150)
    ax.xaxis.set_major_locator(FixedLocator(xa))
    ax.yaxis.set_major_locator(FixedLocator([0.3, 1, 3, 10, 30, 100]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    if cross:
        ax.axvline(cross, color=AXIS, linewidth=1, linestyle=(0, (3, 3)))
        points.append(("e2e_vs_kq", "crossover AMTP = SE-COLLAB", cross, None))
    miss_labels(ax, run, data, keys, lambda y: f"{y:,.1f} ms")
    labels(ax, "Keywords in the query $k_Q$", "End-to-end time per query (ms)")
    save(fig, ax, out, "e2e_vs_kq",
         f"With {xa[0]} keywords AMTP is {ys[0] / ya[0]:.1f}× faster than SE-COLLAB; with more, "
         f"SE-COLLAB is faster but misses hidden and injected results",
         f"dashed line: AMTP = SE-COLLAB at k_Q ≈ {cross:.1f} · AND query · one domain of 100,000 files · 80 queries per point · right-hand labels: the attacks a "
         "scheme does not detect (attack_detection.png)")


EX5_FIXED ="query on one domain of 5,000 files while 1–32 domains are deployed · mixed query shapes"


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
# Global-MT (unversioned) is not comparable; Global-MT(v) is drawn when its rows exist, either in the θ = 64
# folder or in a separate splitmerge_*_t64_<tag> folder (a run on another machine with the same seed)
SM_ALL = ("AMTP", "Static-MT", "Global-MT(v)")


def sm_rows(run, name):
    d = sorted(glob.glob(os.path.join(run, "amtp", "splitmerge_*_t64")) +
               glob.glob(os.path.join(run, "amtp", "splitmerge_*_t64_*")))
    out = []
    for folder in d:
        with open(os.path.join(folder, name)) as f:
            out += list(csv.DictReader(f))
    return out


def sm_variants(rs):
    return tuple(v for v in SM_ALL if any(x["variant"] == v for x in rs))


SM_SETUP = ("100,000 files · then 100,000 more, 95% of them into one hot group, then 65% of that group deleted · "
            "b = 100 files per batch · Static-MT = AMTP's starting layout with the same placement rule, never split")


def sm_axes(ax, rs, run):
    switch = min(int(x["batch"]) for x in sm_rows(run, "updates.csv") if x["phase"] == "hot_delete")
    ax.axvline(switch, color=AXIS, linewidth=1, linestyle=(0, (3, 3)))
    top = ax.get_ylim()[1]
    ax.text(switch * 0.5, top, "insert phase", ha="center", va="top", fontsize=8.5, color=INK2)
    ax.text((switch + max(int(x["batch"]) for x in rs)) / 2, top, "hot-key delete phase", ha="center",
            va="top", fontsize=8.5, color=INK2)


def max_partition(run, out, points):
    rs = [x for x in sm_rows(run, "layout.csv") if x["variant"] in SM_ALL and x["run"] == "0"]
    SM_VARIANTS = sm_variants(rs)
    fig, ax = new_fig(6.6, 5.0)
    data = {}
    for v in SM_VARIANTS:
        r = sorted((int(x["batch"]), float(x["max_partition"])) for x in rs if x["variant"] == v)
        data[v] = ([b for b, _ in r], [m for _, m in r])
    lines(ax, data, {v: EXP4_STYLE[v] for v in SM_VARIANTS}, points, "max_partition_vs_batch",
          lambda y: f"{y:,.0f}")
    ax.axhline(64, color=AXIS, linewidth=1)
    ax.set_yscale("log")                                      # 64 next to ~100,000: a linear axis hides AMTP
    ax.text(300, 64 * 1.15, r"$\theta_{\max}$ = 64", va="bottom", fontsize=9, color=INK2)
    ax.set_ylim(20, max(max(y) for _, y in data.values()) * 6)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    labels(ax, "Update batch", "Largest partition (files, log scale)")
    ax.legend(frameon=False, fontsize=9.5, loc="center left")         # the empty band between 64 and ~10,000
    sm_axes(ax, rs, run)
    peak = max(data["Static-MT"][1])
    save(fig, ax, out, "max_partition_vs_batch",
         f"AMTP keeps every partition within $\\theta_{{\\max}}$ = 64; Static-MT's largest grows to {peak:,.0f}",
         SM_SETUP + (" · Global-MT(v) = one partition" if "Global-MT(v)" in SM_VARIANTS else ""))


def update_vs_batch(run, out, points, window=50):
    rs = [x for x in sm_rows(run, "updates.csv") if x["variant"] in SM_ALL and x["run"] == "0"]
    SM_VARIANTS = sm_variants(rs)
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
    ax.yaxis.set_major_locator(FixedLocator([0.5, 1, 2, 5, 10, 20, 50]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    labels(ax, "Update batch", "Update time per batch (s)")
    ax.legend(frameon=False, fontsize=9.5, loc="lower right", bbox_to_anchor=(1, 0.02))   # below AMTP's delete phase
    ax.set_ylim(ax.get_ylim()[0], ax.get_ylim()[1] * 1.6)
    sm_axes(ax, rs, run)
    allm = {v: med([float(x["update_ms"]) for x in rs if x["variant"] == v]) for v in SM_VARIANTS}
    nb = len([x for x in rs if x["variant"] == "AMTP"])
    title = (f"By splitting hot partitions, AMTP updates {allm['Static-MT'] / allm['AMTP']:.1f}× faster than "
             f"Static-MT over the whole stream")
    if "Global-MT(v)" in allm:
        title += f" and {allm['Global-MT(v)'] / allm['AMTP']:.1f}× faster than one partition (Global-MT(v))"
    save(fig, ax, out, "update_vs_batch", title,
         f"{SM_SETUP} · θ_max = 64 · γ with v · each point = median of {window} batches · "
         f"ratio = medians over all {nb:,} batches")

# ---------------------------------------------------------------- attack detection as lines
def detection_vs_tampered(run, out, points):
    """per scheme and number of tampered files t: how many of the 4 attack types are detected in every run"""
    res = {}
    for s in SCHEMES:
        agg = collections.defaultdict(lambda: [0, 0])
        for x in rows(run, s, "tamper_detection"):
            if x["tamper"] != "none" and x["status"] == "ok":
                a = agg[(int(x["tampered"]), x["tamper"])]
                a[0] += int(x["detected_runs"] or 0)
                a[1] += int(x["runs"] or 0)
        ts = sorted({t for t, _ in agg})
        res[s] = (ts, [sum(1 for k in ATTACK_SHORT if agg[(t, k)][1] and agg[(t, k)][0] == agg[(t, k)][1])
                       for t in ts])
    fig, ax = new_fig(7.6, 5.0)
    seen = collections.Counter()
    for s in SCHEMES:                                         # equal lines are drawn 0.08 apart, and said so
        ts, ys = res[s]
        tie = seen[ys[0]]
        off = 0.12 * tie
        seen[ys[0]] += 1
        color, marker = STYLE[s]
        ax.plot(ts, [y - off for y in ys], color=color, marker=marker, markersize=7, markeredgecolor="white",
                linewidth=2.2, label=NAME[s])
        m = missed(run, s)
        na = [ATTACK_SHORT[k] for k in ATTACK_SHORT
              if not any(x["tamper"] == k and x["status"] == "ok" for x in rows(run, s, "tamper_detection"))]
        text = f"{ys[-1]} of 4"
        if na:
            text = f"{ys[-1]} of {4 - len(na)} applicable  ·  returns no files"
        elif m:
            text += "  ·  misses " + ", ".join(m)
        else:
            text += "  ·  every attack"
        dy = 0 if not tie and seen[ys[0]] == 1 and not any(res[o][1][0] == ys[0] for o in SCHEMES if o != s) \
            else (6 if not tie else -8)
        ax.annotate(text, (ts[-1], ys[-1] - off), xytext=(8, dy), textcoords="offset points", va="center",
                    fontsize=8.5, color=INK2)
        points.extend(("detection_vs_tampered", NAME[s], t, y) for t, y in zip(ts, ys))
    ts = res["amtp"][0]
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(ts))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.set_xlim(ts[0] * 0.75, ts[-1] * 14)
    ax.set_ylim(-0.3, 4.9)
    ax.set_yticks(range(5))
    ax.legend(frameon=False, fontsize=9.5, loc="upper left", ncol=4)
    labels(ax, "Tampered files t (of 2,021 returned)", "Attack types detected in every run (of 4)")
    save(fig, ax, out, "detection_vs_tampered",
         "Only AMTP detects all 4 attack types, whether 5 or 1,000 files are tampered",
         "modified file, hidden result, injected result, old file version · keyword with 2,021 results in "
         "100,000 files · D1–D4 · 15 runs per domain and t · no false alarm by any scheme · equal lines drawn "
         "slightly apart")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=os.path.join(HERE, "results", "new_amtp_result", "gamma_with_v"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "new_amtp_result", "graph_op"))
    a = ap.parse_args()
    points = []
    main_dir, limits_dir = os.path.join(a.out, "main"), os.path.join(a.out, "limits")
    for fn in (detection_vs_tampered, proof_size, proof_size_multi, query_vs_domains, update_vs_domains,
               max_partition, update_vs_batch):
        fn(a.run, main_dir, points)
    for fn in (e2e_vs_rq, e2e_vs_files, server_vs_files, e2e_vs_kq):
        fn(a.run, limits_dir, points)
    with open(os.path.join(a.out, "figure_points.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["figure", "series", "x", "value"])
        w.writerows(points)
    print(len(points), "points ->", os.path.relpath(os.path.join(a.out, "figure_points.csv")))


if __name__ == "__main__":
    main()
