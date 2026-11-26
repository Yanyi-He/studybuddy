import hashlib
import json
from pathlib import Path

import pytest

from studybuddy.assessments import correct, read_attempts
from studybuddy.database import open_database
from studybuddy.errors import StudyBuddyError
from studybuddy.events import EventRequest, append_event
from studybuddy.indexer import index_vault
from studybuddy.ledger import export_ledger, import_ledger
from studybuddy.models import EventKind
from studybuddy.queries import list_concepts, list_events, progress
from studybuddy.validation import canonical_json, digest
from tests.assessment_helpers import at, attempt
from tests.helpers import concept_id, database_dump


@pytest.fixture
def exported(
    indexed: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    vault, database = indexed
    identifier = concept_id(database)
    attempt(database, identifier, monkeypatch, key="first")
    second = attempt(database, identifier, monkeypatch, minute=1441, key="second")
    monkeypatch.setattr("studybuddy.assessments.utc_now", lambda: at(1500))
    with open_database(database, writable=True) as db:
        correct(db, second["id"], "invalidate", "synthetic correction", "invalidate")
        monkeypatch.setattr("studybuddy.assessments.utc_now", lambda: at(1600))
        correct(db, second["id"], "restore", "synthetic restoration", "restore")
        append_event(db, EventRequest(identifier, EventKind.AI_ANSWER_COPIED, "legacy-copied"))
    output = tmp_path / "ledger.jsonl"
    export_ledger(database, output)
    return vault, database, output


def rewrite(path: Path, records: list[dict]) -> None:
    payload = "".join(canonical_json(record) + "\n" for record in records[:-1]).encode()
    checksum = hashlib.sha256(payload).hexdigest()
    path.write_bytes(
        payload
        + (
            canonical_json({"type": "checksum", "records": len(records) - 2, "sha256": checksum})
            + "\n"
        ).encode()
    )


def test_logical_round_trip_preserves_evidence_projection_and_ids(
    exported: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    vault, database, output = exported
    restored = tmp_path / "restored.sqlite3"
    original_dump = database_dump(database)
    result = import_ledger(restored, output, vault)
    assert result["records"] > 0
    with open_database(database) as before, open_database(restored) as after:
        assert after.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert list_concepts(before) == list_concepts(after)
        assert list_events(before) == list_events(after)
        assert read_attempts(before) == read_attempts(after)
        assert progress(before) == progress(after)
        assert progress(before, as_of=at(1501)) == progress(after, as_of=at(1501))
        assert (
            after.execute("SELECT COUNT(*) FROM audit_log WHERE action='ledger.import'").fetchone()[
                0
            ]
            == 1
        )
        assert len(list_concepts(after, search="Networking")) == 1
    repeated = tmp_path / "restored.jsonl"
    export_ledger(restored, repeated)
    assert repeated.read_bytes() == output.read_bytes()
    assert database_dump(database) == original_dump
    assert index_vault(vault, restored).unchanged == 1


def test_round_trip_preserves_tombstones_and_event_replays(
    exported: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    vault, database, _ = exported
    identifier = concept_id(database)
    (vault / "network.md").unlink()
    index_vault(vault, database)
    output = tmp_path / "deleted.jsonl"
    export_ledger(database, output)
    restored = tmp_path / "restored.sqlite3"
    import_ledger(restored, output, vault)
    with open_database(restored, writable=True) as db:
        assert not list_concepts(db)
        assert len(list_events(db)) == 1
        _, created = append_event(
            db, EventRequest(identifier, EventKind.AI_ANSWER_COPIED, "legacy-copied")
        )
        assert not created


def test_import_explicitly_binds_user_selected_vault_not_manifest_authority(
    exported: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    _, _, output = exported
    chosen = tmp_path / "chosen-vault"
    chosen.mkdir()
    restored = tmp_path / "restored.sqlite3"
    import_ledger(restored, output, chosen)
    with open_database(restored) as db:
        assert db.execute("SELECT value FROM settings WHERE key='vault_root'").fetchone()[0] == str(
            chosen
        )
    assert not list(chosen.iterdir())


@pytest.mark.parametrize("damage", ["truncate", "checksum", "extra", "blank", "no-trailer"])
def test_corrupt_or_truncated_exports_leave_no_target(
    exported: tuple[Path, Path, Path], tmp_path: Path, damage: str
) -> None:
    vault, _, output = exported
    raw = output.read_bytes()
    if damage == "truncate":
        raw = raw[:-1]
    elif damage == "checksum":
        raw = raw.replace(b'"score":1.0', b'"score":0.0')
    elif damage == "extra":
        raw += b"{}\n"
    elif damage == "blank":
        raw = b"\n" + raw
    else:
        raw = b"\n".join(raw.splitlines()[:-1]) + b"\n"
    output.write_bytes(raw)
    target = tmp_path / "bad.sqlite3"
    with pytest.raises(StudyBuddyError):
        import_ledger(target, output, vault)
    assert not target.exists()


@pytest.mark.parametrize(
    "damage",
    [
        "traversal",
        "absolute",
        "score",
        "answer",
        "rubric",
        "evaluator",
        "topic",
        "assistance",
        "restore",
        "timestamp",
        "mastered",
        "source",
        "source-version",
        "source-hash",
        "unknown-table",
        "version-type",
        "foreign-key",
        "duplicate-key",
        "concept-version",
        "concept-line",
        "metadata-shape",
    ],
)
def test_even_rechecksummed_invalid_or_forged_records_are_rejected(
    exported: tuple[Path, Path, Path], tmp_path: Path, damage: str
) -> None:
    vault, _, output = exported
    records = [json.loads(line) for line in output.read_text().splitlines()]

    def data(kind: str) -> dict:
        return next(record["data"] for record in records if record["type"] == kind)

    if damage in {"traversal", "absolute"}:
        data("documents")["path"] = (
            "../outside.md" if damage == "traversal" else "/private/outside.md"
        )
    elif damage == "score":
        data("assessment_attempts")["score"] = 0.5
    elif damage == "answer":
        answer = {"timeout": "absent", "identity": "new"}
        data("assessment_attempts").update(
            answer_json=canonical_json(answer), answer_sha256=digest(answer)
        )
    elif damage == "rubric":
        session = data("assessment_sessions")
        item = json.loads(session["assessment_json"])
        item["expected"]["timeout"] = "absent"
        session.update(assessment_json=canonical_json(item), assessment_sha256=digest(item))
    elif damage == "evaluator":
        data("assessment_attempts")["evaluator_version"] = "forged-evaluator"
    elif damage == "topic":
        data("assessment_sessions")["topic"] = "unrelated-topic"
    elif damage == "assistance":
        data("assessment_attempts")["hints_used"] = 1
    elif damage == "restore":
        data("assessment_corrections")["action"] = "restore"
    elif damage == "timestamp":
        data("learning_events")["occurred_at"] = "2026-01-01T00:00:00"
    elif damage == "mastered":
        data("concepts")["mastered"] = True
    elif damage in {"source", "source-version", "source-hash"}:
        record = data("assessment_sessions")
        snapshot = json.loads(record["source_snapshot_json"])
        if damage == "source":
            snapshot["concept_id"] = "c_" + "0" * 32
        elif damage == "source-version":
            snapshot["content_version"] = 999
        else:
            snapshot["sha256"] = "0" * 64
        record["source_snapshot_json"] = canonical_json(snapshot)
    elif damage == "unknown-table":
        records[1]["type"] = "sqlite_master"
    elif damage == "version-type":
        records[0]["format_version"] = True
    elif damage == "foreign-key":
        data("assessment_attempts")["session_id"] = "s_" + "0" * 32
    elif damage == "duplicate-key":
        attempts = [row["data"] for row in records if row["type"] == "assessment_attempts"]
        attempts[1]["idempotency_key"] = attempts[0]["idempotency_key"]
    elif damage == "concept-version":
        data("concepts")["source_content_version"] = 42
    elif damage == "concept-line":
        data("concepts")["line"] = 0
    else:
        data("documents")["frontmatter_json"] = "[]"
    rewrite(output, records)
    target = tmp_path / "invalid.sqlite3"
    with pytest.raises(StudyBuddyError):
        import_ledger(target, output, vault)
    assert not target.exists()


def test_export_and_import_never_overwrite_or_write_inside_vault(
    exported: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    vault, database, output = exported
    before = output.read_bytes()
    with pytest.raises(StudyBuddyError, match="already exists"):
        export_ledger(database, output)
    assert output.read_bytes() == before
    with pytest.raises(StudyBuddyError, match="new database"):
        import_ledger(database, output, vault)
    with pytest.raises(StudyBuddyError, match="outside"):
        export_ledger(database, vault / "export.jsonl")
    with pytest.raises(StudyBuddyError, match="outside"):
        import_ledger(vault / "restored.sqlite3", output, vault)
    assert output.stat().st_mode & 0o777 == 0o600


def test_export_read_snapshot_leaves_source_database_unchanged(
    exported: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    _, database, first = exported
    before = database_dump(database)
    second = tmp_path / "another.jsonl"
    export_ledger(database, second)
    assert first.read_bytes() == second.read_bytes()
    assert database_dump(database) == before


def test_historical_source_version_survives_note_edit_and_restore(
    exported: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    vault, database, _ = exported
    (vault / "network.md").write_text("# Networking\n## Edited topic\n", encoding="utf-8")
    index_vault(vault, database)
    output = tmp_path / "edited.ledger.jsonl"
    export_ledger(database, output)
    restored = tmp_path / "edited-restored.sqlite3"
    import_ledger(restored, output, vault)
    with open_database(restored) as db:
        evidence = read_attempts(db)[0]
        assert json.loads(evidence["source_snapshot_json"])["content_version"] == 1
        assert list_concepts(db)[0]["content_version"] == 2


def test_import_audit_failure_leaves_no_target(
    exported: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, _, output = exported
    target = tmp_path / "failed.sqlite3"

    def fail(*args: object) -> None:
        raise RuntimeError("audit failure")

    monkeypatch.setattr("studybuddy.ledger.audit", fail)
    with pytest.raises(RuntimeError, match="audit failure"):
        import_ledger(target, output, vault)
    assert not target.exists()
