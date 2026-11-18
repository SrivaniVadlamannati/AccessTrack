"""
The review engine.

A submission is checked against every row in `requirements`:

    not_submitted  nothing received for the cycle
    missing        received, but at least one document or plan section is absent
    late           everything is there, but it came in after the due date
    complete       everything is there and it was on time

The pure function `classify` holds the rules so it can be unit tested
without a database. `run_review` applies it to a whole cycle and records
the run so the dashboard can show progress across runs.
"""
import time
from dataclasses import dataclass, field
from datetime import date, datetime

from .db import get_db, log, now

STATUSES = ("complete", "late", "missing", "not_submitted")
LABELS = {"complete": "Complete", "late": "Late", "missing": "Missing items", "not_submitted": "Not submitted"}


@dataclass
class Result:
    status: str
    missing: list = field(default_factory=list)


def classify(submitted_at, due_date, present_by_requirement, requirement_names):
    """present_by_requirement: {requirement name: bool}."""
    if not submitted_at:
        return Result("not_submitted", list(requirement_names))
    missing = [n for n in requirement_names if not present_by_requirement.get(n)]
    if missing:
        return Result("missing", missing)
    sub_day = datetime.fromisoformat(submitted_at).date()
    due = date.fromisoformat(due_date) if isinstance(due_date, str) else due_date
    return Result("late" if sub_day > due else "complete")


def requirement_names(db=None):
    db = db or get_db()
    return [r["name"] for r in db.execute("SELECT name FROM requirements ORDER BY id")]


def present_map(submission_id, db=None):
    db = db or get_db()
    rows = db.execute(
        """SELECT r.name, COALESCE(si.present, 0) AS present
           FROM requirements r
           LEFT JOIN submission_items si ON si.requirement_id = r.id AND si.submission_id = ?""",
        (submission_id,),
    )
    return {r["name"]: bool(r["present"]) for r in rows}


def review_one(submission_id, db=None):
    db = db or get_db()
    s = db.execute(
        "SELECT s.id, s.submitted_at, c.due_date FROM submissions s JOIN cycles c ON c.id = s.cycle_id WHERE s.id = ?",
        (submission_id,),
    ).fetchone()
    res = classify(s["submitted_at"], s["due_date"], present_map(s["id"], db), requirement_names(db))
    db.execute("UPDATE submissions SET status = ?, open_items = ?, reviewed_at = ? WHERE id = ?",
               (res.status, len(res.missing), now(), s["id"]))
    return res


def run_review(cycle_id, username):
    db = get_db()
    t0 = time.perf_counter()
    names = requirement_names(db)
    due = db.execute("SELECT due_date FROM cycles WHERE id = ?", (cycle_id,)).fetchone()["due_date"]

    # one query for all items in the cycle instead of one per submission
    items = {}
    for r in db.execute(
        """SELECT si.submission_id, r.name, si.present FROM submission_items si
           JOIN requirements r ON r.id = si.requirement_id
           JOIN submissions s ON s.id = si.submission_id WHERE s.cycle_id = ?""",
        (cycle_id,),
    ):
        items.setdefault(r["submission_id"], {})[r["name"]] = bool(r["present"])

    counts = dict.fromkeys(STATUSES, 0)
    open_total = 0
    stamp = now()
    updates = []
    subs = db.execute("SELECT id, submitted_at FROM submissions WHERE cycle_id = ?", (cycle_id,)).fetchall()
    for s in subs:
        res = classify(s["submitted_at"], due, items.get(s["id"], {}), names)
        counts[res.status] += 1
        open_total += len(res.missing)
        updates.append((res.status, len(res.missing), stamp, s["id"]))
    db.executemany("UPDATE submissions SET status = ?, open_items = ?, reviewed_at = ? WHERE id = ?", updates)

    ms = round((time.perf_counter() - t0) * 1000)
    db.execute(
        """INSERT INTO review_runs (cycle_id, run_at, run_by, total, complete, missing, late, not_submitted, open_items, duration_ms)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (cycle_id, stamp, username, len(subs), counts["complete"], counts["missing"], counts["late"],
         counts["not_submitted"], open_total, ms),
    )
    log(username, "review_run", None, f"{len(subs)} reviewed, {counts['missing'] + counts['not_submitted']} flagged, {ms} ms")
    db.commit()
    return {"cycle_id": cycle_id, "total": len(subs), **counts, "open_items": open_total, "duration_ms": ms, "run_at": stamp}
