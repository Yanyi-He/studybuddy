from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from studybuddy.errors import StudyBuddyError


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def normalize_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise StudyBuddyError("occurred_at must be an ISO 8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StudyBuddyError("occurred_at must include a timezone, such as Z or +08:00.")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds")


class EventKind(StrEnum):
    EXPOSURE = "exposure"
    AI_ANSWER_COPIED = "ai_answer_copied"
    ASSISTED_EXPLANATION = "assisted_explanation"
    RECALL_ATTEMPT = "recall_attempt"
    PRACTICE_ATTEMPT = "practice_attempt"
    TRANSFER_ATTEMPT = "transfer_attempt"


@dataclass(frozen=True)
class Heading:
    title: str
    anchor: str
    key: str
    line: int


@dataclass(frozen=True)
class WikiLink:
    target: str
    anchor: str
    alias: str
    line: int


@dataclass(frozen=True)
class ParsedNote:
    metadata_json: str
    headings: tuple[Heading, ...]
    wikilinks: tuple[WikiLink, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NoteSnapshot:
    path: str
    sha256: str
    mtime_ns: int
    parsed: ParsedNote | None


@dataclass
class IndexResult:
    added: int = 0
    updated: int = 0
    renamed: int = 0
    restored: int = 0
    unchanged: int = 0
    deleted: int = 0
    skipped_symlinks: int = 0
    warnings: list[dict[str, str]] = field(default_factory=list)
