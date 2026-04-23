"""
plot_blog.py — figures for the "What the Data Says About Accuracy" blog post.

Uses "semantic layer" terminology (instead of "metadata level") and consistent
styling across all five figures. Outputs land in outputs/blog/.

Figures produced:
  fig1_shots_substitute.png      — accuracy vs shots, one line per semantic layer
  fig2_complexity_dominates.png  — accuracy by complexity tier (avg across L0-L3)
  fig3_complex_heatmap.png       — semantic-layer x shots heatmap, complex tier
  fig4_ambiguity_shots.png       — accuracy vs shots, split by ambiguity
  fig5_ambiguity_layers.png      — accuracy vs semantic-layer, split by ambiguity
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
TAGS      = json.load(open(BASE / "benchmark" / "ambiguity_tags.json"))["tags"]
OUTDIR    = BASE / "outputs" / "blog"
OUTDIR.mkdir(parents=True, exist_ok=True)

LEVELS      = ["L0", "L1", "L2", "L3"]
SHOT_COUNTS = [0, 10, 20, 30, 40]

LEVEL_LABELS = {
    "L0": "L0 — DDL only",
    "L1": "L1 — + glossary",
    "L2": "L2 — + descriptions",
    "L3": "L3 — + business rules",
}
LEVEL_COLORS = {"L0": "#c6dbef", "L1": "#6baed6", "L2": "#2171b5", "L3": "#08306b"}

TIER_ORDER = [
    ("single_table", "Single-table"),
    ("two_join",     "Two-join"),
    ("three_join",   "Three-join"),
    ("complex",      "Complex"),
]
TIER_COLORS = {
    "Single-table": "#2a9d8f",
    "Two-join":     "#8ab17d",
    "Three-join":   "#e9c46a",
    "Complex":      "#e76f51",
}

AMBIG_ORDER  = ["low", "med", "high"]
AMBIG_COLORS = {"low": "#2a9d8f", "med": "#e9c46a", "high": "#e76f51"}
AMBIG_LABELS = {"low": "Low ambiguity", "med": "Medium ambiguity", "high": "High ambiguity"}


def pct_format(ax):
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))


def tier_qids(tier_key):
    return [q["id"] for q in QUESTIONS["questions"]
            if q["tier"] == tier_key and not q.get("variant")]


def qids_by_ambiguity():
    buckets = {a: [] for a in AMBIG_ORDER}
    for q in QUESTIONS["questions"]:
        tag = TAGS.get(q["id"], "low")
        if tag in buckets:
            buckets[tag].append(q["id"])
    return buckets


def accuracy_by_cell(qids, level, sc):
    prefixes = {f"{qid}__{level}__{sc}__" for qid in qids}
    total = hit = 0
    for key, v in CACHE.items():
        if any(key.startswith(p) for p in prefixes):
            total += 1
            hit += int(v["result_matches"])
    return 100 * hit / total if total else float("nan")


def accuracy_avg_levels(qids, sc):
    """Accuracy at shot count sc, averaged across L0-L3."""
    total = hit = 0
    for lvl in LEVELS:
        prefixes = {f"{qid}__{lvl}__{sc}__" for qid in qids}
        for key, v in CACHE.items():
            if any(key.startswith(p) for p in prefixes):
                total += 1
                hit += int(v["result_matches"])
    return 100 * hit / total if total else float("nan")


def accuracy_avg_shots(qids, lvl):
    """Accuracy at semantic-layer lvl, averaged across shot counts."""
    accs = [accuracy_by_cell(qids, lvl, sc) for sc in SHOT_COUNTS]
    return sum(accs) / len(accs)


# ---------- Figure 1 ----------
def make_fig1():
    ALL_QIDS = [q["id"] for q in QUESTIONS["questions"] if not q.get("variant")]
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for lvl in LEVELS:
        accs = [accuracy_by_cell(ALL_QIDS, lvl, sc) for sc in SHOT_COUNTS]
        ax.plot(SHOT_COUNTS, accs, marker="o", linewidth=2.4, markersize=8,
                color=LEVEL_COLORS[lvl], label=LEVEL_LABELS[lvl])
    ax.set_xticks(SHOT_COUNTS)
    ax.set_xlabel("Example shot count", fontsize=12)
    ax.set_ylabel("Result-set accuracy", fontsize=12)
    ax.set_title("Shots substitute for the semantic layer",
                 fontsize=14, pad=10, fontweight="bold")
    ax.set_ylim(0, 100)
    pct_format(ax)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right", title="Semantic layer", frameon=True)
    fig.tight_layout()
    path = OUTDIR / "fig1_shots_substitute.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


# ---------- Figure 2 ----------
def make_fig2():
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for tier_key, tier_label in TIER_ORDER:
        qids = tier_qids(tier_key)
        accs = [accuracy_avg_levels(qids, sc) for sc in SHOT_COUNTS]
        ax.plot(SHOT_COUNTS, accs, marker="o", linewidth=2.4, markersize=8,
                color=TIER_COLORS[tier_label],
                label=f"{tier_label} (n={len(qids)})")
    ax.set_xticks(SHOT_COUNTS)
    ax.set_xlabel("Example shot count", fontsize=12)
    ax.set_ylabel("Result-set accuracy", fontsize=12)
    fig.suptitle("SQL complexity dominates every other factor",
                 fontsize=14, fontweight="bold", y=0.98)
    ax.set_title("Averaged across semantic-layer levels L0–L3",
                 fontsize=10, color="#555", pad=8)
    ax.set_ylim(0, 100)
    pct_format(ax)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right", title="Complexity tier")
    fig.tight_layout()
    path = OUTDIR / "fig2_complexity_dominates.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


# ---------- Figure 3 ----------
def make_fig3():
    panels = [
        ("single_table", "Single-table"),
        ("two_join",     "Two-join"),
        ("complex",      "Complex"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), sharey=True)
    y_labels = ["DDL only", "+ glossary", "+ descriptions", "+ business rules"]
    im = None
    for ax, (tier_key, tier_label) in zip(axes, panels):
        qids = tier_qids(tier_key)
        data = np.full((len(LEVELS), len(SHOT_COUNTS)), np.nan)
        for i, lvl in enumerate(LEVELS):
            for j, sc in enumerate(SHOT_COUNTS):
                data[i, j] = accuracy_by_cell(qids, lvl, sc)

        im = ax.imshow(data, cmap="Greens", vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(len(SHOT_COUNTS)))
        ax.set_xticklabels([str(sc) for sc in SHOT_COUNTS], fontsize=10)
        ax.set_yticks(range(len(LEVELS)))
        ax.set_yticklabels(y_labels, fontsize=10)
        ax.set_xlabel("Example shot count", fontsize=11)
        ax.set_title(f"{tier_label} (n={len(qids)})",
                     fontsize=12, fontweight="bold", pad=6)

        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                v = data[i, j]
                if np.isnan(v):
                    ax.text(j, i, "—", ha="center", va="center", color="#999")
                    continue
                ax.text(j, i, f"{v:.0f}%", ha="center", va="center",
                        fontsize=10.5, fontweight="bold",
                        color="white" if v > 65 else "black")

    axes[0].set_ylabel("Semantic layer", fontsize=11)
    fig.suptitle("Accuracy by semantic layer × shots, across complexity tiers",
                 fontsize=14, fontweight="bold", y=1.02)
    cbar = fig.colorbar(im, ax=axes, fraction=0.018, pad=0.02)
    cbar.set_label("Accuracy (%)")
    path = OUTDIR / "fig3_complex_heatmap.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


# ---------- Figure 4 ----------
def make_fig4():
    buckets = qids_by_ambiguity()
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for tag in AMBIG_ORDER:
        qids = buckets[tag]
        if len(qids) < 5:
            continue
        accs = [accuracy_avg_levels(qids, sc) for sc in SHOT_COUNTS]
        ax.plot(SHOT_COUNTS, accs, marker="o", linewidth=2.4, markersize=8,
                color=AMBIG_COLORS[tag],
                label=f"{AMBIG_LABELS[tag]} (n={len(qids)})")
    ax.set_xticks(SHOT_COUNTS)
    ax.set_xlabel("Example shot count", fontsize=12)
    ax.set_ylabel("Result-set accuracy", fontsize=12)
    fig.suptitle("Ambiguity is a tax that shots don't pay",
                 fontsize=14, fontweight="bold", y=0.98)
    ax.set_title("Averaged across semantic-layer levels L0–L3",
                 fontsize=10, color="#555", pad=8)
    ax.set_ylim(0, 100)
    pct_format(ax)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right", title="Question ambiguity")
    fig.tight_layout()
    path = OUTDIR / "fig4_ambiguity_shots.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


# ---------- Figure 5 ----------
def make_fig5():
    buckets = qids_by_ambiguity()
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    x = list(range(len(LEVELS)))
    for tag in AMBIG_ORDER:
        qids = buckets[tag]
        if len(qids) < 5:
            continue
        accs = [accuracy_avg_shots(qids, lvl) for lvl in LEVELS]
        ax.plot(x, accs, marker="o", linewidth=2.4, markersize=9,
                color=AMBIG_COLORS[tag],
                label=f"{AMBIG_LABELS[tag]} (n={len(qids)})")
    ax.set_xticks(x)
    ax.set_xticklabels(
        ["L0\nDDL only", "L1\n+ glossary", "L2\n+ descriptions", "L3\n+ business rules"],
        fontsize=10,
    )
    ax.set_xlabel("Semantic layer", fontsize=12, labelpad=8)
    ax.set_ylabel("Result-set accuracy", fontsize=12)
    fig.suptitle("A richer semantic layer lifts both curves — but the gap is structural",
                 fontsize=13, fontweight="bold", y=0.98)
    ax.set_title("Averaged across shot counts 0–40",
                 fontsize=10, color="#555", pad=8)
    ax.set_ylim(0, 100)
    pct_format(ax)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right", title="Question ambiguity")
    fig.tight_layout()
    path = OUTDIR / "fig5_ambiguity_layers.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


if __name__ == "__main__":
    make_fig1()
    make_fig2()
    make_fig3()
    make_fig4()
    make_fig5()
    print("Done.")
