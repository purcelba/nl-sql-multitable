# NL-to-SQL Accuracy Benchmark — Multi-Table Edition

## Context
Follow-on to `nl-sql-benchmark/` (single-table baseline). That experiment showed:
- Metadata richness (glossary, descriptions) provides no lift over bare DDL when column names are already descriptive
- Business rules (L3) are the only metadata layer that meaningfully improves accuracy
- 20 shots substitute effectively for rich metadata documentation
- Opaque column names are not rescued by glossary/descriptions alone

This project extends the experiment across two new dimensions:
1. **SQL complexity** — from single-table queries up to 3-table joins with subqueries
2. **Shot count** — extended to 0, 10, 20, 30, 40

## Repo Structure
```
nl-sql-multitable/
├── db/
│   ├── schema.sql          # 3-table definitions + relationships
│   └── seed.py             # Generates realistic relational data (~1000 orders, ~200 customers, ~30 products)
├── metadata/
│   ├── level_0.json        # Bare DDL only
│   ├── level_1.json        # DDL + column glossary
│   ├── level_2.json        # + field descriptions + enum values
│   └── level_3.json        # + business rules, join hints, gotchas
│   └── shots/
│       ├── shots_00.json   # 0 examples (empty)
│       ├── shots_10.json   # 10 example Q→SQL pairs
│       ├── shots_20.json   # 20 example Q→SQL pairs
│       ├── shots_30.json   # 30 example Q→SQL pairs
│       └── shots_40.json   # 40 example Q→SQL pairs
├── benchmark/
│   ├── questions.json      # 100 questions (25 per complexity tier) with ground-truth SQL
│   ├── runner.py           # Async API orchestration with caching
│   └── scorer.py           # Execution + result-set accuracy scoring
├── results/
│   ├── cache.json          # Keyed by (question_id, metadata_level, shot_count, trial)
│   └── failures.jsonl      # Failed/wrong SQL with full prompt for post-hoc analysis
├── analysis/
│   ├── plot.py             # Standard heatmap + line chart + bar chart
│   └── plot_complexity.py  # Complexity-focused charts
└── outputs/                # Generated plots
```

## The Domain
Three normalized tables representing a SaaS e-commerce system:

The schema uses opaque-style field names by design — units and types are not encoded
in column names. Metadata levels L1–L3 progressively supply that context.
`L_ref` uses a descriptive-name view as a ceiling anchor.

```sql
CREATE TABLE customers (
    cust_id   INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    email     TEXT NOT NULL,
    region    TEXT NOT NULL,   -- 'North', 'South', 'East', 'West'
    plan      TEXT NOT NULL,   -- 'free', 'starter', 'pro', 'enterprise'
    joined    DATE NOT NULL,
    rep       TEXT             -- NULL if self-serve
);

CREATE TABLE products (
    sku       TEXT PRIMARY KEY,
    product   TEXT NOT NULL,
    cat       TEXT NOT NULL,   -- 'Software', 'Hardware', 'Services', 'Support'
    price     INTEGER NOT NULL -- list price in USD cents
);

CREATE TABLE orders (
    oid        INTEGER PRIMARY KEY,
    cust_id    INTEGER NOT NULL REFERENCES customers(cust_id),
    sku        TEXT    NOT NULL REFERENCES products(sku),
    dt         DATE    NOT NULL,
    qty        INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,  -- actual price in USD cents (= list price, no divergence)
    discount   REAL    NOT NULL DEFAULT 0,  -- fraction 0.0–1.0
    revenue    INTEGER NOT NULL,            -- qty * unit_price * (1 - discount)
    refunded   INTEGER NOT NULL DEFAULT 0   -- 0 or 1
);
```

## Experiment Design

### SQL Complexity Tiers (4 tiers × 25 questions = 100 total)
- **Single-table**: queries against only one of the three tables
- **Two-join**: joins exactly 2 tables (orders↔customers or orders↔products)
- **Three-join**: joins all 3 tables
- **Complex**: 3-table join + subquery / CTE / window function / HAVING with aggregation filter

### Metadata Levels (same as v1)
- **L0**: Raw DDL only
- **L1**: DDL + column glossary
- **L2**: L1 + field descriptions + allowed values
- **L3**: L2 + business rules (cents, booleans, join guidance, "recent" = 30 days)

### Shot Counts
0, 10, 20, 30, 40 — shots are stratified across complexity tiers so each count includes examples of all join types.

### Trials
3 trials per condition. Temperature = 0. Model = `claude-sonnet-4-20250514`.

### Total API calls
100 questions × 4 metadata levels × 5 shot counts × 3 trials = **6,000 calls**

## Prompt Template
Same as v1:
```
You are a SQL expert for a SaaS e-commerce analytics system.
Convert the user's natural language question into a valid SQLite query.
Return ONLY the raw SQL. No explanation, no markdown fences, no preamble.

--- SCHEMA AND METADATA ---
{metadata}

--- EXAMPLE QUESTIONS AND QUERIES ---
{shots}

--- QUESTION ---
{question}
```

## Scoring
Same as v1 — execution rate + result-set accuracy (column-name agnostic sorted tuple comparison).
Primary metric: result-set accuracy.

## Cache Key Format
`"{question_id}__{metadata_level}__{shot_count}__{trial}"` e.g. `"q042__L2__20__3"`

## Key Implementation Notes
- Shot files must be stratified: each shots_N.json should contain examples from all 4 complexity tiers
- Shots are disjoint from the 100 test questions
- Ground-truth SQL must be validated against the seeded database before running the benchmark
- Log all failures to results/failures.jsonl with full prompt and generated SQL
- Fan out with asyncio, max 10 concurrent requests
- Never re-call API if cache key exists

## How to Run
```bash
pip install anthropic matplotlib pandas numpy
python db/seed.py
python benchmark/runner.py
python analysis/plot.py
python analysis/plot_complexity.py
```
