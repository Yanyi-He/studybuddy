# StudyBuddy roadmap

The executable, distribution, import package, and repository directory are named
`studybuddy`. The original planning pack used OpenMentor; the product was renamed
at project creation. Original planning context is preserved under `vision/` with
the adopted product name and an explicit not-yet-shipped notice.

## Sprint 1 — offline evidence ingestion and concept ledger

Four implementation milestones:

1. [x] Python package, CLI entry point, Git repository, MIT license, and uv lockfile.
2. [x] Scoped read-only vault scan, incremental SQLite WAL/FTS5 index, YAML/headings/links,
   stable identities for supported renames, deletion tombstones, and persistence.
3. [x] Source-backed `seen` candidates, append-once self-reported events with two timestamps,
   conservative progress view, JSON output, and a reproducible offline demo.
4. [x] Synthetic regression suite, Ruff, package build verification, bilingual README,
   ADRs, contribution templates, and GitHub Actions configuration.

Hosted CI and public releases are separate from a local pass. See `VALIDATION.md`.

### Sprint 1 requirement trace

| Requirement from the blueprint | Implementation / evidence |
| --- | --- |
| Read-only doctor and index | `vault.py`, `indexer.py`, doctor and unchanged-vault tests |
| YAML, headings, Wikilinks, hash/version | `markdown.py`, `schema.sql`, parser/indexer regressions |
| Candidates with source provenance, never automatic mastery | `queries.py`, schema checks, every-event-kind negative mastery test |
| Explicit events, unique keys, occurred/recorded timestamps | `events.py`, conflict/timezone/replay/concurrency tests |
| Useful exposure-without-assessment progress | `queries.progress`, CLI integration, `examples/demo.py` |
| Unicode, duplicates, modify/rename/delete, invalid YAML | Synthetic parser and reconciliation fixtures |
| Traversal/symlink defense, rollback, database reopen | `test_vault.py`, fault injection, reopen and persistence tests |
| Offline runtime, WAL + FTS5, parameterized SQL | Runtime socket guard, database/query tests, implementation inspection |
| Open-source packaging and explanation | README, ADRs, CI, LICENSE, contributing guide, local wheel smoke check |

## Sprint 2 — attributable fixed-item assessment evidence

Completed in v0.2.0. Scores verify fixed choices; assistance is learner-declared.

- [x] Nine original recall/application/transfer items over three topics, with immutable
  rubric/evaluator snapshots and deterministic choice scoring.
- [x] Persist answers/hashes, assistance/hints, score, topic and source attribution,
  system-issued sessions, one-answer submissions, and append-only invalidate/restore corrections.
- [x] Replay conservative states with supporting evidence, 24-hour recall delay,
  application/transfer prerequisites, failed-check regression, and `--as-of` corrections.
- [x] Exercise 32 seeded histories (acceptance minimum: 25), including success/failure,
  assisted and AI-generated responses, early repeats, delayed recall, recovery, and reversals.
- [x] Versioned JSONL export/restore with strict staging validation, grade recomputation,
  preserved IDs/idempotency, tombstones, and byte-reproducible same-root round trips.
- [x] Add schema v2 with explicit backup-first migration and rollback/backup restoration tests.
- [x] Update bilingual documentation, full demo, changelog, ADRs, CI and installed-wheel checks.

| Acceptance evidence | Location |
| --- | --- |
| Original versioned items | `src/studybuddy/assessment_catalog.json`, catalog/evaluator tests |
| Atomic session/answer/correction operations | `assessments.py`, idempotency/concurrency/audit-failure tests |
| Replay and conservative regressions | `projector.py`, `tests/fixtures/learning_histories.json`, cutoff/issuance tests |
| Backup-first v1 upgrade | `migration.py`, `tests/test_migrations.py` |
| JSONL domain validation and portability | `ledger.py`, corrupt/rechecksummed-forgery/round-trip tests |
| Full offline product flow | `examples/demo.py`, socket-guard CLI integration, wheel smoke test |

The local result is recorded in [VALIDATION.md](VALIDATION.md); hosted CI remains pending
a GitHub push. `verified_mastered` stays zero because this release does not certify general
mastery or evaluate free-text reasoning. No external adapter was added.

## Subsequent slices — not implemented

- Explicit confirmation and merging of concept candidates; reviewable source relationships.
- MCP read tools first; write tools require independent authorization, validation, and audit.
- Small deterministic review queue and transparent daily task recommendations.
- React dashboard once the evidence/query interfaces stabilize.
- Licensed vocabulary import and FSRS scheduling; optional Eudic integration.
- Opt-in ActivityWatch/availability adapters after privacy and deletion controls.
- Restricted code execution as a separately designed sandbox, never host execution of learner code.

The broader product hypotheses in `vision/PRD.md` need validation. They are not
performance results, clinical claims, or a promise of specific release dates.

## Preparing the public GitHub launch

Local source and history are ready for a new remote. Before announcing a release:

1. Create the intended GitHub repository and push the `main` branch.
2. Confirm the configured Linux/macOS CI actually passes remotely.
3. Enable private vulnerability reporting and choose repository topics/description.
4. Record a real demo and label the release as an alpha with the shipped scope.
5. Invite small contributions with reproducible examples and clearly scoped issues.

Suggested description: “Local-first learning ledger for Obsidian. Turn notes into
source-backed concept candidates and see what still needs independent proof.”
Suggested topics: `obsidian`, `learning`, `local-first`, `python`, `sqlite`, `cli`.
No stars, user counts, benchmark figures, or hosted CI badges are claimed in advance.
