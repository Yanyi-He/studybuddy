import argparse
import sqlite3
from pathlib import Path

from studybuddy.assessments import (
    ASSISTANCE,
    Submission,
    correct,
    public_session,
    read_attempts,
    start_session,
    submit,
)
from studybuddy.catalog import catalog, get_assessment, public_assessment
from studybuddy.validation import read_json_file, strict_json


def register_quiz(commands: argparse._SubParsersAction) -> None:
    quiz = commands.add_parser("quiz", help="Versioned offline fixed-item assessments.")
    actions = quiz.add_subparsers(dest="quiz_command", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--topic")
    showing = actions.add_parser("show")
    showing.add_argument("assessment")
    starting = actions.add_parser("start")
    starting.add_argument("--concept", required=True)
    starting.add_argument("--assessment", required=True)
    starting.add_argument("--idempotency-key", required=True)
    answering = actions.add_parser("submit")
    answering.add_argument("--session", required=True)
    answering.add_argument("--answer-file", type=Path, required=True)
    answering.add_argument("--assistance", choices=ASSISTANCE, required=True)
    answering.add_argument("--hints-used", type=int, default=0)
    answering.add_argument("--idempotency-key", required=True)
    history = actions.add_parser("history")
    history.add_argument("--concept")
    correction = actions.add_parser("correct")
    correction.add_argument("--attempt", required=True)
    correction.add_argument("--action", choices=["invalidate", "restore"], required=True)
    correction.add_argument("--reason", required=True)
    correction.add_argument("--idempotency-key", required=True)
    for parser in [listing, showing, starting, answering, history, correction]:
        parser.add_argument("--json", action="store_true")


def public_attempt(attempt: dict) -> dict:
    result = dict(attempt)
    for name in ["answer_json", "feedback_json", "source_snapshot_json"]:
        if name in result:
            result[name.removesuffix("_json")] = strict_json(result.pop(name))
    return result


def quiz_without_database(args: argparse.Namespace) -> list[dict] | dict:
    if args.quiz_command == "show":
        return public_assessment(get_assessment(args.assessment))
    return [
        public_assessment(item)
        for item in catalog()
        if not args.topic or item["topic"] == args.topic
    ]


def dispatch_quiz(db: sqlite3.Connection, args: argparse.Namespace) -> dict:
    if args.quiz_command == "start":
        session, created = start_session(db, args.concept, args.assessment, args.idempotency_key)
        return {"created": created, "session": session}
    if args.quiz_command == "submit":
        attempt, created = submit(
            db,
            Submission(
                args.session,
                read_json_file(args.answer_file),
                args.assistance,
                args.hints_used,
                args.idempotency_key,
            ),
        )
        return {"created": created, "attempt": public_attempt(attempt)}
    if args.quiz_command == "correct":
        correction, created = correct(
            db, args.attempt, args.action, args.reason, args.idempotency_key
        )
        return {"created": created, "correction": correction}
    where = " WHERE concept_id=?" if args.concept else ""
    sessions = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM assessment_sessions" + where + " ORDER BY issued_at,id",
            (args.concept,) if args.concept else (),
        )
    ]
    attempts = read_attempts(db, args.concept)
    ids = {attempt["id"] for attempt in attempts}
    return {
        "sessions": [public_session(session) for session in sessions],
        "attempts": [public_attempt(attempt) for attempt in attempts],
        "corrections": [
            dict(row)
            for row in db.execute("SELECT * FROM assessment_corrections ORDER BY sequence")
            if row["attempt_id"] in ids
        ],
    }
