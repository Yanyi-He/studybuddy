"""Read-only vault access. Note/link text is data and is never executed."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from studybuddy.errors import StudyBuddyError

MAX_NOTE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class VaultScan:
    files: tuple[str, ...]
    skipped_symlinks: int


def validate_vault(value: Path) -> Path:
    try:
        root = value.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise StudyBuddyError("Vault must be an existing directory.")
        return root
    except (OSError, RuntimeError) as exc:
        raise StudyBuddyError("Vault is missing or cannot be accessed.") from exc


def validate_database_location(database: Path, vault: Path) -> None:
    if database.expanduser().resolve().is_relative_to(vault):
        raise StudyBuddyError("Database must be outside the read-only vault.")


def _raise_walk_error(error: OSError) -> None:
    raise StudyBuddyError("Vault scan failed; no deletion reconciliation was performed.") from error


def scan_vault(root: Path) -> VaultScan:
    files: list[str] = []
    skipped = 0
    for directory, names, filenames in os.walk(root, followlinks=False, onerror=_raise_walk_error):
        parent = Path(directory)
        kept = []
        for name in sorted(names):
            candidate = parent / name
            if candidate.is_symlink():
                skipped += 1
            elif not name.startswith("."):
                kept.append(name)
        names[:] = kept
        for name in sorted(filenames):
            candidate = parent / name
            if candidate.is_symlink():
                skipped += 1
            elif not name.startswith(".") and candidate.suffix.lower() == ".md":
                files.append(candidate.relative_to(root).as_posix())
    return VaultScan(tuple(sorted(files)), skipped)


def _validated_parts(relative: str) -> tuple[str, ...]:
    candidate = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or "\x00" in relative
        or candidate.is_absolute()
        or any(part in {"..", "."} or part.startswith(".") for part in relative.split("/"))
        or any(not part for part in relative.split("/"))
    ):
        raise StudyBuddyError("Note path must stay inside the configured vault.")
    return candidate.parts


def _open_relative(root: Path, parts: tuple[str, ...]) -> int:
    # Open every component relative to a directory descriptor. Resolving a path and
    # opening it later would allow a symlink replacement between those operations.
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)


def read_note(root: Path, relative: str) -> tuple[bytes, int]:
    parts = _validated_parts(relative)
    try:
        descriptor = _open_relative(root, parts)
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_NOTE_BYTES:
                raise StudyBuddyError("Notes must be regular files no larger than 2 MiB.")
            data = stream.read(MAX_NOTE_BYTES + 1)
            after = os.fstat(stream.fileno())
        if len(data) > MAX_NOTE_BYTES or (before.st_mtime_ns, before.st_size) != (
            after.st_mtime_ns,
            after.st_size,
        ):
            raise StudyBuddyError("Note changed during reading or exceeds 2 MiB; retry indexing.")
        return data, after.st_mtime_ns
    except OSError as exc:
        raise StudyBuddyError("A note cannot be read safely; indexing was not committed.") from exc
