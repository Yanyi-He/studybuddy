# Local validation — 2026-11-25

Environment: macOS arm64, CPython 3.12.6, SQLite 3.54.1 with FTS5,
uv 0.13.9, pytest 9.2.0, Ruff 0.17.6, PyYAML 6.0.4.
Dependencies are pinned in `uv.lock`. Runtime checks used synthetic notes only.

| Check | Observed result |
| --- | --- |
| `pytest -q` | **85 passed** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed |
| Offline demo | 3 documents, 6 candidates; repeated index reports 3 unchanged |
| Copied AI event demo | First append created; retry returns existing event; 0 verified mastered |
| `uv build --offline` with prepared build cache | Source distribution and wheel built successfully |
| Installed-wheel smoke test | Wheel imported from isolated site-packages outside the checkout; full demo passed |
| GitHub configuration YAML | Workflow, Dependabot, and both issue forms parsed successfully |
| Relative documentation links | Checked against repository files |

The test suite covers CJK, hashes with unchanged mtime, source/version provenance,
duplicate files/headings, rename/delete/restore, tombstone search removal, malformed
or unsafe YAML, note size/encoding failures, traversal and symlinks, read-only vault
behavior, database reopen, schema ownership, rollback on audit failure, concurrent
initial indexing, event replay/conflicts/timezones, and negative mastery assertions.
A 100-note fixture produces 200 candidates and an idempotent second index.
Runtime network calls are prohibited by a socket guard in the CLI integration test.

## Reproduce

```sh
uv sync --locked
uv run --offline ruff check .
uv run --offline ruff format --check .
uv run --offline pytest -q
uv run --offline python examples/demo.py
uv build
uv run --offline python scripts/smoke_wheel.py dist/*.whl
```

The wheel smoke script prepares only runtime dependencies from the lockfile in a
temporary environment, installs the actual wheel with `--no-deps`, checks the import
location, then invokes the original demo from a temporary working directory.
It uses the existing dependency cache; initial dependency installation/build may
require network access. The application runtime does not.

## Not yet verified

- GitHub-hosted CI: configured, not run until the repository is pushed.
- Linux and Python 3.13 execution: included in CI, not exercised in this local session.
- Windows: unsupported; POSIX descriptor-based file access is intentional.
- Real private vaults, very large vault performance, power-loss recovery, long-running
  contention, or adversarial filesystem mutation beyond the current boundary tests.
- Assessments, independent grading, MCP, scheduler, frontend, code sandbox, or external
  integrations: not implemented in Sprint 1.

No throughput, p95, retention improvement, user count, or GitHub star claim is made.
