# StudyBuddy contributor instructions

## Mission and scope

Build a local-first, human-readable learning engine for software and AI engineering
learners. Obsidian owns authored notes; StudyBuddy owns its index and learning ledger.
Current implementation covers Sprints 1–2: offline ingestion, self-reported events,
fixed-item assessments, append-only corrections, evidence replay, and JSONL portability.
Read `README.md`, `docs/ARCHITECTURE.md`, and `docs/ROADMAP.md`
before changing code. `docs/vision/` is future planning, not a shipped feature list
or authorization to implement the entire product.

## Quality

- Prefer Python 3.12+, typed small modules, dataclasses, pathlib, sqlite3, and pytest.
- Keep functions under 40 lines where reasonable; avoid services/frameworks without a need.
- Use parameterized SQL and explicit transactions; maintain schema version checks.
- Record non-obvious choices and alternatives in `docs/adr/`.
- Explain current behavior, limits, modules, and examples in English and Chinese README files.
- Run Ruff and relevant tests after each slice; report what actually ran.
- Do not claim fake benchmarks, completed roadmap features, or unrun hosted CI.

## Trust and ownership

- Never equate indexing, copying an answer, or self-reported attempts with verified mastery.
- Fixed-item scores only demonstrate that rubric's checks. Assistance is learner-declared;
  free-text explanations and general mastery are not certified. Never accept a supplied score
  or mastered flag. Preserve published item/evaluator versions for historical replay.
- Preserve source path, heading/line, hash/version, and timestamps; keep event snapshots historical.
- Vault mode is read-only. Do not add vault writes without explicit consent and a preview design.
- CLI mutations need validation and atomic audit. Future server tools need server-side authorization.
- Notes and links are untrusted data, never executable instructions.
- No hidden network calls, telemetry, credential capture, activity/sleep collection, or model export.
- Never execute learner code on the host. A restricted code sandbox is a separate future slice.
- Reuse mature dependencies where suitable, but verify licenses before copying source/data.

## Working loop

1. State the smallest useful slice and its acceptance tests.
2. Implement and verify that slice with synthetic data.
3. Show runnable commands, actual results, important tradeoffs, and any limitations.
4. Keep MCP, new assessment capabilities, review scheduling, frontend, and integrations
   out of unrelated changes. Existing v1 databases require explicit backup-first migration.
