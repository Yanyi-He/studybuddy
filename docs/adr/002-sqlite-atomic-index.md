# ADR-002: SQLite, FTS5, and atomic reconciliation

Status: accepted · 2026-11-25

## Context

The first useful slice is offline and single-user. Rename matching, stale concepts,
search entries, deletions, and audit must agree after failures or concurrent retries.

## Decision

Use standard-library sqlite3 with WAL, foreign keys, `synchronous=FULL`, a busy timeout,
and a version/application marker. Use one `BEGIN IMMEDIATE` transaction per scan,
including vault binding, source/candidate/search mutations, tombstones, and audit.
Unchanged scans have no logical mutations. Use FTS5 for titles/paths/anchors without
persisting whole note bodies. Use a one-to-one missing/new content-hash pair as the
only rename inference; do not guess ambiguous matches.

## Alternatives

Per-file transactions shorten write locks but allow half-applied reconciliation after
failure. PostgreSQL adds an unnecessary service for one local user. An ORM or migration
framework adds little value to one initial schema. Embeddings require an additional
model/index lifecycle without a measured retrieval need.

## Consequences and revisit trigger

Scans hold a writer lock while reading; large vaults may block event writes. Every
visible Markdown file is still hashed. FTS5 must exist in the Python SQLite build;
`unicode61` does not provide Chinese word segmentation. If profiling shows meaningful
lock/search problems, add staged snapshots with generation checks or measured retrieval
improvements. Add explicit, backup-tested migrations before introducing schema v2.
