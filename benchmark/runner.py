"""
runner.py — orchestrates the NL-to-SQL multi-table benchmark.

Usage:
  python benchmark/runner.py                         # full run
  python benchmark/runner.py --questions s01 j04     # subset
  python benchmark/runner.py --trials 1              # smoke test
  python benchmark/runner.py --levels L0 L3          # specific levels

Design notes:
  - L_ref uses descriptive-name views (customers_desc etc.) so opaque shots
    would be misleading. L_ref is therefore run at shots=0 only.
  - All other levels run across all shot counts: 0, 10, 20, 30, 40.
  - Cache key: "{question_id}__{level}__{shot_count}__{trial}"
  - Results written after every API call; safe to interrupt and resume.
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

BASE          = Path(__file__).parent.parent
load_dotenv(BASE / ".env", override=True)
DB_PATH       = str(BASE / "db" / "orders.db")
CACHE_PATH    = BASE / "results" / "cache.json"
FAILURES_PATH = BASE / "results" / "failures.jsonl"

METADATA_LEVELS = ["L0", "L1", "L2", "L3", "L_ref"]
SHOT_COUNTS     = [0, 10, 20, 30, 40]
DEFAULT_TRIALS  = 3
MODEL           = "claude-haiku-4-5-20251001"
MAX_CONCURRENT  = 3
PROGRESS_EVERY  = 50

# L_ref uses descriptive-name views; shots use opaque names → run L_ref at 0 shots only
L_REF_SHOT_COUNTS = [0]

PROMPT_TEMPLATE = """\
You are a SQL expert for a SaaS e-commerce analytics system.
Convert the user's natural language question into a valid SQLite query.
Return ONLY the raw SQL. No explanation, no markdown fences, no preamble.

--- SCHEMA AND METADATA ---
{metadata}

--- EXAMPLE QUESTIONS AND QUERIES ---
{shots}

--- QUESTION ---
{question}"""


def load_json(path):
    with open(path) as f:
        return json.load(f)


def build_shots_text(shots):
    if not shots:
        return "(none)"
    parts = []
    for s in shots:
        parts.append(f"Q: {s['question']}")
        parts.append(f"SQL: {s['sql']}")
    return "\n".join(parts)


def strip_fences(text):
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def save_cache(cache):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def append_failure(record):
    with open(FAILURES_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def _bar(done, total, width=30):
    filled = int(width * done / total) if total else 0
    return "[" + "#" * filled + "." * (width - filled) + "]"


def _print_banner(progress):
    done    = progress["done"]
    total   = progress["total"]
    elapsed = time.time() - progress["start_t"]
    rate    = done / elapsed if elapsed > 0 else 0
    eta     = (total - done) / rate if rate > 0 else 0
    exec_pct  = 100 * progress["exec_ok"]  / done if done else 0
    match_pct = 100 * progress["matches"]  / done if done else 0
    print(
        f"\n  {_bar(done, total)} {done}/{total}  "
        f"exec {exec_pct:.0f}%  match {match_pct:.0f}%  "
        f"elapsed {elapsed/60:.1f}m  eta {eta/60:.1f}m\n",
        flush=True,
    )


async def call_api(client, sem, prompt):
    backoff = 5
    async with sem:
        for attempt in range(6):
            try:
                response = await client.messages.create(
                    model=MODEL,
                    max_tokens=200,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text.strip()
            except anthropic.RateLimitError:
                if attempt == 5:
                    raise
                wait = backoff * (2 ** attempt)
                print(f"  [RATE LIMIT] backing off {wait}s (attempt {attempt+1}/6)", flush=True)
                await asyncio.sleep(wait)


async def process_task(*, key, question, level, shot_count, trial,
                       metadata, shots_data, cache, cache_lock,
                       client, sem, can_execute_fn, result_matches_fn, progress):
    shots  = shots_data.get(shot_count, []) if shot_count > 0 else []
    prompt = PROMPT_TEMPLATE.format(
        metadata=metadata[level],
        shots=build_shots_text(shots),
        question=question["question"],
    )

    api_error = False
    try:
        raw = await call_api(client, sem, prompt)
    except Exception as e:
        raw = ""
        api_error = True
        print(f"  [API ERROR] {key}: {e}", flush=True)

    # Don't cache API errors — the key stays uncached so it's retried on resume.
    if api_error:
        return

    generated_sql = strip_fences(raw)
    exec_ok  = can_execute_fn(generated_sql, DB_PATH)
    matches  = result_matches_fn(generated_sql, question["ground_truth_sql"], DB_PATH)

    result = {
        "generated_sql":  generated_sql,
        "can_execute":    exec_ok,
        "result_matches": matches,
        "question_id":    question["id"],
        "tier":           question["tier"],
        "metadata_level": level,
        "shot_count":     shot_count,
        "trial":          trial,
    }

    async with cache_lock:
        cache[key] = result
        save_cache(cache)
        progress["done"]    += 1
        progress["exec_ok"] += int(exec_ok)
        progress["matches"] += int(matches)
        done  = progress["done"]
        total = progress["total"]
        should_banner = (done % PROGRESS_EVERY == 0) or (done == total)

    if not exec_ok or not matches:
        append_failure({
            "cache_key":     key,
            "question":      question["question"],
            "tier":          question["tier"],
            "generated_sql": generated_sql,
            "error_or_mismatch": "execution_error" if not exec_ok else "wrong_result",
            "ground_truth_sql": question["ground_truth_sql"],
        })

    symbol = "✓" if matches else ("✗exec" if not exec_ok else "✗res")
    print(f"  [{done:>4}/{total}] {key:<36} {symbol}", flush=True)
    if should_banner:
        _print_banner(progress)


async def run_benchmark(questions_filter=None, level_filter=None, shot_filter=None,
                        per_tier=None, num_trials=DEFAULT_TRIALS):
    questions_data = load_json(BASE / "benchmark" / "questions.json")
    questions      = questions_data["questions"]
    if questions_filter:
        questions = [q for q in questions if q["id"] in questions_filter]
    if per_tier is not None:
        from collections import defaultdict
        by_tier = defaultdict(list)
        for q in questions:
            by_tier[q["tier"]].append(q)
        questions = [q for tier in by_tier for q in by_tier[tier][:per_tier]]

    levels_to_run = level_filter or METADATA_LEVELS

    metadata = {
        "L0":    load_json(BASE / "metadata" / "level_0.json")["context"],
        "L1":    load_json(BASE / "metadata" / "level_1.json")["context"],
        "L2":    load_json(BASE / "metadata" / "level_2.json")["context"],
        "L3":    load_json(BASE / "metadata" / "level_3.json")["context"],
        "L_ref": load_json(BASE / "metadata" / "level_ref.json")["context"],
    }

    shots_data = {
        10: load_json(BASE / "metadata" / "shots" / "shots_10.json"),
        20: load_json(BASE / "metadata" / "shots" / "shots_20.json"),
        30: load_json(BASE / "metadata" / "shots" / "shots_30.json"),
        40: load_json(BASE / "metadata" / "shots" / "shots_40.json"),
    }

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache = load_json(CACHE_PATH) if CACHE_PATH.exists() else {}
    if not CACHE_PATH.exists():
        save_cache(cache)

    all_tasks = []
    for q in questions:
        for level in levels_to_run:
            shot_counts = L_REF_SHOT_COUNTS if level == "L_ref" else SHOT_COUNTS
            if shot_filter is not None:
                shot_counts = [sc for sc in shot_counts if sc in shot_filter]
            for shot_count in shot_counts:
                for trial in range(1, num_trials + 1):
                    key = f"{q['id']}__{level}__{shot_count}__{trial}"
                    if key not in cache:
                        all_tasks.append((key, q, level, shot_count, trial))

    def _scs_for(level):
        scs = L_REF_SHOT_COUNTS if level == "L_ref" else SHOT_COUNTS
        return [sc for sc in scs if shot_filter is None or sc in shot_filter]

    n_cached = sum(
        1 for q in questions
        for level in levels_to_run
        for sc in _scs_for(level)
        for trial in range(1, num_trials + 1)
        if f"{q['id']}__{level}__{sc}__{trial}" in cache
    )

    print(f"Tasks: {len(all_tasks)} to run, {n_cached} already cached.\n")
    if not all_tasks:
        print("Nothing to do.")
        return cache

    sys.path.insert(0, str(BASE / "benchmark"))
    from scorer import can_execute, result_matches

    sem        = asyncio.Semaphore(MAX_CONCURRENT)
    client     = anthropic.AsyncAnthropic()
    cache_lock = asyncio.Lock()
    progress   = {"done": 0, "total": len(all_tasks),
                  "exec_ok": 0, "matches": 0, "start_t": time.time()}

    await asyncio.gather(*[
        process_task(
            key=key, question=q, level=level, shot_count=sc, trial=trial,
            metadata=metadata, shots_data=shots_data, cache=cache,
            cache_lock=cache_lock, client=client, sem=sem,
            can_execute_fn=can_execute, result_matches_fn=result_matches,
            progress=progress,
        )
        for key, q, level, sc, trial in all_tasks
    ])

    elapsed = time.time() - progress["start_t"]
    print(f"\nFinished {len(all_tasks)} calls in {elapsed/60:.1f} min.")
    return cache


def print_accuracy_table(cache, questions, num_trials):
    all_qids = [q["id"] for q in questions]
    tiers    = list({q["tier"] for q in questions})

    print("\n" + "=" * 70)
    print("  RESULT-SET ACCURACY BY CONDITION")
    print("=" * 70)

    shots_header = "".join(f"  sc={sc:<4}" for sc in SHOT_COUNTS)
    print(f"  {'':8}{shots_header}")
    print(f"  {'':8}" + "  --------" * len(SHOT_COUNTS))

    for level in METADATA_LEVELS:
        row = f"  {level:<8}"
        shot_counts = L_REF_SHOT_COUNTS if level == "L_ref" else SHOT_COUNTS
        for sc in SHOT_COUNTS:
            if sc not in shot_counts:
                row += f"  {'—':>6}    "
                continue
            total = matched = 0
            for qid in all_qids:
                for trial in range(1, num_trials + 1):
                    key = f"{qid}__{level}__{sc}__{trial}"
                    if key in cache:
                        total   += 1
                        matched += int(cache[key]["result_matches"])
            row += f"  {100*matched/total:>5.1f}%  " if total else f"  {'—':>6}    "
        print(row)
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", nargs="+", metavar="ID")
    parser.add_argument("--levels",    nargs="+", metavar="LEVEL")
    parser.add_argument("--shots",     nargs="+", type=int, metavar="N")
    parser.add_argument("--per-tier",  type=int, metavar="N",
                        help="use only the first N questions per tier")
    parser.add_argument("--trials",    type=int, default=DEFAULT_TRIALS)
    args = parser.parse_args()

    cache = asyncio.run(run_benchmark(
        questions_filter=args.questions,
        level_filter=args.levels,
        shot_filter=args.shots,
        per_tier=args.per_tier,
        num_trials=args.trials,
    ))

    questions_data = load_json(BASE / "benchmark" / "questions.json")
    print_accuracy_table(cache, questions_data["questions"], args.trials)


if __name__ == "__main__":
    main()
