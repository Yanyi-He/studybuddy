# Local validation — 2026-11-26 / v0.2.0

Environment: macOS arm64, CPython 3.12.6, SQLite 3.54.1 with FTS5,
uv 0.13.9, pytest 9.2.0, Ruff 0.17.6, PyYAML 6.0.4.
Dependencies remain pinned in `uv.lock`; all product checks used synthetic data.
The previous Sprint 1 baseline was 85 passing tests on 2026-11-25.

| Check | Observed result |
| --- | --- |
| Full pytest suite | **192 passed** |
| Ruff check and format | Passed |
| Seeded evidence histories | **32 histories** passed (minimum requested: 25) |
| Source ingestion demo | 3 documents / 6 candidates; repeated scan reports 3 unchanged |
| Copied AI event | Append-once replay; no assessment state promotion |
| Fixed-item assessment | Synthetic answer scores 1.0; state is only `assessed_once` |
| Append-only correction | Invalidate returns to `exposed`; restore returns to `assessed_once` |
| JSONL round trip | Same-root export/import/export byte equality; IDs, projections, cutoffs, and replay keys preserved |
| Corrupt/forged inputs | Truncation, checksum/format errors, traversal, broken references, modified rubrics/evaluators, score mismatch, and mastery fields rejected |
| Schema v1 migration | Backup integrity, old events, restore/re-migrate, no overwrite, no-op repeat, and failed-audit rollback passed |
| Build | v0.2.0 source distribution and wheel built with prepared offline cache |
| Isolated wheel | Imported from temporary site-packages outside checkout; complete Sprint 1+2 demo passed |

The suite retains the Sprint 1 CJK, duplicate/source-version, rename/delete/restore,
invalid YAML/UTF-8, 100-note indexing, traversal/symlink, persistence, idempotency, and
transaction/audit checks. New coverage includes one answer per session, explicit
assistance, conflicting replays, grade version consistency, concurrent submission retries,
partial failures, historical corrections, and a session issued too early to qualify for
delayed recall even if submitted days later. Runtime socket guards cover the quiz,
correction, export, import, index, and progress CLI paths.

The demo uses a supplied synthetic answer and does not claim a real delayed-learning
outcome. The 24-hour histories use an injected clock only in tests; the CLI has no
fake-time/backdated-assessment flag. General mastery is never certified.

## Reproduce

```sh
uv sync --locked
uv run --offline ruff check .
uv run --offline ruff format --check .
uv run --offline pytest -q
uv run --offline python examples/demo.py
uv build
uv run --offline python scripts/smoke_wheel.py
```

The smoke script selects the current version's wheel by default, so an older artifact
in `dist/` does not get selected accidentally. It prepares locked runtime dependencies
in a temporary environment, installs the wheel without an editable project, verifies
the site-packages import, and runs the full demo outside the checkout. Fresh dependency
installation/build can need network access; application runtime remains offline.

## Not yet verified

- GitHub-hosted CI: configured, not run until the repository is pushed.
- Linux/Python 3.13 execution: in CI, not exercised in this macOS/Python 3.12 session.
- Windows: unsupported; POSIX descriptor-based access is intentional.
- Real private vaults, large-history memory/performance, power-loss recovery, sustained
  contention, or adversarial filesystem races beyond current boundary tests.
- Free-text correctness, actual unobserved assistance, honest wall-clock times, scientific
  learning thresholds, or real-world application/transfer ability.
- MCP, scheduling, frontend, model grading, code sandbox, or external integrations: not implemented.

No throughput, retention improvement, user count, hosted CI, or GitHub star claim is made.
