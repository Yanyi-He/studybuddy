"""Reproducible offline demo. Uses synthetic notes and a temporary database."""

import json
import shlex
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

VAULT = Path(__file__).resolve().parent / "demo-vault"


def run(database: Path, *arguments: str, json_output: bool = False, show: bool = True) -> Any:
    command = [sys.executable, "-m", "studybuddy", "--db", str(database), *arguments]
    if json_output:
        command.append("--json")
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    if show:
        display = [part.replace(str(VAULT), "examples/demo-vault") for part in arguments]
        print(f"$ studybuddy --db <temporary-db> {shlex.join(display)}")
        print(result.stdout.rstrip())
        print()
    return json.loads(result.stdout) if json_output else result.stdout


def demonstrate(database: Path) -> None:
    run(database, "doctor", "--vault", str(VAULT))
    run(database, "index", "--vault", str(VAULT))
    run(database, "index", "--vault", str(VAULT))
    run(database, "concepts", "list")
    concepts = run(database, "concepts", "list", json_output=True, show=False)
    identifier = next(item["id"] for item in concepts if item["title"] == "Copied AI explanation")
    arguments = (
        "events",
        "add",
        "--concept",
        identifier,
        "--kind",
        "ai_answer_copied",
        "--idempotency-key",
        "demo-copied-answer",
        "--occurred-at",
        "2026-01-01T12:00:00Z",
    )
    first = run(database, *arguments, json_output=True, show=False)
    repeated = run(database, *arguments, json_output=True, show=False)
    print(
        f"Copied AI answer: created={first['created']}; repeated key: created={repeated['created']}"
    )
    print()
    run(database, "progress")
    result = run(database, "progress", json_output=True, show=False)
    if result["verified_mastered"] != 0 or repeated["created"]:
        raise RuntimeError("Demo invariants failed")
    demonstrate_assessments(database, concepts)


def demonstrate_assessments(database: Path, concepts: list[dict]) -> None:
    identifier = next(item["id"] for item in concepts if item["title"] == "Idempotency")
    session = run(
        database,
        "quiz",
        "start",
        "--concept",
        identifier,
        "--assessment",
        "retry-recall",
        "--idempotency-key",
        "demo-session",
        json_output=True,
        show=False,
    )["session"]
    answer = str(Path(__file__).resolve().parent / "answers" / "retry-recall.json")
    attempt = run(
        database,
        "quiz",
        "submit",
        "--session",
        session["id"],
        "--answer-file",
        answer,
        "--assistance",
        "independent",
        "--idempotency-key",
        "demo-submission",
        json_output=True,
        show=False,
    )["attempt"]
    snapshot = run(database, "progress", json_output=True, show=False)
    state = next(
        item["learning_state"] for item in snapshot["concepts"] if item["id"] == identifier
    )
    assert state == "assessed_once" and attempt["score"] == 1.0
    print(
        f"Synthetic fixed-item answer: score={attempt['score']}; state={state} (no delayed retest)"
    )
    for action, expected in [("invalidate", "exposed"), ("restore", "assessed_once")]:
        run(
            database,
            "quiz",
            "correct",
            "--attempt",
            attempt["id"],
            "--action",
            action,
            "--reason",
            "Synthetic demo correction",
            "--idempotency-key",
            "demo-" + action,
            json_output=True,
            show=False,
        )
        snapshot = run(database, "progress", json_output=True, show=False)
        state = next(
            item["learning_state"] for item in snapshot["concepts"] if item["id"] == identifier
        )
        assert state == expected
        print(f"Append-only correction: {action} -> {state}")
    output, restored = database.with_suffix(".ledger.jsonl"), database.with_name("restored.sqlite3")
    run(database, "export", "--output", str(output), json_output=True, show=False)
    run(
        restored,
        "import",
        "--input",
        str(output),
        "--vault",
        str(VAULT),
        json_output=True,
        show=False,
    )
    assert snapshot == run(restored, "progress", json_output=True, show=False)
    assert run(database, "events", "list", json_output=True, show=False) == run(
        restored, "events", "list", json_output=True, show=False
    )
    print("JSONL round trip: projections and event history preserved")
    print()
    run(database, "progress")


if __name__ == "__main__":
    with TemporaryDirectory(prefix="studybuddy-demo-") as directory:
        demonstrate(Path(directory) / "demo.sqlite3")
