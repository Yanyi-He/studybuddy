# ADR-001: Read-only Obsidian source

Status: accepted · 2026-11-25

## Context

Authored Markdown belongs to the learner. Importing a source must not edit it or
silently widen access through links, hidden folders, or injected instructions.

## Decision

Use direct filesystem reads for one explicitly chosen canonical vault root. Skip
all symlinks and hidden paths. Use descriptor-relative `O_NOFOLLOW` reads on POSIX;
place SQLite outside the vault. Parse Wikilinks as inert strings, never as commands
or permission to read another location. Do not persist note bodies.

## Alternatives

An Obsidian plugin/REST integration would add setup and another authorization surface.
A duplicate editor would add maintenance while moving ownership away from the vault.
Following only internal symlinks would require more alias and race handling.

## Consequences and revisit trigger

The alpha supports macOS/Linux and ordinary Markdown files. Metadata remains private
and must be protected locally. Internal symlink collections and Windows need tested
adapters before support is advertised. Vault writes, if requested later, require a
separate opt-in authorization and preview design.
