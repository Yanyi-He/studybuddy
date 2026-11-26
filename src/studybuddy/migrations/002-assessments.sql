CREATE TABLE assessment_sessions (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    concept_id TEXT NOT NULL REFERENCES concepts(id),
    assessment_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    assessment_json TEXT NOT NULL,
    assessment_sha256 TEXT NOT NULL,
    source_snapshot_json TEXT NOT NULL,
    issued_at TEXT NOT NULL
);

CREATE TABLE assessment_attempts (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL UNIQUE REFERENCES assessment_sessions(id),
    answer_json TEXT NOT NULL,
    answer_sha256 TEXT NOT NULL,
    assistance TEXT NOT NULL CHECK (assistance IN ('independent', 'assisted', 'ai_generated')),
    hints_used INTEGER NOT NULL CHECK (hints_used >= 0),
    score REAL NOT NULL CHECK (score >= 0 AND score <= 1),
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    rubric_version TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    feedback_json TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    CHECK (assistance != 'independent' OR hints_used = 0)
);

CREATE TABLE assessment_corrections (
    sequence INTEGER PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    attempt_id TEXT NOT NULL REFERENCES assessment_attempts(id),
    action TEXT NOT NULL CHECK (action IN ('invalidate', 'restore')),
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX sessions_concept ON assessment_sessions(concept_id, issued_at);
CREATE INDEX corrections_attempt ON assessment_corrections(attempt_id, sequence);
