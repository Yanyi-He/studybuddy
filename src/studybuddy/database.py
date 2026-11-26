import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any

from studybuddy.errors import StudyBuddyError
from studybuddy.models import utc_now
from studybuddy.vault import validate_database_location

SCHEMA_VERSION = 2
APPLICATION_ID = 0x53544259


def default_database() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "studybuddy" / "studybuddy.sqlite3"


def _prepare_path(path: Path, create: bool) -> Path:
    resolved = path.expanduser().resolve()
    if create and not resolved.exists():
        resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(resolved, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass  # Another StudyBuddy process created it; SQLite serializes initialization.
        else:
            os.close(descriptor)
    if not resolved.is_file():
        raise StudyBuddyError("Database does not exist; run 'studybuddy index --vault PATH' first.")
    return resolved


def _execute_schema(connection: sqlite3.Connection, schema: str) -> None:
    # executescript() can commit an existing transaction. Execute complete statements
    # separately so schema creation stays inside the caller's transaction.
    statement = ""
    for line in schema.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        raise StudyBuddyError("The packaged database schema is incomplete.")


def _initialize(connection: sqlite3.Connection) -> None:
    # The lock also protects the first-use schema check from concurrent indexers.
    with transaction(connection):
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version:
            _verify_schema(connection)
            return
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        if tables:
            raise StudyBuddyError("Refusing to initialize a database owned by another application.")
        schema = files("studybuddy").joinpath("schema.sql").read_text(encoding="utf-8")
        _execute_schema(connection, schema)
        migration = files("studybuddy").joinpath("migrations/002-assessments.sql")
        _execute_schema(connection, migration.read_text(encoding="utf-8"))
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _verify_schema(connection: sqlite3.Connection) -> None:
    app_id = connection.execute("PRAGMA application_id").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if app_id == APPLICATION_ID and version == 1:
        raise StudyBuddyError(
            "Schema v1 needs an explicit upgrade: "
            "studybuddy --db PATH migrate --backup BACKUP_PATH."
        )
    if app_id != APPLICATION_ID or version != SCHEMA_VERSION:
        raise StudyBuddyError(
            "Unsupported database format/version; no automatic migration attempted."
        )


@contextmanager
def open_database(
    path: Path, *, create: bool = False, writable: bool = False
) -> Iterator[sqlite3.Connection]:
    resolved = _prepare_path(path, create)
    mode = "rw" if writable else "ro"
    connection = sqlite3.connect(f"{resolved.as_uri()}?mode={mode}", uri=True, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if create:
            _initialize(connection)
        _verify_schema(connection)
        if writable:
            configured = connection.execute(
                "SELECT value FROM settings WHERE key='vault_root'"
            ).fetchone()
            if configured:
                validate_database_location(resolved, Path(configured[0]))
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
        else:
            connection.execute("PRAGMA query_only = ON")
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def audit(connection: sqlite3.Connection, action: str, target_id: str, details: Any) -> None:
    connection.execute(
        "INSERT INTO audit_log(action, target_id, recorded_at, details_json) VALUES (?, ?, ?, ?)",
        (action, target_id, utc_now(), json.dumps(details, ensure_ascii=False, sort_keys=True)),
    )
