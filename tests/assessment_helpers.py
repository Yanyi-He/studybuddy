from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from studybuddy.assessments import Submission, start_session, submit
from studybuddy.catalog import get_assessment
from studybuddy.database import open_database

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def at(minute: int) -> str:
    return (BASE + timedelta(minutes=minute)).isoformat(timespec="microseconds")


def attempt(
    database: Path,
    concept: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    minute: int = 0,
    kind: str = "recall",
    passed: bool = True,
    assistance: str = "independent",
    hints: int = 0,
    key: str = "attempt",
) -> dict:
    identifier = f"retry-{kind}"
    monkeypatch.setattr("studybuddy.assessments.utc_now", lambda: at(minute))
    with open_database(database, writable=True) as db:
        session, _ = start_session(db, concept, identifier, "start-" + key)
        answer = dict(get_assessment(identifier)["expected"])
        if not passed:
            field = next(iter(answer))
            answer[field] = next(
                value
                for value in get_assessment(identifier)["questions"][field]["choices"]
                if value != answer[field]
            )
        monkeypatch.setattr("studybuddy.assessments.utc_now", lambda: at(minute + 1))
        return submit(db, Submission(session["id"], answer, assistance, hints, key))[0]
