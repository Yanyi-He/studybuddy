import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from studybuddy.database import audit, open_database, transaction
from studybuddy.errors import StudyBuddyError
from studybuddy.markdown import parse_note
from studybuddy.models import IndexResult, NoteSnapshot, utc_now
from studybuddy.vault import read_note, scan_vault, validate_database_location, validate_vault


def _bind_vault(connection: sqlite3.Connection, root: Path) -> None:
    row = connection.execute("SELECT value FROM settings WHERE key = 'vault_root'").fetchone()
    if row and row[0] != str(root):
        raise StudyBuddyError("This database belongs to another vault; choose a separate --db.")
    if row is None:
        connection.execute(
            "INSERT INTO settings(key, value) VALUES ('vault_root', ?)", (str(root),)
        )
        audit(connection, "vault.bind", "vault_root", {"root": str(root)})


def _snapshot(root: Path, path: str, previous: sqlite3.Row | None) -> NoteSnapshot:
    content, mtime_ns = read_note(root, path)
    digest = hashlib.sha256(content).hexdigest()
    unchanged = previous is not None and previous["sha256"] == digest and not previous["deleted_at"]
    parsed = None
    if not unchanged:
        try:
            parsed = parse_note(content.decode("utf-8-sig"), path)
        except UnicodeDecodeError as exc:
            raise StudyBuddyError("A note is not UTF-8; indexing was not committed.") from exc
    return NoteSnapshot(path, digest, mtime_ns, parsed)


def _rename_candidates(
    existing: dict[str, sqlite3.Row], snapshots: list[NoteSnapshot]
) -> dict[str, sqlite3.Row]:
    current_paths = {note.path for note in snapshots}
    missing: dict[str, list[sqlite3.Row]] = defaultdict(list)
    incoming: dict[str, list[NoteSnapshot]] = defaultdict(list)
    for path, row in existing.items():
        if path not in current_paths and not row["deleted_at"]:
            missing[row["sha256"]].append(row)
    for note in snapshots:
        if note.path not in existing:
            incoming[note.sha256].append(note)
    return {
        notes[0].path: missing[digest][0]
        for digest, notes in incoming.items()
        if len(notes) == 1 and len(missing[digest]) == 1
    }


def _retire_concepts(connection: sqlite3.Connection, document_id: str, now: str) -> None:
    connection.execute(
        "DELETE FROM concept_search WHERE concept_id IN "
        "(SELECT id FROM concepts WHERE document_id = ?)",
        (document_id,),
    )
    connection.execute(
        "UPDATE concepts SET retired_at = ? WHERE document_id = ? AND retired_at IS NULL",
        (now, document_id),
    )


def _sync_concepts(
    connection: sqlite3.Connection, document_id: str, note: NoteSnapshot, version: int, now: str
) -> None:
    assert note.parsed is not None
    _retire_concepts(connection, document_id, now)
    for heading in note.parsed.headings:
        concept_id = "c_" + uuid5(NAMESPACE_URL, f"studybuddy:{document_id}:{heading.key}").hex
        connection.execute(
            "INSERT INTO concepts(id, document_id, heading_key, title, anchor, line, "
            "source_sha256, source_content_version, first_seen_at, source_indexed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET title=excluded.title, anchor=excluded.anchor, "
            "line=excluded.line, source_sha256=excluded.source_sha256, "
            "source_content_version=excluded.source_content_version, "
            "source_indexed_at=excluded.source_indexed_at, retired_at=NULL",
            (
                concept_id,
                document_id,
                heading.key,
                heading.title,
                heading.anchor,
                heading.line,
                note.sha256,
                version,
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO concept_search(concept_id, title, path, anchor) VALUES (?, ?, ?, ?)",
            (concept_id, heading.title, note.path, heading.anchor),
        )
    connection.execute("DELETE FROM wikilinks WHERE document_id = ?", (document_id,))
    connection.executemany(
        "INSERT INTO wikilinks(document_id, target, anchor, alias, line) VALUES (?, ?, ?, ?, ?)",
        [
            (document_id, link.target, link.anchor, link.alias, link.line)
            for link in note.parsed.wikilinks
        ],
    )


def _save_document(
    connection: sqlite3.Connection, note: NoteSnapshot, previous: sqlite3.Row | None, now: str
) -> str:
    assert note.parsed is not None
    document_id = previous["id"] if previous else "d_" + uuid4().hex
    version = previous["content_version"] if previous else 1
    if previous and previous["sha256"] != note.sha256:
        version += 1
    connection.execute(
        "INSERT INTO documents(id, path, sha256, content_version, source_mtime_ns, "
        "first_indexed_at, indexed_at, frontmatter_json, warnings_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
        "path=excluded.path, sha256=excluded.sha256, content_version=excluded.content_version, "
        "source_mtime_ns=excluded.source_mtime_ns, indexed_at=excluded.indexed_at, "
        "frontmatter_json=excluded.frontmatter_json, "
        "warnings_json=excluded.warnings_json, deleted_at=NULL",
        (
            document_id,
            note.path,
            note.sha256,
            version,
            note.mtime_ns,
            now,
            now,
            note.parsed.metadata_json,
            json.dumps(note.parsed.warnings),
        ),
    )
    _sync_concepts(connection, document_id, note, version, now)
    return document_id


def _apply_snapshot(
    connection: sqlite3.Connection,
    note: NoteSnapshot,
    previous: sqlite3.Row | None,
    renamed: bool,
    result: IndexResult,
    now: str,
) -> None:
    if note.parsed is None:
        result.unchanged += 1
        assert previous is not None
        warnings = json.loads(previous["warnings_json"])
    else:
        _save_document(connection, note, previous, now)
        warnings = note.parsed.warnings
        if renamed:
            result.renamed += 1
        elif previous is None:
            result.added += 1
        elif previous["deleted_at"]:
            result.restored += 1
        else:
            result.updated += 1
    result.warnings.extend({"path": note.path, "code": warning} for warning in warnings)


def _reconcile(connection: sqlite3.Connection, root: Path) -> IndexResult:
    scan = scan_vault(root)
    existing = {row["path"]: row for row in connection.execute("SELECT * FROM documents")}
    snapshots = [_snapshot(root, path, existing.get(path)) for path in scan.files]
    renames = _rename_candidates(existing, snapshots)
    now = utc_now()
    result = IndexResult(skipped_symlinks=scan.skipped_symlinks)
    for note in snapshots:
        previous = existing.get(note.path)
        _apply_snapshot(
            connection, note, previous or renames.get(note.path), note.path in renames, result, now
        )
    renamed_ids = {row["id"] for row in renames.values()}
    paths = set(scan.files)
    for path, row in existing.items():
        if path not in paths and row["id"] not in renamed_ids and not row["deleted_at"]:
            connection.execute("UPDATE documents SET deleted_at = ? WHERE id = ?", (now, row["id"]))
            _retire_concepts(connection, row["id"], now)
            result.deleted += 1
    if result.added + result.updated + result.renamed + result.restored + result.deleted:
        audit(connection, "index.commit", "vault_root", asdict(result))
    return result


def index_vault(vault: Path, database: Path) -> IndexResult:
    root = validate_vault(vault)
    validate_database_location(database, root)
    with open_database(database, create=True, writable=True) as connection, transaction(connection):
        _bind_vault(connection, root)
        return _reconcile(connection, root)
