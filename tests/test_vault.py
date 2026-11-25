from pathlib import Path

import pytest

from studybuddy.errors import StudyBuddyError
from studybuddy.indexer import index_vault
from studybuddy.vault import MAX_NOTE_BYTES, read_note, scan_vault, validate_vault


@pytest.mark.parametrize(
    "relative",
    [
        "../secret.md",
        "/tmp/secret.md",
        "nested/../../secret.md",
        "nested/../note.md",
        "..\\secret.md",
        "note.md\x00",
        "./note.md",
        ".hidden/note.md",
        "nested//note.md",
        "",
    ],
)
def test_rejects_path_traversal_before_opening(vault: Path, relative: str) -> None:
    with pytest.raises(StudyBuddyError, match="inside"):
        read_note(vault, relative)


def test_skips_external_and_internal_symlinks(vault: Path, database: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("# Private", encoding="utf-8")
    (vault / "actual.md").write_text("# Public", encoding="utf-8")
    (vault / "external.md").symlink_to(outside / "secret.md")
    (vault / "external-dir").symlink_to(outside, target_is_directory=True)
    (vault / "internal.md").symlink_to(vault / "actual.md")
    assert scan_vault(vault).files == ("actual.md",)
    result = index_vault(vault, database)
    assert result.added == 1
    assert result.skipped_symlinks == 3
    with pytest.raises(StudyBuddyError, match="safely"):
        read_note(vault, "external-dir/secret.md")
    with pytest.raises(StudyBuddyError, match="safely"):
        read_note(vault, "external.md")


def test_hidden_folders_and_non_markdown_files_are_ignored(vault: Path) -> None:
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "config.md").write_text("hidden", encoding="utf-8")
    (vault / ".secret.md").write_text("hidden", encoding="utf-8")
    (vault / "image.png").write_bytes(b"not markdown")
    (vault / "UPPER.MD").write_text("# Seen", encoding="utf-8")
    assert scan_vault(vault).files == ("UPPER.MD",)


def test_oversized_note_is_rejected(vault: Path) -> None:
    (vault / "huge.md").write_bytes(b"x" * (MAX_NOTE_BYTES + 1))
    with pytest.raises(StudyBuddyError, match="2 MiB"):
        read_note(vault, "huge.md")


def test_missing_vault_and_file_as_vault_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(StudyBuddyError, match="missing"):
        validate_vault(tmp_path / "missing")
    note = tmp_path / "note.md"
    note.touch()
    with pytest.raises(StudyBuddyError, match="directory"):
        validate_vault(note)


def test_unreadable_walk_aborts_without_reconciliation(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_walk(root: Path, *, followlinks: bool, onerror: object) -> None:
        onerror(PermissionError("private filesystem detail"))

    monkeypatch.setattr("studybuddy.vault.os.walk", fail_walk)
    with pytest.raises(StudyBuddyError, match="no deletion reconciliation"):
        scan_vault(vault)


def test_vault_files_are_unchanged_after_index(indexed: tuple[Path, Path]) -> None:
    vault, database = indexed
    before = {
        p.relative_to(vault): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in vault.rglob("*")
        if p.is_file()
    }
    index_vault(vault, database)
    after = {
        p.relative_to(vault): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in vault.rglob("*")
        if p.is_file()
    }
    assert before == after
