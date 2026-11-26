import json
from pathlib import Path

import pytest

from studybuddy.assessments import Submission, correct, start_session, submit
from studybuddy.catalog import get_assessment
from studybuddy.database import open_database
from studybuddy.queries import progress
from tests.assessment_helpers import at, attempt
from tests.helpers import concept_id

HISTORIES = json.loads((Path(__file__).parent / "fixtures" / "learning_histories.json").read_text())


@pytest.mark.parametrize("history", HISTORIES, ids=[history["name"] for history in HISTORIES])
def test_seeded_learning_histories(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, history: dict
) -> None:
    _, database = indexed
    identifier = concept_id(database)
    records = []
    for number, step in enumerate(history["steps"]):
        if step.get("action", "attempt") == "attempt":
            records.append(
                attempt(database, identifier, monkeypatch, key=f"history-{number}", **step)
            )
        else:
            monkeypatch.setattr(
                "studybuddy.assessments.utc_now", lambda minute=step["minute"]: at(minute)
            )
            with open_database(database, writable=True) as db:
                correct(
                    db,
                    records[step["ref"]]["id"],
                    step["action"],
                    "synthetic correction",
                    f"correction-{number}",
                )
    with open_database(database) as db:
        result = progress(db)
        projection = result["concepts"][0]
        assert projection["learning_state"] == history["expected"]
        assert projection["projector_version"] == "fixed-evidence-v1"
        assert projection["independence_source"] == "learner_declaration"
        assert result["verified_mastered"] == 0
        assert (
            db.execute("SELECT status FROM concepts WHERE id=?", (identifier,)).fetchone()[0]
            == "seen"
        )


def test_session_issued_before_delay_does_not_qualify_even_if_submitted_later(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, database = indexed
    identifier = concept_id(database)
    attempt(database, identifier, monkeypatch)
    monkeypatch.setattr("studybuddy.assessments.utc_now", lambda: at(60))
    with open_database(database, writable=True) as db:
        session, _ = start_session(db, identifier, "retry-recall", "issued-early")
        monkeypatch.setattr("studybuddy.assessments.utc_now", lambda: at(3000))
        submit(
            db,
            Submission(
                session["id"],
                get_assessment("retry-recall")["expected"],
                "independent",
                0,
                "late-submit",
            ),
        )
        assert progress(db)["concepts"][0]["learning_state"] == "assessed_once"


def test_as_of_replay_uses_corrections_known_at_that_time(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, database = indexed
    identifier = concept_id(database)
    attempt(database, identifier, monkeypatch, minute=0, key="first")
    later = attempt(database, identifier, monkeypatch, minute=1441, key="delayed")
    monkeypatch.setattr("studybuddy.assessments.utc_now", lambda: at(1500))
    with open_database(database, writable=True) as db:
        correct(db, later["id"], "invalidate", "help was used", "invalidate")
        assert progress(db, as_of=at(0))["concepts"][0]["learning_state"] == "exposed"
        assert progress(db, as_of=at(1))["concepts"][0]["learning_state"] == "assessed_once"
        assert (
            progress(db, as_of=at(1442))["concepts"][0]["learning_state"] == "recalled_unassisted"
        )
        assert progress(db, as_of=at(1500))["concepts"][0]["learning_state"] == "assessed_once"
        monkeypatch.setattr("studybuddy.assessments.utc_now", lambda: at(1600))
        correct(db, later["id"], "restore", "wrong attempt was invalidated", "restore")
        assert progress(db)["concepts"][0]["learning_state"] == "recalled_unassisted"


def test_correction_for_one_concept_does_not_leak_into_another(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, database = indexed
    record = attempt(database, concept_id(database), monkeypatch)
    with open_database(database, writable=True) as db:
        correct(db, record["id"], "invalidate", "test", "x")
        assert progress(db)["concepts"][1]["invalidated_attempt_ids"] == []
