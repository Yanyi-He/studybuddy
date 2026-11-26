import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from studybuddy.errors import StudyBuddyError


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def validate_key(value: str) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 200
        or not value.strip()
        or not value.isprintable()
    ):
        raise StudyBuddyError("Idempotency key must contain 1-200 printable characters.")


def validate_id(value: str, prefix: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(prefix + r"_[a-f0-9]{32}", value):
        raise StudyBuddyError(f"Use the full {prefix}_... identifier.")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_number(value: str) -> Any:
    raise ValueError("Non-finite JSON number")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite JSON number")
    return result


def strict_json(text: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_pairs,
            parse_constant=_invalid_number,
            parse_float=_finite_float,
        )
    except (ValueError, RecursionError) as exc:
        raise StudyBuddyError(
            "Invalid JSON; duplicate keys and non-finite numbers are not allowed."
        ) from exc


def read_json_file(path: Path) -> Any:
    with path.open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise StudyBuddyError("Answer JSON must not exceed 64 KiB.")
    try:
        return strict_json(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise StudyBuddyError("JSON input must be UTF-8.") from exc
