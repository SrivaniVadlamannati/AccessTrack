"""Read/write helpers shared by the JSON API, the HTML views and the CLI."""
import csv
import io
from datetime import date, datetime, timedelta

from .db import get_db, log, now
from .review import LABELS, classify, present_map, requirement_names, review_one


# ---------- cycles ----------
def cycles():
    return [dict(r) for r in get_db().execute("SELECT * FROM cycles ORDER BY due_date DESC")]


def current_cycle():
    r = get_db().execute("SELECT * FROM cycles WHERE is_current = 1").fetchone() or \
        get_db().execute("SELECT * FROM cycles ORDER BY due_date DESC").fetchone()
    return dict(r)


def cycle(cycle_id):
    r = get_db().execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,)).fetchone()
    return dict(r) if r else None


def requirements():
    return [dict(r) for r in get_db().execute("SELECT * FROM requirements ORDER BY id")]


# ---------- submissions ----------
SORTS = {"program": "p.name", "college": "p.college, p.name", "submitted": "s.submitted_at IS NULL, s.submitted_at",
         "status": "s.status, p.name", "open": "s.open_items DESC, p.name", "coordinator": "co.name, p.name"}


def list_submissions(cycle_id, status=None, college=None, q=None, sort="program"):
    sql = """SELECT s.id, s.submitted_at, s.status, s.open_items, s.reviewed_at,
                    p.id AS program_id, p.code, p.name AS program, p.level, p.college,
                    co.name AS coordinator, co.email
             FROM submissions s JOIN programs p ON p.id = s.program_id
             JOIN coordinators co ON co.id = p.coordinator_id
             WHERE s.cycle_id = ?"""
    args = [cycle_id]
    if status:
        sql += " AND s.status = ?"
        args.append(status)
    if college:
        sql += " AND p.college = ?"
        args.append(college)
    if q:
        sql += " AND (p.name LIKE ? OR p.code LIKE ? OR co.name LIKE ?)"
        args += [f"%{q}%"] * 3
    sql += " ORDER BY " + SORTS.get(sort, SORTS["program"])
    rows = [dict(r) for r in get_db().execute(sql, args)]
    missing = missing_by_submission(cycle_id)
    for r in rows:
        r["status_label"] = LABELS.get(r["status"], "Not reviewed")
        r["missing"] = missing.get(r["id"], []) if r["status"] else []
    return rows


def missing_by_submission(cycle_id):
    db = get_db()
    names = requirement_names(db)
    out = {}
    for s in db.execute("SELECT id, submitted_at FROM submissions WHERE cycle_id = ?", (cycle_id,)):
        out[s["id"]] = list(names) if not s["submitted_at"] else []
    for r in db.execute(
        """SELECT si.submission_id, r.name FROM submission_items si JOIN requirements r ON r.id = si.requirement_id
           JOIN submissions s ON s.id = si.submission_id
           WHERE s.cycle_id = ? AND si.present = 0 AND s.submitted_at IS NOT NULL ORDER BY r.id""", (cycle_id,)):
        out[r["submission_id"]].append(r["name"])
    return out


def submission(submission_id):
    db = get_db()
    s = db.execute(
        """SELECT s.*, p.code, p.name AS program, p.level, p.college, co.name AS coordinator, co.email,
                  c.label AS cycle_label, c.due_date
           FROM submissions s JOIN programs p ON p.id = s.program_id
           JOIN coordinators co ON co.id = p.coordinator_id JOIN cycles c ON c.id = s.cycle_id
           WHERE s.id = ?""", (submission_id,)).fetchone()
    if not s:
        return None
    s = dict(s)
    s["status_label"] = LABELS.get(s["status"], "Not reviewed")
    s["items"] = [dict(r) for r in db.execute(
        """SELECT r.id AS requirement_id, r.kind, r.name, r.description,
                  COALESCE(si.present, 0) AS present, si.received_at, si.updated_by
           FROM requirements r LEFT JOIN submission_items si
             ON si.requirement_id = r.id AND si.submission_id = ? ORDER BY r.id""", (submission_id,))]
    s["history"] = [dict(r) for r in db.execute(
        "SELECT at, username, action, detail FROM activity WHERE submission_id = ? ORDER BY at DESC, id DESC", (submission_id,))]
    s["previous"] = [dict(r) for r in db.execute(
        """SELECT c.label, s2.status, s2.open_items FROM submissions s2 JOIN cycles c ON c.id = s2.cycle_id
           WHERE s2.program_id = ? AND s2.id != ? ORDER BY c.due_date DESC""", (s["program_id"], submission_id))]
    return s


def set_item(submission_id, requirement_id, present, username):
    """Record a document/section as received (or reopen it). This is the 'update the assessment software' step."""
    db = get_db()
    sub = db.execute("SELECT submitted_at FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    if sub is None:
        raise LookupError("submission not found")
    if not sub["submitted_at"]:
        # first item for a program that had sent nothing: open the packet
        db.execute("UPDATE submissions SET submitted_at = ? WHERE id = ?", (now(), submission_id))
        for r in db.execute("SELECT id FROM requirements"):
            db.execute("INSERT OR IGNORE INTO submission_items (submission_id, requirement_id, present) VALUES (?,?,0)",
                       (submission_id, r["id"]))
    name = db.execute("SELECT name FROM requirements WHERE id = ?", (requirement_id,)).fetchone()
    if name is None:
        raise LookupError("requirement not found")
    db.execute(
        """INSERT INTO submission_items (submission_id, requirement_id, present, received_at, updated_by)
           VALUES (?,?,?,?,?)
           ON CONFLICT (submission_id, requirement_id) DO UPDATE SET
             present = excluded.present, received_at = excluded.received_at, updated_by = excluded.updated_by""",
        (submission_id, requirement_id, int(present), now() if present else None, username))
    log(username, "item_received" if present else "item_reopened", submission_id, name["name"])
    res = review_one(submission_id, db)
    db.commit()
    return res


def save_notes(submission_id, notes, username):
    db = get_db()
    db.execute("UPDATE submissions SET notes = ? WHERE id = ?", (notes, submission_id))
    log(username, "note", submission_id, notes[:120])
    db.commit()


# ---------- summaries ----------
def summary(cycle_id):
    db = get_db()
    r = dict(db.execute(
        """SELECT COUNT(*) total,
                  SUM(submitted_at IS NOT NULL) received,
                  SUM(status = 'complete') complete, SUM(status = 'late') late,
                  SUM(status = 'missing') missing, SUM(status = 'not_submitted') not_submitted,
                  SUM(status IS NULL) unreviewed, COALESCE(SUM(open_items), 0) open_items
           FROM submissions WHERE cycle_id = ?""", (cycle_id,)).fetchone())
    r = {k: (v or 0) for k, v in r.items()}
    r["on_time_complete_pct"] = round(100 * r["complete"] / r["total"]) if r["total"] else 0
    last = db.execute("SELECT * FROM review_runs WHERE cycle_id = ? ORDER BY id DESC LIMIT 1", (cycle_id,)).fetchone()
    first = db.execute("SELECT * FROM review_runs WHERE cycle_id = ? ORDER BY id LIMIT 1", (cycle_id,)).fetchone()
    r["last_run"] = dict(last) if last else None
    r["first_run"] = dict(first) if first else None
    return r


def gaps(cycle_id):
    db = get_db()
    by_req = [dict(r) for r in db.execute(
        """SELECT r.kind, r.name, SUM(si.present = 0) AS missing, COUNT(si.present) AS received
           FROM requirements r LEFT JOIN submission_items si ON si.requirement_id = r.id
           LEFT JOIN submissions s ON s.id = si.submission_id AND s.cycle_id = ?
           WHERE s.id IS NOT NULL GROUP BY r.id ORDER BY r.id""", (cycle_id,))]
    by_college = [dict(r) for r in db.execute(
        """SELECT p.college, COUNT(*) programs, SUM(s.status='complete') complete, SUM(s.status='late') late,
                  SUM(s.status='missing') missing, SUM(s.status='not_submitted') not_submitted,
                  COALESCE(SUM(s.open_items),0) open_items
           FROM submissions s JOIN programs p ON p.id = s.program_id WHERE s.cycle_id = ?
           GROUP BY p.college ORDER BY open_items DESC""", (cycle_id,))]
    trend = [dict(r) for r in db.execute(
        """SELECT c.label, COUNT(*) total, SUM(s.status='complete') complete,
                  ROUND(100.0 * SUM(s.status='complete') / COUNT(*)) pct
           FROM submissions s JOIN cycles c ON c.id = s.cycle_id GROUP BY c.id ORDER BY c.due_date""")]
    return {"by_requirement": by_req, "by_college": by_college, "trend": trend}


def colleges():
    return [r[0] for r in get_db().execute("SELECT DISTINCT college FROM programs ORDER BY college")]


def review_runs(cycle_id):
    return [dict(r) for r in get_db().execute("SELECT * FROM review_runs WHERE cycle_id = ? ORDER BY id DESC", (cycle_id,))]


def activity(limit=100):
    return [dict(r) for r in get_db().execute(
        """SELECT a.*, p.name AS program FROM activity a
           LEFT JOIN submissions s ON s.id = a.submission_id LEFT JOIN programs p ON p.id = s.program_id
           ORDER BY a.at DESC, a.id DESC LIMIT ?""", (limit,))]


# ---------- reminders ----------
def reminders(cycle_id, reply_by=None):
    c = cycle(cycle_id)
    reply_by = reply_by or (date.today() + timedelta(days=7))
    groups = {}
    for s in list_submissions(cycle_id, sort="coordinator"):
        if s["status"] not in ("missing", "not_submitted"):
            continue
        g = groups.setdefault(s["email"], {"coordinator": s["coordinator"], "email": s["email"], "programs": []})
        g["programs"].append({"id": s["id"], "program": s["program"], "status": s["status"], "missing": s["missing"]})
    out = []
    for g in groups.values():
        first = g["coordinator"].split()[0]
        lines = []
        for p in g["programs"]:
            if p["status"] == "not_submitted":
                lines.append(f"  - {p['program']}: report not received yet")
            else:
                lines.append(f"  - {p['program']}: {', '.join(p['missing'])}")
        g["subject"] = f"{c['label']} assessment report: {sum(len(p['missing']) for p in g['programs'])} open item(s)"
        g["body"] = (
            f"Hi {first},\n\nThank you for your work on the {c['label']} assessment reports. "
            f"Our review found a few pieces still open:\n\n" + "\n".join(lines) +
            f"\n\nCould you upload these to the assessment software by {reply_by:%B %d}? "
            "If something is already in progress, send what you have and mark it as a draft. "
            "Reply to this email if you'd like help.\n\nThank you,\nOffice of Academic Assessment")
        out.append(g)
    return out


# ---------- import ----------
def import_csv(cycle_id, text, username):
    """
    Columns: program_code, submitted_at (YYYY-MM-DD or blank), then one column per requirement name with Y/N.
    Creates or updates the submission for each program in the given cycle.
    """
    db = get_db()
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    reqs = {r["name"]: r["id"] for r in db.execute("SELECT id, name FROM requirements")}
    needed = {"program_code", "submitted_at", *reqs}
    missing_cols = needed - set(reader.fieldnames or [])
    if missing_cols:
        raise ValueError("missing columns: " + ", ".join(sorted(missing_cols)))
    created = updated = 0
    errors = []
    for i, row in enumerate(reader, start=2):
        prog = db.execute("SELECT id FROM programs WHERE code = ?", (row["program_code"].strip(),)).fetchone()
        if not prog:
            errors.append(f"line {i}: unknown program code {row['program_code']!r}")
            continue
        sub_at = row["submitted_at"].strip() or None
        if sub_at:
            try:
                sub_at = datetime.fromisoformat(sub_at).replace(microsecond=0).isoformat()
            except ValueError:
                errors.append(f"line {i}: bad date {row['submitted_at']!r}")
                continue
        existing = db.execute("SELECT id FROM submissions WHERE program_id = ? AND cycle_id = ?", (prog["id"], cycle_id)).fetchone()
        if existing:
            sid = existing["id"]
            db.execute("UPDATE submissions SET submitted_at = ? WHERE id = ?", (sub_at, sid))
            updated += 1
        else:
            sid = db.execute("INSERT INTO submissions (program_id, cycle_id, submitted_at) VALUES (?,?,?)",
                             (prog["id"], cycle_id, sub_at)).lastrowid
            created += 1
        for name, rid in reqs.items():
            present = row[name].strip().lower() in ("y", "yes", "1", "true", "x")
            db.execute("""INSERT INTO submission_items (submission_id, requirement_id, present, updated_by) VALUES (?,?,?,?)
                          ON CONFLICT (submission_id, requirement_id) DO UPDATE SET present = excluded.present,
                          updated_by = excluded.updated_by""", (sid, rid, int(present), username))
    log(username, "import", None, f"{created} created, {updated} updated, {len(errors)} errors")
    db.commit()
    return {"created": created, "updated": updated, "errors": errors}


def import_template():
    names = [r["name"] for r in requirements()]
    progs = get_db().execute("SELECT code FROM programs ORDER BY id LIMIT 3").fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["program_code", "submitted_at", *names])
    for i, p in enumerate(progs):
        w.writerow([p["code"], f"2026-10-{10 + i:02d}" if i < 2 else "", *(["Y"] * len(names) if i == 0 else ["Y", "Y", "N", "Y", "Y", "Y", "Y", "Y", "Y", "N"] if i == 1 else ["N"] * len(names))])
    return out.getvalue()
