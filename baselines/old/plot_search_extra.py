#!/usr/bin/env python3
"""Extra single-domain search figures (search1), trial set next to the plan figures.

    python3 old/plot_search_extra.py --results ../new_result --out ../new_result/test

Writes <out>/ex1_search/:
  server_vs_kQ, server_vs_files       server (cloud) time per query, every scheme
  speedup_vs_du_vs_kQ / _vs_files     Du time / AMTP time per query (Du = the baseline with the same tamper detection)
  ratio_<scheme>_heatmap              median end-to-end time of <scheme> / AMTP for every (files, kQ) cell
Every scheme replays the same queries (same domain, N, query_id), so ratios are taken per query and then the median.
"""
import argparse
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # baselines/ (this script now lives in baselines/old/)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "old"))
from plot_results import (INK, INK2, NAME, STYLE, load, ok, paper_fig, paper_finish, paper_line, plt,  # noqa: E402
                          rq_axis)

SCHEMES = ["amtp", "chen", "du", "secollab"]
TITLE = "Search · single domain (extra)"


def iqr(xs):
    m = statistics.median(xs)
    if len(xs) < 2:
        return m, 0.0
    q1, _, q3 = statistics.quantiles(xs, n=4, method="inclusive")
    return m, (m - q1, q3 - m)


def kfmt(ax, xname):
    if xname == "files":
        from matplotlib.ticker import FuncFormatter
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))


def keyed(rows):
    return {(r["domain"], r["N"], r["query_id"]): r for r in ok(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fix", type=int, default=100_000)
    ap.add_argument("--kq", type=int, default=5)
    ap.add_argument("--note", default="AWS r7i.4xlarge")
    a = ap.parse_args()
    out = os.path.join(a.out, "ex1_search")
    os.makedirs(out, exist_ok=True)
    data = {s: keyed(rows) for s in SCHEMES if (rows := load(s, "search_single", a.results))}
    amtp = data["amtp"]
    ns = sorted({int(k[1]) for k in amtp})
    kqs = sorted({int(r["kQ"]) for r in amtp.values()})
    base = "dataset-v4 (arXiv) · one domain, AND queries, every scheme replays the same queries"
    letter = iter("abcdefghijklmnop")

    def pick(rows, n=None, kq=None):
        return [r for r in rows if (n is None or int(r["N"]) == n) and (kq is None or int(r["kQ"]) == kq)]

    # server time per query
    for xname, xs, sel, xlabel in (("kQ", kqs, lambda rs, x: pick(rs, a.fix, x), "Keywords per query $k_Q$"),
                                   ("files", ns, lambda rs, x: pick(rs, x, a.kq), "Files in the domain")):
        fig, ax = paper_fig()
        for s, rows in data.items():
            pts = []
            for x in xs:
                v = [float(r["server_total_ms_median"]) for r in sel(rows.values(), x)]
                if v:
                    pts.append((x, *iqr(v)))
            color, marker = STYLE[s]
            paper_line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], color, marker, NAME[s])
        rq_axis(ax, xs)
        kfmt(ax, xname)
        ax.set_yscale("log")
        fixed = f"{a.fix:,} files" if xname == "kQ" else f"$k_Q$ = {a.kq}"
        paper_finish(fig, ax, next(letter), f"{TITLE}\nServer time per query vs {xlabel.split(' $')[0].lower()}",
                     xlabel, "Server time per query (ms)",
                     f"{base}, {fixed} · server = search + proof generation (SE-COLLAB: + trapdoor admission and "
                     f"PRE transform) · median over queries, bars: 25th–75th percentile · {a.note}",
                     os.path.join(out, f"server_vs_{xname}"), ncol=4)

    # Du / AMTP per query (same tamper detection, see Verify 1.2)
    du = data["du"]
    for xname, xs, sel, xlabel in (("kQ", kqs, lambda x: pick(amtp.values(), a.fix, x), "Keywords per query $k_Q$"),
                                   ("files", ns, lambda x: pick(amtp.values(), x, a.kq), "Files in the domain")):
        fig, ax = paper_fig()
        pts = []
        for x in xs:
            v = [float(du[k]["end_to_end_ms_median"]) / float(r["end_to_end_ms_median"])
                 for r in sel(x) if (k := (r["domain"], r["N"], r["query_id"])) in du]
            if v:
                pts.append((x, *iqr(v)))
        color, marker = STYLE["amtp"]
        paper_line(ax, [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts], color, marker,
                   "AMTP speed-up over Du [7]")
        ax.axhline(1, color=INK2, linewidth=1, linestyle=":")
        rq_axis(ax, xs)
        kfmt(ax, xname)
        ax.set_yscale("log")
        fixed = f"{a.fix:,} files" if xname == "kQ" else f"$k_Q$ = {a.kq}"
        paper_finish(fig, ax, next(letter), f"{TITLE}\nAMTP vs Du [7] (same tamper detection)", xlabel,
                     "Du end-to-end time / AMTP end-to-end time",
                     f"{base}, {fixed} · ratio per query, median over queries, bars: 25th–75th percentile · "
                     f"> 1 = AMTP faster · {a.note}", os.path.join(out, f"speedup_vs_du_vs_{xname}"), ncol=1)

    # heatmaps: <scheme> / AMTP end-to-end, median per (files, kQ)
    for s in ("secollab", "du", "chen"):
        if s not in data:
            continue
        other = data[s]
        grid = []
        for kq in kqs:
            row = []
            for n in ns:
                v = [float(other[k]["end_to_end_ms_median"]) / float(r["end_to_end_ms_median"])
                     for r in pick(amtp.values(), n, kq) if (k := (r["domain"], r["N"], r["query_id"])) in other]
                row.append(statistics.median(v) if v else float("nan"))
            grid.append(row)
        fig, ax = paper_fig()
        import numpy as np
        from matplotlib.colors import LogNorm, TwoSlopeNorm  # noqa: F401
        g = np.array(grid)
        lim = max(abs(np.log10(np.nanmin(g))), abs(np.log10(np.nanmax(g))), 0.3)
        im = ax.imshow(np.log10(g), cmap="RdBu", vmin=-lim, vmax=lim, origin="lower", aspect="auto")
        for i, kq in enumerate(kqs):
            for j, n in enumerate(ns):
                r = grid[i][j]
                txt = f"{r:.1f}×" if r < 10 else f"{r:.0f}×"
                ax.text(j, i, txt, ha="center", va="center", fontsize=9,
                        color="white" if abs(np.log10(r)) > lim * 0.6 else INK)
        ax.set_xticks(range(len(ns)), [f"{n // 1000}k" for n in ns])
        ax.set_yticks(range(len(kqs)), [str(k) for k in kqs])
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        ticks = [t for t in (-2, -1, 0, 1, 2) if -lim <= t <= lim]
        cb.set_ticks(ticks, labels=[f"{10 ** t:g}×" for t in ticks])
        cb.set_label(f"{NAME[s]} time / AMTP time", color=INK2, fontsize=10)
        ax.set_title(f"({next(letter)}) {TITLE}\nEnd-to-end time: {NAME[s]} / AMTP  (blue = AMTP faster)",
                     fontsize=13, color=INK)
        ax.set_xlabel("Files in the domain", color=INK2, fontsize=12)
        ax.set_ylabel("Keywords per query $k_Q$", color=INK2, fontsize=12)
        fig.text(0.01, 0.012, f"{base} · median over the 80 queries of each cell (4 domains x 20) of the per-query "
                              f"ratio · {a.note}", color=INK2, fontsize=6.6, wrap=True)
        fig.tight_layout(rect=(0, 0.05, 1, 1))
        path = os.path.join(out, f"ratio_{s}_heatmap")
        for ext in ("png", "pdf"):
            fig.savefig(f"{path}.{ext}")
        plt.close(fig)
        print(f"-> {os.path.relpath(path)}.png / .pdf")


if __name__ == "__main__":
    main()
