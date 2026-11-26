import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from studybuddy.database import open_database
from studybuddy.errors import StudyBuddyError
from studybuddy.events import EventRequest, append_event
from studybuddy.indexer import index_vault
from studybuddy.models import EventKind
from studybuddy.queries import list_concepts, list_events, progress
from tests.helpers import concept_id, database_dump


def test_event_persists_and_uses_separate_timestamps(indexed: tuple[Path, Path]) -> None:
    _, database = indexed
    request = EventRequest(
        concept_id(database), EventKind.EXPOSURE, "read-1", "2026-01-02T08:00:00+08:00"
    )
    with open_database(database, writable=True) as connection:
        event, created = append_event(connection, request)
    assert created
    assert event["occurred_at"] == "2026-01-02T00:00:00.000000+00:00"
    assert event["recorded_at"] != event["occurred_at"]
    assert event["provenance_kind"] == "self_reported"
    with open_database(database) as connection:
        assert list_events(connection)[0]["id"] == event["id"]
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM audit_log WHERE action = 'event.add'"
            ).fetchone()[0]
            == 1
        )


def test_retries_without_occurred_at_do_not_make_duplicate_events(
    indexed: tuple[Path, Path],
) -> None:
    _, database = indexed
    request = EventRequest(concept_id(database), EventKind.RECALL_ATTEMPT, "same-key")
    with open_database(database, writable=True) as connection:
        first, created = append_event(connection, request)
        second, repeated = append_event(connection, request)
        assert len(list_events(connection)) == 1
    assert created and not repeated
    assert first == second


def test_equivalent_timezone_timestamps_are_idempotent(indexed: tuple[Path, Path]) -> None:
    _, database = indexed
    identifier = concept_id(database)
    with open_database(database, writable=True) as connection:
        append_event(
            connection,
            EventRequest(identifier, EventKind.EXPOSURE, "tz", "2026-01-02T08:00:00+08:00"),
        )
        _, created = append_event(
            connection, EventRequest(identifier, EventKind.EXPOSURE, "tz", "2026-01-02T00:00:00Z")
        )
        assert not created


@pytest.mark.parametrize("change", ["kind", "concept", "time"])
def test_reusing_a_key_with_different_input_is_a_conflict(
    indexed: tuple[Path, Path], change: str
) -> None:
    _, database = indexed
    with open_database(database, writable=True) as connection:
        identifiers = [item["id"] for item in list_concepts(connection)]
        append_event(
            connection,
            EventRequest(identifiers[0], EventKind.EXPOSURE, "key", "2026-01-01T00:00:00Z"),
        )
        request = EventRequest(
            identifiers[1] if change == "concept" else identifiers[0],
            EventKind.RECALL_ATTEMPT if change == "kind" else EventKind.EXPOSURE,
            "key",
            "2026-02-01T00:00:00Z" if change == "time" else "2026-01-01T00:00:00Z",
        )
        with pytest.raises(StudyBuddyError, match="different event"):
            append_event(connection, request)
        assert len(list_events(connection)) == 1


@pytest.mark.parametrize("key", ["", " ", "x" * 201, "newline\n", "escape\x1b"])
def test_invalid_keys_do_not_mutate_database(indexed: tuple[Path, Path], key: str) -> None:
    _, database = indexed
    before = database_dump(database)
    with (
        open_database(database, writable=True) as connection,
        pytest.raises(StudyBuddyError, match="Idempotency"),
    ):
        append_event(connection, EventRequest(concept_id(database), EventKind.EXPOSURE, key))
    assert database_dump(database) == before


@pytest.mark.parametrize(
    "timestamp", ["", "2026-01-01T10:00:00", "not a time", "2026-13-01T00:00:00Z"]
)
def test_invalid_or_naive_timestamps_are_rejected(
    indexed: tuple[Path, Path], timestamp: str
) -> None:
    _, database = indexed
    with (
        open_database(database, writable=True) as connection,
        pytest.raises(StudyBuddyError, match="occurred_at"),
    ):
        append_event(
            connection, EventRequest(concept_id(database), EventKind.EXPOSURE, "time", timestamp)
        )


@pytest.mark.parametrize("kind", list(EventKind))
def test_self_reported_events_including_copied_ai_answers_never_imply_mastery(
    indexed: tuple[Path, Path], kind: EventKind
) -> None:
    _, database = indexed
    with open_database(database, writable=True) as connection:
        append_event(connection, EventRequest(concept_id(database), kind, f"event-{kind.value}"))
        result = progress(connection)
        assert result["verified_mastered"] == 0
        assert result["awaiting_independent_assessment"] == 2
        assert result["assessment_available"]
        assert result["assessment_capability"] == "fixed_items_only"
        assert {item["status"] for item in list_concepts(connection)} == {"seen"}


def test_schema_rejects_mastered_status(indexed: tuple[Path, Path]) -> None:
    _, database = indexed
    with (
        open_database(database, writable=True) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute("UPDATE concepts SET status = 'mastered'")


def test_unknown_and_inactive_concepts_cannot_receive_new_events(
    indexed: tuple[Path, Path],
) -> None:
    vault, database = indexed
    identifier = concept_id(database)
    (vault / "network.md").unlink()
    index_vault(vault, database)
    for concept in [identifier, "c_" + "0" * 32]:
        with (
            open_database(database, writable=True) as connection,
            pytest.raises(StudyBuddyError, match="inactive"),
        ):
            append_event(connection, EventRequest(concept, EventKind.EXPOSURE, "inactive"))


def test_a_retry_can_retrieve_existing_event_after_source_deletion(
    indexed: tuple[Path, Path],
) -> None:
    vault, database = indexed
    request = EventRequest(concept_id(database), EventKind.EXPOSURE, "retry-after-delete")
    with open_database(database, writable=True) as connection:
        first, _ = append_event(connection, request)
    (vault / "network.md").unlink()
    index_vault(vault, database)
    with open_database(database, writable=True) as connection:
        second, created = append_event(connection, request)
    assert first == second and not created


def test_concurrent_retries_append_once(indexed: tuple[Path, Path]) -> None:
    _, database = indexed
    request = EventRequest(concept_id(database), EventKind.EXPOSURE, "concurrent")

    def write_event() -> bool:
        with open_database(database, writable=True) as connection:
            return append_event(connection, request)[1]

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: write_event(), range(2))) == [False, True]


def test_audit_failure_rolls_back_event_append(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, database = indexed
    identifier = concept_id(database)
    before = database_dump(database)

    def fail_audit(*args: object) -> None:
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr("studybuddy.events.audit", fail_audit)
    with (
        open_database(database, writable=True) as connection,
        pytest.raises(RuntimeError, match="audit failure"),
    ):
        append_event(connection, EventRequest(identifier, EventKind.EXPOSURE, "atomic-event"))
    assert database_dump(database) == before
