# ADR-005: Deterministic fixed-item evidence and replayable states

Status: accepted · 2026-11-26

## Context

The first assessment slice must work offline and distinguish answer checking from
unverified self-reports. A learner may use assistance, fail a delayed check, or later
discover a result was misattributed. None of these should erase the historical record.

## Decision

Ship nine original structured-choice items over three topics. Store the exact item,
rubric/evaluator versions, hash, and source snapshot when a session starts. A session
accepts one answer, with explicit assistance and hints. Compute score from exact choice
keys; all fields must be correct to pass. Store optional explanations but never grade
them. Public commands omit answer keys; the open-source package still contains them.

Append `invalidate`/`restore` corrections with reasons and idempotency keys. Corrections
cannot inject a new score. Recompute states from attributable active results using
`fixed-evidence-v1`; do not persist mutable mastery flags. A concept is bound to the
topic explicitly selected by its first session, so unrelated topics cannot be combined.

Require two declared-independent correct recall sessions with the second issued at
least 24 hours after the first submission. Leaving an early session open does not meet
the delay. Application requires a later independent application pass; transfer requires
a later pass in another context. Any active failed check clears that chain to
`needs_review`. Assisted passes cannot promote independent evidence. Invalidation
replays history, so removing a success can lower state and removing a failure can
restore the earlier chain. `--as-of` applies the corrections known by that cutoff.

## Alternatives

Manual score entry or keyword grading would make unsupported claims easy to promote.
LLM grading adds cost, privacy, uncertainty, and rubric-calibration work outside this
slice. One successful answer or same-day repeats provide no delayed-recall evidence.

## Consequences

The thresholds are explicit product heuristics, not scientific mastery criteria.
Assistance is learner-declared and the local clock is not externally attested. Items
are public and the system is not cheat-resistant. `applied`/`transferred` refer only to
the fixed scenarios; there is no code execution, reasoning evaluation, or general
mastery certification. `verified_mastered` remains zero. A known item ID/version must
remain immutable; changing a published rubric requires a separately versioned item.
The regression suite contains 32 seeded success/failure/assistance/delay/correction
histories, plus session-issuance and historical-cutoff edge cases.
