"""Replayable product heuristics for fixed-item evidence; not a certification of mastery."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from studybuddy.models import normalize_timestamp

PROJECTOR_VERSION = "fixed-evidence-v1"
MIN_RECALL_DELAY = timedelta(hours=24)
STATES = (
    "exposed",
    "needs_review",
    "answered_with_help",
    "assessed_once",
    "recalled_unassisted",
    "applied",
    "transferred",
)


@dataclass
class _Projection:
    state: str = "exposed"
    recall_at: str | None = None
    delayed_at: str | None = None
    applied_at: str | None = None
    applied_context: str | None = None
    support: list[str] = field(default_factory=list)

    def apply(self, attempt: dict) -> None:
        if not attempt["passed"]:
            self.state = "needs_review"
            self.recall_at = self.delayed_at = self.applied_at = self.applied_context = None
            self.support.clear()
            return
        self.support.append(attempt["id"])
        if attempt["assistance"] != "independent" or attempt["hints_used"]:
            if STATES.index(self.state) < STATES.index("answered_with_help"):
                self.state = "answered_with_help"
            return
        if STATES.index(self.state) < STATES.index("assessed_once"):
            self.state = "assessed_once"
        self._independent(attempt)

    def _independent(self, attempt: dict) -> None:
        if attempt["kind"] == "recall":
            if self.recall_at is None:
                self.recall_at = attempt["submitted_at"]
            elif (
                datetime.fromisoformat(attempt["issued_at"])
                - datetime.fromisoformat(self.recall_at)
                >= MIN_RECALL_DELAY
            ):
                self.delayed_at = self.delayed_at or attempt["submitted_at"]
                if STATES.index(self.state) < STATES.index("recalled_unassisted"):
                    self.state = "recalled_unassisted"
        elif (
            attempt["kind"] == "application"
            and self.delayed_at
            and attempt["issued_at"] >= self.delayed_at
        ):
            self.applied_at, self.applied_context = attempt["submitted_at"], attempt["context"]
            if self.state != "transferred":
                self.state = "applied"
        elif (
            attempt["kind"] == "transfer"
            and self.applied_at
            and attempt["issued_at"] >= self.applied_at
            and attempt["context"] != self.applied_context
        ):
            self.state = "transferred"


def project(attempts: list[dict], corrections: list[dict], *, as_of: str | None = None) -> dict:
    cutoff = normalize_timestamp(as_of) if as_of is not None else None
    visible = [a for a in attempts if cutoff is None or a["recorded_at"] <= cutoff]
    identifiers = {a["id"] for a in visible}
    invalidated: dict[str, bool] = {}
    for correction in sorted(corrections, key=lambda row: row["sequence"]):
        if correction["attempt_id"] in identifiers and (
            cutoff is None or correction["recorded_at"] <= cutoff
        ):
            invalidated[correction["attempt_id"]] = correction["action"] == "invalidate"
    active = [a for a in visible if not invalidated.get(a["id"], False)]
    projection = _Projection()
    for attempt in sorted(active, key=lambda row: (row["submitted_at"], row["id"])):
        projection.apply(attempt)
    return {
        "learning_state": projection.state,
        "projector_version": PROJECTOR_VERSION,
        "minimum_recall_delay_hours": 24,
        "independence_source": "learner_declaration",
        "assessment_topic": active[0]["topic"] if active else None,
        "assessment_count": len(active),
        "last_assessed_at": max((a["submitted_at"] for a in active), default=None),
        "supporting_attempt_ids": projection.support,
        "invalidated_attempt_ids": sorted(
            identifier for identifier, invalid in invalidated.items() if invalid
        ),
        "as_of": cutoff,
    }
