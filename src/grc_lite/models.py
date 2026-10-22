"""Data model for a gap assessment: criteria, evidence and findings."""

from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

CriterionId = Annotated[str, StringConstraints(pattern=r"^C-\d+$")]
EvidenceId = Annotated[str, StringConstraints(pattern=r"^E-\d+$")]
FindingId = Annotated[str, StringConstraints(pattern=r"^F-\d+$")]
RiskId = Annotated[str, StringConstraints(pattern=r"^K-\d+$")]
RequestId = Annotated[str, StringConstraints(pattern=r"^R-\d+$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Result(str, Enum):
    NOT_TESTED = "not tested"
    MEETS = "meets"
    GAP = "gap"
    CANT_TEST = "can't test"


class EvidenceType(str, Enum):
    SYSTEM = "system"
    DOCUMENT = "document"
    OBSERVATION = "observation"
    INTERVIEW = "interview"


class FindingStatus(str, Enum):
    CANDIDATE = "candidate"
    SELECTED = "selected"
    DROPPED = "dropped"


class Strength(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class Treatment(str, Enum):
    MITIGATE = "mitigate"
    ACCEPT = "accept"
    TRANSFER = "transfer"
    AVOID = "avoid"


class RiskStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    CLOSED = "closed"


class _Base(BaseModel):
    # forbid unknown keys so a typo in a YAML file is an error, not silently ignored
    model_config = ConfigDict(extra="forbid")


class Criterion(_Base):
    id: CriterionId
    source: Text  # any framework, policy or contract clause
    rule: Text
    evidence_needed: str = ""
    evidence: list[EvidenceId] = []
    result: Result = Result.NOT_TESTED


class Evidence(_Base):
    id: EvidenceId
    date: date
    source: Text
    type: EvidenceType
    shows: Text
    reliability: str = ""


# Fields a finding must have once it is selected for the report.
_SELECTED_REQUIRED = (
    "criteria",
    "condition",
    "consequence",
    "action",
    "owner",
    "due",
    "likelihood",
    "likelihood_reason",
    "impact",
    "impact_reason",
)


class Finding(_Base):
    id: FindingId
    title: Text
    status: FindingStatus
    strength: Strength
    strength_reason: Text
    # required only when status is selected
    criteria: list[CriterionId] = []
    condition: str = ""
    cause: str = ""
    consequence: str = ""
    action: str = ""
    owner: str = ""
    due: date | None = None
    likelihood: int | None = None
    likelihood_reason: str = ""
    impact: int | None = None
    impact_reason: str = ""
    control_ref: str = ""

    @model_validator(mode="after")
    def _selected_is_complete(self):
        if self.status is FindingStatus.SELECTED:
            missing = [f for f in _SELECTED_REQUIRED if not getattr(self, f)]
            if missing:
                raise ValueError(f"selected finding is missing: {', '.join(missing)}")
        return self


class Request(_Base):
    id: RequestId
    asked: date
    what: Text
    asked_who: Text
    received: date | None = None
    evidence: EvidenceId | None = None  # the evidence item the answer became
    notes: str = ""

    @model_validator(mode="after")
    def _received_after_asked(self):
        if self.received and self.received < self.asked:
            raise ValueError("received is before asked")
        return self

    @property
    def outstanding(self) -> bool:
        return self.received is None


class Risk(_Base):
    id: RiskId
    title: Text
    description: str = ""
    owner: Text
    likelihood: int
    likelihood_reason: Text
    impact: int
    impact_reason: Text
    treatment: Treatment
    status: RiskStatus = RiskStatus.OPEN
    findings: list[FindingId] = []
    criteria: list[CriterionId] = []


class Meta(_Base):
    name: str = "Untitled assessment"
    scale: int = 3  # risk scale: 3 (1-3) or 5 (1-5)

    @model_validator(mode="after")
    def _scale_is_supported(self):
        if self.scale not in RATING_BANDS:
            raise ValueError("scale must be 3 or 5")
        return self


# (minimum score, label), highest band first
RATING_BANDS = {
    3: [(7, "High"), (4, "Medium"), (1, "Low")],
    5: [(20, "Critical"), (13, "High"), (6, "Medium"), (1, "Low")],
}


def rating(likelihood: int, impact: int, scale: int = 3) -> str:
    """Rating = likelihood x impact, banded for the given scale."""
    score = likelihood * impact
    return next(label for floor, label in RATING_BANDS[scale] if score >= floor)
