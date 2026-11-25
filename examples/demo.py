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


if __name__ == "__main__":
    with TemporaryDirectory(prefix="studybuddy-demo-") as directory:
        demonstrate(Path(directory) / "demo.sqlite3")
