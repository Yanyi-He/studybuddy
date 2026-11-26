# ADR-003: Keep source exposure separate from verified learning

Status: accepted · 2026-11-25

Sprint 2 follow-up: [ADR-005](005-fixed-item-evidence.md) implements a separate
assessment/projector layer. The no-promotion rule for self-reports remains in force;
the conservative Sprint 1 progress limitation below is historical context.

## Context

Notes and copied answers do not demonstrate independent recall. File modification
times are unrelated to actual study time. Retried commands must not inflate evidence.

## Decision

Treat extracted headings as candidates with status `seen`. Store explicitly supplied
learning events as `self_reported`, with separate timezone-aware `occurred_at` and
`recorded_at`, a unique idempotency key, and a source snapshot. Append event and audit
atomically. Reject semantic conflicts on a reused key. Preserve events across source
changes/deletions. No event type can promote mastery in Sprint 1.

## Alternatives

A mutable learned boolean loses evidence and invites false confidence. Automatically
turning a `recall_attempt` into a passed assessment confuses a user claim with verified
outcome. Using mtime as exposure time or study duration invents learning activity.

## Consequences and revisit trigger

The progress view conservatively lists every active candidate as awaiting independent
assessment. This is useful gap visibility, not an evaluator. A future projector must
use attributable outcomes, versioned rubrics, assistance, failed checks, and correction
events. Add that as a tested layer without rewriting or upgrading historical self-reports.
