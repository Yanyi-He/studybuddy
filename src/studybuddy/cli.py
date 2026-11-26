import argparse
import json
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from studybuddy import __version__
from studybuddy.database import default_database, open_database
from studybuddy.errors import StudyBuddyError
from studybuddy.events import EventRequest, append_event
from studybuddy.indexer import index_vault
from studybuddy.ledger import export_ledger, import_ledger
from studybuddy.migration import migrate_database
from studybuddy.models import EventKind
from studybuddy.queries import list_concepts, list_events, progress
from studybuddy.quiz_cli import dispatch_quiz, quiz_without_database, register_quiz
from studybuddy.vault import scan_vault, validate_vault


def _output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="studybuddy", description="See what your notes don't prove."
    )
    parser.add_argument("--version", action="version", version=f"studybuddy {__version__}")
    parser.add_argument(
        "--db", type=Path, default=default_database(), help="SQLite file outside the vault."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("doctor", "Check a vault without reading note contents or creating a DB."),
        ("index", "Incrementally index a read-only vault."),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--vault", type=Path, required=True)
        _output_options(command)
    concepts = commands.add_parser("concepts", help="Inspect source-backed concept candidates.")
    concept_commands = concepts.add_subparsers(dest="concept_command", required=True)
    listing = concept_commands.add_parser("list")
    listing.add_argument(
        "--search", help="Literal phrase search over active headings and source paths."
    )
    listing.add_argument("--include-inactive", action="store_true")
    _output_options(listing)
    events = commands.add_parser(
        "events", help="Explicitly record or inspect self-reported events."
    )
    event_commands = events.add_subparsers(dest="event_command", required=True)
    adding = event_commands.add_parser("add")
    adding.add_argument("--concept", required=True)
    adding.add_argument("--kind", choices=[kind.value for kind in EventKind], required=True)
    adding.add_argument("--idempotency-key", required=True)
    adding.add_argument("--occurred-at", help="ISO 8601 with timezone; defaults to recording time.")
    _output_options(adding)
    listing = event_commands.add_parser("list")
    listing.add_argument("--concept")
    _output_options(listing)
    progress_parser = commands.add_parser("progress", help="Replay fixed-item assessment evidence.")
    progress_parser.add_argument(
        "--as-of", help="Replay evidence recorded on/before this timezone-aware time."
    )
    _output_options(progress_parser)
    register_quiz(commands)
    migration = commands.add_parser(
        "migrate", help="Upgrade schema after making a new SQLite backup."
    )
    migration.add_argument("--backup", type=Path, required=True)
    _output_options(migration)
    exporting = commands.add_parser(
        "export", help="Export a consistent logical JSONL ledger snapshot."
    )
    exporting.add_argument("--output", type=Path, required=True)
    _output_options(exporting)
    importing = commands.add_parser(
        "import", help="Restore validated JSONL into a new database, never merge."
    )
    importing.add_argument("--input", type=Path, required=True)
    importing.add_argument("--vault", type=Path, required=True)
    _output_options(importing)
    return parser


def dispatch(args: argparse.Namespace) -> Any:
    if args.command == "doctor":
        scan = scan_vault(validate_vault(args.vault))
        return {
            "read_only": True,
            "markdown_files": len(scan.files),
            "skipped_symlinks": scan.skipped_symlinks,
        }
    if args.command == "index":
        return asdict(index_vault(args.vault, args.db))
    if args.command == "migrate":
        return migrate_database(args.db, args.backup)
    if args.command == "export":
        return export_ledger(args.db, args.output)
    if args.command == "import":
        return import_ledger(args.db, args.input, args.vault)
    if args.command == "quiz" and args.quiz_command in {"list", "show"}:
        return quiz_without_database(args)
    writable = (args.command == "events" and args.event_command == "add") or (
        args.command == "quiz" and args.quiz_command in {"start", "submit", "correct"}
    )
    with open_database(args.db, writable=writable) as connection:
        if args.command == "concepts":
            return list_concepts(
                connection, include_inactive=args.include_inactive, search=args.search
            )
        if args.command == "progress":
            return progress(connection, as_of=args.as_of)
        if args.command == "quiz":
            return dispatch_quiz(connection, args)
        if args.event_command == "list":
            return list_events(connection, args.concept)
        event, created = append_event(
            connection,
            EventRequest(
                args.concept, EventKind(args.kind), args.idempotency_key, args.occurred_at
            ),
        )
        event["source_snapshot"] = json.loads(event.pop("source_snapshot_json"))
        return {"created": created, "event": event}


def _safe_text(value: Any) -> str:
    # Notes may contain terminal escape sequences; plain output must not execute them.
    return "".join(char if char.isprintable() else f"\\u{ord(char):04x}" for char in str(value))


def _concept_line(concept: dict) -> str:
    source = f"{concept['path']}#{concept['anchor']}:{concept['line']}"
    active = not concept["retired_at"] and not concept["source_deleted_at"]
    state = concept["status"] if active else "inactive"
    return _safe_text(f"{concept['id']}  [{state}/candidate]  {concept['title']}  <- {source}")


def render_text(command: str, result: Any) -> str:
    if command == "concepts":
        return "\n".join(_concept_line(item) for item in result) or "No concept candidates."
    if command == "progress":
        lines = [
            f"{result['active_candidates']} active concept candidates",
            f"{result['awaiting_independent_assessment']} awaiting independent assessment",
            f"{result['delayed_recall_demonstrated']} with delayed fixed-item recall evidence",
            "0 verified mastered (fixed-item checks do not certify general mastery)",
            result["explanation"],
        ]
        lines.extend(
            _concept_line(item) + f"  learning_state={item['learning_state']}"
            for item in result["concepts"]
        )
        return "\n".join(lines)
    return json.dumps(result, ensure_ascii=True, indent=2)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = dispatch(args)
        text = (
            json.dumps(result, ensure_ascii=True, indent=2)
            if args.json
            else render_text(args.command, result)
        )
        print(text)
        return 0
    except StudyBuddyError as exc:
        print(f"studybuddy: {_safe_text(exc)}", file=sys.stderr)
    except (OSError, sqlite3.Error, RuntimeError):
        print(
            "studybuddy: Storage or filesystem operation failed; "
            "check access and SQLite FTS5 support.",
            file=sys.stderr,
        )
    return 1
