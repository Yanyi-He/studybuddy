import json
import re
import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from studybuddy.database import audit, transaction
from studybuddy.errors import StudyBuddyError
from studybuddy.models import EventKind, normalize_timestamp, utc_now


@dataclass(frozen=True)
class EventRequest:
    concept_id: str
    kind: EventKind
    idempotency_key: str
    occurred_at: str | None = None

    def validate(self) -> str | None:
        if not re.fullmatch(r"c_[a-f0-9]{32}", self.concept_id):
            raise StudyBuddyError("Use the complete concept ID from 'concepts list'.")
        if (
            not 1 <= len(self.idempotency_key) <= 200
            or not self.idempotency_key.strip()
            or not self.idempotency_key.isprintable()
        ):
            raise StudyBuddyError("Idempotency key must contain 1-200 printable characters.")
        if not isinstance(self.kind, EventKind):
            raise StudyBuddyError("Unsupported learning event kind.")
        return normalize_timestamp(self.occurred_at) if self.occurred_at is not None else None


def _existing_event(
    connection: sqlite3.Connection, request: EventRequest, occurred_at: str | None
) -> dict | None:
    row = connection.execute(
        "SELECT * FROM learning_events WHERE idempotency_key = ?", (request.idempotency_key,)
    ).fetchone()
    if row is None:
        return None
    if (
        row["concept_id"] != request.concept_id
        or row["kind"] != request.kind
        or (occurred_at is not None and row["occurred_at"] != occurred_at)
    ):
        raise StudyBuddyError("Idempotency key already belongs to a different event.")
    return dict(row)


def _source_snapshot(connection: sqlite3.Connection, concept_id: str) -> str:
    row = connection.execute(
        "SELECT c.id AS concept_id, c.document_id, c.anchor, c.line, c.source_sha256 AS sha256, "
        "d.path, c.source_content_version AS content_version "
        "FROM concepts c JOIN documents d ON d.id = c.document_id "
        "WHERE c.id = ? AND c.retired_at IS NULL AND d.deleted_at IS NULL",
        (concept_id,),
    ).fetchone()
    if row is None:
        raise StudyBuddyError(
            "Concept is unknown or its source is inactive; reindex and list concepts."
        )
    return json.dumps(dict(row), ensure_ascii=False, sort_keys=True)


def append_event(connection: sqlite3.Connection, request: EventRequest) -> tuple[dict, bool]:
    occurred_at = request.validate()
    with transaction(connection):
        existing = _existing_event(connection, request, occurred_at)
        if existing is not None:
            return existing, False
        source = _source_snapshot(connection, request.concept_id)
        recorded_at = utc_now()
        event = {
            "id": "e_" + uuid4().hex,
            "idempotency_key": request.idempotency_key,
            "concept_id": request.concept_id,
            "kind": request.kind.value,
            "provenance_kind": "self_reported",
            "occurred_at": occurred_at or recorded_at,
            "recorded_at": recorded_at,
            "source_snapshot_json": source,
        }
        connection.execute(
            "INSERT INTO learning_events(id, idempotency_key, concept_id, kind, provenance_kind, "
            "occurred_at, recorded_at, source_snapshot_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(event.values()),
        )
        audit(
            connection,
            "event.add",
            event["id"],
            {"concept_id": request.concept_id, "kind": request.kind},
        )
        return event, True
