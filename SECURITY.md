# Security and privacy

StudyBuddy runs locally with the current user's filesystem permissions. There is
no server, authentication endpoint, telemetry, note execution, or model provider
in Sprint 1. Source text and Wikilinks are untrusted data.

The indexer opens notes for reading only, skips every symlink and hidden path,
and uses directory descriptors plus `O_NOFOLLOW` on macOS/Linux. The SQLite
database must be outside the vault. Explicit CLI mutations validate inputs and
append a local audit entry in the same transaction. A future MCP/HTTP adapter
must enforce authorization on the server; this CLI is not that authorization layer.

The database contains private metadata: the absolute vault root, relative paths,
frontmatter, headings, Wikilink targets, hashes, timestamps, and self-reported
learning events. It does not store note bodies. It is not encrypted. Use your OS
account and disk encryption to control access. Generated database files are ignored
by Git; that does not make arbitrary copies of private notes safe to publish.

For a sensitive vulnerability, use the repository's GitHub **Security → Report a
vulnerability** if private reporting is enabled. If unavailable, create a minimal
issue asking the maintainer to enable private reporting without disclosing the
vulnerability, private notes, credentials, or exploit details. Ordinary bugs can
use the bug report template with synthetic fixtures.

There is no formal support SLA for this alpha. Only the current source tree is maintained.
