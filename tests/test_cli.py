import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from studybuddy.cli import main
from studybuddy.database import open_database
from studybuddy.errors import StudyBuddyError
from studybuddy.queries import list_concepts


def test_doctor_only_counts_files_without_reading_contents_or_creating_db(
    vault: Path, database: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    (vault / "bad.md").write_bytes(b"\xff private content")

    def forbidden_read(*args: object) -> None:
        pytest.fail("doctor must not read note contents")

    monkeypatch.setattr("studybuddy.indexer.read_note", forbidden_read)
    assert main(["--db", str(database), "doctor", "--vault", str(vault), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"read_only": True, "markdown_files": 1, "skipped_symlinks": 0}
    assert not database.exists()


def test_full_cli_flow(vault: Path, database: Path, capsys: pytest.CaptureFixture) -> None:
    (vault / "学习.md").write_text("# 幂等性\n", encoding="utf-8")
    prefix = ["--db", str(database)]
    assert main([*prefix, "index", "--vault", str(vault), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["added"] == 1
    assert main([*prefix, "concepts", "list", "--json"]) == 0
    concept = json.loads(capsys.readouterr().out)[0]
    assert concept["status"] == "seen"
    event_args = [
        *prefix,
        "events",
        "add",
        "--concept",
        concept["id"],
        "--kind",
        "ai_answer_copied",
        "--idempotency-key",
        "demo",
        "--json",
    ]
    assert main(event_args) == 0
    assert json.loads(capsys.readouterr().out)["created"]
    assert main(event_args) == 0
    assert not json.loads(capsys.readouterr().out)["created"]
    assert main([*prefix, "events", "list", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1
    assert main([*prefix, "progress", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["verified_mastered"] == 0
    assert main([*prefix, "concepts", "list"]) == 0
    assert "幂等性" in capsys.readouterr().out


def test_missing_database_is_an_actionable_error(
    database: Path, capsys: pytest.CaptureFixture
) -> None:
    assert main(["--db", str(database), "progress"]) == 1
    assert "index --vault PATH" in capsys.readouterr().err
    assert not database.exists()


def test_fts_search_is_literal_and_does_not_accept_query_syntax(indexed: tuple[Path, Path]) -> None:
    _, database = indexed
    with open_database(database) as connection:
        assert len(list_concepts(connection, search="TCP retries")) == 1
        assert len(list_concepts(connection, search="network")) == 2
        assert list_concepts(connection, search='" OR * ; DROP TABLE concepts; --') == []
        assert len(list_concepts(connection)) == 2
        with pytest.raises(StudyBuddyError, match="Search"):
            list_concepts(connection, search=" ")


def test_cli_sanitizes_terminal_control_sequences(
    vault: Path, database: Path, capsys: pytest.CaptureFixture
) -> None:
    (vault / "note.md").write_text("# Hello\x1b[31m\n", encoding="utf-8")
    from studybuddy.indexer import index_vault

    index_vault(vault, database)
    assert main(["--db", str(database), "concepts", "list"]) == 0
    output = capsys.readouterr().out
    assert "\x1b" not in output
    assert "\\u001b" in output


def test_runtime_works_offline(
    indexed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    vault, database = indexed

    def reject_network(*args: object, **kwargs: object) -> None:
        pytest.fail("No network access is allowed at runtime")

    monkeypatch.setattr("socket.socket", reject_network)
    monkeypatch.setattr("socket.create_connection", reject_network)
    assert main(["--db", str(database), "index", "--vault", str(vault)]) == 0
    capsys.readouterr()
    assert main(["--db", str(database), "progress"]) == 0
    capsys.readouterr()


def test_python_module_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "studybuddy", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "studybuddy 0.2.0"


def test_unknown_database_format_is_not_modified(tmp_path: Path) -> None:
    database = tmp_path / "other.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE personal (value TEXT)")
    before = database.read_bytes()
    with (
        pytest.raises(StudyBuddyError, match="another application"),
        open_database(database, create=True, writable=True),
    ):
        pass
    assert database.read_bytes() == before
