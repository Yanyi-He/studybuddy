"""Explicit fixed-item sessions, submissions, and append-only corrections."""

import sqlite3
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from studybuddy.catalog import evaluate, get_assessment, public_assessment, trusted_assessment
from studybuddy.database import audit, transaction
from studybuddy.errors import StudyBuddyError
from studybuddy.events import source_snapshot
from studybuddy.models import utc_now
from studybuddy.validation import canonical_json, digest, strict_json, validate_id, validate_key

ASSISTANCE = ("independent", "assisted", "ai_generated")


def _replay(db: sqlite3.Connection, table: str, key: str, expected: dict) -> dict | None:
    assert table in {"assessment_sessions", "assessment_attempts", "assessment_corrections"}
    row = db.execute(f"SELECT * FROM {table} WHERE idempotency_key=?", (key,)).fetchone()
    if row is None:
        return None
    if any(row[name] != value for name, value in expected.items()):
        raise StudyBuddyError(
            "Idempotency key already belongs to a different assessment operation."
        )
    return dict(row)


def _insert(db: sqlite3.Connection, table: str, data: dict) -> None:
    assert table in {"assessment_sessions", "assessment_attempts", "assessment_corrections"}
    columns = ",".join(data)
    placeholders = ",".join("?" for _ in data)
    db.execute(f"INSERT INTO {table}({columns}) VALUES ({placeholders})", tuple(data.values()))


def public_session(session: dict) -> dict:
    result = {
        key: value
        for key, value in session.items()
        if key not in {"assessment_json", "source_snapshot_json"}
    }
    result["assessment"] = public_assessment(strict_json(session["assessment_json"]))
    result["source_snapshot"] = strict_json(session["source_snapshot_json"])
    return result


def start_session(
    db: sqlite3.Connection, concept_id: str, assessment_id: str, key: str
) -> tuple[dict, bool]:
    validate_id(concept_id, "c")
    validate_key(key)
    item = get_assessment(assessment_id)
    expected = {"concept_id": concept_id, "assessment_id": assessment_id}
    with transaction(db):
        existing = _replay(db, "assessment_sessions", key, expected)
        if existing:
            return public_session(existing), False
        topic = db.execute(
            "SELECT topic FROM assessment_sessions WHERE concept_id=? LIMIT 1", (concept_id,)
        ).fetchone()
        if topic and topic[0] != item["topic"]:
            raise StudyBuddyError("This concept is already bound to another assessment topic.")
        session = {
            "id": "s_" + uuid4().hex,
            "idempotency_key": key,
            **expected,
            "topic": item["topic"],
            "assessment_json": canonical_json(item),
            "assessment_sha256": digest(item),
            "source_snapshot_json": source_snapshot(db, concept_id),
            "issued_at": utc_now(),
        }
        _insert(db, "assessment_sessions", session)
        audit(db, "quiz.start", session["id"], expected)
        return public_session(session), True


@dataclass(frozen=True)
class Submission:
    session_id: str
    answer: Any
    assistance: str
    hints_used: int
    idempotency_key: str

    def validate(self) -> None:
        validate_id(self.session_id, "s")
        validate_key(self.idempotency_key)
        if (
            self.assistance not in ASSISTANCE
            or type(self.hints_used) is not int
            or not 0 <= self.hints_used <= 10000
        ):
            raise StudyBuddyError(
                "Choose a supported assistance level and hints_used between 0 and 10000."
            )
        if self.assistance == "independent" and self.hints_used:
            raise StudyBuddyError("An independent submission cannot report hints; choose assisted.")


def submit(db: sqlite3.Connection, request: Submission) -> tuple[dict, bool]:
    request.validate()
    expected = {
        "session_id": request.session_id,
        "answer_json": canonical_json(request.answer),
        "assistance": request.assistance,
        "hints_used": request.hints_used,
    }
    with transaction(db):
        existing = _replay(db, "assessment_attempts", request.idempotency_key, expected)
        if existing:
            return existing, False
        session = db.execute(
            "SELECT * FROM assessment_sessions WHERE id=?", (request.session_id,)
        ).fetchone()
        if not session:
            raise StudyBuddyError("Unknown assessment session; use 'quiz start' first.")
        if db.execute(
            "SELECT 1 FROM assessment_attempts WHERE session_id=?", (request.session_id,)
        ).fetchone():
            raise StudyBuddyError(
                "This session already has an answer; start a new session for another attempt."
            )
        item = trusted_assessment(session["assessment_json"], session["assessment_sha256"])
        now = utc_now()
        if now < session["issued_at"]:
            raise StudyBuddyError("Clock is earlier than session issuance; submission refused.")
        attempt = {
            "id": "a_" + uuid4().hex,
            "idempotency_key": request.idempotency_key,
            **expected,
            "answer_sha256": digest(request.answer),
            **evaluate(item, request.answer),
            "submitted_at": now,
            "recorded_at": now,
        }
        _insert(db, "assessment_attempts", attempt)
        audit(
            db,
            "quiz.submit",
            attempt["id"],
            {"session_id": request.session_id, "passed": attempt["passed"]},
        )
        return attempt, True


def correct(
    db: sqlite3.Connection, attempt_id: str, action: str, reason: str, key: str
) -> tuple[dict, bool]:
    validate_id(attempt_id, "a")
    validate_key(key)
    if (
        action not in {"invalidate", "restore"}
        or not isinstance(reason, str)
        or not reason.strip()
        or len(reason) > 2000
    ):
        raise StudyBuddyError(
            "Correction requires invalidate/restore and a reason of 1-2000 characters."
        )
    expected = {"attempt_id": attempt_id, "action": action, "reason": reason}
    with transaction(db):
        existing = _replay(db, "assessment_corrections", key, expected)
        if existing:
            return existing, False
        attempt = db.execute(
            "SELECT recorded_at FROM assessment_attempts WHERE id=?", (attempt_id,)
        ).fetchone()
        if not attempt:
            raise StudyBuddyError("Unknown assessment attempt.")
        previous = db.execute(
            "SELECT * FROM assessment_corrections WHERE attempt_id=? "
            "ORDER BY sequence DESC LIMIT 1",
            (attempt_id,),
        ).fetchone()
        if action == "restore" and (not previous or previous["action"] != "invalidate"):
            raise StudyBuddyError("Restore requires a currently invalidated attempt.")
        now = utc_now()
        if now < (previous["recorded_at"] if previous else attempt["recorded_at"]):
            raise StudyBuddyError("Clock is earlier than existing evidence; correction refused.")
        correction = {
            "id": "x_" + uuid4().hex,
            "idempotency_key": key,
            **expected,
            "recorded_at": now,
        }
        _insert(db, "assessment_corrections", correction)
        audit(db, "quiz.correct", correction["id"], expected)
        return dict(
            db.execute(
                "SELECT * FROM assessment_corrections WHERE id=?", (correction["id"],)
            ).fetchone()
        ), True


def read_attempts(db: sqlite3.Connection, concept_id: str | None = None) -> list[dict]:
    where = " WHERE s.concept_id=?" if concept_id else ""
    rows = db.execute(
        "SELECT a.*, s.concept_id, s.issued_at, s.topic, s.assessment_id, s.assessment_json, "
        "s.assessment_sha256, s.source_snapshot_json FROM assessment_attempts a "
        "JOIN assessment_sessions s ON a.session_id=s.id" + where + " ORDER BY a.submitted_at,a.id",
        (concept_id,) if concept_id else (),
    ).fetchall()
    results = []
    for row in rows:
        record = dict(row)
        item = trusted_assessment(record.pop("assessment_json"), record.pop("assessment_sha256"))
        answer = strict_json(record["answer_json"])
        grade = evaluate(item, answer)
        if digest(answer) != record["answer_sha256"] or any(
            record[name] != value for name, value in grade.items()
        ):
            raise StudyBuddyError("Stored assessment result does not match the versioned rubric.")
        results.append({**record, "kind": item["kind"], "context": item["context"]})
    return results
