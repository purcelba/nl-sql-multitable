"""
plot_complexity.py — accuracy broken down by complexity tier.

  1. tier_heatmaps.png — 2x2 grid of heatmaps (metadata x shots) per tier
  2. tier_lines.png    — 2x2 grid of line charts (accuracy vs shots) per tier
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE      = Path(__file__).parent.parent
CACHE     = json.load(open(BASE / "results" / "cache.json"))
QUESTIONS = json.load(open(BASE / "benchmark" / "questions.json"))
OUTDIR    = BASE / "outputs"
OUTDIR.mkdir(exist_ok=True)

LEVELS      = ["L0", "L1", "L2", "L3"]
SHOT_COUNTS = [0, 10, 20, 30, 40]
TRIALS      = 3
TIER_ORDER  = [("single_table", "Single-table"),
               ("two_join",     "Two-join"),
               ("three_join",   "Three-join"),
               ("complex",      "Complex")]

SUBTITLE = "Mixed models: Sonnet-4 + Haiku-4.5"

LEVEL_COLORS = {"L0": "#c6dbef", "L1": "#6baed6", "L2": "#2171b5", "L3": "#08306b"}


def tier_qids(tier_key):
    return [q["id"] for q in QUESTIONS["questions"] if q["tier"] == tier_key]


def accuracy(level, shot_count, qids):
    prefixes = {f"{qid}__{level}__{shot_count}__" for qid in qids}
    total = match = 0
    for key, v in CACHE.items():
        if any(key.startswith(p) for p in prefixes):
            total += 1
            match += int(v["result_matches"])
    return 100 * match / total if total else 0.0


def make_tier_heatmaps():
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    for ax, (key, label) in zip(axes.flat, TIER_ORDER):
        qids = tier_qids(key)
        data = np.full((len(LEVELS) + 1, len(SHOT_COUNTS)), np.nan)
        for i, lvl in enumerate(LEVELS):
            for j, sc in enumerate(SHOT_COUNTS):
                data[i, j] = accuracy(lvl, sc, qids)
        data[len(LEVELS), 0] = accuracy("L_ref", 0, qids)

        im = ax.imshow(data, cmap="Greens", vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(len(SHOT_COUNTS)))
        ax.set_xticklabels([str(sc) for sc in SHOT_COUNTS], fontsize=10)
        ax.set_yticks(range(len(LEVELS) + 1))
        ax.set_yticklabels(LEVELS + ["L_ref"], fontsize=11, fontweight="bold")
        ax.set_title(f"{label} (n={len(qids)})", fontsize=12, fontweight="bold")
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                v = data[i, j]
                if np.isnan(v):
                    ax.text(j, i, "—", ha="center", va="center", color="#999")
                    continue
                ax.text(j, i, f"{v:.0f}", ha="center", va="center",
                        fontsize=10, fontweight="bold",
                        color="white" if v > 65 else "black")

    fig.suptitle("Accuracy by Complexity Tier (metadata × shots) — " + SUBTITLE,
                 fontsize=14, y=1.00)
    fig.supxlabel("Shot count", fontsize=12)
    fig.supylabel("Metadata level", fontsize=12)
    fig.tight_layout()
    path = OUTDIR / "tier_heatmaps.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def make_tier_lines():
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharey=True)
    for ax, (key, label) in zip(axes.flat, TIER_ORDER):
        qids = tier_qids(key)
        for lvl in LEVELS:
            accs = [accuracy(lvl, sc, qids) for sc in SHOT_COUNTS]
            ax.plot(SHOT_COUNTS, accs, marker="o", linewidth=2.0,
                    markersize=6, color=LEVEL_COLORS[lvl], label=lvl)
        ref_acc = accuracy("L_ref", 0, qids)
        ax.axhline(ref_acc, color="#b06cbd", linestyle="--", linewidth=1.4,
                   label=f"L_ref ({ref_acc:.0f}%)")
        ax.set_title(f"{label} (n={len(qids)})", fontsize=12, fontweight="bold")
        ax.set_xticks(SHOT_COUNTS)
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.legend(fontsize=9, loc="lower right")

    fig.suptitle("Accuracy vs. Shot Count by Complexity Tier — " + SUBTITLE,
                 fontsize=14, y=1.00)
    fig.supxlabel("Shot count", fontsize=12)
    fig.supylabel("Result-set accuracy", fontsize=12)
    fig.tight_layout()
    path = OUTDIR / "tier_lines.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


if __name__ == "__main__":
    make_tier_heatmaps()
    make_tier_lines()
    print("Done.")
