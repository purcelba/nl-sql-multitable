"""
plot_ambiguity.py — accuracy broken down by subjective ambiguity tag.

Tags live in benchmark/ambiguity_tags.json (low/med/high).
Outputs:
  1. ambiguity.png       — accuracy vs shots, one line per ambiguity level
  2. ambiguity_table.txt — accuracy table by ambiguity x metadata level (avg across shots)
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

AMBIG_ORDER  = ["low", "med", "high"]
AMBIG_COLORS = {"low": "#2a9d8f", "med": "#e9c46a", "high": "#e76f51"}
AMBIG_LABELS = {"low": "Low ambiguity", "med": "Medium ambiguity", "high": "High ambiguity"}

SUBTITLE = "Mixed models: Sonnet-4 + Haiku-4.5"


def qids_by_ambiguity(tiers=None):
    buckets = {a: [] for a in AMBIG_ORDER}
    for q in QUESTIONS["questions"]:
        if tiers is not None and q["tier"] not in tiers:
            continue
        tag = TAGS.get(q["id"], "low")
        buckets[tag].append(q["id"])
    return buckets


def accuracy_at_shots(qids, sc):
    """Avg accuracy across L0-L3 for these qids at the given shot count."""
    total = hit = 0
    for lvl in LEVELS:
        prefixes = {f"{qid}__{lvl}__{sc}__" for qid in qids}
        for key, v in CACHE.items():
            if any(key.startswith(p) for p in prefixes):
                total += 1
                hit += int(v["result_matches"])
    return 100 * hit / total if total else 0


def accuracy_at_cell(qids, lvl, sc):
    prefixes = {f"{qid}__{lvl}__{sc}__" for qid in qids}
    total = hit = 0
    for key, v in CACHE.items():
        if any(key.startswith(p) for p in prefixes):
            total += 1
            hit += int(v["result_matches"])
    return 100 * hit / total if total else 0


def make_ambiguity_chart():
    buckets = qids_by_ambiguity()
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for tag in AMBIG_ORDER:
        qids = buckets[tag]
        if not qids:
            continue
        accs = [accuracy_at_shots(qids, sc) for sc in SHOT_COUNTS]
        ax.plot(SHOT_COUNTS, accs, marker="o", linewidth=2.3, markersize=8,
                color=AMBIG_COLORS[tag],
                label=f"{AMBIG_LABELS[tag]} (n={len(qids)})")

    ax.set_xticks(SHOT_COUNTS)
    ax.set_xlabel("Shot count", fontsize=12)
    ax.set_ylabel("Result-set accuracy (%)", fontsize=12)
    ax.set_title("Accuracy by Question Ambiguity\n"
                 "(averaged across metadata levels L0-L3) — " + SUBTITLE,
                 fontsize=12, pad=10)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right", title="Ambiguity")
    fig.tight_layout()
    path = OUTDIR / "ambiguity.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def make_ambiguity_by_metadata_chart(tiers=None, filename="ambiguity_by_metadata.png",
                                     tier_label=None):
    """x = metadata level, y = accuracy, one line per ambiguity (avg across shots)."""
    buckets = qids_by_ambiguity(tiers=tiers)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    x = list(range(len(LEVELS)))
    for tag in AMBIG_ORDER:
        qids = buckets[tag]
        if not qids:
            continue
        accs = []
        for lvl in LEVELS:
            per_shot = [accuracy_at_cell(qids, lvl, sc) for sc in SHOT_COUNTS]
            accs.append(sum(per_shot) / len(per_shot))
        ax.plot(x, accs, marker="o", linewidth=2.3, markersize=9,
                color=AMBIG_COLORS[tag],
                label=f"{AMBIG_LABELS[tag]} (n={len(qids)})")

    ax.set_xticks(x)
    ax.set_xticklabels(LEVELS, fontsize=12)
    ax.set_xlabel("Metadata level", fontsize=12)
    ax.set_ylabel("Result-set accuracy (%)", fontsize=12)
    scope = f"{tier_label} questions only" if tier_label else "all questions"
    ax.set_title(f"Accuracy by Metadata Level, split by Question Ambiguity\n"
                 f"({scope}, averaged across shot counts 0-40) — " + SUBTITLE,
                 fontsize=12, pad=10)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=10, loc="lower right", title="Ambiguity")
    fig.tight_layout()
    path = OUTDIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def print_ambiguity_table():
    buckets = qids_by_ambiguity()
    print("\n" + "=" * 70)
    print("  ACCURACY BY AMBIGUITY × METADATA LEVEL (avg across all shots)")
    print("=" * 70)
    header = f"  {'Tag':<8} {'n':>4}  " + "  ".join(f"{lvl:>6}" for lvl in LEVELS) + f"  {'mean':>6}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for tag in AMBIG_ORDER:
        qids = buckets[tag]
        row = f"  {tag:<8} {len(qids):>4}  "
        level_accs = []
        for lvl in LEVELS:
            accs_across_shots = [accuracy_at_cell(qids, lvl, sc) for sc in SHOT_COUNTS]
            avg = sum(accs_across_shots) / len(accs_across_shots)
            level_accs.append(avg)
            row += f"{avg:>5.1f}%  "
        row += f"{sum(level_accs)/len(level_accs):>5.1f}%"
        print(row)
    print()


if __name__ == "__main__":
    print_ambiguity_table()
    make_ambiguity_chart()
    make_ambiguity_by_metadata_chart()
    make_ambiguity_by_metadata_chart(
        tiers=["single_table"],
        filename="ambiguity_by_metadata_single_table.png",
        tier_label="Single-table",
    )
    make_ambiguity_by_metadata_chart(
        tiers=["single_table", "two_join", "three_join"],
        filename="ambiguity_by_metadata_up_to_three_join.png",
        tier_label="Single-table, Two-join, Three-join",
    )
    print("Done.")
