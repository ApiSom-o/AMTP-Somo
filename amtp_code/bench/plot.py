"""Turn benchmark CSVs into figures (PNG for slides, PDF for the LaTeX paper).

    python -m bench.plot results_exp4

Every point is a median with a 95% bootstrap confidence interval.
  * With several runs: each run is first reduced to its own median, and the
    interval is taken across runs (this is what the paper should report).
  * With one run: the interval is taken across batches/queries, and every
    figure says so in its subtitle - such a figure is a smoke test, not a result.
The numbers behind each figure are written to figure_data.csv (table view).
"""
import csv
import json
import os
import random
import statistics
import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Validated categorical slots 1-4 (blue, orange, aqua, yellow) + distinct markers,
# so identity never depends on colour alone.
STYLE = {
    "AMTP": ("#2a78d6", "o"),
    "Static-MT": ("#eb6834", "s"),
    "Global-MT": ("#1baf7a", "^"),
    "Global-MT(v)": ("#eda100", "D"),
}
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

METRICS = [
    # (file, column, title, y label, scale, log axis)
    ("updates", "update_ms", "Update latency per batch", "milliseconds", 1, False),
    ("updates", "hash_bytes", "Bytes hashed per batch", "MB hashed", 1e-6, False),
    ("layout", "max_partition", "Largest partition after updates", "live files (log scale)", 1, True),
    ("queries", "server_ms", "Server search + proof time", "milliseconds", 1, False),
    ("queries", "verify_ms", "DU verification time", "milliseconds", 1, False),
    ("queries", "proof_bytes", "Proof size", "KB", 1e-3, False),
]


def load(folder, name):
    with open(os.path.join(folder, f"{name}.csv")) as fh:
        return list(csv.DictReader(fh))


def boot_ci(values, reps=2000, seed=0):
    if len(values) < 2:
        return values[0], values[0]
    rnd = random.Random(seed)
    meds = sorted(statistics.median(rnd.choices(values, k=len(values))) for _ in range(reps))
    return meds[int(0.025 * reps)], meds[int(0.975 * reps) - 1]


def aggregate(rows, column, scale):
    """-> {variant: {skew: (median, lo, hi, n, unit)}}"""
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[(r["variant"], float(r["skew"]))][int(r["run"])].append(float(r[column]) * scale)
    out = defaultdict(dict)
    for (variant, skew), runs in by.items():
        if len(runs) > 1:
            vals, unit = [statistics.median(v) for v in runs.values()], "runs"
        else:
            vals, unit = next(iter(runs.values())), "samples (1 run)"
        lo, hi = boot_ci(vals)
        out[variant][skew] = (statistics.median(vals), lo, hi, len(vals), unit)
    return out


def style_axes(ax, title, ylabel, log):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="semibold")
    ax.set_xlabel("share of inserts sent to the hot bucket (skew)", color=INK2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    if log:
        ax.set_yscale("log")


def draw(ax, data, variants):
    ends = []
    for v in variants:
        if v not in data:
            continue
        color, marker = STYLE.get(v, ("#6250d6", "o"))
        xs = sorted(data[v])
        med = [data[v][x][0] for x in xs]
        err = [[data[v][x][0] - data[v][x][1] for x in xs],
               [data[v][x][2] - data[v][x][0] for x in xs]]
        ax.errorbar(xs, med, yerr=err, color=color, marker=marker, markersize=6,
                    linewidth=2, capsize=3, elinewidth=1, label=v,
                    markeredgecolor=SURFACE, markeredgewidth=1.5)
        ends.append((v, xs[-1], med[-1]))
    ax.margins(x=0.12)
    if ax.get_yscale() != "log":
        ax.set_ylim(bottom=0)        # after plotting, so the top still autoscales
    _direct_labels(ax, ends)


def _direct_labels(ax, ends, gap_px=11):
    """Label each line at its last point in ink (not series colour), pushing
    labels apart vertically so close lines do not print on top of each other."""
    ax.figure.canvas.draw()
    to_px = ax.transData.transform
    placed = sorted(([v, x, y, to_px((x, y))[1]] for v, x, y in ends), key=lambda e: e[3])
    for i in range(1, len(placed)):
        placed[i][3] = max(placed[i][3], placed[i - 1][3] + gap_px)
    for v, x, y, py in placed:
        dy = py - to_px((x, y))[1]
        ax.annotate(v, (x, y), xytext=(6, dy), textcoords="offset points",
                    va="center", fontsize=8, color=INK)


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "results"
    out = os.path.join(folder, "figures")
    os.makedirs(out, exist_ok=True)
    tables = {name: load(folder, name) for name in ("updates", "layout", "queries")}
    variants = [v for v in STYLE if any(r["variant"] == v for r in tables["layout"])]

    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": SURFACE})
    grid_fig, grid_axes = plt.subplots(2, 3, figsize=(15, 8.5))
    table_rows = []
    note = ""
    for i, (src, col, title, ylabel, scale, log) in enumerate(METRICS):
        data = aggregate(tables[src], col, scale)
        unit = next(iter(next(iter(data.values())).values()))[4]
        note = ("95% CI across runs" if unit == "runs"
                else "ONE RUN: CI across samples, smoke test only - not a result")
        for v in data:
            for skew, (m, lo, hi, n, u) in sorted(data[v].items()):
                table_rows.append({"metric": col, "variant": v, "skew": skew, "median": m,
                                   "ci_low": lo, "ci_high": hi, "n": n, "over": u})
        fig, ax = plt.subplots(figsize=(6.4, 4.2))
        style_axes(ax, title, ylabel, log)
        draw(ax, data, variants)
        ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.18), ncol=4)
        fig.text(0.01, 0.005, f"median, error bars = {note}", fontsize=7, color=INK2)
        fig.tight_layout()
        for ext in ("png", "pdf"):
            fig.savefig(os.path.join(out, f"{col}.{ext}"), dpi=200)
        plt.close(fig)

        gax = grid_axes.flat[i]
        style_axes(gax, title, ylabel, log)
        draw(gax, data, variants)

    handles, labels = grid_axes.flat[0].get_legend_handles_labels()
    grid_fig.legend(handles, labels, loc="lower center", ncol=len(labels), frameon=False, fontsize=9)
    try:
        with open(os.path.join(folder, "manifest.json")) as fh:
            args = json.load(fh)["args"]
        source = f"{args['source']} data, N={args['n']}, θ_max={args['theta_max']}, θ_min={args['theta_min']}"
        if args["source"] == "synthetic":
            source += " (SYNTHETIC: harness check only)"
    except (OSError, KeyError, ValueError):
        source = "unknown data source"
    grid_fig.suptitle(f"Ablation: AMTP vs Static-MT vs Global-MT  ·  {source}  ·  {note}",
                      x=0.01, ha="left", fontsize=12, color=INK)
    grid_fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    for ext in ("png", "pdf"):
        grid_fig.savefig(os.path.join(out, f"overview.{ext}"), dpi=170)

    with open(os.path.join(out, "figure_data.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table_rows[0]))
        w.writeheader()
        w.writerows(table_rows)
    print(f"figures written to {out}/")


if __name__ == "__main__":
    main()
