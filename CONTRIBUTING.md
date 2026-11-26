# Contributing to StudyBuddy

Start with a small, reproducible improvement: a parser edge case, CLI error,
source-provenance bug, synthetic fixture, or documentation fix.
For a feature, describe the learning problem and an acceptance test in an issue first.

## Development

Requires Python 3.12+ on macOS/Linux, SQLite with FTS5, and uv.

```sh
uv sync --locked
uv run --offline ruff check .
uv run --offline ruff format --check .
uv run --offline pytest -q
uv run --offline python examples/demo.py
uv build
uv run --offline python scripts/smoke_wheel.py
```

Use synthetic notes in tests and reports. Do not commit a personal vault,
SQLite database, credential, or exported learning history.

## Design rules

- An indexed note is `seen`; self-reported attempts are not verified assessments.
- The vault is read-only. New write adapters require a separate authorization design.
- Parameterize SQL. Record mutations and their audit entry in one transaction.
- Keep the runtime offline. New external integrations must be explicit and opt-in.
- Keep modules small and typed. Add a focused regression test for a meaningful bug.
- Record non-obvious architecture changes in `docs/adr/` and update current behavior docs.
- Do not introduce a frontend, model provider, MCP adapter, or scheduler as incidental scope.
- Preserve published assessment definitions and evaluator versions. A changed rubric
  needs a new item/version; existing snapshots must remain evaluable.
- Learning-state heuristics must remain replayable. Add a seeded history for changes
  to delay, assistance, correction, or regression behavior.

See [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), and [AGENTS.md](AGENTS.md).
By contributing, you agree to license your contribution under the repository's MIT license.
