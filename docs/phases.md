# Project Phases — NL-to-SQL Multi-Table Benchmark

## Phase 1 — Database & Schema
**Goal:** Working 3-table SQLite database with realistic seed data.

Tasks:
- [x] Write `db/schema.sql` (customers, products, orders + FK constraints)
- [x] Write `db/seed.py` (~200 customers, ~30 products, ~1000 orders with referential integrity)
- [x] Seed the database and sanity-check row counts and join results

---

## Phase 2 — Ground-Truth Questions
**Goal:** 100 validated questions with correct SQL, organized by complexity tier.

Tasks:
- [x] Write 25 single-table questions with ground-truth SQL
- [x] Write 25 two-join questions with ground-truth SQL
- [x] Write 25 three-join questions with ground-truth SQL
- [x] Write 25 complex questions with ground-truth SQL (subquery/CTE/window)
- [x] Run all 100 ground-truth queries against seeded DB and verify results look reasonable
- [x] Assign tier labels and assemble `benchmark/questions.json`

---

## Phase 3 — Metadata Files
**Goal:** L0–L3 metadata files for the 3-table schema.

Design decision: the DB schema itself uses opaque-style field names (e.g. `price` not
`unit_price_cents`, `dt` not `order_date`, `refunded` not `is_refunded`). L0 is therefore
a genuinely hard baseline. L1–L3 progressively rescue meaning through metadata.
A descriptive-DDL reference level (`L_ref`) is included as an accuracy ceiling anchor.

Tasks:
- [x] Write `metadata/level_0.json` — bare opaque DDL only
- [x] Write `metadata/level_1.json` — opaque DDL + glossary (plain-English column labels)
- [x] Write `metadata/level_2.json` — + field descriptions + allowed values + units
- [x] Write `metadata/level_3.json` — + business rules + join guidance + "recent" convention
- [x] Write `metadata/level_ref.json` — descriptive-name views (customers_desc, products_desc, orders_desc) as ceiling anchor

---

## Phase 4 — Shot Files
**Goal:** Stratified example Q→SQL pairs for counts 10, 20, 30, 40 (disjoint from test questions).

Shot examples should be written as if the author has no knowledge of the specific test
questions — natural business questions a real analyst might ask, not tailored to the test
set. No identical questions; overlap in SQL patterns (joins, aggregations) is fine and
expected.

Stratification rule: within every block of 10 shots, include 2–3 examples from each
complexity tier so the model sees all join types regardless of shot count used.

Structure (cumulative — each file is a superset of the previous):
  shots_10.json : 10 shots = ~3 single-table, ~3 two-join, ~2 three-join, ~2 complex
  shots_20.json : 20 shots = above + 10 more (same tier balance)
  shots_30.json : 30 shots = above + 10 more (same tier balance)
  shots_40.json : 40 shots = above + 10 more → 10 per tier

Extending shot counts: add a shots_N.json (append 10 more examples in the same tier
balance) and add N to SHOT_COUNTS in runner.py. Cache keys are unaffected so existing
results don't need to be re-run.

Tasks:
- [x] Complete Phase 2 first — shot questions are written against the finalised test set
- [x] Write all 40 shot examples written blind to test set, natural analyst questions
- [x] Validate all 40 shot SQLs execute correctly against the seeded DB
- [x] Assemble cumulative shot files (shots_10 ⊂ shots_20 ⊂ shots_30 ⊂ shots_40)

---

## Phase 5 — Runner & Scorer
**Goal:** Working benchmark pipeline that respects cache and logs failures.

Tasks:
- [x] Write `benchmark/scorer.py` (port from v1, no changes needed)
- [x] Write `benchmark/runner.py` (5 levels, shot counts 0/10/20/30/40, 100 questions, L_ref at shots=0 only)
- [x] Smoke test: 3 questions × all conditions × 1 trial — 94% exec rate, cache and failure logging verified

---

## Phase 6 — Full Benchmark Run
**Goal:** Complete 6,000 API calls with results in `results/cache.json`.

Tasks:
- [ ] Run `python benchmark/runner.py`
- [ ] Monitor progress and resume if interrupted
- [ ] Verify all 6,000 cache keys are populated

---

## Phase 7 — Analysis & Plots
**Goal:** Charts that show how complexity tier interacts with metadata level and shot count.

Tasks:
- [ ] Write `analysis/plot.py` — heatmap and line chart (metadata × shots, averaged over tiers)
- [ ] Write `analysis/plot_complexity.py` — accuracy by complexity tier × metadata level × shot count
- [ ] Generate all plots to `outputs/`
- [ ] Write findings summary

---

## Status Key
- [ ] Not started
- [~] In progress
- [x] Done
