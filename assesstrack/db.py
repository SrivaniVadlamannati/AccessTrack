import csv
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = Path(__file__).with_name("schema.sql")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now():
    return datetime.now().replace(microsecond=0).isoformat()


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def init_db(seed=True):
    """Create tables and load the CSVs in data/. Safe to call on a fresh file only."""
    db = get_db()
    db.executescript(SCHEMA.read_text())
    if seed:
        data = Path(current_app.config["DATA_DIR"])
        db.executemany("INSERT INTO requirements VALUES (:id,:kind,:name,:description)", _rows(data / "requirements.csv"))
        db.executemany("INSERT INTO coordinators VALUES (:id,:name,:email)", _rows(data / "coordinators.csv"))
        db.executemany("INSERT INTO programs VALUES (:id,:code,:name,:level,:college,:coordinator_id)", _rows(data / "programs.csv"))
        db.executemany("INSERT INTO cycles VALUES (:id,:label,:due_date,:is_current)", _rows(data / "cycles.csv"))
        subs = _rows(data / "submissions.csv")
        for s in subs:
            s["submitted_at"] = s["submitted_at"] or None
        db.executemany("INSERT INTO submissions (id, program_id, cycle_id, submitted_at) VALUES (:id,:program_id,:cycle_id,:submitted_at)", subs)
        db.executemany("INSERT INTO submission_items (submission_id, requirement_id, present) VALUES (:submission_id,:requirement_id,:present)",
                       _rows(data / "submission_items.csv"))
    pw = os.environ.get("ASSESSTRACK_ADMIN_PASSWORD", "assess2026")
    db.execute("INSERT INTO users (username, full_name, password_hash, role) VALUES (?,?,?,?)",
               ("admin", "Assessment Office", generate_password_hash(pw), "admin"))
    db.execute("INSERT INTO users (username, full_name, password_hash, role) VALUES (?,?,?,?)",
               ("gra", "Graduate Research Assistant", generate_password_hash(pw), "staff"))
    db.commit()
    if seed:
        # past cycles were already reviewed; the current one waits for someone to press Run review
        from .review import run_review
        for c in db.execute("SELECT id FROM cycles WHERE is_current = 0 ORDER BY due_date").fetchall():
            run_review(c["id"], "seed")


def log(username, action, submission_id=None, detail=""):
    get_db().execute("INSERT INTO activity (at, username, action, submission_id, detail) VALUES (?,?,?,?,?)",
                     (now(), username, action, submission_id, detail))
