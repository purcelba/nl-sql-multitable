"""
plot_single_table.py — single-table accuracy vs shots, one line per metadata level.
Used to make the headline point: near-perfect accuracy with metadata + ~20 shots.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE      = Path(__file__).parent.parent
CACHE     = json.load(open(BASE / "results" / "cache.json"))
QUESTIONS = json.load(open(BASE / "benchmark" / "questions.json"))
TAGS      = json.load(open(BASE / "benchmark" / "ambiguity_tags.json"))["tags"]
OUTDIR    = BASE / "outputs"
OUTDIR.mkdir(exist_ok=True)

LEVELS      = ["L0", "L1", "L2", "L3"]
SHOT_COUNTS = [0, 10, 20, 30, 40]

LEVEL_COLORS = {"L0": "#c6dbef", "L1": "#6baed6", "L2": "#2171b5", "L3": "#08306b"}
LEVEL_LABELS = {
    "L0": "L0 — DDL only",
    "L1": "L1 — + glossary",
    "L2": "L2 — + descriptions",
    "L3": "L3 — + business rules",
}


def single_table_qids(mode="all"):
    """mode: 'all' (non-variant), 'low' (low-ambiguity non-variant),
             'ambiguous' (med/high tag, variants included)."""
    all_st = [q for q in QUESTIONS["questions"] if q["tier"] == "single_table"]
    if mode == "all":
        return [q["id"] for q in all_st if not q.get("variant")]
    if mode == "low":
        return [q["id"] for q in all_st
                if not q.get("variant") and TAGS.get(q["id"], "low") == "low"]
    if mode == "ambiguous":
        return [q["id"] for q in all_st
                if TAGS.get(q["id"], "low") in ("med", "high")]
    raise ValueError(mode)


def accuracy(level, sc, qids):
    prefixes = {f"{qid}__{level}__{sc}__" for qid in qids}
    total = hit = 0
    for key, v in CACHE.items():
        if any(key.startswith(p) for p in prefixes):
            total += 1
            hit += int(v["result_matches"])
    return 100 * hit / total if total else 0.0


def make_chart(mode="all", filename="single_table_lines.png",
               title_suffix=""):
    qids = single_table_qids(mode=mode)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for lvl in LEVELS:
        accs = [accuracy(lvl, sc, qids) for sc in SHOT_COUNTS]
        ax.plot(SHOT_COUNTS, accs, marker="o", linewidth=2.3, markersize=8,
                color=LEVEL_COLORS[lvl], label=LEVEL_LABELS[lvl])

    ax.set_xticks(SHOT_COUNTS)
    ax.set_xlabel("Shot count", fontsize=12)
    ax.set_ylabel("Result-set accuracy (%)", fontsize=12)
    ax.set_title(f"Single-table Accuracy vs. Shot Count{title_suffix} (n={len(qids)})",
                 fontsize=13, pad=10)
    ax.set_ylim(0, 102)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right")
    fig.tight_layout()
    path = OUTDIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


if __name__ == "__main__":
    make_chart(mode="all")
    make_chart(mode="low",
               filename="single_table_lines_low_ambig.png",
               title_suffix=" — low-ambiguity only")
    make_chart(mode="ambiguous",
               filename="single_table_lines_ambig.png",
               title_suffix=" — ambiguous only")
