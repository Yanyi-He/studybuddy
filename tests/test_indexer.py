import hashlib
import json
import os
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


def test_index_has_provenance_and_never_implies_mastery(indexed: tuple[Path, Path]) -> None:
    vault, database = indexed
    with open_database(database) as connection:
        concepts = list_concepts(connection)
        assert len(concepts) == 2
        assert {item["status"] for item in concepts} == {"seen"}
        assert {item["confirmation"] for item in concepts} == {"candidate"}
        assert (
            concepts[0]["source_sha256"]
            == hashlib.sha256((vault / "network.md").read_bytes()).hexdigest()
        )
        assert concepts[0]["path"] == "network.md"
        assert concepts[0]["anchor"] == "Networking"
        assert concepts[0]["first_seen_at"]
        assert concepts[0]["source_indexed_at"]
        row = connection.execute("SELECT * FROM documents").fetchone()
        assert json.loads(row["frontmatter_json"])["tags"] == ["network", "学习"]
        assert connection.execute("SELECT COUNT(*) FROM wikilinks").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert progress(connection)["verified_mastered"] == 0


def test_repeated_index_is_logically_identical(indexed: tuple[Path, Path]) -> None:
    vault, database = indexed
    before = database_dump(database)
    result = index_vault(vault, database)
    assert result.unchanged == 1
    assert result.added == result.updated == result.deleted == result.renamed == 0
    assert database_dump(database) == before


def test_content_hash_detects_change_even_if_mtime_is_unchanged(indexed: tuple[Path, Path]) -> None:
    vault, database = indexed
    note = vault / "network.md"
    original_mtime = note.stat().st_mtime_ns
    original_id = concept_id(database)
    note.write_text("# Networking\n## New heading\n", encoding="utf-8")
    os.utime(note, ns=(original_mtime, original_mtime))
    result = index_vault(vault, database)
    assert result.updated == 1
    with open_database(database) as connection:
        concepts = list_concepts(connection)
        assert concepts[0]["id"] == original_id
        assert concepts[0]["content_version"] == 2
        assert len(list_concepts(connection, include_inactive=True)) == 3
        retired = [
            item for item in list_concepts(connection, include_inactive=True) if item["retired_at"]
        ]
        assert retired[0]["content_version"] == 1
        assert retired[0]["source_sha256"] != concepts[0]["source_sha256"]
        assert list_events(connection) == []
        assert connection.execute("SELECT COUNT(*) FROM wikilinks").fetchone()[0] == 0


def test_mtime_only_change_does_not_create_exposure_or_learning_events(
    indexed: tuple[Path, Path],
) -> None:
    vault, database = indexed
    note = vault / "network.md"
    before = database_dump(database)
    os.utime(note, ns=(note.stat().st_atime_ns, note.stat().st_mtime_ns + 1_000_000_000))
    assert index_vault(vault, database).unchanged == 1
    assert database_dump(database) == before


def test_identical_files_are_distinct_sources(vault: Path, database: Path) -> None:
    for name in ["a.md", "b.md"]:
        (vault / name).write_text("# Same concept\n", encoding="utf-8")
    assert index_vault(vault, database).added == 2
    with open_database(database) as connection:
        concepts = list_concepts(connection)
        assert len({item["id"] for item in concepts}) == 2
        assert len({item["source_sha256"] for item in concepts}) == 1


def test_rename_preserves_ids_and_historical_event_source(indexed: tuple[Path, Path]) -> None:
    vault, database = indexed
    original_id = concept_id(database)
    with open_database(database, writable=True) as connection:
        append_event(connection, EventRequest(original_id, EventKind.EXPOSURE, "before-rename"))
    (vault / "network.md").rename(vault / "网络重命名.md")
    assert index_vault(vault, database).renamed == 1
    with open_database(database) as connection:
        concepts = list_concepts(connection)
        assert concepts[0]["id"] == original_id
        assert concepts[0]["path"] == "网络重命名.md"
        assert concepts[0]["content_version"] == 1
        assert list_events(connection)[0]["source_snapshot"]["path"] == "network.md"
        assert len(list_concepts(connection, search="Networking")) == 1


def test_delete_tombstones_without_erasing_events(indexed: tuple[Path, Path]) -> None:
    vault, database = indexed
    original_id = concept_id(database)
    with open_database(database, writable=True) as connection:
        append_event(connection, EventRequest(original_id, EventKind.RECALL_ATTEMPT, "recall-1"))
    (vault / "network.md").unlink()
    assert index_vault(vault, database).deleted == 1
    with open_database(database) as connection:
        assert list_concepts(connection) == []
        assert len(list_concepts(connection, include_inactive=True)) == 2
        assert len(list_events(connection)) == 1
        assert connection.execute("SELECT COUNT(*) FROM concept_search").fetchone()[0] == 0
    assert index_vault(vault, database).deleted == 0


def test_restore_same_path_reuses_source_and_concept_ids(indexed: tuple[Path, Path]) -> None:
    vault, database = indexed
    note = vault / "network.md"
    content = note.read_bytes()
    original_id = concept_id(database)
    note.unlink()
    index_vault(vault, database)
    note.write_bytes(content)
    assert index_vault(vault, database).restored == 1
    assert concept_id(database) == original_id


def test_ambiguous_duplicate_renames_are_not_guessed(vault: Path, database: Path) -> None:
    for name in ["a.md", "b.md"]:
        (vault / name).write_text("# Same\n", encoding="utf-8")
    index_vault(vault, database)
    (vault / "a.md").rename(vault / "c.md")
    (vault / "b.md").rename(vault / "d.md")
    result = index_vault(vault, database)
    assert (result.renamed, result.added, result.deleted) == (0, 2, 2)


def test_rename_and_edit_is_new_source(vault: Path, database: Path) -> None:
    (vault / "a.md").write_text("# Before", encoding="utf-8")
    index_vault(vault, database)
    (vault / "a.md").rename(vault / "b.md")
    (vault / "b.md").write_text("# After", encoding="utf-8")
    result = index_vault(vault, database)
    assert (result.renamed, result.added, result.deleted) == (0, 1, 1)


def test_invalid_yaml_is_reported_without_leaking_content(vault: Path, database: Path) -> None:
    (vault / "bad.md").write_text("---\nsecret: [private-value\n---\n# Useful", encoding="utf-8")
    result = index_vault(vault, database)
    assert result.warnings == [{"path": "bad.md", "code": "invalid_yaml"}]
    assert "private-value" not in str(result)
    assert index_vault(vault, database).warnings == result.warnings


def test_rejects_database_inside_vault_without_creating_it(vault: Path) -> None:
    database = vault / "private.sqlite3"
    with pytest.raises(StudyBuddyError, match="outside"):
        index_vault(vault, database)
    assert not database.exists()


def test_database_is_bound_to_one_vault(indexed: tuple[Path, Path], tmp_path: Path) -> None:
    _, database = indexed
    other = tmp_path / "other"
    other.mkdir()
    before = database_dump(database)
    with pytest.raises(StudyBuddyError, match="another vault"):
        index_vault(other, database)
    assert database_dump(database) == before


def test_invalid_utf8_aborts_whole_scan_without_tombstones(indexed: tuple[Path, Path]) -> None:
    vault, database = indexed
    before = database_dump(database)
    (vault / "network.md").unlink()
    (vault / "bad.md").write_bytes(b"\xff\xfe")
    with pytest.raises(StudyBuddyError, match="UTF-8"):
        index_vault(vault, database)
    assert database_dump(database) == before


def test_failure_before_audit_rolls_back_all_index_changes(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, database = indexed
    before = database_dump(database)
    (vault / "network.md").write_text("# Changed", encoding="utf-8")

    def fail_audit(*args: object) -> None:
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr("studybuddy.indexer.audit", fail_audit)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        index_vault(vault, database)
    assert database_dump(database) == before


def test_100_synthetic_notes_are_indexed_idempotently(vault: Path, database: Path) -> None:
    for number in range(100):
        (vault / f"note-{number:03d}.md").write_text(
            f"---\nnumber: {number}\n---\n# Concept {number}\n## 概念 {number}\n[[note-000]]\n",
            encoding="utf-8",
        )
    assert index_vault(vault, database).added == 100
    assert index_vault(vault, database).unchanged == 100
    with open_database(database) as connection:
        assert len(list_concepts(connection)) == 200
        assert progress(connection)["awaiting_independent_assessment"] == 200


def test_sql_like_source_text_is_stored_as_data(vault: Path, database: Path) -> None:
    title = "Robert'); DROP TABLE concepts;--"
    (vault / "quote's.md").write_text(f"# {title}\n", encoding="utf-8")
    index_vault(vault, database)
    with open_database(database) as connection:
        assert list_concepts(connection)[0]["title"] == title


def test_concurrent_first_index_serializes_initialization(vault: Path, database: Path) -> None:
    (vault / "note.md").write_text("# Concurrent source\n", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: index_vault(vault, database), range(2)))
    assert sorted(result.added for result in results) == [0, 1]
    assert sorted(result.unchanged for result in results) == [0, 1]
    with open_database(database) as connection:
        assert len(list_concepts(connection)) == 1
