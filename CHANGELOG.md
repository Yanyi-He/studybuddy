# Changelog

## 0.2.0 — 2026-11-26 (Sprint 2)

- Add nine original, versioned fixed-item recall/application/transfer assessments.
- Record immutable sessions, scored answers, assistance, hints, hashes, and source snapshots.
- Add idempotent invalidation/restoration records and historical evidence replay.
- Introduce conservative learning states, delayed-recall checks, and regression after failures.
- Add validated JSONL export and restore into new databases with round-trip coverage.
- Introduce schema v2 and explicit, backup-first migration from Sprint 1 databases.
- Expand offline demo, package smoke checks, and synthetic regression histories.

Existing v1 databases require `studybuddy --db PATH migrate --backup NEW_BACKUP_PATH`.
The evaluator checks fixed choices only; assistance is declared, explanations are ungraded,
and general mastery is not certified. MCP, review scheduling, and frontend remain future work.

## 0.1.0 — 2026-11-25 (Sprint 1)

- Ship read-only Obsidian indexing, source-backed candidates, self-reported events,
  conservative progress, offline demo, and open-source project foundations.
