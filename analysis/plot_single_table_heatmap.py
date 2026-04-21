"""
plot_single_table_heatmap.py — single-table heatmap with descriptive metadata labels.
Mirrors the upper-left panel of tier_heatmaps.png but:
  - y-axis labels are descriptive (no "L0/L1" codes)
  - L_ref row dropped
  - x-axis labelled "Example Query Shots"
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

LEVELS       = ["L0", "L1", "L2", "L3"]
LEVEL_LABELS = ["DDL only", "+ glossary", "+ descriptions", "+ business rules"]
SHOT_COUNTS  = [0, 10, 20, 30, 40]


def tier_qids(tier_key):
    return [q["id"] for q in QUESTIONS["questions"]
            if q["tier"] == tier_key and not q.get("variant")]


def accuracy(level, sc, qids):
    prefixes = {f"{qid}__{level}__{sc}__" for qid in qids}
    total = hit = 0
    for key, v in CACHE.items():
        if any(key.startswith(p) for p in prefixes):
            total += 1
            hit += int(v["result_matches"])
    return 100 * hit / total if total else float("nan")


def make_heatmap(tier_key, tier_label, filename):
    qids = tier_qids(tier_key)
    data = np.full((len(LEVELS), len(SHOT_COUNTS)), np.nan)
    for i, lvl in enumerate(LEVELS):
        for j, sc in enumerate(SHOT_COUNTS):
            data[i, j] = accuracy(lvl, sc, qids)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    im = ax.imshow(data, cmap="Greens", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(SHOT_COUNTS)))
    ax.set_xticklabels([str(sc) for sc in SHOT_COUNTS], fontsize=11)
    ax.set_yticks(range(len(LEVELS)))
    ax.set_yticklabels(LEVEL_LABELS, fontsize=12)
    ax.set_xlabel("Example Query Shots", fontsize=12)
    ax.set_ylabel("Metadata level", fontsize=12)
    ax.set_title(f"{tier_label} Accuracy by Metadata × Shots (n={len(qids)})",
                 fontsize=13, pad=10)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = data[i, j]
            if np.isnan(v):
                ax.text(j, i, "—", ha="center", va="center", color="#999")
                continue
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center",
                    fontsize=12, fontweight="bold",
                    color="white" if v > 65 else "black")

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).set_label("Accuracy (%)")
    fig.tight_layout()
    path = OUTDIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


if __name__ == "__main__":
    make_heatmap("single_table", "Single-table", "single_table_heatmap.png")
    make_heatmap("two_join",     "Two-join",     "two_join_heatmap.png")
    make_heatmap("three_join",   "Three-join",   "three_join_heatmap.png")
    make_heatmap("complex",      "Complex",      "complex_heatmap.png")
