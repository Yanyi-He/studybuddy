"""Versioned original fixed items. Exact-field checks do not evaluate free-text reasoning."""

from importlib.resources import files
from typing import Any

from studybuddy.errors import StudyBuddyError
from studybuddy.validation import canonical_json, digest, strict_json

EVALUATOR_VERSION = "exact-fields-v1"


def catalog() -> list[dict]:
    return strict_json(
        files("studybuddy").joinpath("assessment_catalog.json").read_text(encoding="utf-8")
    )["items"]


def get_assessment(identifier: str) -> dict:
    for item in catalog():
        if item["id"] == identifier:
            return item
    raise StudyBuddyError("Unknown assessment ID; use 'quiz list'.")


def public_assessment(item: dict) -> dict:
    return {key: value for key, value in item.items() if key != "expected"}


def trusted_assessment(snapshot: str, sha256: str) -> dict:
    parsed = strict_json(snapshot)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("id"), str):
        raise StudyBuddyError("Invalid assessment snapshot.")
    known = get_assessment(parsed["id"])
    if digest(parsed) != sha256 or canonical_json(parsed) != canonical_json(known):
        raise StudyBuddyError("Unsupported or modified assessment/rubric snapshot.")
    return known


def evaluate(item: dict, answer: Any) -> dict:
    fields = set(item["questions"])
    if not isinstance(answer, dict) or set(answer) - {"explanation"} != fields:
        raise StudyBuddyError(
            "Answer must contain exactly the question fields, plus optional explanation."
        )
    if "explanation" in answer and (
        not isinstance(answer["explanation"], str) or len(answer["explanation"]) > 8000
    ):
        raise StudyBuddyError(
            "Optional explanation must be text of at most 8000 characters; it is not graded."
        )
    for name, question in item["questions"].items():
        if not isinstance(answer[name], str) or answer[name] not in question["choices"]:
            raise StudyBuddyError("Each answer must be one of that question's listed choice keys.")
    correct = {name: answer[name] == expected for name, expected in item["expected"].items()}
    return {
        "score": sum(correct.values()) / len(correct),
        "passed": int(all(correct.values())),
        "feedback_json": canonical_json({"correct_fields": correct, "explanation_graded": False}),
        "rubric_version": item["rubric_version"],
        "evaluator_version": EVALUATOR_VERSION,
    }
