import json
from pathlib import Path

import pytest

from studybuddy.catalog import get_assessment
from studybuddy.cli import main
from tests.helpers import concept_id


def test_catalog_commands_do_not_require_or_create_database(
    database: Path, capsys: pytest.CaptureFixture
) -> None:
    assert main(["--db", str(database), "quiz", "list", "--json"]) == 0
    items = json.loads(capsys.readouterr().out)
    assert len(items) == 9 and all("expected" not in item for item in items)
    assert main(["--db", str(database), "quiz", "show", "retry-recall", "--json"]) == 0
    assert "expected" not in json.loads(capsys.readouterr().out)
    assert not database.exists()


def test_quiz_corrections_export_import_cli_flow_is_offline(
    indexed: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault, database = indexed
    identifier = concept_id(database)

    def reject_network(*args: object, **kwargs: object) -> None:
        pytest.fail("Runtime must remain offline")

    monkeypatch.setattr("socket.socket", reject_network)
    monkeypatch.setattr("socket.create_connection", reject_network)
    prefix = ["--db", str(database)]
    assert (
        main(
            [
                *prefix,
                "quiz",
                "start",
                "--concept",
                identifier,
                "--assessment",
                "retry-recall",
                "--idempotency-key",
                "start",
                "--json",
            ]
        )
        == 0
    )
    session = json.loads(capsys.readouterr().out)["session"]
    assert "expected" not in session["assessment"]
    answer = tmp_path / "answer.json"
    answer.write_text(json.dumps(get_assessment("retry-recall")["expected"]))
    arguments = [
        *prefix,
        "quiz",
        "submit",
        "--session",
        session["id"],
        "--answer-file",
        str(answer),
        "--assistance",
        "independent",
        "--idempotency-key",
        "submit",
        "--json",
    ]
    assert main(arguments) == 0
    attempt = json.loads(capsys.readouterr().out)["attempt"]
    assert attempt["passed"] == 1 and attempt["score"] == 1
    assert main(arguments) == 0
    assert not json.loads(capsys.readouterr().out)["created"]
    assert main([*prefix, "progress", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["awaiting_independent_assessment"] == 1
    assert (
        main(
            [
                *prefix,
                "quiz",
                "correct",
                "--attempt",
                attempt["id"],
                "--action",
                "invalidate",
                "--reason",
                "Used external help",
                "--idempotency-key",
                "correction",
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main([*prefix, "quiz", "history", "--concept", identifier, "--json"]) == 0
    history = json.loads(capsys.readouterr().out)
    assert len(history["attempts"]) == len(history["corrections"]) == 1
    output = tmp_path / "learning.ledger.jsonl"
    assert main([*prefix, "export", "--output", str(output), "--json"]) == 0
    capsys.readouterr()
    target = tmp_path / "restored.sqlite3"
    assert (
        main(
            ["--db", str(target), "import", "--input", str(output), "--vault", str(vault), "--json"]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["--db", str(target), "progress"]) == 0
    assert "learning_state=exposed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "raw",
    [
        '{"timeout":"unknown","timeout":"absent","identity":"stable"}',
        '{"mastered":true}',
        "x" * 65537,
    ],
)
def test_cli_rejects_invalid_answer_files_without_tracebacks(
    indexed: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture, raw: str
) -> None:
    _, database = indexed
    prefix = ["--db", str(database)]
    assert (
        main(
            [
                *prefix,
                "quiz",
                "start",
                "--concept",
                concept_id(database),
                "--assessment",
                "retry-recall",
                "--idempotency-key",
                "s",
                "--json",
            ]
        )
        == 0
    )
    identifier = json.loads(capsys.readouterr().out)["session"]["id"]
    answer = tmp_path / "answer.json"
    answer.write_text(raw)
    assert (
        main(
            [
                *prefix,
                "quiz",
                "submit",
                "--session",
                identifier,
                "--answer-file",
                str(answer),
                "--assistance",
                "independent",
                "--idempotency-key",
                "a",
            ]
        )
        == 1
    )
    assert "Traceback" not in capsys.readouterr().err


def test_migrate_cli_creates_backup(
    vault: Path, database: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    from tests.test_migrations import create_v1

    create_v1(database, vault)
    backup = tmp_path / "v1.sqlite3"
    assert main(["--db", str(database), "migrate", "--backup", str(backup), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["migrated"]
    assert backup.exists()
