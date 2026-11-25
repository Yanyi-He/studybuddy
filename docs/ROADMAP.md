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

## Proposed Sprint 2 — independent assessment evidence

Not implemented. Keep the first follow-up as a separate reviewable slice:

- Add a small original assessment fixture set with explicit rubric/evaluator versions.
- Record answers, assistance, score, source/assessment attribution, and corrections.
- Derive conservative learning states by replaying evidence; never trust a supplied `mastered` flag.
- Verify success, failure, assisted attempts, delayed recall, and state reversals over
  at least 25 seeded histories. Treat any thresholds as product heuristics to evaluate.
- Add ledger JSONL export with round-trip validation before adding external adapters.

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
