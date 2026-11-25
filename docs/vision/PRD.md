> Planning context adapted from the supplied blueprint. This describes future product scope, not shipped features. See [current roadmap](../ROADMAP.md) and [implemented architecture](../ARCHITECTURE.md). Referenced versions, licenses, and community statistics are historical planning notes and must be checked before reuse.

# StudyBuddy PRD (v0.1)

## Product hypothesis

People accumulate notes and AI-generated explanations without durable mastery. An agent should distinguish **exposure** from **retrieval**, **independent application**, and **transfer**, then recommend the next short, high-value learning action with source-backed reasoning. The product is not another note editor or chat UI.

Target public persona: software and AI engineering learners, including working SDEs, job applicants, and self-directed switchers. English and Chinese content first; customizable language.

## Core promises

1. **Bring your own notes**: Obsidian vault in Markdown; do not migrate or duplicate documents. Read-only by default, deep links to source notes.
2. **Know the difference between having read and having learned**: a note/edit/import is `seen`; assessments and independent work are evidence of mastery.
3. **Recall intelligently**: active recall, delayed re-tests, spaced repetition for atomic items; programming and design tasks require rubric-based evidence and tests.
4. **Plan adaptively**: goals and time constraints drive a short daily queue; completion, misses, and changing availability revise future tasks.
5. **Model-agnostic**: MCP tools and deterministic core work without a paid API; a BYO-LLM provider is optional. Do not assume ChatGPT will invoke tools on every turn.
6. **Data ownership**: local-first, export/delete controls, opt-in activity monitoring, explanation for each recommendation.

## Representative flows

### A. From notes to independent knowledge

- User creates/updates `Network/TCP vs UDP.md` in Obsidian.
- Local indexer records hash, file mtime, headings, Wikilinks and YAML properties, then creates source spans.
- Concept candidate: `TCP retransmission`; status `seen`, source `path#heading`; no assumption of comprehension.
- The app suggests a 2-minute recall probe. User explains retransmission and timeout unassisted. Store scored evidence with rubric, confidence, provenance and evaluator version.
- Follow-up after a delay tests transfer: explain how retries can duplicate HTTP payments. Update mastery only using attributable evidence.

### B. Fragmented knowledge capture

- The user pastes a short Q&A or selects a paragraph in Obsidian; append to an `Inbox` note or use an explicit capture command.
- Classifier suggests topic, concept candidates and associations; all are reviewable. Do **not** invent source text or silently rewrite the vault.
- Daily/weekly digest clusters related fragments into a suggested map: `Networking → TCP → Timeout → Retry → Idempotency`.
- Each cluster has backlinks to the original fragments; links do not count as proof of mastery.

### C. Coding rehearsal

- Learner selects a skill and chooses `practice` mode.
- Generate or load a task with public tests + hidden edge cases; execute in a restricted subprocess/container; return failure category and a hint ladder.
- Require an independent explanation of algorithm invariants/complexity. Track `hint_count`, `time_to_first_attempt`, `pass_rate`, `transfer_outcome` separately from `read_minutes`.

### D. Mock interview

- Technical: system-design scenarios, debugging, DSA, incremental follow-up questions, rubric with evidence.
- Behavioral: STAR prompts with user-owned experiences, no fabricated achievements; user chooses text or compatible voice provider.
- Personalizable English feedback: clarity, structure, filler words, technical precision, but no invented audio/pronunciation analysis from text alone.

### E. Daily plan and recovery

- Daily plan has **one main task**, **one optional review**, **one fallback two-minute task**.
- Plans must adapt to deadlines, new tests, missed days and low capacity without accumulating guilt/backlog.
- Every suggestion shows `Why this now?` with underlying evidence and is dismissible.

## First-run onboarding (<= 5 minutes, skippable)

- Goal(s): new-grad SDE, AI engineering, interviews, or custom.
- Topic areas and deadlines, available study time (weekday/weekend), preferred feedback language and intensity.
- Optional baseline diagnostic: 5-10 adaptive questions with mixed recall, application and explanation; user can skip and begin with conservative unknown priors.
- Self-reported friction: task initiation, time fragmentation, reading tolerance, preferred exercise format. Treat as preferences, not medical diagnosis or a permanent 'learner type'.
- Explicit opt-ins per integration (Obsidian, ActivityWatch, Apple Health/manual sleep, vocabulary imports). Screenshots and full window titles OFF by default.

## Memory and mastery semantics

`knowledge_state` is a derived view from evidence, not a boolean. Example stages:
`unseen → exposed → explained_with_help → recalled_unassisted → applied → transferred`.
A more advanced state may lapse after failed delayed checks; preserve event history. Distinguish what the learner *claims*, what the AI *infers*, and what tests *demonstrate*.

Suggested knowledge evidence fields:
`concept_id, event_time, kind, source_type, source_ref, session_id, assessment_id, answer_hash, score, rubric_version, independence_level, hints_used, confidence, created_at`.
Time fields: `first_seen_at, last_exposed_at, last_assessed_at, last_successful_recall_at, valid_from, imported_at, source_modified_at` have different semantics. Never infer study time from note file modification time.

## Learning system feature modules

| Module | MVP | Next | Later |
|---|---|---|---|
| Obsidian Markdown read-only integration | Yes | Optional in-vault capture | Cross-device sync |
| Concept graph + provenance | Yes (manual approval) | Automated consolidation | Advanced uncertainty tracking |
| Diagnostic / assessment | Short baseline + fixed tests | Adaptive item selection | IRT/BKT experiment |
| Daily adaptive queue | Small rule-based | Deadline/risk-aware planner | Learned scheduler |
| Spaced repetition | Simple deterministic reviews | FSRS vocabulary cards | Personal fitted parameters |
| Coding coach | CLI + deterministic test harness | Containerized executor | AI generated coding curriculum |
| Technical/BQ mock | Question templates + rubrics | Interactive AI | Voice and feedback |
| Vocabulary capture | Manual import | Browser share target + FSRS | Subtitle/OCR import with rights checks |
| ActivityWatch | No | Opt-in local aggregated summaries | More integrations |
| Sleep/circadian | No | Manual availability / sleep import | User-controlled longitudinal analysis |
| React dashboard | No | Yes | Mobile companion |
| Multi-user deployment | No | Docker/Postgres optional | Authorized hosted SaaS |

## Vocabulary subproduct

Three item types: (1) IELTS/general, (2) developer terminology & technical collocations, (3) user-mined phrases from reading/video/meetings.

Each card contains `lemma_or_phrase, meaning, IPA_if_licensed, original_context, source_uri, subject_tags, confidence, context_example, production_prompt, review_state, attribution`.

Do not make everything an English-Chinese recognition flashcard. Mix cloze, phrase production, listening (if authorized audio exists), and workplace role play. Store exact context excerpt only if rights permit. Allow user to add term via clipboard/extension/Obsidian note with one action.

Word Atlas upstream has MIT application code and CC BY 4.0 vocabulary/assets with attribution; site may diverge from repo. Prefer an **importer for licensed vocabulary data**, not screen scraping the online site. Keep upstream license and credits. The model must not hallucinate translated definitions.

## Evaluation plan

**Behavioral product hypotheses:** users who only copy AI answers have lower delayed independent recall than users actively tested; personalized review queue increases verified transfer tasks, not just study minutes. Measure; do not assert as achieved outcomes.

MVP acceptance:
- 100 sample Markdown notes index with source file, heading, file hash and timestamp; reindex changes idempotently.
- Note ingest alone NEVER sets mastered status.
- 25 seeded concept/quiz flows support evidence-backed state changes and reversals.
- Repeated event ID does not duplicate assessment events.
- Source deletion/tombstone and resync behave predictably.
- No vault overwrite in default mode; no hidden network calls.
- CLI `doctor`, `index`, `concepts`, `quiz`, `progress`, `export`; tests pass offline.
- README has live demo and architecture/ADR, documented limits, opt-in privacy defaults.

Post-MVP: 1-week, 2-week held-out recall checks, answer correctness and transfer pass rate; retrieval Recall@K against labeled note spans; recommendation adherence; p95 latency; review completion and false mastery rate; request costs if model enabled.

## Explicit exclusions for the first sprint

No screen recording, no Apple Health integration, no built-in notebook editor, no full calendar assistant, no infinite auto-generated tasks, no universal 'learner style' classification, no microservices, no Redis/Kafka/Kubernetes, no external LLM requirement, and no mass-copied copyrighted dictionary data.

### Existing dictionary compatibility

Eudic/欧路 is an existing learner workflow. Add an optional adapter (after MVP) for Eudic OpenAPI word-book synchronization; fall back to CSV/Anki export/import supported by current desktop versions. A successful dictionary lookup is only `seen`, not recalled. Do not require users to abandon Eudic to use StudyBuddy.
