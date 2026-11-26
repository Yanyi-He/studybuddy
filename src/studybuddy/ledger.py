"""Logical JSONL ledger snapshots. Imported data is validated, never executed."""

import hashlib
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from studybuddy.assessments import read_attempts
from studybuddy.catalog import trusted_assessment
from studybuddy.database import SCHEMA_VERSION, _initialize, audit, open_database, transaction
from studybuddy.errors import StudyBuddyError
from studybuddy.migration import reserve_output
from studybuddy.models import normalize_timestamp
from studybuddy.validation import canonical_json, strict_json, validate_id, validate_key
from studybuddy.vault import _validated_parts, validate_database_location, validate_vault

FORMAT = "studybuddy-ledger"
FORMAT_VERSION = 1
MAX_EXPORT_BYTES = 64 * 1024 * 1024
TABLES = {
    "documents": "id",
    "concepts": "id",
    "wikilinks": "document_id,line,target,anchor,alias",
    "learning_events": "id",
    "assessment_sessions": "id",
    "assessment_attempts": "id",
    "assessment_corrections": "sequence",
}


def _encode_snapshot(db: sqlite3.Connection) -> tuple[bytes, int, str]:
    root = db.execute("SELECT value FROM settings WHERE key='vault_root'").fetchone()
    if not root:
        raise StudyBuddyError("Index a vault before exporting its ledger.")
    header = {
        "type": "manifest",
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "vault_root": root[0],
    }
    lines = [canonical_json(header) + "\n"]
    count = 0
    for table, order in TABLES.items():
        for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}"):
            lines.append(canonical_json({"type": table, "data": dict(row)}) + "\n")
            count += 1
    payload = "".join(lines).encode()
    checksum = hashlib.sha256(payload).hexdigest()
    trailer = canonical_json({"type": "checksum", "records": count, "sha256": checksum}) + "\n"
    return payload + trailer.encode(), count, checksum


def export_ledger(database: Path, output: Path) -> dict:
    with open_database(database) as db:
        db.execute("BEGIN")
        try:
            root = db.execute("SELECT value FROM settings WHERE key='vault_root'").fetchone()
            if root:
                validate_database_location(output, Path(root[0]))
            if output.expanduser().resolve() == database.expanduser().resolve():
                raise StudyBuddyError("Export output must not be the database.")
            payload, count, checksum = _encode_snapshot(db)
        finally:
            db.rollback()
    if len(payload) > MAX_EXPORT_BYTES:
        raise StudyBuddyError("Ledger exceeds the current 64 MiB export limit.")
    target = reserve_output(output)
    try:
        with target.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return {"records": count, "sha256": checksum, "output": str(target)}


def _decode_snapshot(path: Path) -> tuple[list[dict], str]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_EXPORT_BYTES + 1)
    if len(raw) > MAX_EXPORT_BYTES:
        raise StudyBuddyError("Ledger exceeds the 64 MiB import limit.")
    lines = raw.splitlines(keepends=True)
    if len(lines) < 2 or any(not line.endswith(b"\n") for line in lines):
        raise StudyBuddyError(
            "Incomplete JSONL ledger; manifest and checksum trailer are required."
        )
    try:
        records = [strict_json(line.decode("utf-8")) for line in lines]
    except UnicodeDecodeError as exc:
        raise StudyBuddyError("Ledger must be UTF-8.") from exc
    if any(not isinstance(record, dict) for record in records):
        raise StudyBuddyError("Ledger records must be JSON objects.")
    header, trailer = records[0], records[-1]
    if (
        type(header.get("format_version")) is not int
        or type(header.get("schema_version")) is not int
    ):
        raise StudyBuddyError("Unsupported ledger version field types.")
    if (
        set(header) != {"type", "format", "format_version", "schema_version", "vault_root"}
        or header
        != {
            "type": "manifest",
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "vault_root": header.get("vault_root"),
        }
        or not isinstance(header["vault_root"], str)
        or not Path(header["vault_root"]).is_absolute()
    ):
        raise StudyBuddyError("Unsupported ledger manifest or format version.")
    checksum = hashlib.sha256(b"".join(lines[:-1])).hexdigest()
    if type(trailer.get("records")) is not int or trailer != {
        "type": "checksum",
        "records": len(records) - 2,
        "sha256": checksum,
    }:
        raise StudyBuddyError("Ledger checksum/count mismatch; nothing was imported.")
    return records[1:-1], checksum


def _insert_record(db: sqlite3.Connection, record: dict) -> None:
    if (
        set(record) != {"type", "data"}
        or record["type"] not in TABLES
        or not isinstance(record["data"], dict)
    ):
        raise StudyBuddyError("Unknown ledger record or fields.")
    table, data = record["type"], record["data"]
    columns = db.execute(f"PRAGMA table_info({table})").fetchall()
    if set(data) != {column["name"] for column in columns}:
        raise StudyBuddyError("Ledger fields do not match the supported schema.")
    for column in columns:
        value = data[column["name"]]
        allowed = {"TEXT": (str,), "INTEGER": (int,), "REAL": (int, float)}[column["type"]]
        nullable = not column["notnull"] and not column["pk"]
        if (value is None and nullable) or type(value) in allowed:
            continue
        raise StudyBuddyError("Ledger contains an invalid field type.")
    names = ",".join(data)
    db.execute(
        f"INSERT INTO {table}({names}) VALUES ({','.join('?' for _ in data)})", tuple(data.values())
    )


def _validate_snapshot(db: sqlite3.Connection, raw: str, concept_id: str) -> None:
    data = strict_json(raw)
    keys = {"concept_id", "document_id", "anchor", "line", "sha256", "path", "content_version"}
    concept = db.execute("SELECT document_id FROM concepts WHERE id=?", (concept_id,)).fetchone()
    if (
        not isinstance(data, dict)
        or set(data) != keys
        or data["concept_id"] != concept_id
        or data["document_id"] != concept[0]
    ):
        raise StudyBuddyError("Ledger source snapshot does not match its concept/document.")
    _validated_parts(data["path"])
    if (
        not isinstance(data["anchor"], str)
        or type(data["line"]) is not int
        or data["line"] < 1
        or type(data["content_version"]) is not int
        or data["content_version"] < 1
    ):
        raise StudyBuddyError("Invalid source snapshot fields.")
    _validate_hash(data["sha256"])
    document = db.execute(
        "SELECT sha256,content_version FROM documents WHERE id=?", (concept[0],)
    ).fetchone()
    if data["content_version"] > document["content_version"] or (
        data["content_version"] == document["content_version"]
        and data["sha256"] != document["sha256"]
    ):
        raise StudyBuddyError("Source snapshot hash/version is inconsistent with its document.")


def _validate_hash(value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise StudyBuddyError("Invalid SHA-256 in ledger.")


def _validate_rows(db: sqlite3.Connection) -> None:
    prefixes = {
        "documents": "d",
        "concepts": "c",
        "learning_events": "e",
        "assessment_sessions": "s",
        "assessment_attempts": "a",
        "assessment_corrections": "x",
    }
    for table in TABLES:
        for row in db.execute(f"SELECT * FROM {table}"):
            data = dict(row)
            if table in prefixes:
                validate_id(data["id"], prefixes[table])
            for name, value in data.items():
                if value is None:
                    continue
                if name.endswith("_at") and normalize_timestamp(value) != value:
                    raise StudyBuddyError("Ledger timestamps must be canonical timezone-aware UTC.")
                if name.endswith("_json"):
                    parsed = strict_json(value)
                    required_type = list if name == "warnings_json" else dict
                    if not isinstance(parsed, required_type):
                        raise StudyBuddyError("Ledger JSON field has the wrong structure.")
                if name in {"sha256", "source_sha256", "assessment_sha256", "answer_sha256"}:
                    _validate_hash(value)
            if "idempotency_key" in data:
                validate_key(data["idempotency_key"])
            if table == "documents":
                _validated_parts(data["path"])
                if Path(data["path"]).suffix.lower() != ".md":
                    raise StudyBuddyError("Source documents must be Markdown paths.")
            if "source_snapshot_json" in data:
                _validate_snapshot(db, data["source_snapshot_json"], data["concept_id"])
    if db.execute(
        "SELECT 1 FROM concepts c JOIN documents d ON c.document_id=d.id "
        "WHERE c.line<1 OR c.source_content_version>d.content_version OR "
        "(c.retired_at IS NULL AND d.deleted_at IS NULL AND "
        "(c.source_sha256!=d.sha256 OR c.source_content_version!=d.content_version))"
    ).fetchone():
        raise StudyBuddyError("Concept source version/hash is inconsistent with its document.")


def _validate_assessments(db: sqlite3.Connection) -> None:
    for row in db.execute("SELECT * FROM assessment_sessions"):
        item = trusted_assessment(row["assessment_json"], row["assessment_sha256"])
        if row["assessment_id"] != item["id"] or row["topic"] != item["topic"]:
            raise StudyBuddyError("Assessment identity/topic mismatch.")
    if db.execute(
        "SELECT concept_id FROM assessment_sessions GROUP BY concept_id "
        "HAVING COUNT(DISTINCT topic)>1"
    ).fetchone():
        raise StudyBuddyError("A concept cannot mix assessment topics.")
    for attempt in read_attempts(db):
        if not attempt["issued_at"] <= attempt["submitted_at"] == attempt["recorded_at"]:
            raise StudyBuddyError("Assessment timestamps are inconsistent.")
    previous: dict[str, dict] = {}
    for row in db.execute("SELECT * FROM assessment_corrections ORDER BY sequence"):
        attempt = db.execute(
            "SELECT recorded_at FROM assessment_attempts WHERE id=?", (row["attempt_id"],)
        ).fetchone()
        last = previous.get(row["attempt_id"])
        lower = last["recorded_at"] if last else attempt[0]
        if (
            row["recorded_at"] < lower
            or not row["reason"].strip()
            or len(row["reason"]) > 2000
            or row["sequence"] < 1
        ):
            raise StudyBuddyError("Invalid correction order or reason.")
        if row["action"] == "restore" and (last is None or last["action"] != "invalidate"):
            raise StudyBuddyError("Restore must follow an invalidation.")
        previous[row["attempt_id"]] = dict(row)


def import_ledger(database: Path, source: Path, vault: Path) -> dict:
    root = validate_vault(vault)
    validate_database_location(database, root)
    if os.path.lexists(database.expanduser()):
        raise StudyBuddyError(
            "Import requires a new database path; "
            "existing databases are never merged or overwritten."
        )
    records, checksum = _decode_snapshot(source)
    with closing(sqlite3.connect(":memory:", isolation_level=None)) as staged:
        staged.row_factory = sqlite3.Row
        staged.execute("PRAGMA foreign_keys=ON")
        _initialize(staged)
        try:
            with transaction(staged):
                for record in records:
                    _insert_record(staged, record)
                _validate_rows(staged)
                _validate_assessments(staged)
                staged.execute("INSERT INTO settings VALUES ('vault_root', ?)", (str(root),))
                staged.execute(
                    "INSERT INTO concept_search(concept_id,title,path,anchor) "
                    "SELECT c.id,c.title,d.path,c.anchor FROM concepts c "
                    "JOIN documents d ON c.document_id=d.id "
                    "WHERE c.retired_at IS NULL AND d.deleted_at IS NULL"
                )
                audit(
                    staged,
                    "ledger.import",
                    checksum,
                    {"records": len(records), "vault_root": str(root)},
                )
        except (sqlite3.Error, TypeError, KeyError, ValueError) as exc:
            raise StudyBuddyError(
                "Ledger validation failed; target database was not created."
            ) from exc
        target = reserve_output(database)
        try:
            with closing(sqlite3.connect(target)) as destination:
                staged.backup(destination)
                destination.execute("PRAGMA journal_mode=WAL")
                destination.execute("PRAGMA synchronous=FULL")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
    return {"records": len(records), "sha256": checksum, "database": str(target)}
