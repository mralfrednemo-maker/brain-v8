"""Core types for the Thinker V8 Brain engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BrainError(Exception):
    """Fatal pipeline error — zero tolerance for silent failures.

    Raised when a critical component fails: LLM call, position extraction,
    argument tracking, synthesis. The pipeline must stop immediately.
    """
    def __init__(self, stage: str, message: str, detail: str = ""):
        self.stage = stage
        self.message = message
        self.detail = detail
        super().__init__(f"[{stage}] {message}")


class Outcome(Enum):
    """The three possible outcomes of a Brain deliberation."""
    DECIDE = "DECIDE"
    ESCALATE = "ESCALATE"
    NEED_MORE = "NEED_MORE"


class Confidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BlockerKind(Enum):
    EVIDENCE_GAP = "EVIDENCE_GAP"
    CONTRADICTION = "CONTRADICTION"
    UNRESOLVED_DISAGREEMENT = "UNRESOLVED_DISAGREEMENT"
    CONTESTED_POSITION = "CONTESTED_POSITION"


class BlockerStatus(Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"
    DROPPED = "DROPPED"


class ArgumentStatus(Enum):
    ADDRESSED = "ADDRESSED"
    MENTIONED = "MENTIONED"
    IGNORED = "IGNORED"


class AcceptanceStatus(Enum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_WARNINGS = "ACCEPTED_WITH_WARNINGS"


@dataclass
class ModelResponse:
    """Raw response from a single LLM call."""
    model: str
    ok: bool
    text: str
    elapsed_s: float
    error: Optional[str] = None


@dataclass
class EvidenceItem:
    """A single piece of verified evidence."""
    evidence_id: str
    topic: str
    fact: str
    url: str
    confidence: Confidence
    content_hash: str = ""
    score: float = 0.0


@dataclass
class Argument:
    """A distinct argument extracted from model output."""
    argument_id: str
    round_num: int
    model: str
    text: str
    status: ArgumentStatus = ArgumentStatus.IGNORED
    addressed_in_round: Optional[int] = None


@dataclass
class Position:
    """A model's position in a given round."""
    model: str
    round_num: int
    primary_option: str
    components: list[str] = field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    qualifier: str = ""
    kind: str = "single"  # "single" or "sequence"


@dataclass
class Blocker:
    """A tracked blocker (evidence gap, contradiction, disagreement)."""
    blocker_id: str
    kind: BlockerKind
    source: str
    detected_round: int
    status: BlockerStatus = BlockerStatus.OPEN
    status_history: list[dict] = field(default_factory=list)
    models_involved: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    detail: str = ""
    resolution_note: str = ""


@dataclass
class Contradiction:
    """A detected contradiction between evidence items."""
    contradiction_id: str
    evidence_ids: list[str]
    topic: str
    severity: str  # "HIGH" or "MEDIUM"
    status: str = "UNRESOLVED"


@dataclass
class SearchResult:
    """A single search result (URL + content)."""
    url: str
    title: str
    snippet: str
    full_content: Optional[str] = None


@dataclass
class Gate1Result:
    """Result of Gate 1 assessment."""
    passed: bool
    outcome: Outcome
    questions: list[str] = field(default_factory=list)
    reasoning: str = ""
    search_recommended: bool = True  # Default to YES (conservative)


@dataclass
class Gate2Assessment:
    """Result of Gate 2 trust assessment."""
    outcome: Outcome
    convergence_ok: bool
    evidence_credible: bool
    dissent_addressed: bool
    enough_data: bool
    report_honest: bool
    reasoning: str = ""


@dataclass
class RoundResult:
    """Result of a single deliberation round."""
    round_num: int
    responses: dict[str, ModelResponse] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)

    @property
    def responded(self) -> list[str]:
        return [m for m, r in self.responses.items() if r.ok]

    @property
    def texts(self) -> dict[str, str]:
        return {m: r.text for m, r in self.responses.items() if r.ok}


@dataclass
class BrainResult:
    """Final result of a complete Brain deliberation."""
    outcome: Outcome
    proof: dict
    report: str
    gate1: Gate1Result
    gate2: Optional[Gate2Assessment] = None
