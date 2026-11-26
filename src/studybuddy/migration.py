"""Explicit schema migration with a consistent pre-migration SQLite backup."""

import os
import sqlite3
from contextlib import closing
from importlib.resources import files
from pathlib import Path

from studybuddy.database import APPLICATION_ID, SCHEMA_VERSION, _execute_schema, audit, transaction
from studybuddy.errors import StudyBuddyError
from studybuddy.vault import validate_database_location


def reserve_output(path: Path) -> Path:
    resolved = path.expanduser().absolute()
    resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(resolved, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StudyBuddyError(
            "Output already exists; choose a new path. Nothing was overwritten."
        ) from exc
    os.close(descriptor)
    return resolved


def _backup(source: Path, target: Path) -> None:
    # Use a separate reader: backing up the writer's open transaction can wait on itself.
    with (
        closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as reader,
        closing(sqlite3.connect(target)) as destination,
    ):
        reader.backup(destination)
        if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise StudyBuddyError("Backup integrity check failed; migration was not applied.")


def migrate_database(database: Path, backup: Path) -> dict:
    source = database.expanduser().resolve(strict=True)
    with closing(
        sqlite3.connect(f"{source.as_uri()}?mode=rw", uri=True, isolation_level=None)
    ) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 5000")
        with transaction(db):
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                raise StudyBuddyError("Unsupported database format; migration refused.")
            if version == SCHEMA_VERSION:
                return {"migrated": False, "schema_version": version, "backup": None}
            if version != 1:
                raise StudyBuddyError("Unsupported schema version; migration refused.")
            root = db.execute("SELECT value FROM settings WHERE key='vault_root'").fetchone()
            if root:
                validate_database_location(source, Path(root[0]))
                validate_database_location(backup, Path(root[0]))
            target = reserve_output(backup)
            _backup(source, target)
            sql = (
                files("studybuddy")
                .joinpath("migrations/002-assessments.sql")
                .read_text(encoding="utf-8")
            )
            _execute_schema(db, sql)
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            audit(
                db, "schema.migrate", str(SCHEMA_VERSION), {"from": version, "backup": str(target)}
            )
    return {"migrated": True, "schema_version": SCHEMA_VERSION, "backup": str(target)}
