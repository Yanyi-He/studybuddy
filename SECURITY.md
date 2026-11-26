# Security and privacy

StudyBuddy runs locally with the current user's filesystem permissions. There is
no server, authentication endpoint, telemetry, note execution, or model provider
in v0.2.0. Source text, Wikilinks, answer files, and imported ledgers are untrusted data.

The indexer opens notes for reading only, skips every symlink and hidden path,
and uses directory descriptors plus `O_NOFOLLOW` on macOS/Linux. The SQLite
database must be outside the vault. Explicit CLI mutations validate inputs and
append a local audit entry in the same transaction. A future MCP/HTTP adapter
must enforce authorization on the server; this CLI is not that authorization layer.

The database contains private metadata: the absolute vault root, relative paths,
frontmatter, headings, Wikilink targets, hashes, timestamps, self-reported learning events,
assessment answers, assistance declarations, scores, and correction reasons.
It does not store note bodies. It is not encrypted. Use your OS
account and disk encryption to control access. Generated database files are ignored
by Git; that does not make arbitrary copies of private notes safe to publish.

JSONL exports also contain private answers and source metadata. Export/backup paths
must be outside the vault and cannot overwrite existing files. Restore requires a
new DB plus an explicitly selected vault; the manifest is not filesystem authority.
All records are staged and checked, and every score is recomputed against the known
catalog. Checksums detect corruption and are not signatures. Source authors can
control exported answers/times; neither imports nor scores certify honest independent
learning. Fixed-item answer keys are public, assistance is declared, explanations are
ungraded, and learner code is never executed.

Schema v1 is upgraded only through the explicit `migrate --backup` command after a
consistent backup and integrity check. Read commands do not silently migrate data.

For a sensitive vulnerability, use the repository's GitHub **Security → Report a
vulnerability** if private reporting is enabled. If unavailable, create a minimal
issue asking the maintainer to enable private reporting without disclosing the
vulnerability, private notes, credentials, or exploit details. Ordinary bugs can
use the bug report template with synthetic fixtures.

There is no formal support SLA for this alpha. Only the current source tree is maintained.
