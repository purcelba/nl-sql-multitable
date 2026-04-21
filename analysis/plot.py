"""
plot.py — top-level charts averaged across complexity tiers.

  1. heatmap.png     — accuracy on a 5×5 grid (metadata × shots); L_ref as sc=0 col
  2. line_chart.png  — accuracy vs shots, one line per metadata level; L_ref as hline
  3. bar_chart.png   — exec rate vs accuracy by tier (best vs worst condition)
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
ALL_QIDS    = [q["id"] for q in QUESTIONS["questions"] if not q.get("variant")]

SUBTITLE = "Mixed models: Sonnet-4 (first ~1,066 calls) + Haiku-4.5 (remainder)"


def condition_accuracy(level, shot_count, qids=None):
    qids = qids or ALL_QIDS
    prefix_set = {f"{qid}__{level}__{shot_count}__" for qid in qids}
    per_trial_match = []
    exec_sum = match_sum = n = 0
    for key, v in CACHE.items():
        if any(key.startswith(p) for p in prefix_set):
            match_sum += int(v["result_matches"])
            exec_sum  += int(v["can_execute"])
            per_trial_match.append(int(v["result_matches"]))
            n += 1
    if not n:
        return 0.0, 0.0, 0.0
    return 100 * match_sum / n, 100 * exec_sum / n, float(np.std(per_trial_match) * 100)


def make_heatmap():
    data = np.full((len(LEVELS) + 1, len(SHOT_COUNTS)), np.nan)
    for i, lvl in enumerate(LEVELS):
        for j, sc in enumerate(SHOT_COUNTS):
            data[i, j], _, _ = condition_accuracy(lvl, sc)
    data[len(LEVELS), 0], _, _ = condition_accuracy("L_ref", 0)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    im = ax.imshow(data, cmap="Greens", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(SHOT_COUNTS)))
    ax.set_xticklabels([str(sc) for sc in SHOT_COUNTS], fontsize=11)
    ax.set_yticks(range(len(LEVELS) + 1))
    ax.set_yticklabels(LEVELS + ["L_ref"], fontsize=12, fontweight="bold")
    ax.set_xlabel("Shot count", fontsize=12)
    ax.set_ylabel("Metadata level", fontsize=12)
    ax.set_title("Result-Set Accuracy by Condition (%)\n" + SUBTITLE,
                 fontsize=13, pad=10)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            if np.isnan(val):
                ax.text(j, i, "—", ha="center", va="center",
                        fontsize=12, color="#999")
                continue
            color = "white" if val > 65 else "black"
            ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                    fontsize=12, fontweight="bold", color=color)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).set_label("Accuracy (%)")
    fig.tight_layout()
    path = OUTDIR / "heatmap.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


LEVEL_COLORS = {"L0": "#c6dbef", "L1": "#6baed6", "L2": "#2171b5", "L3": "#08306b"}
LEVEL_LABELS = {
    "L0": "L0 — DDL only",
    "L1": "L1 — + glossary",
    "L2": "L2 — + descriptions",
    "L3": "L3 — + business rules",
}


def make_line_chart():
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for lvl in LEVELS:
        accs, stds = [], []
        for sc in SHOT_COUNTS:
            acc, _, std = condition_accuracy(lvl, sc)
            accs.append(acc); stds.append(std)
        accs, stds = np.array(accs), np.array(stds)
        c = LEVEL_COLORS[lvl]
        ax.plot(SHOT_COUNTS, accs, marker="o", linewidth=2.2, markersize=7,
                color=c, label=LEVEL_LABELS[lvl])
        ax.fill_between(SHOT_COUNTS, accs - stds, accs + stds, alpha=0.12, color=c)

    ref_acc, _, _ = condition_accuracy("L_ref", 0)
    ax.axhline(ref_acc, color="#b06cbd", linestyle="--", linewidth=1.6,
               label=f"L_ref (descriptive DDL, 0 shots) — {ref_acc:.0f}%")

    ax.set_xticks(SHOT_COUNTS)
    ax.set_xlabel("Shot count", fontsize=12)
    ax.set_ylabel("Result-set accuracy (%)", fontsize=12)
    ax.set_title("Accuracy vs. Shot Count by Metadata Level\n" + SUBTITLE,
                 fontsize=13, pad=10)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right")
    fig.tight_layout()
    path = OUTDIR / "line_chart.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


TIERS = {
    "Single-table": [q["id"] for q in QUESTIONS["questions"] if q["tier"] == "single_table" and not q.get("variant")],
    "Two-join":     [q["id"] for q in QUESTIONS["questions"] if q["tier"] == "two_join"     and not q.get("variant")],
    "Three-join":   [q["id"] for q in QUESTIONS["questions"] if q["tier"] == "three_join"   and not q.get("variant")],
    "Complex":      [q["id"] for q in QUESTIONS["questions"] if q["tier"] == "complex"      and not q.get("variant")],
}
BEST  = ("L3", 40)
WORST = ("L0",  0)


def _tier_values(metric, lvl, sc):
    vals = []
    for qids in TIERS.values():
        prefixes = {f"{qid}__{lvl}__{sc}__" for qid in qids}
        total = hit = 0
        for key, v in CACHE.items():
            if any(key.startswith(p) for p in prefixes):
                total += 1
                hit += int(v[metric])
        vals.append(100 * hit / total if total else 0)
    return vals


def make_bar_chart():
    tier_names = list(TIERS.keys())
    x = np.arange(len(tier_names))
    w = 0.18
    specs = [
        (BEST,  "result_matches", "#2a7a3b", "L3 + 40 shots  accuracy"),
        (BEST,  "can_execute",    "#76c893", "L3 + 40 shots  exec rate"),
        (WORST, "result_matches", "#c0392b", "L0 + 0 shots   accuracy"),
        (WORST, "can_execute",    "#f1948a", "L0 + 0 shots   exec rate"),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.8))
    for k, ((lvl, sc), metric, color, label) in enumerate(specs):
        vals = _tier_values(metric, lvl, sc)
        offset = (k - 1.5) * w
        bars = ax.bar(x + offset, vals, w, color=color, label=label,
                      edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, vals):
            if val > 5:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 1.2, f"{val:.0f}%",
                        ha="center", va="bottom", fontsize=7.5, color="#333")

    ax.set_xticks(x)
    ax.set_xticklabels(tier_names, fontsize=12)
    ax.set_ylabel("Rate (%)", fontsize=12)
    ax.set_ylim(0, 115)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_title("Exec Rate vs. Accuracy by Complexity Tier\n"
                 "(best vs. worst condition) — " + SUBTITLE,
                 fontsize=12, pad=10)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(fontsize=9.5, loc="upper right", ncol=2)
    fig.tight_layout()
    path = OUTDIR / "bar_chart.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


TIER_COLORS = {
    "Single-table": "#2a9d8f",
    "Two-join":     "#e9c46a",
    "Three-join":   "#f4a261",
    "Complex":      "#e76f51",
}


def _tier_accuracy_at_shots(qids, sc):
    """Average accuracy across L0-L3 for these qids at the given shot count."""
    total = hit = 0
    for lvl in LEVELS:
        prefixes = {f"{qid}__{lvl}__{sc}__" for qid in qids}
        for key, v in CACHE.items():
            if any(key.startswith(p) for p in prefixes):
                total += 1
                hit += int(v["result_matches"])
    return 100 * hit / total if total else 0


def make_complexity_chart():
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for tier_name, qids in TIERS.items():
        accs = [_tier_accuracy_at_shots(qids, sc) for sc in SHOT_COUNTS]
        ax.plot(SHOT_COUNTS, accs, marker="o", linewidth=2.3, markersize=8,
                color=TIER_COLORS[tier_name],
                label=f"{tier_name} (n={len(qids)})")

    ax.set_xticks(SHOT_COUNTS)
    ax.set_xlabel("Shot count", fontsize=12)
    ax.set_ylabel("Result-set accuracy (%)", fontsize=12)
    ax.set_title("Accuracy by Question Complexity\n"
                 "(averaged across metadata levels L0-L3) — " + SUBTITLE,
                 fontsize=12, pad=10)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right", title="Complexity tier")
    fig.tight_layout()
    path = OUTDIR / "complexity.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


if __name__ == "__main__":
    make_heatmap()
    make_line_chart()
    make_bar_chart()
    make_complexity_chart()
    print("Done.")
