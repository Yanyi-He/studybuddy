import sqlite3
from contextlib import closing
from importlib.resources import files
from pathlib import Path

import pytest

from studybuddy.database import APPLICATION_ID, _execute_schema, open_database, transaction
from studybuddy.errors import StudyBuddyError
from studybuddy.events import EventRequest, append_event
from studybuddy.indexer import _reconcile
from studybuddy.migration import migrate_database
from studybuddy.models import EventKind
from studybuddy.queries import list_events, progress


def create_v1(database: Path, vault: Path) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    (vault / "old.md").write_text("# Legacy concept\n", encoding="utf-8")
    with closing(sqlite3.connect(database, isolation_level=None)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        _execute_schema(db, files("studybuddy").joinpath("schema.sql").read_text())
        db.execute(f"PRAGMA application_id={APPLICATION_ID}")
        db.execute("PRAGMA user_version=1")
        with transaction(db):
            db.execute("INSERT INTO settings VALUES ('vault_root', ?)", (str(vault),))
            _reconcile(db, vault)
        identifier = db.execute("SELECT id FROM concepts").fetchone()[0]
        append_event(db, EventRequest(identifier, EventKind.AI_ANSWER_COPIED, "legacy-event"))


def test_v1_requires_explicit_migration_and_keeps_reads_unchanged(
    vault: Path, database: Path
) -> None:
    create_v1(database, vault)
    before = database.read_bytes()
    with pytest.raises(StudyBuddyError, match="migrate --backup"), open_database(database):
        pass
    assert database.read_bytes() == before


def test_migration_creates_restorable_backup_and_preserves_events(
    vault: Path, database: Path, tmp_path: Path
) -> None:
    create_v1(database, vault)
    backup = tmp_path / "before-v2.sqlite3"
    result = migrate_database(database, backup)
    assert result["migrated"] and result["schema_version"] == 2
    assert backup.stat().st_mode & 0o777 == 0o600
    with closing(sqlite3.connect(backup)) as old:
        assert old.execute("PRAGMA user_version").fetchone()[0] == 1
        assert old.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert old.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0] == 1
        assert not old.execute(
            "SELECT name FROM sqlite_master WHERE name='assessment_sessions'"
        ).fetchone()
    with open_database(database) as db:
        events = list_events(db)
        assert len(events) == 1 and events[0]["kind"] == "ai_answer_copied"
        assert progress(db)["verified_mastered"] == 0
        assert (
            db.execute("SELECT COUNT(*) FROM audit_log WHERE action='schema.migrate'").fetchone()[0]
            == 1
        )
    migrate_database(backup, tmp_path / "backup-of-backup.sqlite3")
    with open_database(backup) as db:
        assert list_events(db) == events


def test_migration_is_idempotent(indexed: tuple[Path, Path], tmp_path: Path) -> None:
    _, database = indexed
    backup = tmp_path / "not-needed.sqlite3"
    assert not migrate_database(database, backup)["migrated"]
    assert not backup.exists()


def test_migration_never_overwrites_a_backup(vault: Path, database: Path, tmp_path: Path) -> None:
    create_v1(database, vault)
    backup = tmp_path / "existing.sqlite3"
    backup.write_bytes(b"do not overwrite")
    with pytest.raises(StudyBuddyError, match="already exists"):
        migrate_database(database, backup)
    assert backup.read_bytes() == b"do not overwrite"
    with closing(sqlite3.connect(database)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1


def test_migration_rejects_backup_inside_vault(vault: Path, database: Path) -> None:
    create_v1(database, vault)
    with pytest.raises(StudyBuddyError, match="outside"):
        migrate_database(database, vault / "backup.sqlite3")
    assert not (vault / "backup.sqlite3").exists()


def test_migration_audit_failure_rolls_back_schema_but_keeps_backup(
    vault: Path, database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_v1(database, vault)
    backup = tmp_path / "backup.sqlite3"

    def fail(*args: object) -> None:
        raise RuntimeError("audit failed")

    monkeypatch.setattr("studybuddy.migration.audit", fail)
    with pytest.raises(RuntimeError, match="audit failed"):
        migrate_database(database, backup)
    with closing(sqlite3.connect(database)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='assessment_sessions'"
        ).fetchone()
    with closing(sqlite3.connect(backup)) as old:
        assert old.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
