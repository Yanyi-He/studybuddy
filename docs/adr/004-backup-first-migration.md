# ADR-004: Explicit backup-first schema migration

Status: accepted · 2026-11-26

## Context

Schema v2 adds assessment sessions, attempts, and corrections to an existing ledger.
Reads must not silently upgrade a user's only copy or discard Sprint 1 history.

## Decision

Fresh databases initialize at v2. Existing v1 databases require an explicit `migrate`
command and a new backup path outside the vault. Under `BEGIN IMMEDIATE`, verify the
application/schema version, make and integrity-check a consistent backup using a separate
reader connection, then apply v2 DDL, schema marker, and audit in one transaction.
The backup API must not run on the connection with an active write transaction.
No existing backup is overwritten. A valid backup remains available after a later
migration failure. A current v2 database is a no-op without creating another backup.

## Alternatives

Automatic migration on a progress query would turn a read into an unannounced write.
Copying just the main SQLite file could omit current WAL data. An ORM/Alembic adds
unnecessary framework machinery for one explicit additive migration.

## Consequences

Upgrading a real v1 ledger requires one user-invoked command. The source is writer-locked
during backup/migration, appropriate for the small single-user alpha. Tests exercise
backup restore, preserved events, overwrite refusal, vault boundaries, idempotency, and
rollback after audit failure. This is not a power-loss or long-running contention proof.

References: [Python backup API](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup),
[SQLite online backup](https://www.sqlite.org/backup.html).
