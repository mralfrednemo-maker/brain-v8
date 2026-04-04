"""Core types for the Thinker V8 Brain engine."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


def extract_json(text: str) -> dict:
    """Extract JSON object from LLM response text.

    Handles: raw JSON, code-fenced JSON, JSON with trailing commentary.
    Raises json.JSONDecodeError if no valid JSON object found.
    """
    # Strip code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])
    cleaned = cleaned.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find first { and match to closing }
    start = cleaned.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", cleaned, 0)

    depth = 0
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start:i + 1])

    raise json.JSONDecodeError("Unterminated JSON object", cleaned, start)


class BrainError(Exception):
    """Fatal pipeline error — zero tolerance for silent failures.

    Raised when a critical component fails: LLM call, position extraction,
    argument tracking, synthesis. The pipeline must stop immediately.
    """
    def __init__(
        self,
        stage: str,
        message: str,
        detail: str = "",
        error_class: str = "FATAL_INTEGRITY",
    ):
        self.stage = stage
        self.message = message
        self.detail = detail
        self.error_class = error_class
        super().__init__(f"[{stage}] {message}")


class Outcome(Enum):
    """Top-level outcomes of a Brain deliberation (DoD v3.0 Section 1)."""
    DECIDE = "DECIDE"
    ESCALATE = "ESCALATE"
    NO_CONSENSUS = "NO_CONSENSUS"
    ANALYSIS = "ANALYSIS"
    ERROR = "ERROR"
    NEED_MORE = "NEED_MORE"  # PreflightAssessment only


class Confidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BlockerKind(Enum):
    EVIDENCE_GAP = "EVIDENCE_GAP"
    CONTRADICTION = "CONTRADICTION"
    UNRESOLVED_DISAGREEMENT = "UNRESOLVED_DISAGREEMENT"
    CONTESTED_POSITION = "CONTESTED_POSITION"
    COVERAGE_GAP = "COVERAGE_GAP"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"


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


class Modality(Enum):
    DECIDE = "DECIDE"
    ANALYSIS = "ANALYSIS"


class Answerability(Enum):
    ANSWERABLE = "ANSWERABLE"
    NEED_MORE = "NEED_MORE"
    INVALID_FORM = "INVALID_FORM"


class SearchScope(Enum):
    NONE = "NONE"
    TARGETED = "TARGETED"
    BROAD = "BROAD"


class PremiseFlagRouting(Enum):
    REQUESTER_FIXABLE = "REQUESTER_FIXABLE"
    MANAGEABLE_UNKNOWN = "MANAGEABLE_UNKNOWN"
    FRAMING_DEFECT = "FRAMING_DEFECT"
    FATAL_PREMISE = "FATAL_PREMISE"


class StakesClass(Enum):
    LOW = "LOW"
    STANDARD = "STANDARD"
    HIGH = "HIGH"


class QuestionClass(Enum):
    TRIVIAL = "TRIVIAL"
    WELL_ESTABLISHED = "WELL_ESTABLISHED"
    OPEN = "OPEN"
    AMBIGUOUS = "AMBIGUOUS"


class EffortTier(Enum):
    SHORT_CIRCUIT = "SHORT_CIRCUIT"
    STANDARD = "STANDARD"
    ELEVATED = "ELEVATED"


class PremiseFlagSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class PremiseFlagType(Enum):
    INTERNAL_CONTRADICTION = "INTERNAL_CONTRADICTION"
    UNSUPPORTED_ASSUMPTION = "UNSUPPORTED_ASSUMPTION"
    AMBIGUITY = "AMBIGUITY"
    IMPOSSIBLE_REQUEST = "IMPOSSIBLE_REQUEST"
    FRAMING_DEFECT = "FRAMING_DEFECT"


class CoverageObligation(Enum):
    CONTRARIAN = "CONTRARIAN"
    MECHANISM_ANALYSIS = "MECHANISM_ANALYSIS"
    OPERATIONAL_RISK = "OPERATIONAL_RISK"
    OBJECTIVE_REFRAMING = "OBJECTIVE_REFRAMING"


class TimeHorizon(Enum):
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"


class FrameType(Enum):
    INVERSION = "INVERSION"
    OBJECTIVE_REWRITE = "OBJECTIVE_REWRITE"
    PREMISE_CHALLENGE = "PREMISE_CHALLENGE"
    CROSS_DOMAIN_ANALOGY = "CROSS_DOMAIN_ANALOGY"
    OPPOSITE_STANCE = "OPPOSITE_STANCE"
    REMOVE_PROBLEM = "REMOVE_PROBLEM"


class FrameSurvivalStatus(Enum):
    ACTIVE = "ACTIVE"
    CONTESTED = "CONTESTED"
    DROPPED = "DROPPED"
    ADOPTED = "ADOPTED"
    REBUTTED = "REBUTTED"
    # ANALYSIS mode statuses
    EXPLORED = "EXPLORED"
    NOTED = "NOTED"
    UNEXPLORED = "UNEXPLORED"


class ResolutionStatus(Enum):
    ORIGINAL = "ORIGINAL"
    REFINED = "REFINED"
    SUPERSEDED = "SUPERSEDED"


class DetectionMode(Enum):
    NUMERIC = "NUMERIC"
    SEMANTIC = "SEMANTIC"


class ContradictionSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ContradictionStatus(Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    NON_MATERIAL = "NON_MATERIAL"


class EvidenceSupportStatus(Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"


class AnalogyTestStatus(Enum):
    UNTESTED = "UNTESTED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"


class QueryProvenance(Enum):
    MODEL_CLAIM = "model_claim"
    PREMISE_DEFECT = "premise_defect"
    FRAME_TEST = "frame_test"
    EVIDENCE_GAP = "evidence_gap"
    UNGROUNDED_STAT = "ungrounded_stat"


class QueryStatus(Enum):
    SUCCESS = "SUCCESS"
    ZERO_RESULT = "ZERO_RESULT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class DispositionTargetType(Enum):
    BLOCKER = "BLOCKER"
    FRAME = "FRAME"
    CLAIM = "CLAIM"
    CONTRADICTION = "CONTRADICTION"
    ARGUMENT = "ARGUMENT"  # DOD §11.3: open material arguments need dispositions


class ErrorClass(Enum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    FATAL_INTEGRITY = "FATAL_INTEGRITY"


class AssumptionVerifiability(Enum):
    # DOD §4.2: VERIFIABLE | UNVERIFIABLE | FALSE | UNKNOWN
    VERIFIABLE = "VERIFIABLE"
    UNVERIFIABLE = "UNVERIFIABLE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


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
    topic_cluster: str = ""
    authority_tier: str = "STANDARD"  # STANDARD, HIGH, AUTHORITATIVE
    is_active: bool = True
    is_archived: bool = False
    referenced_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "topic": self.topic,
            "fact": self.fact,
            "source_url": self.url,
            "confidence": self.confidence.value,
            "content_hash": self.content_hash,
            "score": self.score,
            "topic_cluster": self.topic_cluster,
            "authority_tier": self.authority_tier,
            "is_active": self.is_active,
            "is_archived": self.is_archived,
            "referenced_by": self.referenced_by,
        }


@dataclass
class Argument:
    """A distinct argument extracted from model output."""
    argument_id: str
    round_num: int
    model: str
    text: str
    status: ArgumentStatus = ArgumentStatus.IGNORED
    addressed_in_round: Optional[int] = None
    resolution_status: ResolutionStatus = ResolutionStatus.ORIGINAL
    superseded_by: Optional[str] = None
    dimension_id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    open: bool = True
    blocker_link_ids: list[str] = field(default_factory=list)  # DOD §11.1

    def to_dict(self) -> dict:
        return {
            "argument_id": self.argument_id,
            "round_origin": self.round_num,
            "model_id": self.model,
            "text": self.text,
            "status": self.status.value,
            "addressed_in_round": self.addressed_in_round,
            "resolution_status": self.resolution_status.value,
            "superseded_by": self.superseded_by,
            "dimension_id": self.dimension_id,
            "blocker_link_ids": self.blocker_link_ids,
            "evidence_refs": self.evidence_refs,
            "open": self.open,
        }


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
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    status_history: list[dict] = field(default_factory=list)
    models_involved: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    detail: str = ""
    resolution_note: str = ""

    def to_dict(self) -> dict:
        serialized_history = []
        for entry in self.status_history:
            status = entry.get("status")
            serialized_history.append({
                **entry,
                "status": "DEFERRED" if status == "DROPPED" else status,
            })
        return {
            "blocker_id": self.blocker_id,
            "type": self.kind.value,
            "source_dimension": self.source,
            "detected_round": self.detected_round,
            "status": "DEFERRED" if self.status.value == "DROPPED" else self.status.value,
            "severity": self.severity,
            "status_history": serialized_history,
            "models_involved": self.models_involved,
            "linked_ids": self.evidence_ids,
            "detail": self.detail,
            "resolution_summary": self.resolution_note,
        }


@dataclass
class Contradiction:
    """A detected contradiction between evidence items."""
    ctr_id: str
    evidence_ids: list[str]
    topic: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    status: str = "OPEN"  # OPEN, RESOLVED, NON_MATERIAL
    detection_mode: str = "NUMERIC"  # NUMERIC, SEMANTIC
    justification: str = ""
    linked_claim_ids: list[str] = field(default_factory=list)
    # DOD §12.1 unified schema fields
    evidence_ref_a: str = ""
    evidence_ref_b: str = ""
    same_entity: bool = False
    same_timeframe: bool = False

    @property
    def contradiction_id(self) -> str:
        """Backward-compatible alias for older callers."""
        return self.ctr_id

    @contradiction_id.setter
    def contradiction_id(self, value: str) -> None:
        self.ctr_id = value

    def to_dict(self) -> dict:
        return {
            "ctr_id": self.ctr_id,
            "detection_mode": self.detection_mode,
            "evidence_ref_a": self.evidence_ref_a,
            "evidence_ref_b": self.evidence_ref_b,
            "same_entity": self.same_entity,
            "same_timeframe": self.same_timeframe,
            "topic": self.topic,
            "severity": self.severity,
            "status": self.status,
            "justification": self.justification,
            "linked_claim_ids": self.linked_claim_ids,
        }


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
    search_reasoning: str = ""


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
    modality: Optional[str] = None  # DECIDE or ANALYSIS
    rule_trace: list[dict] = field(default_factory=list)


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
    gate1: Optional[Gate1Result] = None
    preflight: Optional["PreflightResult"] = None
    gate2: Optional[Gate2Assessment] = None
    dimensions: Optional["DimensionSeedResult"] = None
    perspective_cards: Optional[list["PerspectiveCard"]] = None
    divergence: Optional["DivergenceResult"] = None
    stability: Optional["StabilityResult"] = None
    error_class: Optional[ErrorClass] = None


# --- V9 New Dataclasses ---


@dataclass
class PremiseFlag:
    """A premise defect detected by PreflightAssessment."""
    flag_id: str
    flag_type: PremiseFlagType
    severity: PremiseFlagSeverity
    summary: str
    routing: PremiseFlagRouting = PremiseFlagRouting.MANAGEABLE_UNKNOWN
    blocking: bool = False
    resolved: bool = False
    resolved_stage: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "flag_id": self.flag_id,
            "flag_type": self.flag_type.value,
            "severity": self.severity.value,
            "summary": self.summary,
            "routing": self.routing.value,
            "blocking": self.blocking,
            "resolved": self.resolved,
            "resolved_stage": self.resolved_stage,
        }


@dataclass
class HiddenContextGap:
    """A hidden context gap detected by PreflightAssessment."""
    gap_id: str
    description: str
    impact_if_unresolved: str
    material: bool = False
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "gap_id": self.gap_id,
            "description": self.description,
            "impact_if_unresolved": self.impact_if_unresolved,
            "material": self.material,
            "resolved": self.resolved,
        }


@dataclass
class CriticalAssumption:
    """A critical assumption surfaced by PreflightAssessment."""
    assumption_id: str
    text: str
    verifiability: AssumptionVerifiability = AssumptionVerifiability.UNKNOWN
    material: bool = True
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "assumption_id": self.assumption_id,
            "text": self.text,
            "verifiability": self.verifiability.value,
            "material": self.material,
            "resolved": self.resolved,
        }


@dataclass
class PreflightResult:
    """Result of PreflightAssessment (DoD v3.0 Section 4)."""
    executed: bool = True
    parse_ok: bool = True
    answerability: Answerability = Answerability.ANSWERABLE
    question_class: QuestionClass = QuestionClass.OPEN
    stakes_class: StakesClass = StakesClass.STANDARD
    effort_tier: EffortTier = EffortTier.STANDARD
    modality: Modality = Modality.DECIDE
    search_scope: SearchScope = SearchScope.TARGETED
    exploration_required: bool = False
    short_circuit_allowed: bool = False
    fatal_premise: bool = False
    follow_up_questions: list[str] = field(default_factory=list)
    premise_flags: list[PremiseFlag] = field(default_factory=list)
    hidden_context_gaps: list[HiddenContextGap] = field(default_factory=list)
    critical_assumptions: list[CriticalAssumption] = field(default_factory=list)
    reasoning: str = ""

    @property
    def has_critical_flags(self) -> bool:
        return any(f.severity == PremiseFlagSeverity.CRITICAL and not f.resolved
                   for f in self.premise_flags)

    @property
    def unresolved_critical_flags(self) -> list[PremiseFlag]:
        return [f for f in self.premise_flags
                if f.severity == PremiseFlagSeverity.CRITICAL and not f.resolved]

    @property
    def has_material_unresolved_gaps(self) -> bool:
        return any(g.material and not g.resolved for g in self.hidden_context_gaps)

    @property
    def has_fatal_assumptions(self) -> bool:
        return any(a.verifiability in (AssumptionVerifiability.UNVERIFIABLE,
                                        AssumptionVerifiability.FALSE)
                   and a.material and not a.resolved
                   for a in self.critical_assumptions)

    def to_dict(self) -> dict:
        return {
            "executed": self.executed,
            "parse_ok": self.parse_ok,
            "answerability": self.answerability.value,
            "question_class": self.question_class.value,
            "stakes_class": self.stakes_class.value,
            "effort_tier": self.effort_tier.value,
            "modality": self.modality.value,
            "search_scope": self.search_scope.value,
            "exploration_required": self.exploration_required,
            "short_circuit_allowed": self.short_circuit_allowed,
            "fatal_premise": self.fatal_premise,
            "follow_up_questions": self.follow_up_questions,
            "premise_flags": [f.to_dict() for f in self.premise_flags],
            "hidden_context_gaps": [g.to_dict() for g in self.hidden_context_gaps],
            "critical_assumptions": [a.to_dict() for a in self.critical_assumptions],
            "reasoning": self.reasoning,
        }


@dataclass
class DimensionItem:
    """A single exploration dimension from the Dimension Seeder."""
    dimension_id: str
    name: str
    mandatory: bool = True
    coverage_status: str = "ZERO"  # ZERO, PARTIAL, SATISFIED
    argument_count: int = 0
    justified_irrelevance: bool = False
    irrelevance_explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "dimension_id": self.dimension_id,
            "name": self.name,
            "mandatory": self.mandatory,
            "coverage_status": self.coverage_status,
            "argument_count": self.argument_count,
            "justified_irrelevance": self.justified_irrelevance,
            "irrelevance_explanation": self.irrelevance_explanation,  # DOD §6.1
        }


@dataclass
class DimensionSeedResult:
    """Result of the Dimension Seeder (DoD v3.0 Section 6)."""
    seeded: bool = True
    parse_ok: bool = True
    items: list[DimensionItem] = field(default_factory=list)
    dimension_count: int = 0
    dimension_coverage_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "seeded": self.seeded,
            "parse_ok": self.parse_ok,
            "items": [d.to_dict() for d in self.items],
            "dimension_count": self.dimension_count,
            "dimension_coverage_score": self.dimension_coverage_score,
        }


@dataclass
class PerspectiveCard:
    """Structured R1 output for a single model (DoD v3.0 Section 7).

    field_provenance tracks per-field extraction method:
    - "native": field extracted directly from model's R1 output via regex
    - "inferred:haiku": field inferred by Haiku from model's R1 output
    - "inferred:sonnet": field inferred by Sonnet (fallback) from model's R1 output
    """
    model_id: str
    primary_frame: str = ""
    hidden_assumption_attacked: str = ""
    stakeholder_lens: str = ""
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM
    failure_mode: str = ""
    coverage_obligation: CoverageObligation = CoverageObligation.MECHANISM_ANALYSIS
    dimensions_addressed: list[str] = field(default_factory=list)
    field_provenance: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "primary_frame": self.primary_frame,
            "hidden_assumption_attacked": self.hidden_assumption_attacked,
            "stakeholder_lens": self.stakeholder_lens,
            "time_horizon": self.time_horizon.value,
            "failure_mode": self.failure_mode,
            "coverage_obligation": self.coverage_obligation.value,
            "dimensions_addressed": self.dimensions_addressed,
            "field_provenance": self.field_provenance,
        }


@dataclass
class FrameInfo:
    """A material alternative frame tracked by the Divergent Framing system."""
    frame_id: str
    text: str
    origin_round: int = 1
    origin_model: str = ""
    frame_type: FrameType = FrameType.INVERSION
    material_to_outcome: bool = True
    survival_status: FrameSurvivalStatus = FrameSurvivalStatus.ACTIVE
    r2_drop_vote_count: int = 0
    r2_drop_vote_refs: list[str] = field(default_factory=list)
    rebuttal_status: str = "NONE"  # NONE, PARTIAL, REBUTTED
    synthesis_disposition_status: str = "UNADDRESSED"  # ADDRESSED, UNADDRESSED

    def to_dict(self) -> dict:
        return {
            "frame_id": self.frame_id,
            "text": self.text,
            "origin_round": self.origin_round,
            "origin_model": self.origin_model,
            "frame_type": self.frame_type.value,
            "material_to_outcome": self.material_to_outcome,
            "survival_status": self.survival_status.value,
            "r2_drop_vote_count": self.r2_drop_vote_count,
            "r2_drop_vote_refs": self.r2_drop_vote_refs,
            "rebuttal_status": self.rebuttal_status,
            "synthesis_disposition_status": self.synthesis_disposition_status,
        }


@dataclass
class CrossDomainAnalogy:
    """A cross-domain analogy extracted from deliberation."""
    analogy_id: str
    source_domain: str
    target_claim_id: str
    transfer_mechanism: str
    test_status: AnalogyTestStatus = AnalogyTestStatus.UNTESTED

    def to_dict(self) -> dict:
        return {
            "analogy_id": self.analogy_id,
            "source_domain": self.source_domain,
            "target_claim_id": self.target_claim_id,
            "transfer_mechanism": self.transfer_mechanism,
            "test_status": self.test_status.value,
        }


@dataclass
class DivergenceResult:
    """Result of the Divergent Framing system (DoD v3.0 Section 8)."""
    required: bool = True
    adversarial_slot_assigned: bool = False
    adversarial_model_id: Optional[str] = None
    adversarial_assignment_type: Optional[str] = None
    framing_pass_executed: bool = False
    exploration_stress_triggered: bool = False
    stress_seed_frames: list[dict] = field(default_factory=list)
    alt_frames: list[FrameInfo] = field(default_factory=list)
    cross_domain_analogies: list[CrossDomainAnalogy] = field(default_factory=list)

    @property
    def material_unrebutted_frame_count(self) -> int:
        return sum(1 for f in self.alt_frames
                   if f.material_to_outcome
                   and f.survival_status in (FrameSurvivalStatus.ACTIVE,
                                              FrameSurvivalStatus.CONTESTED))

    def to_dict(self) -> dict:
        return {
            "required": self.required,
            "adversarial_slot_assigned": self.adversarial_slot_assigned,
            "adversarial_model_id": self.adversarial_model_id,
            "adversarial_assignment_type": self.adversarial_assignment_type,
            "framing_pass_executed": self.framing_pass_executed,
            "exploration_stress_triggered": self.exploration_stress_triggered,
            "stress_seed_frames": self.stress_seed_frames,
            "material_unrebutted_frame_count": self.material_unrebutted_frame_count,
            "alt_frames": [f.to_dict() for f in self.alt_frames],
            "cross_domain_analogies": [a.to_dict() for a in self.cross_domain_analogies],
        }


@dataclass
class SearchLogEntry:
    """A single search query log entry (DoD v3.0 Section 9)."""
    query_id: str
    query_text: str
    provenance: QueryProvenance
    issued_after_stage: str
    pages_fetched: int = 0
    evidence_yield_count: int = 0
    query_status: QueryStatus = QueryStatus.SUCCESS

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "provenance": self.provenance.value,
            "issued_after_stage": self.issued_after_stage,
            "pages_fetched": self.pages_fetched,
            "evidence_yield_count": self.evidence_yield_count,
            "query_status": self.query_status.value,
        }


@dataclass
class EvictionEvent:
    """An evidence eviction event for the two-tier ledger."""
    event_id: str
    evidence_id: str
    from_active: bool = True
    to_archive: bool = True
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "evidence_id": self.evidence_id,
            "from_active": self.from_active,
            "to_archive": self.to_archive,
            "reason": self.reason,
        }


@dataclass
class DecisiveClaim:
    """A decisive claim with evidence bindings (DoD v3.0 Section 13)."""
    claim_id: str
    text: str
    material_to_conclusion: bool = True
    evidence_refs: list[str] = field(default_factory=list)
    evidence_support_status: EvidenceSupportStatus = EvidenceSupportStatus.UNSUPPORTED
    analogy_refs: list[str] = field(default_factory=list)
    supporting_model_ids: list[str] = field(default_factory=list)  # DOD §15.2: which models share this claim

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "material_to_conclusion": self.material_to_conclusion,
            "evidence_refs": self.evidence_refs,
            "evidence_support_status": self.evidence_support_status.value,
            "analogy_refs": self.analogy_refs,
            "supporting_model_ids": self.supporting_model_ids,
        }


@dataclass
class StabilityResult:
    """Stability test results (DoD v3.0 Section 15)."""
    conclusion_stable: bool = True
    reason_stable: bool = True
    assumption_stable: bool = True
    independent_evidence_present: bool = False
    fast_consensus_observed: bool = False
    groupthink_warning: bool = False

    def to_dict(self) -> dict:
        return {
            "conclusion_stable": self.conclusion_stable,
            "reason_stable": self.reason_stable,
            "assumption_stable": self.assumption_stable,
            "independent_evidence_present": self.independent_evidence_present,
            "fast_consensus_observed": self.fast_consensus_observed,
            "groupthink_warning": self.groupthink_warning,
        }


@dataclass
class DispositionObject:
    """A structured disposition for synthesis residue (DoD v3.0 Section 14)."""
    target_type: DispositionTargetType
    target_id: str
    status: str
    importance: str  # LOW, MEDIUM, HIGH, CRITICAL
    narrative_explanation: str
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_type": self.target_type.value,
            "target_id": self.target_id,
            "status": self.status,
            "importance": self.importance,
            "narrative_explanation": self.narrative_explanation,
            "evidence_refs": self.evidence_refs,
        }


@dataclass
class UngroundedStatItem:
    """DOD §9.2 schema for a flagged ungrounded statistical claim."""
    claim_id: str
    text: str
    numeric: bool = True
    verified: bool = False
    blocker_id: Optional[str] = None
    severity: str = "MEDIUM"
    status: str = "UNVERIFIED_CLAIM"

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "numeric": self.numeric,
            "verified": self.verified,
            "blocker_id": self.blocker_id,
            "severity": self.severity,
            "status": self.status,
        }


@dataclass
class UngroundedStatResult:
    """DOD Â§9.2 container for detector findings and execution state."""
    items: list[UngroundedStatItem] = field(default_factory=list)
    post_r1_executed: bool = False
    post_r2_executed: bool = False

    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() if hasattr(item, "to_dict") else item for item in self.items],
            "post_r1_executed": self.post_r1_executed,
            "post_r2_executed": self.post_r2_executed,
        }


@dataclass
class SynthesisPacket:
    """DOD §14.1 controller-curated synthesis packet."""
    packet_complete: bool = False
    brief_excerpt: str = ""
    final_positions: dict = field(default_factory=dict)
    argument_lifecycle: list[dict] = field(default_factory=list)
    argument_count_total: int = 0
    argument_count_open: int = 0
    frame_summary: list[dict] = field(default_factory=list)
    material_unrebutted_frames: int = 0
    blocker_summary: list[dict] = field(default_factory=list)
    open_blocker_count: int = 0
    decisive_claims: list[dict] = field(default_factory=list)
    contradiction_summary: list[dict] = field(default_factory=list)
    premise_flag_summary: list[dict] = field(default_factory=list)
    evidence_count: int = 0

    def to_dict(self) -> dict:
        return {
            "packet_complete": self.packet_complete,
            "brief_excerpt": self.brief_excerpt,
            "final_positions": self.final_positions,
            "argument_lifecycle": self.argument_lifecycle,
            "argument_count_total": self.argument_count_total,
            "argument_count_open": self.argument_count_open,
            "frame_summary": self.frame_summary,
            "material_unrebutted_frames": self.material_unrebutted_frames,
            "blocker_summary": self.blocker_summary,
            "open_blocker_count": self.open_blocker_count,
            "decisive_claims": self.decisive_claims,
            "contradiction_summary": self.contradiction_summary,
            "premise_flag_summary": self.premise_flag_summary,
            "evidence_count": self.evidence_count,
        }


@dataclass
class ResidueVerification:
    """DOD §14.4 residue verification / disposition coverage result."""
    coverage_pass: bool = True
    omission_rate: float = 0.0
    omissions: list[dict] = field(default_factory=list)
    deep_scan_triggered: bool = False
    expected_disposition_count: int = 0
    emitted_disposition_count: int = 0
    total_required: int = 0
    total_disposed: int = 0
    deep_scan: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "coverage_pass": self.coverage_pass,
            "omission_rate": self.omission_rate,
            "omissions": self.omissions,
            "deep_scan_triggered": self.deep_scan_triggered,
            "expected_disposition_count": self.expected_disposition_count,
            "emitted_disposition_count": self.emitted_disposition_count,
            "total_required": self.total_required,
            "total_disposed": self.total_disposed,
            "deep_scan": self.deep_scan,
        }


@dataclass
class AnalysisMap:
    """DOD §18.3 analysis-mode exploratory map."""
    header: str = "EXPLORATORY MAP — NOT A DECISION"
    dimensions: dict = field(default_factory=dict)
    hypothesis_ledger: list[dict] = field(default_factory=list)
    total_argument_count: int = 0
    dimension_coverage_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "header": self.header,
            "dimensions": self.dimensions,
            "hypothesis_ledger": self.hypothesis_ledger,
            "total_argument_count": self.total_argument_count,
            "dimension_coverage_score": self.dimension_coverage_score,
        }


@dataclass
class AnalysisDebug:
    """DOD §18.4 analysis-mode debug audit record."""
    debug_mode: bool = False
    debug_gate2_result: Optional[str] = None
    actual_output: Optional[str] = None
    rules_enforced: bool = True
    remaining_debug_runs: int = 0
    analysis_mode_active: bool = True
    dimension_coverage_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "debug_mode": self.debug_mode,
            "debug_gate2_result": self.debug_gate2_result,
            "actual_output": self.actual_output,
            "rules_enforced": self.rules_enforced,
            "remaining_debug_runs": self.remaining_debug_runs,
            "analysis_mode_active": self.analysis_mode_active,
            "dimension_coverage_score": self.dimension_coverage_score,
        }


@dataclass
class SemanticContradiction:
    """A semantic contradiction detected by LLM analysis."""
    ctr_id: str
    detection_mode: DetectionMode = DetectionMode.SEMANTIC
    evidence_ref_a: str = ""
    evidence_ref_b: str = ""
    same_entity: bool = False
    same_timeframe: bool = False
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    status: ContradictionStatus = ContradictionStatus.OPEN
    justification: str = ""
    linked_claim_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ctr_id": self.ctr_id,
            "detection_mode": self.detection_mode.value,
            "evidence_ref_a": self.evidence_ref_a,
            "evidence_ref_b": self.evidence_ref_b,
            "same_entity": self.same_entity,
            "same_timeframe": self.same_timeframe,
            "severity": self.severity.value,
            "status": self.status.value,
            "justification": self.justification,
            "linked_claim_ids": self.linked_claim_ids,
        }
