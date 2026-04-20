"""
scorer.py — execution and result-set accuracy scoring.

can_execute : returns True if the SQL runs without error.
result_matches : returns True if the generated SQL produces the same result set
                 as the ground-truth SQL (column-name agnostic, sorted tuples).
                 Float tolerance: 0.01 for scalar numeric results.
"""
import sqlite3


def _run(sql: str, db_path: str):
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(sql).fetchall()
        return rows
    finally:
        con.close()


def can_execute(sql: str, db_path: str) -> bool:
    try:
        _run(sql, db_path)
        return True
    except Exception:
        return False


def _normalise(rows):
    """Sort rows and round floats for stable comparison."""
    def norm_row(row):
        out = []
        for v in row:
            if isinstance(v, float):
                out.append(round(v, 2))
            else:
                out.append(v)
        return tuple(out)
    return sorted((norm_row(r) for r in rows),
                  key=lambda row: tuple((v is None, type(v).__name__, v) for v in row))


def result_matches(generated_sql: str, ground_truth_sql: str, db_path: str) -> bool:
    try:
        gen_rows = _run(generated_sql, db_path)
        gt_rows  = _run(ground_truth_sql, db_path)
    except Exception:
        return False

    gen_norm = _normalise(gen_rows)
    gt_norm  = _normalise(gt_rows)

    # Scalar case: allow float tolerance
    if len(gt_norm) == 1 and len(gt_norm[0]) == 1:
        gt_val  = gt_norm[0][0]
        gen_val = gen_norm[0][0] if gen_norm and gen_norm[0] else None
        if isinstance(gt_val, (int, float)) and isinstance(gen_val, (int, float)):
            return abs(float(gt_val) - float(gen_val)) <= 0.01
        return gt_val == gen_val

    return gen_norm == gt_norm
