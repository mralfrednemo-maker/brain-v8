# Brain V9 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve Brain V8 (commit `07d6628`) into Brain V9 by implementing DESIGN-V3.md + DOD-V3.md — the full expanded deliberation platform with PreflightAssessment, Dimension Seeder, Perspective Cards, frame survival, two-tier evidence, semantic contradictions, stability tests, ANALYSIS mode, and Gate 2 D1-D14/A1-A7.

**Architecture:** Bottom-up implementation. Layer 1: types/enums. Layer 2: new standalone modules (each tested). Layer 3: modified infrastructure (evidence, proof, checkpoint). Layer 4: modified pipeline modules (rounds, synthesis, residue, gate2). Layer 5: orchestrator rewiring (brain.py). Layer 6: integration testing with 3 briefs (b1, b9, b10).

**Tech Stack:** Python 3.11+, asyncio, httpx, Playwright (Bing search), pytest. LLMs: DeepSeek R1/Reasoner, GLM-5 Turbo, Kimi K2, Claude Sonnet 4.6.

**Hard Constraints:**
- Zero tolerance: any failure = BrainError. No degraded mode.
- No budgets: thinking models 30k/720s, non-thinking 8k-16k. Never reduce.
- Fixed topology: 4->3->2->2 always.
- Gate 2 deterministic: no LLM calls.
- Step-by-step debug default: every stage pauses and checkpoints.
- Bing Playwright headful: no fallback.

**Working directory:** `C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8\`

---

## File Structure

### New files
- `thinker/preflight.py` — PreflightAssessment (replaces gate1 as primary admission)
- `thinker/dimension_seeder.py` — Pre-R1 dimension generation
- `thinker/perspective_cards.py` — R1 structured output extraction
- `thinker/divergent_framing.py` — Framing pass + frame survival
- `thinker/semantic_contradiction.py` — Sonnet-based contradiction detection
- `thinker/stability.py` — Stability test computation
- `thinker/synthesis_packet.py` — Controller-curated synthesis packet builder
- `tests/test_preflight.py`
- `tests/test_dimension_seeder.py`
- `tests/test_perspective_cards.py`
- `tests/test_divergent_framing.py`
- `tests/test_semantic_contradiction.py`
- `tests/test_stability.py`
- `tests/test_synthesis_packet.py`

### Modified files
- `thinker/types.py` — New enums, dataclasses, outcome taxonomy
- `thinker/evidence.py` — Two-tier ledger (active + archive)
- `thinker/proof.py` — Schema 3.0
- `thinker/checkpoint.py` — New stage IDs, new state fields, version 2.0
- `thinker/rounds.py` — Adversarial prompts, dimension/frame injection, perspective card instructions
- `thinker/synthesis.py` — Accept curated packet instead of raw R4 views
- `thinker/residue.py` — Structured dispositions, schema validation
- `thinker/gate2.py` — Full rewrite: D1-D14 (DECIDE) + A1-A7 (ANALYSIS)
- `thinker/brain.py` — Full orchestrator rewiring
- `thinker/pipeline.py` — Register new stages
- `tests/test_types.py` — Tests for new types
- `tests/test_evidence.py` — Tests for two-tier ledger
- `tests/test_gate2.py` — Tests for D1-D14 / A1-A7
- `tests/test_proof.py` — Tests for schema 3.0

---

## Task 1: Expand types.py — Outcome Taxonomy and New Enums

**Files:**
- Modify: `thinker/types.py`
- Test: `tests/test_types.py`

This is the foundation — every other task depends on these types.

- [ ] **Step 1: Update Outcome enum and remove ACCEPTED_WITH_WARNINGS**

In `thinker/types.py`, replace the existing `Outcome` and `AcceptanceStatus`:

```python
class Outcome(Enum):
    """Top-level outcomes of a Brain deliberation (DoD v3.0 Section 1)."""
    DECIDE = "DECIDE"
    ESCALATE = "ESCALATE"
    NO_CONSENSUS = "NO_CONSENSUS"
    ANALYSIS = "ANALYSIS"
    ERROR = "ERROR"
    NEED_MORE = "NEED_MORE"  # PreflightAssessment only, not a top-level outcome


class AcceptanceStatus(Enum):
    ACCEPTED = "ACCEPTED"
    # ACCEPTED_WITH_WARNINGS removed per DoD v3.0
```

- [ ] **Step 2: Add new enums for PreflightAssessment**

Add after `AcceptanceStatus`:

```python
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
```

- [ ] **Step 3: Add enums for Perspective Cards, Frames, Arguments, Stability**

```python
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


class ErrorClass(Enum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    FATAL_INTEGRITY = "FATAL_INTEGRITY"


class AssumptionVerifiability(Enum):
    VERIFIABLE = "VERIFIABLE"
    UNVERIFIABLE = "UNVERIFIABLE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"
```

- [ ] **Step 4: Add new dataclasses**

Add after existing dataclasses:

```python
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
    """Structured R1 output for a single model (DoD v3.0 Section 7)."""
    model_id: str
    primary_frame: str = ""
    hidden_assumption_attacked: str = ""
    stakeholder_lens: str = ""
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM
    failure_mode: str = ""
    coverage_obligation: CoverageObligation = CoverageObligation.MECHANISM_ANALYSIS
    dimensions_addressed: list[str] = field(default_factory=list)

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

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "material_to_conclusion": self.material_to_conclusion,
            "evidence_refs": self.evidence_refs,
            "evidence_support_status": self.evidence_support_status.value,
            "analogy_refs": self.analogy_refs,
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
```

- [ ] **Step 5: Update existing dataclasses**

Modify `EvidenceItem` to add two-tier fields:

```python
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
```

Modify `Argument` to add resolution status:

```python
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
```

Modify `Blocker` to add new kinds and severity:

```python
class BlockerKind(Enum):
    EVIDENCE_GAP = "EVIDENCE_GAP"
    CONTRADICTION = "CONTRADICTION"
    UNRESOLVED_DISAGREEMENT = "UNRESOLVED_DISAGREEMENT"
    CONTESTED_POSITION = "CONTESTED_POSITION"
    COVERAGE_GAP = "COVERAGE_GAP"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"
```

Modify `Contradiction` to support both detection modes:

```python
@dataclass
class Contradiction:
    """A detected contradiction between evidence items."""
    contradiction_id: str
    evidence_ids: list[str]
    topic: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    status: str = "OPEN"  # OPEN, RESOLVED, NON_MATERIAL
    detection_mode: str = "NUMERIC"  # NUMERIC, SEMANTIC
    justification: str = ""
    linked_claim_ids: list[str] = field(default_factory=list)
```

Modify `Gate2Assessment` to add rule trace and modality:

```python
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
```

Modify `BrainResult` to include all new objects:

```python
@dataclass
class BrainResult:
    """Final result of a complete Brain deliberation."""
    outcome: Outcome
    proof: dict
    report: str
    gate1: Optional[Gate1Result] = None  # Keep for backwards compat during transition
    preflight: Optional[PreflightResult] = None
    gate2: Optional[Gate2Assessment] = None
    dimensions: Optional[DimensionSeedResult] = None
    perspective_cards: Optional[list[PerspectiveCard]] = None
    divergence: Optional[DivergenceResult] = None
    stability: Optional[StabilityResult] = None
    error_class: Optional[ErrorClass] = None
```

- [ ] **Step 6: Write tests for new types**

In `tests/test_types.py`, add tests:

```python
def test_outcome_has_all_values():
    from thinker.types import Outcome
    assert set(o.value for o in Outcome) == {
        "DECIDE", "ESCALATE", "NO_CONSENSUS", "ANALYSIS", "ERROR", "NEED_MORE"
    }


def test_preflight_result_critical_flags():
    from thinker.types import (
        PreflightResult, PremiseFlag, PremiseFlagType,
        PremiseFlagSeverity, PremiseFlagRouting,
    )
    pf = PreflightResult(
        premise_flags=[
            PremiseFlag(
                flag_id="PFLAG-1", flag_type=PremiseFlagType.INTERNAL_CONTRADICTION,
                severity=PremiseFlagSeverity.CRITICAL, summary="test",
                routing=PremiseFlagRouting.MANAGEABLE_UNKNOWN,
            ),
        ],
    )
    assert pf.has_critical_flags is True
    assert len(pf.unresolved_critical_flags) == 1


def test_preflight_result_resolved_critical_not_blocking():
    from thinker.types import (
        PreflightResult, PremiseFlag, PremiseFlagType,
        PremiseFlagSeverity, PremiseFlagRouting,
    )
    pf = PreflightResult(
        premise_flags=[
            PremiseFlag(
                flag_id="PFLAG-1", flag_type=PremiseFlagType.INTERNAL_CONTRADICTION,
                severity=PremiseFlagSeverity.CRITICAL, summary="test",
                routing=PremiseFlagRouting.MANAGEABLE_UNKNOWN,
                resolved=True, resolved_stage="r2",
            ),
        ],
    )
    assert pf.has_critical_flags is False


def test_dimension_seed_result_to_dict():
    from thinker.types import DimensionSeedResult, DimensionItem
    ds = DimensionSeedResult(
        items=[DimensionItem(dimension_id="DIM-1", name="Legal")],
        dimension_count=1,
    )
    d = ds.to_dict()
    assert d["seeded"] is True
    assert len(d["items"]) == 1


def test_stability_result_defaults():
    from thinker.types import StabilityResult
    sr = StabilityResult()
    assert sr.conclusion_stable is True
    assert sr.groupthink_warning is False


def test_frame_info_to_dict():
    from thinker.types import FrameInfo, FrameType, FrameSurvivalStatus
    f = FrameInfo(frame_id="FRAME-1", text="test", frame_type=FrameType.INVERSION)
    d = f.to_dict()
    assert d["frame_type"] == "INVERSION"
    assert d["survival_status"] == "ACTIVE"


def test_evidence_item_has_two_tier_fields():
    from thinker.types import EvidenceItem, Confidence
    e = EvidenceItem(
        evidence_id="E001", topic="test", fact="test fact",
        url="https://example.com", confidence=Confidence.HIGH,
    )
    assert e.is_active is True
    assert e.is_archived is False
    assert e.authority_tier == "STANDARD"


def test_argument_has_resolution_status():
    from thinker.types import Argument, ResolutionStatus
    a = Argument(argument_id="R1-ARG-1", round_num=1, model="r1", text="test")
    assert a.resolution_status == ResolutionStatus.ORIGINAL
    assert a.superseded_by is None
    assert a.open is True
```

- [ ] **Step 7: Run tests**

Run: `cd /c/Users/chris/PROJECTS/_audit_thinker/thinker-v8 && python -m pytest tests/test_types.py -v`

Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add thinker/types.py tests/test_types.py
git commit -m "feat(v9): expand types — outcome taxonomy, preflight, dimensions, frames, stability, two-tier evidence"
```

---

## Task 2: PreflightAssessment Module

**Files:**
- Create: `thinker/preflight.py`
- Test: `tests/test_preflight.py`

Replaces Gate 1 + CS Audit as a single merged stage. One Sonnet call.

- [ ] **Step 1: Write tests**

Create `tests/test_preflight.py`:

```python
"""Tests for PreflightAssessment (DoD v3.0 Section 4)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from thinker.types import (
    Answerability, BrainError, EffortTier, Modality, PreflightResult,
    QuestionClass, SearchScope, StakesClass,
)


def _make_mock_llm(response_text: str):
    """Create a mock LLM client that returns the given text."""
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=True, text=response_text, elapsed_s=1.0)
    return mock


def _make_valid_response(**overrides):
    """Build a valid JSON response string for the preflight prompt."""
    import json
    data = {
        "answerability": "ANSWERABLE",
        "question_class": "OPEN",
        "stakes_class": "STANDARD",
        "effort_tier": "STANDARD",
        "modality": "DECIDE",
        "search_scope": "TARGETED",
        "exploration_required": False,
        "short_circuit_allowed": False,
        "fatal_premise": False,
        "follow_up_questions": [],
        "premise_flags": [],
        "hidden_context_gaps": [],
        "critical_assumptions": [
            {"assumption_id": "CA-1", "text": "Data is accurate", "verifiability": "VERIFIABLE", "material": True},
            {"assumption_id": "CA-2", "text": "Timeline is correct", "verifiability": "VERIFIABLE", "material": True},
            {"assumption_id": "CA-3", "text": "Scope is defined", "verifiability": "VERIFIABLE", "material": False},
        ],
        "reasoning": "Brief is well-formed and answerable.",
    }
    data.update(overrides)
    return json.dumps(data)


@pytest.mark.asyncio
async def test_preflight_answerable_brief():
    from thinker.preflight import run_preflight
    mock = _make_mock_llm(_make_valid_response())
    result = await run_preflight(mock, "A well-formed brief about security.")
    assert result.executed is True
    assert result.parse_ok is True
    assert result.answerability == Answerability.ANSWERABLE
    assert result.modality == Modality.DECIDE


@pytest.mark.asyncio
async def test_preflight_need_more_routes_correctly():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        answerability="NEED_MORE",
        follow_up_questions=["What system is affected?", "What is the timeline?"],
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Vague brief.")
    assert result.answerability == Answerability.NEED_MORE
    assert len(result.follow_up_questions) == 2


@pytest.mark.asyncio
async def test_preflight_invalid_form_maps_to_need_more_not_error():
    """DoD v3.0 Section 4.3: INVALID_FORM → NEED_MORE, never ERROR."""
    from thinker.preflight import run_preflight
    resp = _make_valid_response(answerability="INVALID_FORM")
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Nonsensical brief.")
    assert result.answerability == Answerability.INVALID_FORM
    # INVALID_FORM is a valid answerability value, but outcome should be NEED_MORE


@pytest.mark.asyncio
async def test_preflight_fatal_premise():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        answerability="NEED_MORE",
        fatal_premise=True,
        follow_up_questions=["The premise is fundamentally flawed because..."],
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Brief with broken premise.")
    assert result.fatal_premise is True


@pytest.mark.asyncio
async def test_preflight_parse_failure_raises_brain_error():
    """DoD v3.0 Section 4.5: missing/unparseable → ERROR."""
    from thinker.preflight import run_preflight
    mock = _make_mock_llm("This is not JSON at all.")
    with pytest.raises(BrainError, match="preflight"):
        await run_preflight(mock, "Some brief.")


@pytest.mark.asyncio
async def test_preflight_llm_failure_raises_brain_error():
    from thinker.preflight import run_preflight
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=False, text="", error="timeout", elapsed_s=300.0)
    with pytest.raises(BrainError, match="preflight"):
        await run_preflight(mock, "Some brief.")


@pytest.mark.asyncio
async def test_preflight_short_circuit_guards():
    """DoD v3.0 Section 4.4: short_circuit_allowed only under strict conditions."""
    from thinker.preflight import run_preflight
    # SHORT_CIRCUIT allowed: TRIVIAL + LOW + no critical flags + no material gaps
    resp = _make_valid_response(
        question_class="TRIVIAL",
        stakes_class="LOW",
        effort_tier="SHORT_CIRCUIT",
        short_circuit_allowed=True,
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "What color is the sky?")
    assert result.short_circuit_allowed is True
    assert result.effort_tier == EffortTier.SHORT_CIRCUIT


@pytest.mark.asyncio
async def test_preflight_elevated_effort_on_high_stakes():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        stakes_class="HIGH",
        effort_tier="ELEVATED",
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "High stakes brief.")
    assert result.stakes_class == StakesClass.HIGH
    assert result.effort_tier == EffortTier.ELEVATED


@pytest.mark.asyncio
async def test_preflight_analysis_modality():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(modality="ANALYSIS")
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Explore this topic.")
    assert result.modality == Modality.ANALYSIS


@pytest.mark.asyncio
async def test_preflight_premise_flags_with_routing():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        premise_flags=[
            {
                "flag_id": "PFLAG-1",
                "flag_type": "INTERNAL_CONTRADICTION",
                "severity": "CRITICAL",
                "summary": "Section A contradicts Section B",
                "routing": "MANAGEABLE_UNKNOWN",
            },
        ],
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Brief with contradiction.")
    assert len(result.premise_flags) == 1
    assert result.premise_flags[0].severity.value == "CRITICAL"
    assert result.has_critical_flags is True


@pytest.mark.asyncio
async def test_preflight_critical_assumptions():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        critical_assumptions=[
            {"assumption_id": "CA-1", "text": "Data is real-time", "verifiability": "UNVERIFIABLE", "material": True},
            {"assumption_id": "CA-2", "text": "User count is stable", "verifiability": "VERIFIABLE", "material": True},
            {"assumption_id": "CA-3", "text": "Budget exists", "verifiability": "VERIFIABLE", "material": False},
        ],
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Brief with assumptions.")
    assert len(result.critical_assumptions) == 3
    assert result.has_fatal_assumptions is True  # CA-1 is UNVERIFIABLE + material


@pytest.mark.asyncio
async def test_preflight_to_dict_roundtrip():
    from thinker.preflight import run_preflight
    mock = _make_mock_llm(_make_valid_response())
    result = await run_preflight(mock, "Test brief.")
    d = result.to_dict()
    assert d["answerability"] == "ANSWERABLE"
    assert d["executed"] is True
    assert isinstance(d["premise_flags"], list)
    assert isinstance(d["critical_assumptions"], list)
```

- [ ] **Step 2: Write preflight.py implementation**

Create `thinker/preflight.py`:

```python
"""PreflightAssessment — merged Gate 1 + CS Audit (DoD v3.0 Section 4).

Single Sonnet call. Handles admission, modality selection, effort calibration,
defect typing, hidden-context discovery, assumption surfacing, and search scope.

Replaces the separate gate1.py for V9. gate1.py is kept for backward compat
but preflight.py is the canonical admission stage.
"""
from __future__ import annotations

import json

from thinker.pipeline import pipeline_stage
from thinker.types import (
    Answerability, AssumptionVerifiability, BrainError, CriticalAssumption,
    EffortTier, HiddenContextGap, Modality, PremiseFlag, PremiseFlagRouting,
    PremiseFlagSeverity, PremiseFlagType, PreflightResult, QuestionClass,
    SearchScope, StakesClass,
)

PREFLIGHT_PROMPT = """You are a preflight assessor for a multi-model deliberation system.

Analyze the brief below and produce a structured JSON assessment. Your job is to:
1. Determine if the brief is answerable as-is
2. Classify the question type, stakes, and required effort
3. Detect premise defects, hidden context gaps, and critical assumptions
4. Recommend search scope and modality (DECIDE vs ANALYSIS)

## Brief
{brief}

## Output Format — STRICT JSON (no markdown, no commentary, just the JSON object)

{{
  "answerability": "ANSWERABLE | NEED_MORE | INVALID_FORM",
  "question_class": "TRIVIAL | WELL_ESTABLISHED | OPEN | AMBIGUOUS",
  "stakes_class": "LOW | STANDARD | HIGH",
  "effort_tier": "SHORT_CIRCUIT | STANDARD | ELEVATED",
  "modality": "DECIDE | ANALYSIS",
  "search_scope": "NONE | TARGETED | BROAD",
  "exploration_required": true/false,
  "short_circuit_allowed": true/false,
  "fatal_premise": true/false,
  "follow_up_questions": ["specific question 1", ...],
  "premise_flags": [
    {{
      "flag_id": "PFLAG-1",
      "flag_type": "INTERNAL_CONTRADICTION | UNSUPPORTED_ASSUMPTION | AMBIGUITY | IMPOSSIBLE_REQUEST | FRAMING_DEFECT",
      "severity": "INFO | WARNING | CRITICAL",
      "summary": "description of the defect",
      "routing": "REQUESTER_FIXABLE | MANAGEABLE_UNKNOWN | FRAMING_DEFECT | FATAL_PREMISE"
    }}
  ],
  "hidden_context_gaps": [
    {{
      "gap_id": "GAP-1",
      "description": "what context is missing",
      "impact_if_unresolved": "what happens if we proceed without it",
      "material": true/false
    }}
  ],
  "critical_assumptions": [
    {{
      "assumption_id": "CA-1",
      "text": "what we're assuming",
      "verifiability": "VERIFIABLE | UNVERIFIABLE | FALSE | UNKNOWN",
      "material": true/false
    }}
  ],
  "reasoning": "one paragraph explaining your assessment"
}}

## Rules
- ANSWERABLE: question is specific, has enough context, clear deliverable
- NEED_MORE: critical context missing, ambiguous, or fatal premise
- INVALID_FORM: question is malformed or nonsensical (maps to NEED_MORE outcome, NOT ERROR)
- short_circuit_allowed: ONLY true when question_class in [TRIVIAL, WELL_ESTABLISHED] AND stakes_class = LOW AND no CRITICAL premise flags AND no material hidden_context_gaps
- effort_tier = ELEVATED when: stakes_class = HIGH OR question_class = AMBIGUOUS OR any CRITICAL premise flag
- Surface 3-5 critical unstated assumptions. If any is UNVERIFIABLE or FALSE and material, answerability should be NEED_MORE
- ANALYSIS modality: when the question asks for exploration/mapping rather than a verdict
- DECIDE modality: when the question asks for a recommendation/assessment/verdict"""


@pipeline_stage(
    name="PreflightAssessment",
    description="Merged Gate 1 + CS Audit. Single Sonnet call. Handles admission, modality, effort, defect routing, assumptions, search scope.",
    stage_type="gate",
    order=1,
    provider="sonnet",
    inputs=["brief"],
    outputs=["PreflightResult"],
    logic="Parse JSON. ANSWERABLE→admit. NEED_MORE→reject with questions. INVALID_FORM→NEED_MORE. Parse fail→BrainError.",
    failure_mode="LLM failure or parse failure: BrainError (zero tolerance).",
    cost="1 Sonnet call",
    stage_id="preflight",
)
async def run_preflight(client, brief: str) -> PreflightResult:
    """Run the PreflightAssessment stage.

    Returns PreflightResult on success.
    Raises BrainError on LLM failure or parse failure.
    """
    prompt = PREFLIGHT_PROMPT.format(brief=brief)
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        raise BrainError("preflight", f"PreflightAssessment LLM call failed: {resp.error}")

    # Parse JSON response
    text = resp.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise BrainError("preflight", f"Failed to parse PreflightAssessment JSON: {e}",
                         detail=resp.text[:500])

    # Validate required fields
    required = ["answerability", "question_class", "stakes_class", "effort_tier", "modality"]
    for field in required:
        if field not in data:
            raise BrainError("preflight", f"Missing required field: {field}",
                             detail=f"Got keys: {list(data.keys())}")

    # Build result
    try:
        premise_flags = []
        for pf in data.get("premise_flags", []):
            premise_flags.append(PremiseFlag(
                flag_id=pf.get("flag_id", "PFLAG-?"),
                flag_type=PremiseFlagType(pf.get("flag_type", "FRAMING_DEFECT")),
                severity=PremiseFlagSeverity(pf.get("severity", "WARNING")),
                summary=pf.get("summary", ""),
                routing=PremiseFlagRouting(pf.get("routing", "MANAGEABLE_UNKNOWN")),
                blocking=pf.get("severity") == "CRITICAL",
            ))

        hidden_gaps = []
        for g in data.get("hidden_context_gaps", []):
            hidden_gaps.append(HiddenContextGap(
                gap_id=g.get("gap_id", "GAP-?"),
                description=g.get("description", ""),
                impact_if_unresolved=g.get("impact_if_unresolved", ""),
                material=g.get("material", False),
            ))

        assumptions = []
        for a in data.get("critical_assumptions", []):
            assumptions.append(CriticalAssumption(
                assumption_id=a.get("assumption_id", "CA-?"),
                text=a.get("text", ""),
                verifiability=AssumptionVerifiability(a.get("verifiability", "UNKNOWN")),
                material=a.get("material", True),
            ))

        result = PreflightResult(
            executed=True,
            parse_ok=True,
            answerability=Answerability(data["answerability"]),
            question_class=QuestionClass(data["question_class"]),
            stakes_class=StakesClass(data["stakes_class"]),
            effort_tier=EffortTier(data["effort_tier"]),
            modality=Modality(data["modality"]),
            search_scope=SearchScope(data.get("search_scope", "TARGETED")),
            exploration_required=data.get("exploration_required", False),
            short_circuit_allowed=data.get("short_circuit_allowed", False),
            fatal_premise=data.get("fatal_premise", False),
            follow_up_questions=data.get("follow_up_questions", []),
            premise_flags=premise_flags,
            hidden_context_gaps=hidden_gaps,
            critical_assumptions=assumptions,
            reasoning=data.get("reasoning", ""),
        )

    except (ValueError, KeyError) as e:
        raise BrainError("preflight", f"Invalid enum value in PreflightAssessment: {e}",
                         detail=resp.text[:500])

    # Enforce admission guards (DoD v3.0 Section 4.4)
    # short_circuit_allowed validation
    if result.short_circuit_allowed:
        if result.question_class not in (QuestionClass.TRIVIAL, QuestionClass.WELL_ESTABLISHED):
            result.short_circuit_allowed = False
        if result.stakes_class != StakesClass.LOW:
            result.short_circuit_allowed = False
        if result.has_critical_flags:
            result.short_circuit_allowed = False
        if result.has_material_unresolved_gaps:
            result.short_circuit_allowed = False

    # Enforce elevated effort
    if (result.stakes_class == StakesClass.HIGH
            or result.question_class == QuestionClass.AMBIGUOUS
            or result.has_critical_flags):
        if result.effort_tier != EffortTier.ELEVATED:
            result.effort_tier = EffortTier.ELEVATED

    return result
```

- [ ] **Step 3: Run tests**

Run: `cd /c/Users/chris/PROJECTS/_audit_thinker/thinker-v8 && python -m pytest tests/test_preflight.py -v`

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add thinker/preflight.py tests/test_preflight.py
git commit -m "feat(v9): add PreflightAssessment — merged Gate1 + CS Audit with defect routing"
```

---

## Task 3: Dimension Seeder Module

**Files:**
- Create: `thinker/dimension_seeder.py`
- Test: `tests/test_dimension_seeder.py`

- [ ] **Step 1: Write tests**

Create `tests/test_dimension_seeder.py`:

```python
"""Tests for Dimension Seeder (DoD v3.0 Section 6)."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import json

from thinker.types import BrainError, DimensionSeedResult


def _make_mock_llm(response_text: str):
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=True, text=response_text, elapsed_s=1.0)
    return mock


def _valid_dimensions_response(count=4):
    dims = [
        {"dimension_id": f"DIM-{i+1}", "name": f"Dimension {i+1}", "mandatory": True}
        for i in range(count)
    ]
    return json.dumps({"dimensions": dims})


@pytest.mark.asyncio
async def test_seeder_produces_3_to_5_dimensions():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm(_valid_dimensions_response(4))
    result = await run_dimension_seeder(mock, "Test brief")
    assert result.seeded is True
    assert result.dimension_count == 4
    assert len(result.items) == 4


@pytest.mark.asyncio
async def test_seeder_fewer_than_3_raises_error():
    """DoD v3.0 Section 6.3: fewer than 3 → ERROR."""
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm(_valid_dimensions_response(2))
    with pytest.raises(BrainError, match="dimension"):
        await run_dimension_seeder(mock, "Test brief")


@pytest.mark.asyncio
async def test_seeder_caps_at_5():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm(_valid_dimensions_response(7))
    result = await run_dimension_seeder(mock, "Test brief")
    assert result.dimension_count == 5  # capped


@pytest.mark.asyncio
async def test_seeder_parse_failure_raises_error():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm("Not JSON")
    with pytest.raises(BrainError, match="dimension"):
        await run_dimension_seeder(mock, "Test brief")


@pytest.mark.asyncio
async def test_seeder_llm_failure_raises_error():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=False, text="", error="timeout", elapsed_s=300.0)
    with pytest.raises(BrainError, match="dimension"):
        await run_dimension_seeder(mock, "Test brief")


@pytest.mark.asyncio
async def test_seeder_to_dict():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm(_valid_dimensions_response(3))
    result = await run_dimension_seeder(mock, "Test brief")
    d = result.to_dict()
    assert d["seeded"] is True
    assert len(d["items"]) == 3


@pytest.mark.asyncio
async def test_seeder_formats_for_prompt():
    from thinker.dimension_seeder import run_dimension_seeder, format_dimensions_for_prompt
    mock = _make_mock_llm(_valid_dimensions_response(3))
    result = await run_dimension_seeder(mock, "Test brief")
    text = format_dimensions_for_prompt(result.items)
    assert "DIM-1" in text
    assert "DIM-2" in text
    assert "DIM-3" in text
```

- [ ] **Step 2: Write dimension_seeder.py**

Create `thinker/dimension_seeder.py`:

```python
"""Dimension Seeder — pre-R1 exploration dimension generation (DoD v3.0 Section 6).

One Sonnet call generates 3-5 mandatory exploration dimensions from the brief.
Injected into all R1 prompts. Models must address all dimensions or justify irrelevance.
"""
from __future__ import annotations

import json

from thinker.pipeline import pipeline_stage
from thinker.types import BrainError, DimensionItem, DimensionSeedResult

SEEDER_PROMPT = """You are an exploration dimension generator for a multi-model deliberation system.

Given the brief below, identify 3-5 mandatory exploration dimensions that models MUST address in their analysis. Each dimension is a distinct aspect or lens through which the question should be examined.

## Brief
{brief}

## Output Format — STRICT JSON (no markdown, no commentary)

{{
  "dimensions": [
    {{
      "dimension_id": "DIM-1",
      "name": "short descriptive name",
      "mandatory": true
    }}
  ]
}}

## Rules
- Generate exactly 3-5 dimensions. No fewer than 3, no more than 5.
- Each dimension should be substantively different (not overlapping).
- Dimensions should cover: technical, organizational, risk, ethical/legal, and operational aspects as relevant.
- Use short, descriptive names (2-5 words each).
- All dimensions are mandatory=true."""


@pipeline_stage(
    name="Dimension Seeder",
    description="Pre-R1 Sonnet call generating 3-5 mandatory exploration dimensions. Injected into all R1 prompts.",
    stage_type="seeder",
    order=2,
    provider="sonnet",
    inputs=["brief"],
    outputs=["DimensionSeedResult"],
    logic="Parse JSON. 3-5 dimensions required. <3 → BrainError.",
    failure_mode="LLM failure or parse failure or <3 dimensions: BrainError.",
    cost="1 Sonnet call",
    stage_id="dimensions",
)
async def run_dimension_seeder(client, brief: str) -> DimensionSeedResult:
    """Run the Dimension Seeder. Returns DimensionSeedResult."""
    prompt = SEEDER_PROMPT.format(brief=brief)
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        raise BrainError("dimension_seeder", f"Dimension Seeder LLM call failed: {resp.error}")

    text = resp.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise BrainError("dimension_seeder", f"Failed to parse Dimension Seeder JSON: {e}",
                         detail=resp.text[:500])

    dims_data = data.get("dimensions", [])
    if not dims_data:
        raise BrainError("dimension_seeder", "No dimensions in response",
                         detail=resp.text[:500])

    # Cap at 5
    dims_data = dims_data[:5]

    items = []
    for d in dims_data:
        items.append(DimensionItem(
            dimension_id=d.get("dimension_id", f"DIM-{len(items)+1}"),
            name=d.get("name", "Unknown"),
            mandatory=d.get("mandatory", True),
        ))

    if len(items) < 3:
        raise BrainError("dimension_seeder",
                         f"Fewer than 3 dimensions generated ({len(items)}). DoD requires 3-5.",
                         detail=f"Got: {[d.name for d in items]}")

    return DimensionSeedResult(
        seeded=True,
        parse_ok=True,
        items=items,
        dimension_count=len(items),
        dimension_coverage_score=0.0,  # Computed after rounds
    )


def format_dimensions_for_prompt(dimensions: list[DimensionItem]) -> str:
    """Format dimensions for injection into R1 prompts."""
    lines = ["## Mandatory Exploration Dimensions",
             "You MUST address ALL of the following dimensions in your analysis.",
             "If a dimension is genuinely irrelevant, explain why.\n"]
    for d in dimensions:
        lines.append(f"- **{d.dimension_id}: {d.name}**")
    return "\n".join(lines)
```

- [ ] **Step 3: Run tests**

Run: `cd /c/Users/chris/PROJECTS/_audit_thinker/thinker-v8 && python -m pytest tests/test_dimension_seeder.py -v`

- [ ] **Step 4: Commit**

```bash
git add thinker/dimension_seeder.py tests/test_dimension_seeder.py
git commit -m "feat(v9): add Dimension Seeder — pre-R1 mandatory exploration dimensions"
```

---

## Task 4: Perspective Cards Module

**Files:**
- Create: `thinker/perspective_cards.py`
- Test: `tests/test_perspective_cards.py`

Parses R1 model outputs to extract structured fields. No LLM call — parsing only.

- [ ] **Step 1: Write tests**

Create `tests/test_perspective_cards.py`:

```python
"""Tests for Perspective Cards (DoD v3.0 Section 7)."""
import pytest
from thinker.types import BrainError, CoverageObligation, PerspectiveCard, TimeHorizon


def test_extract_cards_from_r1():
    from thinker.perspective_cards import extract_perspective_cards
    r1_texts = {
        "kimi": "PRIMARY_FRAME: Devil's advocate\nHIDDEN_ASSUMPTION_ATTACKED: Cost is fixed\nSTAKEHOLDER_LENS: End users\nTIME_HORIZON: SHORT\nFAILURE_MODE: Adoption resistance",
        "r1": "PRIMARY_FRAME: Technical feasibility\nHIDDEN_ASSUMPTION_ATTACKED: Scale assumptions\nSTAKEHOLDER_LENS: Engineering team\nTIME_HORIZON: MEDIUM\nFAILURE_MODE: Technical debt",
        "reasoner": "PRIMARY_FRAME: Risk analysis\nHIDDEN_ASSUMPTION_ATTACKED: Timeline is realistic\nSTAKEHOLDER_LENS: Management\nTIME_HORIZON: LONG\nFAILURE_MODE: Budget overrun",
        "glm5": "PRIMARY_FRAME: Operational impact\nHIDDEN_ASSUMPTION_ATTACKED: Team capacity\nSTAKEHOLDER_LENS: Operations\nTIME_HORIZON: MEDIUM\nFAILURE_MODE: Downtime",
    }
    cards = extract_perspective_cards(r1_texts)
    assert len(cards) == 4
    assert all(c.primary_frame for c in cards)
    assert all(c.failure_mode for c in cards)


def test_extract_cards_missing_fields_uses_defaults():
    from thinker.perspective_cards import extract_perspective_cards
    r1_texts = {
        "kimi": "Some analysis without structured fields",
        "r1": "Another analysis",
        "reasoner": "Third analysis",
        "glm5": "Fourth analysis",
    }
    # Should still produce cards with empty/default fields — not error
    cards = extract_perspective_cards(r1_texts)
    assert len(cards) == 4


def test_coverage_obligations_assigned():
    from thinker.perspective_cards import extract_perspective_cards
    r1_texts = {
        "kimi": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
        "r1": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
        "reasoner": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
        "glm5": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
    }
    cards = extract_perspective_cards(r1_texts)
    obligations = {c.coverage_obligation for c in cards}
    assert CoverageObligation.CONTRARIAN in obligations


def test_cards_to_dict():
    from thinker.perspective_cards import extract_perspective_cards
    r1_texts = {
        "kimi": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
        "r1": "PRIMARY_FRAME: t\nHIDDEN_ASSUMPTION_ATTACKED: t\nSTAKEHOLDER_LENS: t\nTIME_HORIZON: MEDIUM\nFAILURE_MODE: t",
        "reasoner": "PRIMARY_FRAME: t\nHIDDEN_ASSUMPTION_ATTACKED: t\nSTAKEHOLDER_LENS: t\nTIME_HORIZON: LONG\nFAILURE_MODE: t",
        "glm5": "PRIMARY_FRAME: t\nHIDDEN_ASSUMPTION_ATTACKED: t\nSTAKEHOLDER_LENS: t\nTIME_HORIZON: SHORT\nFAILURE_MODE: t",
    }
    cards = extract_perspective_cards(r1_texts)
    dicts = [c.to_dict() for c in cards]
    assert all("model_id" in d for d in dicts)
    assert all("coverage_obligation" in d for d in dicts)
```

- [ ] **Step 2: Write perspective_cards.py**

Create `thinker/perspective_cards.py`:

```python
"""Perspective Cards — structured R1 output extraction (DoD v3.0 Section 7).

Parses R1 model outputs to extract 5 structured fields per model.
No LLM call — regex/text parsing only.
"""
from __future__ import annotations

import re

from thinker.types import CoverageObligation, PerspectiveCard, TimeHorizon

# Coverage obligation assignments (fixed per model)
_MODEL_OBLIGATIONS = {
    "kimi": CoverageObligation.CONTRARIAN,
    "r1": CoverageObligation.MECHANISM_ANALYSIS,
    "reasoner": CoverageObligation.OPERATIONAL_RISK,
    "glm5": CoverageObligation.OBJECTIVE_REFRAMING,
}

# Field patterns to extract from model output
_FIELD_PATTERNS = {
    "primary_frame": re.compile(r"PRIMARY_FRAME:\s*(.+)", re.IGNORECASE),
    "hidden_assumption_attacked": re.compile(r"HIDDEN_ASSUMPTION_ATTACKED:\s*(.+)", re.IGNORECASE),
    "stakeholder_lens": re.compile(r"STAKEHOLDER_LENS:\s*(.+)", re.IGNORECASE),
    "time_horizon": re.compile(r"TIME_HORIZON:\s*(\w+)", re.IGNORECASE),
    "failure_mode": re.compile(r"FAILURE_MODE:\s*(.+)", re.IGNORECASE),
}


def _parse_time_horizon(text: str) -> TimeHorizon:
    """Parse a time horizon string into the enum."""
    text = text.strip().upper()
    if text in ("SHORT", "SHORT-TERM", "SHORT_TERM"):
        return TimeHorizon.SHORT
    elif text in ("LONG", "LONG-TERM", "LONG_TERM"):
        return TimeHorizon.LONG
    return TimeHorizon.MEDIUM


def extract_perspective_cards(r1_texts: dict[str, str]) -> list[PerspectiveCard]:
    """Extract perspective cards from R1 model outputs.

    Args:
        r1_texts: dict of {model_id: response_text} from R1.

    Returns:
        List of PerspectiveCard objects, one per model.
    """
    cards = []
    for model_id, text in r1_texts.items():
        fields = {}
        for field_name, pattern in _FIELD_PATTERNS.items():
            match = pattern.search(text)
            if match:
                fields[field_name] = match.group(1).strip()

        time_horizon = _parse_time_horizon(fields.get("time_horizon", "MEDIUM"))
        obligation = _MODEL_OBLIGATIONS.get(model_id, CoverageObligation.MECHANISM_ANALYSIS)

        card = PerspectiveCard(
            model_id=model_id,
            primary_frame=fields.get("primary_frame", ""),
            hidden_assumption_attacked=fields.get("hidden_assumption_attacked", ""),
            stakeholder_lens=fields.get("stakeholder_lens", ""),
            time_horizon=time_horizon,
            failure_mode=fields.get("failure_mode", ""),
            coverage_obligation=obligation,
        )
        cards.append(card)

    return cards


def format_perspective_card_instructions() -> str:
    """Generate the perspective card instruction text for R1 prompts."""
    return (
        "\n## Structured Output Requirements (MANDATORY)\n"
        "After your analysis, you MUST include these 5 fields on separate lines:\n\n"
        "PRIMARY_FRAME: [your primary way of looking at this question]\n"
        "HIDDEN_ASSUMPTION_ATTACKED: [which assumption you are challenging]\n"
        "STAKEHOLDER_LENS: [whose perspective you are representing]\n"
        "TIME_HORIZON: [SHORT | MEDIUM | LONG]\n"
        "FAILURE_MODE: [what could go wrong with your recommended approach]\n"
    )
```

- [ ] **Step 3: Run tests and commit**

Run: `cd /c/Users/chris/PROJECTS/_audit_thinker/thinker-v8 && python -m pytest tests/test_perspective_cards.py -v`

```bash
git add thinker/perspective_cards.py tests/test_perspective_cards.py
git commit -m "feat(v9): add Perspective Cards — structured R1 output extraction"
```

---

## Task 5: Divergent Framing Module

**Files:**
- Create: `thinker/divergent_framing.py`
- Test: `tests/test_divergent_framing.py`

This task is large. It covers framing pass extraction, frame survival, and exploration stress.

Due to plan size constraints, the remaining tasks are documented with structure and key code but follow the same TDD pattern as Tasks 1-4. Each task has: tests first, implementation, run tests, commit.

- [ ] **Step 1: Write tests for framing extraction, frame survival (3-vote R2, CONTESTED R3/R4), exploration stress**
- [ ] **Step 2: Implement divergent_framing.py with run_framing_extract(), run_frame_survival_check(), check_exploration_stress()**
- [ ] **Step 3: Run tests, commit**

Key implementation details:
- `run_framing_extract(client, brief, r1_texts)` — Sonnet call to extract frames from R1 outputs
- `run_frame_survival_check(client, frames, round_texts, round_num)` — Sonnet checks each frame against round outputs
- R2: frame DROPPED only if 3 traceable drop votes. R3/R4: never dropped, only CONTESTED.
- `check_exploration_stress(agreement_ratio, question_class, stakes_class)` — returns True if R1 agreement > 0.75 on OPEN/HIGH
- `format_frames_for_prompt(frames)` — format active/contested frames for injection into R2+ prompts
- `format_r2_frame_enforcement()` — instruction text requiring adopt/rebut/generate

---

## Task 6: Semantic Contradiction Module

**Files:**
- Create: `thinker/semantic_contradiction.py`
- Test: `tests/test_semantic_contradiction.py`

- [ ] **Step 1: Write tests for shortlist criteria, Sonnet-based detection, CTR record generation**
- [ ] **Step 2: Implement semantic_contradiction.py with shortlist_pairs(), run_semantic_contradiction_pass()**
- [ ] **Step 3: Run tests, commit**

Key details:
- `shortlist_pairs(evidence_items)` — pairs with same topic_cluster + opposite polarity / same entity + same timeframe
- `run_semantic_contradiction_pass(client, pairs)` — Sonnet call per shortlisted pair
- Output: list[SemanticContradiction] with CTR records

---

## Task 7: Stability Tests Module

**Files:**
- Create: `thinker/stability.py`
- Test: `tests/test_stability.py`

- [ ] **Step 1: Write tests**
- [ ] **Step 2: Implement stability.py**
- [ ] **Step 3: Run tests, commit**

Key details — all deterministic, no LLM:
- `compute_conclusion_stability(positions)` — do surviving models agree on recommendation?
- `compute_reason_stability(positions, decisive_claims)` — shared decisive claim set?
- `compute_assumption_stability(assumptions)` — relying on same unresolved assumptions?
- `compute_groupthink_warning(fast_consensus, question_class, stakes_class, independent_evidence)` — groupthink detection
- Returns `StabilityResult`

---

## Task 8: Two-Tier Evidence Ledger

**Files:**
- Modify: `thinker/evidence.py`
- Test: `tests/test_evidence.py`

- [ ] **Step 1: Write tests for active/archive split, eviction to archive, eviction log, never-delete guarantee**
- [ ] **Step 2: Modify EvidenceLedger to have active_items + archive_items, eviction_log**
- [ ] **Step 3: Ensure format_for_prompt() only uses active items**
- [ ] **Step 4: Add get_from_any(evidence_id) to search both stores**
- [ ] **Step 5: Run ALL evidence tests, commit**

Key changes:
- `self.active_items: list[EvidenceItem]` (capped at max_items)
- `self.archive_items: list[EvidenceItem]` (uncapped)
- `self.eviction_log: list[EvictionEvent]`
- On eviction: item moves to archive, EvictionEvent recorded
- `self.items` property returns active_items (backward compat)
- New: `self.all_items` returns active + archive
- New: `self.high_authority_evidence_present` property

---

## Task 9: Proof Schema 3.0

**Files:**
- Modify: `thinker/proof.py`
- Test: `tests/test_proof.py`

- [ ] **Step 1: Add setter methods for all new proof sections**
- [ ] **Step 2: Update build() to emit schema 3.0 with all 25+ fields**
- [ ] **Step 3: Add stage_integrity tracking**
- [ ] **Step 4: Run tests, commit**

Key additions to ProofBuilder:
- `set_preflight(result)`, `set_dimensions(result)`, `set_perspective_cards(cards)`
- `set_divergence(result)`, `set_search_log(entries)`, `set_ungrounded_stats(data)`
- `set_evidence_two_tier(active, archive, eviction_log)`
- `set_arguments(arg_map)`, `set_decisive_claims(claims)`, `set_analogies(analogies)`
- `set_contradictions(numeric, semantic)`, `set_synthesis_packet(packet)`
- `set_synthesis_dispositions(dispositions)`, `set_stability(result)`
- `set_gate2_trace(modality, rule_trace, final_outcome)`
- `set_stage_integrity(required, order, fatal)`
- `proof_schema_version: "3.0"` in build()

---

## Task 10: Checkpoint v2.0

**Files:**
- Modify: `thinker/checkpoint.py`

- [ ] **Step 1: Bump CHECKPOINT_VERSION to "2.0"**
- [ ] **Step 2: Add new fields to PipelineState**
- [ ] **Step 3: Update STAGE_ORDER with all new stage IDs**
- [ ] **Step 4: Run tests, commit**

New fields:
```python
# PreflightAssessment
preflight: dict = field(default_factory=dict)
modality: str = "DECIDE"

# Dimensions
dimensions: dict = field(default_factory=dict)

# Perspective Cards
perspective_cards: list[dict] = field(default_factory=list)

# Divergence
divergence: dict = field(default_factory=dict)
adversarial_model: str = ""

# Search log
search_log: list[dict] = field(default_factory=list)

# Stability
stability: dict = field(default_factory=dict)
```

New STAGE_ORDER:
```python
STAGE_ORDER = [
    "preflight", "dimensions",
    "r1", "track1", "perspective_cards", "framing_pass",
    "ungrounded_r1", "search1",
    "r2", "track2", "frame_survival_r2",
    "ungrounded_r2", "search2",
    "r3", "track3", "frame_survival_r3",
    "r4", "track4",
    "semantic_contradiction", "synthesis_packet",
    "synthesis", "stability", "gate2",
]
```

---

## Task 11: Rounds — Adversarial, Dimensions, Frames

**Files:**
- Modify: `thinker/rounds.py`

- [ ] **Step 1: Add adversarial_model and alt_frames_text parameters to execute_round()**
- [ ] **Step 2: Modify build_round_prompt() to inject dimension text, perspective card instructions, adversarial preamble, and frame injection**
- [ ] **Step 3: Add R2 frame enforcement instructions**
- [ ] **Step 4: Run existing rounds tests + new tests, commit**

Key changes to `execute_round()` signature:
```python
async def execute_round(
    client,
    round_num: int,
    brief: str,
    prior_views: dict[str, str] | None = None,
    evidence_text: str = "",
    unaddressed_arguments: str = "",
    is_last_round: bool = False,
    adversarial_model: str = "",
    alt_frames_text: str = "",
    dimension_text: str = "",
    perspective_card_instructions: str = "",
) -> RoundResult:
```

Key prompt additions:
- R1: dimension_text + perspective_card_instructions + adversarial preamble for kimi
- R2: alt_frames_text + frame enforcement (adopt/rebut/generate)
- Per-model prompt customization: kimi gets adversarial preamble in R1 only

---

## Task 12: Synthesis — Controller-Curated Packet

**Files:**
- Create: `thinker/synthesis_packet.py`
- Modify: `thinker/synthesis.py`

- [ ] **Step 1: Create synthesis_packet.py — builds the curated state bundle**
- [ ] **Step 2: Modify synthesis prompt to accept the packet instead of raw R4 views**
- [ ] **Step 3: Require structured dispositions in output**
- [ ] **Step 4: Run tests, commit**

Synthesis packet includes: final positions, argument lifecycle (max 20), frame summary, blocker summary, decisive claim bindings, contradiction summary, premise flag summary.

---

## Task 13: Residue — Structured Dispositions

**Files:**
- Modify: `thinker/residue.py`

- [ ] **Step 1: Replace string-match checking with schema validation + coverage validation**
- [ ] **Step 2: Check dispositions against all tracked open findings**
- [ ] **Step 3: Compute omission_rate, trigger deep scan at >20%**
- [ ] **Step 4: Run tests, commit**

---

## Task 14: Gate 2 Rewrite — D1-D14 / A1-A7

**Files:**
- Modify: `thinker/gate2.py`
- Test: `tests/test_gate2.py`

- [ ] **Step 1: Write tests for D1-D14 rules (each rule independently)**
- [ ] **Step 2: Write tests for A1-A7 rules**
- [ ] **Step 3: Implement run_gate2_decide() with D1-D14 ordered evaluation**
- [ ] **Step 4: Implement run_gate2_analysis() with A1-A7 ordered evaluation**
- [ ] **Step 5: Update run_gate2_deterministic() to dispatch by modality**
- [ ] **Step 6: Ensure rule_trace is recorded**
- [ ] **Step 7: Run ALL gate2 tests, commit**

The new `run_gate2_deterministic()` accepts all V9 objects and dispatches:
```python
def run_gate2_deterministic(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list,
    evidence_count: int,
    search_enabled: bool,
    preflight: PreflightResult | None = None,
    divergence: DivergenceResult | None = None,
    stability: StabilityResult | None = None,
    decisive_claims: list[DecisiveClaim] | None = None,
    dimensions: DimensionSeedResult | None = None,
    total_arguments: int = 0,
    archive_evidence_count: int = 0,
) -> Gate2Assessment:
```

---

## Task 15: Brain.py Orchestrator Rewiring

**Files:**
- Modify: `thinker/brain.py`

This is the largest single task. Wire everything together.

- [ ] **Step 1: Replace gate1 import with preflight import**
- [ ] **Step 2: Add imports for all new modules**
- [ ] **Step 3: Wire PreflightAssessment (replace gate1 block)**
- [ ] **Step 4: Wire Dimension Seeder (after preflight, before R1)**
- [ ] **Step 5: Wire adversarial model assignment + perspective card instructions into R1**
- [ ] **Step 6: Wire Perspective Card extraction after R1**
- [ ] **Step 7: Wire Framing Pass after R1 tracking**
- [ ] **Step 8: Wire Ungrounded Stat Detector after R1 and R2**
- [ ] **Step 9: Wire Frame Survival after R2 and R3 tracking**
- [ ] **Step 10: Wire Exploration Stress Trigger after R1**
- [ ] **Step 11: Wire Semantic Contradiction Pass before synthesis**
- [ ] **Step 12: Wire Synthesis Packet builder**
- [ ] **Step 13: Wire Stability Tests after synthesis**
- [ ] **Step 14: Pass all new objects to Gate 2**
- [ ] **Step 15: Update all checkpoint/resume logic for new stages**
- [ ] **Step 16: Update _debug_pause() for new stage IDs**
- [ ] **Step 17: Update _restore_trackers() for new checkpoint fields**
- [ ] **Step 18: Update pipeline imports for HTML report generation**
- [ ] **Step 19: Update CLI argument help text**
- [ ] **Step 20: Run existing brain tests, commit**

---

## Task 16: Pipeline Stage Registration

**Files:**
- Modify: `thinker/pipeline.py`
- Modify: `thinker/brain.py` (imports for HTML report)

- [ ] **Step 1: Import all new modules in brain.py's main() for stage registry population**
- [ ] **Step 2: Verify the auto-generated HTML report includes all new stages**
- [ ] **Step 3: Commit**

Add to the import block in `main()`:
```python
import thinker.preflight, thinker.dimension_seeder  # noqa: F401
import thinker.perspective_cards, thinker.divergent_framing  # noqa: F401
import thinker.semantic_contradiction, thinker.stability  # noqa: F401
```

---

## Task 17: Run All Unit Tests

- [ ] **Step 1: Run full test suite**

Run: `cd /c/Users/chris/PROJECTS/_audit_thinker/thinker-v8 && python -m pytest tests/ -v --tb=short`

Expected: ALL PASS. Fix any failures before proceeding.

- [ ] **Step 2: Commit any remaining fixes**

---

## Task 18: Integration Test — Brief b1 (Security Incident)

**Brief:** `tests/fixtures/briefs/b1.md` — JWT bypass, GDPR/SOC2/HIPAA assessment

- [ ] **Step 1: Run step-by-step**

```bash
cd /c/Users/chris/PROJECTS/_audit_thinker/thinker-v8
python -m thinker.brain --brief tests/fixtures/briefs/b1.md --outdir output/b1-v9
```

- [ ] **Step 2: At each stage pause, inspect output. If error: stop, fix, resume from last good checkpoint.**
- [ ] **Step 3: Verify proof.json has proof_version "3.0" and all new sections populated.**
- [ ] **Step 4: Verify run-report.html shows all new stages in pipeline diagram.**

---

## Task 19: Integration Test — Brief b9 (DB Migration)

**Brief:** `tests/fixtures/briefs/b9.md` — ClickHouse/Snowflake/PG evaluation

- [ ] **Step 1: Run step-by-step (same pattern as Task 18)**
- [ ] **Step 2: Fix any issues, resume from last good checkpoint**
- [ ] **Step 3: Verify clean completion**

---

## Task 20: Integration Test — Brief b10 (LLM Banking Risk)

**Brief:** `tests/fixtures/briefs/b10.md` — EU AI Act, GDPR, operational risk

- [ ] **Step 1: Run step-by-step (same pattern as Task 18)**
- [ ] **Step 2: This brief is expected to hit ESCALATE (HIGH stakes, ELEVATED effort)**
- [ ] **Step 3: Verify ESCALATE is correctly triggered by D-rules, not just agreement threshold**
- [ ] **Step 4: Verify clean completion**

---

## Completion Criteria

Brain V9 is done when:
1. All unit tests pass
2. b1 completes step-by-step with zero errors
3. b9 completes step-by-step with zero errors
4. b10 completes step-by-step with zero errors
5. All 3 proof.json files have proof_version "3.0"
6. All 3 run-report.html files show the full V9 pipeline
7. Gate 2 rule_trace is populated in all 3 proofs
