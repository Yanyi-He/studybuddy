import json
import sqlite3
from collections import defaultdict

from studybuddy.assessments import read_attempts
from studybuddy.errors import StudyBuddyError
from studybuddy.models import normalize_timestamp
from studybuddy.projector import project


def list_concepts(
    connection: sqlite3.Connection, *, include_inactive: bool = False, search: str | None = None
) -> list[dict]:
    clauses = [] if include_inactive else ["c.retired_at IS NULL", "d.deleted_at IS NULL"]
    parameters: list[str] = []
    if search is not None:
        if not search.strip() or len(search) > 200:
            raise StudyBuddyError("Search must contain 1-200 characters.")
        # Treat the whole input as a literal FTS phrase, never FTS query syntax or SQL.
        phrase = '"' + search.replace('"', '""') + '"'
        clauses.append(
            "c.id IN (SELECT concept_id FROM concept_search WHERE concept_search MATCH ?)"
        )
        parameters.append(phrase)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = connection.execute(
        "SELECT c.id, c.title, c.status, c.confirmation, c.anchor, c.line, c.source_sha256, "
        "c.first_seen_at, c.source_indexed_at, c.retired_at, d.id AS document_id, d.path, "
        "c.source_content_version AS content_version, d.deleted_at AS source_deleted_at "
        "FROM concepts c "
        "JOIN documents d ON d.id = c.document_id" + where + " ORDER BY d.path, c.line, c.id",
        parameters,
    ).fetchall()
    return [dict(row) for row in rows]


def list_events(connection: sqlite3.Connection, concept_id: str | None = None) -> list[dict]:
    where = " WHERE concept_id = ?" if concept_id else ""
    parameters = (concept_id,) if concept_id else ()
    rows = connection.execute(
        "SELECT * FROM learning_events" + where + " ORDER BY recorded_at, id", parameters
    ).fetchall()
    events = []
    for row in rows:
        event = dict(row)
        event["source_snapshot"] = json.loads(event.pop("source_snapshot_json"))
        events.append(event)
    return events


def progress(connection: sqlite3.Connection, *, as_of: str | None = None) -> dict:
    cutoff = normalize_timestamp(as_of) if as_of is not None else None
    concepts = list_concepts(connection)
    counts = {
        row["concept_id"]: row["total"]
        for row in connection.execute(
            "SELECT concept_id, COUNT(*) AS total FROM learning_events "
            "WHERE (? IS NULL OR recorded_at<=?) GROUP BY concept_id",
            (cutoff, cutoff),
        )
    }
    attempts: dict[str, list[dict]] = defaultdict(list)
    for attempt in read_attempts(connection):
        attempts[attempt["concept_id"]].append(attempt)
    corrections = [
        dict(row)
        for row in connection.execute("SELECT * FROM assessment_corrections ORDER BY sequence")
    ]
    projected = [
        {
            **concept,
            "self_reported_events": counts.get(concept["id"], 0),
            **project(attempts[concept["id"]], corrections, as_of=cutoff),
        }
        for concept in concepts
    ]
    independent_states = {"assessed_once", "recalled_unassisted", "applied", "transferred"}
    gaps = [item for item in projected if item["learning_state"] not in independent_states]
    return {
        "active_candidates": len(concepts),
        "awaiting_independent_assessment": len(gaps),
        "verified_mastered": 0,
        "assessment_available": True,
        "assessment_capability": "fixed_items_only",
        "delayed_recall_demonstrated": sum(
            item["learning_state"] in {"recalled_unassisted", "applied", "transferred"}
            for item in projected
        ),
        "explanation": (
            "States reflect versioned fixed-item checks. Assistance is learner-declared; "
            "free-text reasoning and general mastery are not verified. "
            "A 24-hour retest delay is a provisional product heuristic."
        ),
        "gaps": gaps,
        "concepts": projected,
    }
