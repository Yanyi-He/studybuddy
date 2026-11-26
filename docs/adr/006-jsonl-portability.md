# ADR-006: Validated logical ledger snapshots

Status: accepted · 2026-11-26

## Context

Learners should own portable history before external adapters are introduced. A
learning-event-only dump would lose assessment definitions, source identities,
corrections, and relationships needed to reproduce a projection.

## Decision

Export a consistent read transaction as versioned JSONL: manifest, source contexts,
self-reported events, sessions, attempts, corrections, and a count/SHA-256 trailer.
Omit operational audit and FTS cache; rebuild FTS on import. Notes' bodies are absent.
The export includes private metadata and submitted answers, and is not encrypted.

Restore only into a new path, with an explicit user-selected vault root; the manifest
does not authorize filesystem access. Bound input to 64 MiB. Validate JSON structure,
field types, IDs, paths, timestamps, references, source consistency, topic binding,
and correction order in a temporary in-memory database. Accept only known immutable
item snapshots and recompute every grade. Unknown fields (including mastery flags),
modified rubrics/evaluators, and inconsistent scores are rejected. Persist the fully
validated ledger, new import audit, and reconstructed search index only after success.

## Alternatives

Blind SQL dumps are executable input and version-sensitive. Merging into an existing
ledger introduces collision and conflict policy outside this slice. A checksum alone
detects corruption but does not validate domain semantics.

## Consequences

JSONL is a logical learning-history transfer, not a complete audit/database backup.
An explicit new root supports relocation without reading any vault file during import.
Exact same-root export/import/export is byte-reproducible, and projections/IDs/replay
keys survive. Import currently requires schema v2 and the known `exact-fields-v1`
catalog. Larger histories need a streaming/staging design. Checksums are not signatures;
a user-controlled export is not authenticated proof of truthful assistance or real
study times. Imported answers are rubric-checked, not externally witnessed learning.
