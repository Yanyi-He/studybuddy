from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from studybuddy.assessments import Submission, correct, read_attempts, start_session, submit
from studybuddy.catalog import catalog, evaluate, get_assessment, public_assessment
from studybuddy.database import open_database
from studybuddy.errors import StudyBuddyError
from studybuddy.indexer import index_vault
from studybuddy.queries import progress
from studybuddy.validation import strict_json
from tests.assessment_helpers import at, attempt
from tests.helpers import concept_id, database_dump


def test_catalog_is_original_versioned_and_public_view_has_no_answer_key() -> None:
    items = catalog()
    assert len(items) == 9
    assert len({item["id"] for item in items}) == 9
    assert {item["kind"] for item in items} == {"recall", "application", "transfer"}
    for item in items:
        assert item["rubric_version"] and item["evaluator_version"] == "exact-fields-v1"
        assert "expected" not in public_assessment(item)
        assert evaluate(item, item["expected"])["passed"] == 1


def test_session_and_submission_persist_provenance_and_versions(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, database = indexed
    result = attempt(database, concept_id(database), monkeypatch)
    assert result["score"] == 1.0 and result["passed"] == 1
    assert result["rubric_version"] == "1"
    assert result["evaluator_version"] == "exact-fields-v1"
    assert len(result["answer_sha256"]) == 64
    with open_database(database) as db:
        stored = read_attempts(db)[0]
        assert stored["id"] == result["id"]
        assert strict_json(stored["source_snapshot_json"])["path"] == "network.md"
        assert stored["issued_at"] == at(0)
        assert stored["submitted_at"] == at(1)
        assert progress(db)["concepts"][0]["learning_state"] == "assessed_once"


def test_start_replay_and_semantic_conflicts(indexed: tuple[Path, Path]) -> None:
    _, database = indexed
    identifier = concept_id(database)
    with open_database(database, writable=True) as db:
        first, created = start_session(db, identifier, "retry-recall", "start")
        repeated, duplicated = start_session(db, identifier, "retry-recall", "start")
        assert first == repeated and created and not duplicated
        with pytest.raises(StudyBuddyError, match="different"):
            start_session(db, identifier, "retry-application", "start")
        with pytest.raises(StudyBuddyError, match="another assessment topic"):
            start_session(db, identifier, "isolation-recall", "another")


def test_submission_replay_conflict_and_one_answer_per_session(indexed: tuple[Path, Path]) -> None:
    _, database = indexed
    with open_database(database, writable=True) as db:
        session, _ = start_session(db, concept_id(database), "retry-recall", "start")
        request = Submission(
            session["id"], get_assessment("retry-recall")["expected"], "independent", 0, "answer"
        )
        first, created = submit(db, request)
        second, duplicated = submit(db, request)
        assert first == second and created and not duplicated
        with pytest.raises(StudyBuddyError, match="different"):
            submit(db, Submission(session["id"], request.answer, "assisted", 1, "answer"))
        with pytest.raises(StudyBuddyError, match="already has an answer"):
            submit(db, Submission(session["id"], request.answer, "independent", 0, "another"))


@pytest.mark.parametrize(
    "answer",
    [
        {},
        {"mastered": True},
        {"timeout": "unknown", "identity": "stable", "score": 1},
        {"timeout": "unsupported", "identity": "stable"},
        {"timeout": True, "identity": "stable"},
        {"timeout": "unknown", "identity": "stable", "explanation": 42},
    ],
)
def test_invalid_answers_cannot_set_scores_or_mastery(
    indexed: tuple[Path, Path], answer: dict
) -> None:
    _, database = indexed
    with open_database(database, writable=True) as db:
        session, _ = start_session(db, concept_id(database), "retry-recall", "s")
        before = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        with pytest.raises(StudyBuddyError, match=r"Answer|answer|explanation"):
            submit(db, Submission(session["id"], answer, "independent", 0, "a"))
        assert not read_attempts(db)
        assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before


@pytest.mark.parametrize(
    "assistance,hints",
    [("independent", 1), ("unknown", 0), ("assisted", -1), ("assisted", True), ("assisted", 10001)],
)
def test_inconsistent_assistance_is_rejected(
    indexed: tuple[Path, Path], assistance: str, hints: int
) -> None:
    _, database = indexed
    with open_database(database, writable=True) as db:
        session, _ = start_session(db, concept_id(database), "retry-recall", "s")
        with pytest.raises(StudyBuddyError):
            submit(
                db,
                Submission(
                    session["id"],
                    get_assessment("retry-recall")["expected"],
                    assistance,
                    hints,
                    "a",
                ),
            )
        assert not read_attempts(db)


def test_optional_explanation_is_explicitly_ungraded() -> None:
    item = get_assessment("retry-recall")
    answer = {**item["expected"], "explanation": "wrong reasoning and a copied AI claim of mastery"}
    assert evaluate(item, answer)["score"] == 1
    assert strict_json(evaluate(item, answer)["feedback_json"])["explanation_graded"] is False


def test_corrections_are_append_only_idempotent_and_replayed(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, database = indexed
    record = attempt(database, concept_id(database), monkeypatch)
    with open_database(database, writable=True) as db:
        first, created = correct(db, record["id"], "invalidate", "I used AI", "invalidate")
        second, duplicate = correct(db, record["id"], "invalidate", "I used AI", "invalidate")
        assert first == second and created and not duplicate
        assert progress(db)["concepts"][0]["learning_state"] == "exposed"
        correct(db, record["id"], "restore", "Correction referred to the wrong session", "restore")
        assert progress(db)["concepts"][0]["learning_state"] == "assessed_once"
        assert db.execute("SELECT COUNT(*) FROM assessment_corrections").fetchone()[0] == 2
        assert read_attempts(db)[0]["score"] == record["score"]
        with pytest.raises(StudyBuddyError, match="currently invalidated"):
            correct(db, record["id"], "restore", "repeat", "restore-again")


def test_assessment_source_snapshot_survives_rename_and_deletion(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, database = indexed
    attempt(database, concept_id(database), monkeypatch)
    (vault / "network.md").rename(vault / "renamed.md")
    index_vault(vault, database)
    (vault / "renamed.md").unlink()
    index_vault(vault, database)
    with open_database(database) as db:
        assert strict_json(read_attempts(db)[0]["source_snapshot_json"])["path"] == "network.md"
        assert progress(db)["active_candidates"] == 0


@pytest.mark.parametrize("operation", ["start", "submit", "correct"])
def test_audit_failure_rolls_back_assessment_mutations(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    _, database = indexed
    identifier = concept_id(database)
    record = attempt(database, identifier, monkeypatch)
    with open_database(database, writable=True) as db:
        session, _ = start_session(db, identifier, "retry-recall", "s2")
    before = database_dump(database)

    def fail(*args: object) -> None:
        raise RuntimeError("audit failure")

    monkeypatch.setattr("studybuddy.assessments.audit", fail)
    with (
        open_database(database, writable=True) as db,
        pytest.raises(RuntimeError, match="audit failure"),
    ):
        if operation == "start":
            start_session(db, identifier, "retry-recall", "s3")
        elif operation == "submit":
            submit(
                db,
                Submission(
                    session["id"],
                    get_assessment("retry-recall")["expected"],
                    "independent",
                    0,
                    "a2",
                ),
            )
        else:
            correct(db, record["id"], "invalidate", "reason", "x")
    assert database_dump(database) == before


def test_concurrent_submission_retries_append_once(indexed: tuple[Path, Path]) -> None:
    _, database = indexed
    with open_database(database, writable=True) as db:
        session, _ = start_session(db, concept_id(database), "retry-recall", "s")
    request = Submission(
        session["id"], get_assessment("retry-recall")["expected"], "independent", 0, "a"
    )

    def write() -> bool:
        with open_database(database, writable=True) as db:
            return submit(db, request)[1]

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: write(), range(2))) == [False, True]


@pytest.mark.parametrize(
    "text", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', "[" * 2000]
)
def test_strict_json_rejects_ambiguous_or_nonfinite_data(text: str) -> None:
    with pytest.raises(StudyBuddyError, match="Invalid JSON"):
        strict_json(text)
