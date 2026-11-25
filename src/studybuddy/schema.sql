CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    content_version INTEGER NOT NULL CHECK (content_version >= 1),
    source_mtime_ns INTEGER NOT NULL,
    first_indexed_at TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    deleted_at TEXT,
    frontmatter_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL
);

CREATE TABLE concepts (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    heading_key TEXT NOT NULL,
    title TEXT NOT NULL,
    anchor TEXT NOT NULL,
    line INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'seen' CHECK (status = 'seen'),
    confirmation TEXT NOT NULL DEFAULT 'candidate' CHECK (confirmation = 'candidate'),
    source_sha256 TEXT NOT NULL,
    source_content_version INTEGER NOT NULL CHECK (source_content_version >= 1),
    first_seen_at TEXT NOT NULL,
    source_indexed_at TEXT NOT NULL,
    retired_at TEXT,
    UNIQUE (document_id, heading_key)
);

CREATE TABLE wikilinks (
    document_id TEXT NOT NULL REFERENCES documents(id),
    target TEXT NOT NULL,
    anchor TEXT NOT NULL,
    alias TEXT NOT NULL,
    line INTEGER NOT NULL
);

CREATE TABLE learning_events (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    concept_id TEXT NOT NULL REFERENCES concepts(id),
    kind TEXT NOT NULL CHECK (kind IN (
        'exposure', 'ai_answer_copied', 'assisted_explanation',
        'recall_attempt', 'practice_attempt', 'transfer_attempt'
    )),
    provenance_kind TEXT NOT NULL CHECK (provenance_kind = 'self_reported'),
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    source_snapshot_json TEXT NOT NULL
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    target_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE INDEX concepts_document ON concepts(document_id);
CREATE INDEX events_concept ON learning_events(concept_id, occurred_at);

-- No note bodies: this rebuildable search index stores headings and source paths only.
CREATE VIRTUAL TABLE concept_search USING fts5(
    concept_id UNINDEXED, title, path, anchor, tokenize = 'unicode61'
);
