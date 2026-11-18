PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'staff'   -- staff | admin
);

CREATE TABLE coordinators (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL,
    email TEXT NOT NULL
);

CREATE TABLE programs (
    id             INTEGER PRIMARY KEY,
    code           TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    level          TEXT NOT NULL,
    college        TEXT NOT NULL,
    coordinator_id INTEGER REFERENCES coordinators(id)
);

CREATE TABLE cycles (
    id         INTEGER PRIMARY KEY,
    label      TEXT UNIQUE NOT NULL,
    due_date   TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE requirements (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('document', 'section')),
    name        TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE submissions (
    id           INTEGER PRIMARY KEY,
    program_id   INTEGER NOT NULL REFERENCES programs(id),
    cycle_id     INTEGER NOT NULL REFERENCES cycles(id),
    submitted_at TEXT,                 -- NULL means nothing received yet
    status       TEXT,                 -- set by the review engine
    open_items   INTEGER,
    reviewed_at  TEXT,
    notes        TEXT DEFAULT '',
    UNIQUE (program_id, cycle_id)
);

CREATE TABLE submission_items (
    submission_id  INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    requirement_id INTEGER NOT NULL REFERENCES requirements(id),
    present        INTEGER NOT NULL DEFAULT 0,
    received_at    TEXT,               -- set when staff mark a missing item received
    updated_by     TEXT,
    PRIMARY KEY (submission_id, requirement_id)
);

CREATE TABLE review_runs (
    id            INTEGER PRIMARY KEY,
    cycle_id      INTEGER NOT NULL REFERENCES cycles(id),
    run_at        TEXT NOT NULL,
    run_by        TEXT NOT NULL,
    total         INTEGER, complete INTEGER, missing INTEGER, late INTEGER,
    not_submitted INTEGER, open_items INTEGER, duration_ms INTEGER
);

CREATE TABLE activity (
    id            INTEGER PRIMARY KEY,
    at            TEXT NOT NULL,
    username      TEXT NOT NULL,
    action        TEXT NOT NULL,
    submission_id INTEGER REFERENCES submissions(id),
    detail        TEXT
);

CREATE INDEX idx_sub_cycle ON submissions(cycle_id);
CREATE INDEX idx_activity_at ON activity(at DESC);
