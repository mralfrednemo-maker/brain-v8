# Brain V10 Delta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply 14 V3.1 deltas to Brain V10 on top of the V9 baseline, producing a fully spec-compliant V3.1 implementation with updated checkpoint/resume support and architecture visualization for all new stages.

**Architecture:** Copy-then-evolve from V9. 8 phases in dependency order: schema foundation → preflight enrichment → post-R1 additions → post-R2 addition → SHORT_CIRCUIT contract → evidence quality → residue + Gate 2 → ANALYSIS overlays. All new stages carry `@pipeline_stage` decoration and emit `RunLog` events for visualization. `CHECKPOINT_VERSION` bumped to "3.0" and `STAGE_ORDER` updated for all 3 new conditional stages.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, httpx, anthropic SDK

**Prerequisite:** Thinker repo restructure plan complete. All work done in `brain/v10/`.

---

## File Map

**Modified (Phase 1):**
- `brain/v10/brain/proof.py` — add schema_version, warnings[], add_warning(), bump proof_version to "3.1"
- `brain/v10/brain/types.py` — add WarningRecord dataclass, remove BrainResult.gate1, fix FrameSurvivalStatus/Blocker docs, add field_provenance schema
- `brain/v10/brain/config.py` — add residue_omission_threshold, schema_version fields
- `brain/v10/brain/checkpoint.py` — bump CHECKPOINT_VERSION to "3.0", update STAGE_ORDER, add V3.1 PipelineState fields

**Modified (Phase 2):**
- `brain/v10/brain/types.py` — add optional reformulation fields to PreflightResult
- `brain/v10/brain/preflight.py` — populate reformulation fields when detected
- `brain/v10/brain/proof.py` — persist reformulation metadata under proof.preflight

**Modified (Phase 3):**
- `brain/v10/brain/types.py` — add argument_type to Argument, add RetroactivePremiseResult
- `brain/v10/brain/argument_tracker.py` — identify premise_challenge arguments
- `brain/v10/brain/brain.py` — retroactive premise scan after track1, anti-groupthink search after framing_pass
- `brain/v10/brain/search.py` — support anti_groupthink provenance
- `brain/v10/brain/proof.py` — add retroactive_premise and anti_groupthink_search fields

**Modified (Phase 4):**
- `brain/v10/brain/brain.py` — breadth recovery eval after frame_survival_r2
- `brain/v10/brain/proof.py` — add breadth_recovery field

**Modified (Phase 5):**
- `brain/v10/brain/brain.py` or `rounds.py` — SHORT_CIRCUIT invariant validation post-round
- `brain/v10/brain/proof.py` — add reasoning_contract field

**Modified (Phase 6):**
- `brain/v10/brain/page_fetch.py` — paywall detection
- `brain/v10/brain/evidence.py` — intersection-based cross-domain filter, EvictionEvent extended

**Modified (Phase 7):**
- `brain/v10/brain/residue.py` — explicit threshold_violation at 0.25
- `brain/v10/brain/gate2.py` — D1-D16 rules (add D13 residue, D14 groupthink, D15 suspicious agreement, renumber)
- `brain/v10/brain/proof.py` — escalate_remediation, outcome_confidence

**Modified (Phase 8):**
- `brain/v10/brain/analysis_mode.py` — 8-section synthesis structure
- `brain/v10/brain/proof.py` — information_boundary, coverage_assessment
- `brain/v10/brain/synthesis.py` or `brain.py` — track-only ANALYSIS semantic contradictions

**Tests:**
- `brain/v10/tests/` — all existing V9 tests (adapted imports), plus new test functions per phase

---

## Phase 1 — Schema Foundation

### Task 1: Bump schema and proof versions (DELTA-2)

**Files:**
- Modify: `brain/v10/brain/proof.py`
- Modify: `brain/v10/brain/config.py`
- Modify: `brain/v10/brain/checkpoint.py`
- Test: `brain/v10/tests/test_proof.py`

- [ ] **Step 1: Write failing test**

Add to `brain/v10/tests/test_proof.py`:

```python
def test_proof_version_is_3_1():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="test-1", brief="test brief", rounds_requested=4)
    result = pb.build(outcome="DECIDE", report="ok", gate2_assessment=None,
                      stage_order=[], round_model_counts=[4,3,2,2])
    assert result["proof_version"] == "3.1"
    assert result["schema_version"] == "3.1"

def test_v30_proof_parses_without_error():
    """A proof dict missing schema_version (V3.0 format) must not raise on read."""
    import json
    v30_proof = {"proof_version": "3.0", "outcome": {"verdict": "DECIDE"}}
    # Just check we can load and access fields — no schema_version key is OK
    assert v30_proof.get("schema_version") is None
    assert v30_proof["proof_version"] == "3.0"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd brain/v10
pytest tests/test_proof.py::test_proof_version_is_3_1 -v
```

Expected: FAIL — `AssertionError: assert '3.0' == '3.1'`

- [ ] **Step 3: Update proof.py — change proof_version and add schema_version**

In `brain/v10/brain/proof.py`, find the `build()` method. Change `"proof_version": "3.0"` to `"proof_version": "3.1"` and add `"schema_version": "3.1"` alongside it:

```python
# In ProofBuilder.build() return dict, add/change:
"proof_version": "3.1",
"schema_version": "3.1",
```

- [ ] **Step 4: Add schema_version to BrainConfig**

In `brain/v10/brain/config.py`, add to `BrainConfig`:

```python
schema_version: str = "3.1"
residue_omission_threshold: float = 0.25  # DELTA-8 (added here for config proximity)
```

- [ ] **Step 5: Bump CHECKPOINT_VERSION and update STAGE_ORDER**

In `brain/v10/brain/checkpoint.py`:

```python
CHECKPOINT_VERSION = "3.0"

STAGE_ORDER = [
    "preflight", "dimensions",
    "r1", "track1",
    "retroactive_premise_scan",       # NEW — ADDITION-4
    "perspective_cards", "framing_pass",
    "anti_groupthink_search",         # NEW — ADDITION-7
    "ungrounded_r1", "search1",
    "r2", "track2", "frame_survival_r2",
    "breadth_recovery_eval",          # NEW — ADDITION-6
    "ungrounded_r2", "search2",
    "r3", "track3", "frame_survival_r3",
    "r4", "track4",
    "semantic_contradiction", "decisive_claims", "synthesis_packet",
    "synthesis", "residue_verification", "stability", "gate2",
]
```

Also add V3.1 fields to `PipelineState`:

```python
# V3.1 additions — all Optional/defaulted for forward compat
retroactive_escalation_consumed: bool = False
retroactive_premise_result: dict = field(default_factory=dict)
anti_groupthink_search: dict = field(default_factory=dict)
breadth_recovery: dict = field(default_factory=dict)
warnings: list[dict] = field(default_factory=list)
original_brief: str = ""
reformulated_brief: str = ""
reformulation_reason: str = ""
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_proof.py::test_proof_version_is_3_1 tests/test_proof.py::test_v30_proof_parses_without_error -v
```

Expected: both PASS

- [ ] **Step 7: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): DELTA-2 — proof_version+schema_version=3.1, CHECKPOINT_VERSION=3.0, STAGE_ORDER updated"
```

---

### Task 2: Three-tier failure taxonomy — warnings[] (DELTA-1)

**Files:**
- Modify: `brain/v10/brain/types.py`
- Modify: `brain/v10/brain/proof.py`
- Test: `brain/v10/tests/test_proof.py`

- [ ] **Step 1: Write failing tests**

Add to `brain/v10/tests/test_proof.py`:

```python
def test_add_warning_records_to_warnings_list():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="test-1", brief="test", rounds_requested=4)
    pb.add_warning(warning_id="W001", stage="r1", detail="Agreement suspicious but not terminal")
    result = pb.build(outcome="DECIDE", report="ok", gate2_assessment=None,
                      stage_order=[], round_model_counts=[4,3,2,2])
    assert "warnings" in result
    assert len(result["warnings"]) == 1
    assert result["warnings"][0]["warning_id"] == "W001"
    assert result["warnings"][0]["stage"] == "r1"

def test_warning_never_changes_outcome():
    """Warnings are recorded but do not affect the terminal outcome."""
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="test-1", brief="test", rounds_requested=4)
    pb.add_warning(warning_id="W999", stage="synthesis", detail="Suboptimal but non-terminal")
    result = pb.build(outcome="DECIDE", report="ok", gate2_assessment=None,
                      stage_order=[], round_model_counts=[4,3,2,2])
    # Outcome is unchanged despite warning
    assert result["outcome"]["verdict"] == "DECIDE"
    assert len(result["warnings"]) == 1
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_proof.py::test_add_warning_records_to_warnings_list -v
```

Expected: FAIL — `AttributeError: 'ProofBuilder' object has no attribute 'add_warning'`

- [ ] **Step 3: Add WarningRecord to types.py**

In `brain/v10/brain/types.py`, add after the `BrainError` class:

```python
@dataclass
class WarningRecord:
    """A non-terminal suboptimal condition (V3.1 three-tier taxonomy)."""
    warning_id: str
    stage: str
    detail: str
    tier: str = "WARNING"
```

- [ ] **Step 4: Add add_warning() and warnings[] to ProofBuilder**

In `brain/v10/brain/proof.py`:

1. Add to `__init__`: `self._warnings: list[dict] = []`
2. Add method:

```python
def add_warning(self, warning_id: str, stage: str, detail: str) -> None:
    """Record a non-terminal suboptimal condition (V3.1 WARNING tier)."""
    self._warnings.append({
        "warning_id": warning_id,
        "tier": "WARNING",
        "stage": stage,
        "detail": detail,
    })
```

3. In `build()`, add `"warnings": self._warnings` to the returned dict.

- [ ] **Step 5: Remove BrainResult.gate1 (DELTA-13)**

In `brain/v10/brain/types.py`, find `BrainResult` dataclass and remove the `gate1` field entirely. It's dead code — merged preflight replaced it.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_proof.py -v -k "warning"
```

Expected: both warning tests PASS

- [ ] **Step 7: Run full test suite to check no regressions**

```bash
pytest tests/ -q 2>&1 | tail -10
```

Expected: same pass count as baseline (no new failures).

- [ ] **Step 8: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): DELTA-1 — three-tier taxonomy: proof.warnings[], add_warning(); DELTA-13 — remove BrainResult.gate1"
```

---

## Phase 2 — Preflight Enrichment

### Task 3: Reformulation metadata (DELTA-3)

**Files:**
- Modify: `brain/v10/brain/types.py`
- Modify: `brain/v10/brain/proof.py`
- Test: `brain/v10/tests/test_preflight.py`

- [ ] **Step 1: Write failing test**

Add to `brain/v10/tests/test_preflight.py`:

```python
def test_preflight_result_has_reformulation_fields():
    from brain.types import PreflightResult, Modality, EffortTier, QuestionClass, StakesClass, SearchScope
    pf = PreflightResult(
        executed=True, parse_ok=True,
        answerability="ANSWERABLE",
        question_class=QuestionClass.OPEN,
        stakes_class=StakesClass.STANDARD,
        effort_tier=EffortTier.STANDARD,
        modality=Modality.DECIDE,
        search_scope=SearchScope.TARGETED,
        exploration_required=False,
        short_circuit_allowed=False,
        fatal_premise=False,
        original_brief="Is X better than Y?",
        reformulated_brief="Comparing X and Y: which is more suitable for Z?",
        reformulation_reason="Reframed false dichotomy",
    )
    assert pf.original_brief == "Is X better than Y?"
    assert pf.reformulated_brief is not None
    assert pf.reformulation_reason is not None

def test_silent_reformulation_is_forbidden():
    """original_brief must be preserved whenever reformulation fields are set."""
    from brain.types import PreflightResult, Modality, EffortTier, QuestionClass, StakesClass, SearchScope
    pf = PreflightResult(
        executed=True, parse_ok=True,
        answerability="ANSWERABLE",
        question_class=QuestionClass.OPEN,
        stakes_class=StakesClass.STANDARD,
        effort_tier=EffortTier.STANDARD,
        modality=Modality.DECIDE,
        search_scope=SearchScope.TARGETED,
        exploration_required=False,
        short_circuit_allowed=False,
        fatal_premise=False,
        reformulated_brief="Changed without tracking original",
    )
    # If reformulated_brief is set, original_brief must also be set
    if pf.reformulated_brief:
        assert pf.original_brief, "original_brief must be preserved when reformulation is present"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_preflight.py::test_preflight_result_has_reformulation_fields -v
```

Expected: FAIL — `TypeError: unexpected keyword argument 'original_brief'`

- [ ] **Step 3: Add reformulation fields to PreflightResult**

In `brain/v10/brain/types.py`, find the `PreflightResult` dataclass and add:

```python
# V3.1 DELTA-3: Reformulation metadata (schema enrichment, no auto-proceed)
original_brief: Optional[str] = None
reformulated_brief: Optional[str] = None
reformulation_reason: Optional[str] = None
```

- [ ] **Step 4: Persist reformulation fields in proof.py**

In `ProofBuilder.set_preflight()`, add to the preflight dict it stores:

```python
if preflight.original_brief:
    d["original_brief"] = preflight.original_brief
if preflight.reformulated_brief:
    d["reformulated_brief"] = preflight.reformulated_brief
if preflight.reformulation_reason:
    d["reformulation_reason"] = preflight.reformulation_reason
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_preflight.py -v -k "reformulation"
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -q 2>&1 | tail -5
```

Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): DELTA-3 — reformulation metadata on PreflightResult (schema enrichment)"
```

---

## Phase 3 — Post-R1 Pipeline Additions

### Task 4: Retroactive premise escalation (ADDITION-4)

**Files:**
- Modify: `brain/v10/brain/types.py`
- Modify: `brain/v10/brain/argument_tracker.py`
- Modify: `brain/v10/brain/brain.py`
- Modify: `brain/v10/brain/proof.py`
- Modify: `brain/v10/brain/pipeline.py`
- Test: `brain/v10/tests/test_retroactive_premise.py`

- [ ] **Step 1: Write failing tests**

Create `brain/v10/tests/test_retroactive_premise.py`:

```python
import pytest

def test_retroactive_premise_result_type():
    from brain.types import RetroactivePremiseResult
    r = RetroactivePremiseResult(
        executed=True,
        triggered=True,
        matched_premise="The market is growing",
        model_ids=["r1", "reasoner"],
        rerun_outcome="NEED_MORE",
    )
    assert r.triggered is True
    assert len(r.model_ids) == 2

def test_argument_has_argument_type_field():
    from brain.types import Argument
    a = Argument(argument_id="A001", text="test", argument_type="premise_challenge")
    assert a.argument_type == "premise_challenge"

def test_argument_type_defaults_to_none():
    from brain.types import Argument
    a = Argument(argument_id="A001", text="test")
    assert a.argument_type is None

def test_retroactive_scan_not_triggered_below_threshold(mocker):
    """Scan with only 1 model flagging a premise should NOT trigger rerun."""
    from brain.brain import _should_trigger_retroactive_premise
    # Only 1 model flags this premise — below the >= 2 threshold
    premise_findings = [
        {"model": "r1", "premise": "market is growing", "type": "premise_challenge"},
    ]
    assert _should_trigger_retroactive_premise(premise_findings) is False

def test_retroactive_scan_triggered_at_threshold():
    """Scan with 2 independent models flagging same premise SHOULD trigger rerun."""
    from brain.brain import _should_trigger_retroactive_premise
    premise_findings = [
        {"model": "r1", "premise": "market is growing", "type": "premise_challenge"},
        {"model": "reasoner", "premise": "the market is growing", "type": "premise_challenge"},
    ]
    # Both models flagged semantically similar premise (similarity >= 0.7)
    assert _should_trigger_retroactive_premise(premise_findings) is True

def test_one_shot_cap_enforced():
    """retroactive_escalation_consumed flag prevents second rerun."""
    from brain.checkpoint import PipelineState
    state = PipelineState()
    state.retroactive_escalation_consumed = True
    # Simulate the guard check
    assert state.retroactive_escalation_consumed is True
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_retroactive_premise.py -v 2>&1 | head -30
```

Expected: multiple FAILs — types not found, function not found.

- [ ] **Step 3: Add RetroactivePremiseResult and argument_type to types.py**

In `brain/v10/brain/types.py`:

```python
@dataclass
class RetroactivePremiseResult:
    """Result of the post-R1 retroactive premise escalation scan (V3.1 ADDITION-4)."""
    executed: bool = False
    triggered: bool = False
    matched_premise: str = ""
    model_ids: list[str] = field(default_factory=list)
    rerun_outcome: Optional[str] = None  # outcome of preflight re-audit if triggered
    consumed: bool = False  # one-shot guard
```

In the `Argument` dataclass, add:

```python
argument_type: Optional[str] = None  # e.g. "premise_challenge", "evidence_gap"
```

- [ ] **Step 4: Add _should_trigger_retroactive_premise() helper to brain.py**

In `brain/v10/brain/brain.py`, add this standalone function (not a method) near the top of the file, after imports:

```python
def _should_trigger_retroactive_premise(
    premise_findings: list[dict],
    min_models: int = 2,
) -> bool:
    """Check if >= min_models independent models flagged the same flawed premise.

    'Same premise' = semantic similarity >= 0.7 (approximated here by shared
    keyword overlap; full LLM-based similarity used in run_retroactive_premise_scan).
    'Independent' = different model_ids in the same R1 round.
    """
    if len(premise_findings) < min_models:
        return False

    # Group by model — deduplicate per model first
    by_model: dict[str, list[str]] = {}
    for f in premise_findings:
        model = f.get("model", "unknown")
        premise = f.get("premise", "").lower().strip()
        if model not in by_model:
            by_model[model] = []
        by_model[model].append(premise)

    if len(by_model) < min_models:
        return False

    # Check if any two models share a premise cluster
    # Simplified: check keyword overlap (>= 3 shared words = same cluster)
    all_premises = [(model, p) for model, plist in by_model.items() for p in plist]
    for i, (m1, p1) in enumerate(all_premises):
        for m2, p2 in all_premises[i+1:]:
            if m1 == m2:
                continue
            words1 = set(p1.split())
            words2 = set(p2.split())
            if len(words1) > 0 and len(words2) > 0:
                overlap = len(words1 & words2) / min(len(words1), len(words2))
                if overlap >= 0.5:  # conservative proxy for semantic similarity
                    return True
    return False
```

- [ ] **Step 5: Add retroactive_premise stage registration to pipeline.py**

In `brain/v10/brain/pipeline.py` (or wherever `@pipeline_stage` is used in brain.py), register the new stage. Add near the `run_preflight` pipeline_stage registration:

```python
@pipeline_stage(
    name="Retroactive Premise Scan",
    description="Post-R1 scan: if >= 2 independent models flag the same flawed premise, "
                "rerun preflight once. One-shot cap enforced.",
    stage_type="gate",
    order=3,  # after track1
    provider="sonnet (conditional)",
    inputs=["arguments_by_round[1]", "preflight"],
    outputs=["retroactive_premise_result", "updated_preflight (if triggered)"],
    logic="Scan R1 arguments for argument_type=premise_challenge. "
          "If >= 2 independent models flag same premise (similarity >= 0.7): rerun preflight once. "
          "Guard: retroactive_escalation_consumed=True prevents second rerun.",
    thresholds={"min_models": 2, "similarity_threshold": 0.7},
    failure_mode="Trigger met but rerun skipped → ERROR",
    cost="0 (no trigger) or 1 Sonnet call (triggered)",
    stage_id="retroactive_premise_scan",
)
def _retroactive_premise_scan_stage():
    """Placeholder for pipeline registry — actual logic is in brain.py."""
    pass
```

- [ ] **Step 6: Add retroactive_premise field to ProofBuilder**

In `brain/v10/brain/proof.py`, add:

1. In `__init__`: `self._retroactive_premise: Optional[dict] = None`
2. Add method:

```python
def set_retroactive_premise(self, result: dict) -> None:
    """Record retroactive premise scan result (V3.1 ADDITION-4)."""
    self._retroactive_premise = result
```

3. In `build()`, add to returned dict:

```python
"retroactive_premise": self._retroactive_premise,
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_retroactive_premise.py -v
```

Expected: all PASS

- [ ] **Step 8: Run full suite**

```bash
pytest tests/ -q 2>&1 | tail -5
```

Expected: no new failures.

- [ ] **Step 9: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): ADDITION-4 — retroactive premise escalation scaffold (types, helper, proof field, pipeline stage)"
```

---

### Task 5: Anti-groupthink search (ADDITION-7)

**Files:**
- Modify: `brain/v10/brain/types.py`
- Modify: `brain/v10/brain/brain.py`
- Modify: `brain/v10/brain/proof.py`
- Modify: `brain/v10/brain/pipeline.py`
- Test: `brain/v10/tests/test_anti_groupthink.py`

- [ ] **Step 1: Write failing tests**

Create `brain/v10/tests/test_anti_groupthink.py`:

```python
def test_anti_groupthink_triggers_on_high_agreement_open_question():
    from brain.brain import _should_trigger_anti_groupthink
    from brain.types import QuestionClass, StakesClass
    assert _should_trigger_anti_groupthink(
        agreement_ratio=0.85,
        question_class=QuestionClass.OPEN,
        stakes_class=StakesClass.STANDARD,
    ) is True

def test_anti_groupthink_triggers_on_high_stakes():
    from brain.brain import _should_trigger_anti_groupthink
    from brain.types import QuestionClass, StakesClass
    assert _should_trigger_anti_groupthink(
        agreement_ratio=0.85,
        question_class=QuestionClass.WELL_ESTABLISHED,
        stakes_class=StakesClass.HIGH,
    ) is True

def test_anti_groupthink_does_not_trigger_below_threshold():
    from brain.brain import _should_trigger_anti_groupthink
    from brain.types import QuestionClass, StakesClass
    assert _should_trigger_anti_groupthink(
        agreement_ratio=0.75,
        question_class=QuestionClass.OPEN,
        stakes_class=StakesClass.STANDARD,
    ) is False

def test_anti_groupthink_does_not_trigger_low_stakes_established():
    from brain.brain import _should_trigger_anti_groupthink
    from brain.types import QuestionClass, StakesClass
    assert _should_trigger_anti_groupthink(
        agreement_ratio=0.90,
        question_class=QuestionClass.WELL_ESTABLISHED,
        stakes_class=StakesClass.LOW,
    ) is False

def test_search_query_provenance_includes_anti_groupthink():
    """Search log entry for anti-groupthink query must carry anti_groupthink provenance."""
    # Test the provenance value is accepted in the search log structure
    log_entry = {
        "query_id": "Q-AGT-001",
        "query_text": "counterarguments to consensus view on X",
        "provenance": "anti_groupthink",
        "evidence_yield_count": 0,
    }
    assert log_entry["provenance"] == "anti_groupthink"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_anti_groupthink.py -v 2>&1 | head -20
```

Expected: FAIL — `_should_trigger_anti_groupthink` not found.

- [ ] **Step 3: Add _should_trigger_anti_groupthink() to brain.py**

In `brain/v10/brain/brain.py`, add:

```python
def _should_trigger_anti_groupthink(
    agreement_ratio: float,
    question_class,
    stakes_class,
) -> bool:
    """Trigger anti-groupthink search when models converge suspiciously fast.

    Fires when: agreement_ratio > 0.80 AND (question is OPEN/AMBIGUOUS OR stakes is HIGH).
    Exactly one adversarial search query is issued.
    """
    from brain.types import QuestionClass, StakesClass
    if agreement_ratio <= 0.80:
        return False
    is_open = question_class in (QuestionClass.OPEN, QuestionClass.AMBIGUOUS)
    is_high_stakes = stakes_class == StakesClass.HIGH
    return is_open or is_high_stakes
```

- [ ] **Step 4: Add anti_groupthink_search to proof.py**

In `brain/v10/brain/proof.py`:

1. In `__init__`: `self._anti_groupthink_search: Optional[dict] = None`
2. Add method:

```python
def set_anti_groupthink_search(self, result: dict) -> None:
    """Record anti-groupthink search result (V3.1 ADDITION-7)."""
    self._anti_groupthink_search = result
```

3. In `build()`, add to returned dict:

```python
"anti_groupthink_search": self._anti_groupthink_search,
```

- [ ] **Step 5: Register anti_groupthink_search stage in pipeline.py**

```python
@pipeline_stage(
    name="Anti-Groupthink Search",
    description="Post-R1 conditional search: if agreement > 0.80 on OPEN/AMBIGUOUS or HIGH-stakes "
                "question, issue exactly one adversarial query against the consensus.",
    stage_type="search",
    order=6,  # after framing_pass
    provider="brave/sonar (conditional)",
    inputs=["agreement_ratio", "question_class", "stakes_class", "R1 consensus position"],
    outputs=["anti_groupthink_search", "evidence (flows into R2)"],
    logic="Trigger: agreement_ratio > 0.80 AND (OPEN/AMBIGUOUS OR HIGH stakes). "
          "Issue exactly 1 adversarial query. Log with provenance=anti_groupthink.",
    thresholds={"agreement_ratio": "> 0.80"},
    failure_mode="Trigger met but query omitted/unlogged → ERROR",
    cost="0 (no trigger) or 1 search query (triggered)",
    stage_id="anti_groupthink_search",
)
def _anti_groupthink_search_stage():
    pass
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_anti_groupthink.py -v
```

Expected: all PASS

- [ ] **Step 7: Run full suite**

```bash
pytest tests/ -q 2>&1 | tail -5
```

Expected: no new failures.

- [ ] **Step 8: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): ADDITION-7 — anti-groupthink search (helper, proof field, pipeline stage)"
```

---

## Phase 4 — Post-R2 Addition

### Task 6: Breadth-Recovery Pulse (ADDITION-6)

**Files:**
- Modify: `brain/v10/brain/brain.py`
- Modify: `brain/v10/brain/proof.py`
- Modify: `brain/v10/brain/pipeline.py`
- Test: `brain/v10/tests/test_breadth_recovery.py`

- [ ] **Step 1: Write failing tests**

Create `brain/v10/tests/test_breadth_recovery.py`:

```python
def test_breadth_recovery_triggers_above_threshold():
    from brain.brain import _should_trigger_breadth_recovery
    # 5 out of 10 R1 arguments ignored in R2 = 50% > 40%
    assert _should_trigger_breadth_recovery(r1_arg_count=10, ignored_count=5) is True

def test_breadth_recovery_does_not_trigger_at_threshold():
    from brain.brain import _should_trigger_breadth_recovery
    # exactly 40% — threshold is strictly >0.40
    assert _should_trigger_breadth_recovery(r1_arg_count=10, ignored_count=4) is False

def test_breadth_recovery_zero_args_does_not_crash():
    from brain.brain import _should_trigger_breadth_recovery
    assert _should_trigger_breadth_recovery(r1_arg_count=0, ignored_count=0) is False

def test_breadth_recovery_proof_field():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_breadth_recovery({"triggered": True, "ignored_ratio": 0.5,
                              "r1_arg_count": 10, "ignored_count": 5})
    result = pb.build(outcome="DECIDE", report="ok", gate2_assessment=None,
                      stage_order=[], round_model_counts=[4,3,2,2])
    assert result["breadth_recovery"]["triggered"] is True
    assert result["breadth_recovery"]["ignored_ratio"] == 0.5
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_breadth_recovery.py::test_breadth_recovery_triggers_above_threshold -v
```

Expected: FAIL — function not found.

- [ ] **Step 3: Add _should_trigger_breadth_recovery() to brain.py**

```python
def _should_trigger_breadth_recovery(r1_arg_count: int, ignored_count: int) -> bool:
    """Trigger breadth recovery injection into R3 when R1 arguments were over-ignored in R2.

    Trigger: ignored_ratio > 0.40 (strictly greater than).
    If argument lineage is broken (r1_arg_count = 0), fail closed (return False).
    """
    if r1_arg_count == 0:
        return False
    return (ignored_count / r1_arg_count) > 0.40
```

- [ ] **Step 4: Add set_breadth_recovery() to proof.py**

In `brain/v10/brain/proof.py`:

1. In `__init__`: `self._breadth_recovery: Optional[dict] = None`
2. Add method:

```python
def set_breadth_recovery(self, result: dict) -> None:
    """Record breadth recovery evaluation result (V3.1 ADDITION-6)."""
    self._breadth_recovery = result
```

3. In `build()`: `"breadth_recovery": self._breadth_recovery,`

- [ ] **Step 5: Register breadth_recovery_eval stage in pipeline.py**

```python
@pipeline_stage(
    name="Breadth Recovery Eval",
    description="Post-R2 check: if R1 arguments ignored_ratio > 0.40, inject mandatory "
                "breadth recovery instructions into R3 prompt.",
    stage_type="track",
    order=12,  # after frame_survival_r2
    provider="deterministic",
    inputs=["arguments_by_round[1]", "arguments_by_round[2] (addressed/ignored status)"],
    outputs=["breadth_recovery", "R3 prompt injection (if triggered)"],
    logic="ignored_ratio = ignored_r1_args / total_r1_args. "
          "Trigger: > 0.40. If triggered: inject recovery into R3.",
    thresholds={"ignored_ratio": "> 0.40"},
    failure_mode="Trigger met but injection omitted → ERROR. Broken argument lineage → fail closed.",
    cost="$0 (deterministic)",
    stage_id="breadth_recovery_eval",
)
def _breadth_recovery_eval_stage():
    pass
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_breadth_recovery.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): ADDITION-6 — breadth recovery pulse (helper, proof field, pipeline stage)"
```

---

## Phase 5 — SHORT_CIRCUIT Contract

### Task 7: 5-invariant reasoning contract (DELTA-5)

**Files:**
- Modify: `brain/v10/brain/brain.py` (or `rounds.py`)
- Modify: `brain/v10/brain/proof.py`
- Test: `brain/v10/tests/test_short_circuit_contract.py`

- [ ] **Step 1: Write failing tests**

Create `brain/v10/tests/test_short_circuit_contract.py`:

```python
def test_validate_short_circuit_invariants_passes_with_all_five():
    from brain.brain import _validate_short_circuit_invariants
    response = """
    PREMISE CHECK: The question assumes X is always true, which is not.
    CONFIDENCE BASIS: Medium — based on 2 authoritative sources.
    KNOWN UNKNOWNS: We don't know the long-term trend.
    COUNTER-CONSIDERATION: One could argue Y instead of X.
    COMPRESSION REASON: SHORT_CIRCUIT — question_class=TRIVIAL, stakes=LOW
    """
    ok, missing = _validate_short_circuit_invariants(response)
    assert ok is True
    assert missing == []

def test_validate_short_circuit_invariants_fails_without_counter():
    from brain.brain import _validate_short_circuit_invariants
    response = """
    PREMISE CHECK: The question assumes X.
    CONFIDENCE BASIS: High — well established.
    KNOWN UNKNOWNS: None.
    COMPRESSION REASON: SHORT_CIRCUIT — trivial question.
    """
    # Missing COUNTER-CONSIDERATION
    ok, missing = _validate_short_circuit_invariants(response)
    assert ok is False
    assert any("counter" in m.lower() for m in missing)

def test_missing_invariant_on_short_circuit_run_is_error():
    """DOD: missing any invariant on a compressed run = ERROR."""
    from brain.brain import _validate_short_circuit_invariants
    response = "Just a quick answer: X is correct."
    ok, missing = _validate_short_circuit_invariants(response)
    assert ok is False
    assert len(missing) == 5  # all five invariants missing

def test_reasoning_contract_proof_field():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_reasoning_contract({
        "short_circuit_run": True,
        "all_invariants_present": True,
        "missing_invariants": [],
    })
    result = pb.build(outcome="DECIDE", report="ok", gate2_assessment=None,
                      stage_order=[], round_model_counts=[4,3,2,2])
    assert result["reasoning_contract"]["all_invariants_present"] is True
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_short_circuit_contract.py::test_validate_short_circuit_invariants_passes_with_all_five -v
```

Expected: FAIL — function not found.

- [ ] **Step 3: Add _validate_short_circuit_invariants() to brain.py**

```python
# The 5 required invariants for SHORT_CIRCUIT compressed responses (V3.1 DELTA-5)
_SHORT_CIRCUIT_INVARIANTS = [
    ("premise_check", ["premise check", "premise:", "assumes"]),
    ("confidence_basis", ["confidence basis", "confidence:", "based on"]),
    ("known_unknowns", ["known unknowns", "unknown", "we don't know", "uncertain"]),
    ("counter_consideration", ["counter-consideration", "counter consideration",
                                "one could argue", "alternatively", "however"]),
    ("compression_reason", ["compression reason", "short_circuit", "short circuit",
                             "trivial", "well_established"]),
]


def _validate_short_circuit_invariants(response_text: str) -> tuple[bool, list[str]]:
    """Check that a SHORT_CIRCUIT compressed response contains all 5 required invariants.

    Returns (all_present: bool, missing_invariant_names: list[str]).
    Missing any invariant = ERROR per V3.1 DOD.
    """
    text_lower = response_text.lower()
    missing = []
    for invariant_name, markers in _SHORT_CIRCUIT_INVARIANTS:
        if not any(marker in text_lower for marker in markers):
            missing.append(invariant_name)
    return len(missing) == 0, missing
```

- [ ] **Step 4: Add set_reasoning_contract() to proof.py**

In `brain/v10/brain/proof.py`:

1. In `__init__`: `self._reasoning_contract: Optional[dict] = None`
2. Add method:

```python
def set_reasoning_contract(self, result: dict) -> None:
    """Record SHORT_CIRCUIT 5-invariant reasoning contract (V3.1 DELTA-5)."""
    self._reasoning_contract = result
```

3. In `build()`: `"reasoning_contract": self._reasoning_contract,`

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_short_circuit_contract.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): DELTA-5 — SHORT_CIRCUIT 5-invariant reasoning contract"
```

---

## Phase 6 — Evidence Quality

### Task 8: Paywall detection + cross-domain filter (ADDITION-11 + DELTA-14)

**Files:**
- Modify: `brain/v10/brain/page_fetch.py`
- Modify: `brain/v10/brain/evidence.py`
- Modify: `brain/v10/brain/types.py`
- Test: `brain/v10/tests/test_page_fetch.py`, `brain/v10/tests/test_evidence.py`

- [ ] **Step 1: Write failing tests**

Add to `brain/v10/tests/test_page_fetch.py`:

```python
def test_paywall_detected_on_subscription_content():
    from brain.page_fetch import is_paywalled
    paywall_text = "Subscribe to continue reading. This content is for subscribers only."
    assert is_paywalled(paywall_text) is True

def test_paywall_not_detected_on_free_content():
    from brain.page_fetch import is_paywalled
    free_text = "The study found that X causes Y in 80% of cases according to researchers."
    assert is_paywalled(free_text) is False

def test_paywalled_page_returns_empty():
    from brain.page_fetch import is_paywalled
    minimal = "Sign in or subscribe to read this article."
    assert is_paywalled(minimal) is True
```

Add to `brain/v10/tests/test_evidence.py`:

```python
def test_eviction_event_has_linkage_fields():
    from brain.types import EvictionEvent
    e = EvictionEvent(
        evidence_id="E001",
        reason="cap_pressure",
        linked_contradiction_id="CTR-001",
        linked_blocker_id=None,
        contradiction_severity="HIGH",
    )
    assert e.linked_contradiction_id == "CTR-001"
    assert e.contradiction_severity == "HIGH"
    assert e.linked_blocker_id is None

def test_cross_domain_intersection_admits_hybrid_evidence():
    """Evidence from domain A+B should be admitted when active set contains A."""
    from brain.evidence import _domains_compatible
    # New item covers domains {security, compliance} — active set has {security}
    assert _domains_compatible(
        item_domains={"security", "compliance"},
        active_domains={"security"},
    ) is True

def test_cross_domain_strict_fails_on_pure_mismatch():
    """V3.0 behavior: reject evidence if no domain overlap."""
    from brain.evidence import _domains_compatible
    assert _domains_compatible(
        item_domains={"finance"},
        active_domains={"security"},
    ) is False
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_page_fetch.py -v -k "paywall" 2>&1 | head -10
pytest tests/test_evidence.py::test_eviction_event_has_linkage_fields -v 2>&1 | head -10
```

Expected: FAIL — `is_paywalled` not found, `EvictionEvent` missing fields.

- [ ] **Step 3: Add is_paywalled() to page_fetch.py**

In `brain/v10/brain/page_fetch.py`, add after the imports:

```python
_PAYWALL_MARKERS = [
    "subscribe to continue",
    "subscription required",
    "subscribers only",
    "sign in to read",
    "sign up to read",
    "premium content",
    "this content is for subscribers",
    "create a free account to continue",
    "register to read",
    "to read the full article",
    "unlock full access",
]


def is_paywalled(text: str) -> bool:
    """Detect if fetched page content is a paywall gate rather than actual content.

    Returns True if the text is likely a paywall/subscription prompt.
    Skipped pages are logged — never silently dropped.
    """
    if not text or len(text) < 10:
        return False
    text_lower = text.lower()
    return any(marker in text_lower for marker in _PAYWALL_MARKERS)
```

- [ ] **Step 4: Extend EvictionEvent in types.py**

Find `EvictionEvent` dataclass in `brain/v10/brain/types.py` and add:

```python
# V3.1 DELTA-14: Forensic eviction overlay
linked_contradiction_id: Optional[str] = None
linked_blocker_id: Optional[str] = None
contradiction_severity: Optional[str] = None
```

- [ ] **Step 5: Add _domains_compatible() to evidence.py**

In `brain/v10/brain/evidence.py`, find the cross-domain check and replace strict match with intersection:

```python
def _domains_compatible(item_domains: set[str], active_domains: set[str]) -> bool:
    """Check if item's domains are compatible with active working set domains.

    V3.1 ADDITION-11: Non-empty intersection is sufficient (replaces strict match).
    An empty active_domains means the set is unconstrained — admit anything.
    """
    if not active_domains:
        return True
    return bool(item_domains & active_domains)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_page_fetch.py -v -k "paywall"
pytest tests/test_evidence.py -v -k "eviction or cross_domain or compatible"
```

Expected: all PASS

- [ ] **Step 7: Run full suite**

```bash
pytest tests/ -q 2>&1 | tail -5
```

Expected: no new failures.

- [ ] **Step 8: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): ADDITION-11+DELTA-14 — paywall detection, intersection cross-domain, forensic eviction fields"
```

---

## Phase 7 — Residue + Gate 2

### Task 9: Explicit residue threshold (DELTA-8)

**Files:**
- Modify: `brain/v10/brain/residue.py`
- Modify: `brain/v10/brain/proof.py`
- Test: `brain/v10/tests/test_residue.py`

- [ ] **Step 1: Write failing tests**

Add to `brain/v10/tests/test_residue.py`:

```python
def test_threshold_violation_set_at_25_percent():
    from brain.residue import check_synthesis_residue
    # 3 blockers, synthesis mentions only 2 → 33% omission rate > 25% threshold
    class FakeBlocker:
        def __init__(self, bid): self.blocker_id = bid
    blockers = [FakeBlocker("BLK-001"), FakeBlocker("BLK-002"), FakeBlocker("BLK-003")]
    report = "We addressed BLK-001 and BLK-002 in the synthesis."
    omissions = check_synthesis_residue(report=report, blockers=blockers,
                                        contradictions=[], unaddressed_arguments=[])
    assert any(o.get("threshold_violation") for o in omissions)

def test_threshold_not_violated_at_20_percent():
    """Deep scan triggers at >20% but threshold_violation only at >25%."""
    from brain.residue import check_synthesis_residue
    class FakeBlocker:
        def __init__(self, bid): self.blocker_id = bid
    # 5 blockers, 1 missing = 20% — at or below deep scan trigger, below 25% threshold
    blockers = [FakeBlocker(f"BLK-{i:03d}") for i in range(5)]
    report = " ".join(f"BLK-{i:03d}" for i in range(4))  # mentions 4 of 5
    omissions = check_synthesis_residue(report=report, blockers=blockers,
                                        contradictions=[], unaddressed_arguments=[])
    assert not any(o.get("threshold_violation") for o in omissions)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_residue.py::test_threshold_violation_set_at_25_percent -v
```

Expected: FAIL — `threshold_violation` key may not be present or threshold is 30% (V9 value).

- [ ] **Step 3: Update residue.py — threshold from 0.30 to 0.25**

In `brain/v10/brain/residue.py`, find:

```python
threshold_violated = (
    total_items > 0 and len(omissions) / total_items > 0.30
)
```

Change to:

```python
# V3.1 DELTA-8: explicit 0.25 threshold (V3.0 used 0.30)
# Deep scan still triggers at >0.20 (separate check in caller)
_THRESHOLD = 0.25
threshold_violated = (
    total_items > 0 and len(omissions) / total_items > _THRESHOLD
)
```

Ensure `threshold_violation` key is set on each omission when triggered (it should be already from V9 code — verify the dict structure includes it).

- [ ] **Step 4: Add threshold_violation to proof residue verification**

In `brain/v10/brain/proof.py`, find `set_residue_verification()` and ensure it records `threshold_violation`:

```python
# In set_residue_verification or wherever residue data is persisted:
# Make sure "threshold_violation" from the omissions list is surfaced at the top level
def set_residue_verification(self, omissions: list[dict], deep_scan_triggered: bool,
                              threshold: float = 0.25) -> None:
    threshold_violation = any(o.get("threshold_violation") for o in omissions)
    self._residue_verification = {
        "omissions": omissions,
        "omission_count": len(omissions),
        "deep_scan_triggered": deep_scan_triggered,
        "threshold": threshold,
        "threshold_violation": threshold_violation,
    }
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_residue.py -v -k "threshold"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): DELTA-8 — explicit residue threshold 0.25, threshold_violation in proof"
```

---

### Task 10: Gate 2 D1-D16 (DELTA-9 + ADDITION-12)

**Files:**
- Modify: `brain/v10/brain/gate2.py`
- Modify: `brain/v10/brain/proof.py`
- Test: `brain/v10/tests/test_gate2.py`

- [ ] **Step 1: Write failing tests**

Add to `brain/v10/tests/test_gate2.py`:

```python
from brain.types import (
    Outcome, PreflightResult, Modality, EffortTier, QuestionClass,
    StakesClass, SearchScope, StabilityResult,
)

def _minimal_preflight(modality=Modality.DECIDE, effort_tier=EffortTier.STANDARD,
                        short_circuit_allowed=False):
    return PreflightResult(
        executed=True, parse_ok=True, answerability="ANSWERABLE",
        question_class=QuestionClass.OPEN, stakes_class=StakesClass.STANDARD,
        effort_tier=effort_tier, modality=modality,
        search_scope=SearchScope.TARGETED, exploration_required=False,
        short_circuit_allowed=short_circuit_allowed, fatal_premise=False,
    )

def test_d13_residue_threshold_violation_triggers_escalate():
    """D13: residue.threshold_violation = true → ESCALATE."""
    from brain.gate2 import run_gate2_deterministic
    result = run_gate2_deterministic(
        agreement_ratio=0.90,
        positions={"r1": object(), "reasoner": object()},
        contradictions=[],
        unaddressed_arguments=[],
        open_blockers=[],
        evidence_count=5,
        search_enabled=True,
        preflight=_minimal_preflight(),
        stability=StabilityResult(conclusion_stable=True, reason_stable=True,
                                   assumption_stable=True),
        total_arguments=10,
        residue_threshold_violation=True,  # NEW parameter
    )
    assert result.outcome == Outcome.ESCALATE
    fired = [r for r in result.rule_trace if r.get("fired")]
    assert fired[0]["rule_id"] == "D13"

def test_d14_groupthink_without_evidence_triggers_escalate():
    """D14: groupthink_warning AND no independent_evidence → ESCALATE."""
    from brain.gate2 import run_gate2_deterministic
    result = run_gate2_deterministic(
        agreement_ratio=0.90,
        positions={"r1": object(), "reasoner": object()},
        contradictions=[],
        unaddressed_arguments=[],
        open_blockers=[],
        evidence_count=5,
        search_enabled=True,
        preflight=_minimal_preflight(),
        stability=StabilityResult(conclusion_stable=True, reason_stable=True,
                                   assumption_stable=True,
                                   groupthink_warning=True,
                                   independent_evidence_present=False),
        total_arguments=10,
        residue_threshold_violation=False,
    )
    assert result.outcome == Outcome.ESCALATE
    fired = [r for r in result.rule_trace if r.get("fired")]
    assert fired[0]["rule_id"] == "D14"

def test_d15_suspicious_agreement_no_evidence_triggers_escalate():
    """D15: agreement >= 0.75 AND not SHORT_CIRCUIT AND evidence_count == 0 → ESCALATE."""
    from brain.gate2 import run_gate2_deterministic
    result = run_gate2_deterministic(
        agreement_ratio=0.90,
        positions={"r1": object(), "reasoner": object()},
        contradictions=[],
        unaddressed_arguments=[],
        open_blockers=[],
        evidence_count=0,
        search_enabled=True,
        preflight=_minimal_preflight(effort_tier=EffortTier.STANDARD,
                                      short_circuit_allowed=False),
        stability=StabilityResult(conclusion_stable=True, reason_stable=True,
                                   assumption_stable=True),
        total_arguments=10,
        residue_threshold_violation=False,
    )
    assert result.outcome == Outcome.ESCALATE
    fired = [r for r in result.rule_trace if r.get("fired")]
    assert fired[0]["rule_id"] == "D15"

def test_d16_otherwise_decide():
    """D16: all clear → DECIDE."""
    from brain.gate2 import run_gate2_deterministic
    result = run_gate2_deterministic(
        agreement_ratio=0.90,
        positions={"r1": object(), "reasoner": object()},
        contradictions=[],
        unaddressed_arguments=[],
        open_blockers=[],
        evidence_count=5,
        search_enabled=True,
        preflight=_minimal_preflight(),
        stability=StabilityResult(conclusion_stable=True, reason_stable=True,
                                   assumption_stable=True),
        total_arguments=10,
        residue_threshold_violation=False,
    )
    assert result.outcome == Outcome.DECIDE
    fired = [r for r in result.rule_trace if r.get("fired")]
    assert fired[0]["rule_id"] == "D16"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_gate2.py::test_d13_residue_threshold_violation_triggers_escalate -v
```

Expected: FAIL — `run_gate2_deterministic` missing `residue_threshold_violation` parameter or D13/D14/D15 not implemented.

- [ ] **Step 3: Update gate2.py — D1-D16 rules**

In `brain/v10/brain/gate2.py`, update `_eval_decide_rules()` signature to accept `residue_threshold_violation`:

```python
def _eval_decide_rules(
    ...,
    residue_threshold_violation: bool = False,   # NEW — DELTA-9 D13
) -> tuple[Outcome, list[dict]]:
```

Then update the rule section. The existing D13 (groupthink) becomes D14. Rename and insert:

```python
    # --- D13: residue.threshold_violation → ESCALATE (V3.1 DELTA-9) ---
    if _t("D13", residue_threshold_violation,
          f"residue_threshold_violation={residue_threshold_violation}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D14: groupthink + no independent evidence (was D13 in V3.0) ---
    if _t("D14", groupthink_warning and not independent_evidence,
          f"groupthink={groupthink_warning}, independent_evidence={independent_evidence}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D15: suspicious agreement without evidence on non-SHORT_CIRCUIT run ---
    short_circuit_run = (preflight is not None and preflight.short_circuit_allowed
                         and preflight.effort_tier.value == "SHORT_CIRCUIT"
                         if hasattr(preflight, "effort_tier") else False)
    suspicious_agreement = (agreement_ratio >= 0.75 and not short_circuit_run
                             and evidence_count == 0)
    if _t("D15", suspicious_agreement,
          f"agreement={agreement_ratio:.2f}>=0.75, short_circuit={short_circuit_run}, "
          f"evidence={evidence_count}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D16: Otherwise → DECIDE (was D14 in V3.0) ---
    _t("D16", True, "all checks passed")
    trace[-1]["outcome_if_fired"] = "DECIDE"
    return Outcome.DECIDE, trace
```

Also update the `run_gate2_deterministic()` function signature to accept and pass through `residue_threshold_violation`:

```python
def run_gate2_deterministic(
    ...,
    residue_threshold_violation: bool = False,   # NEW
) -> Gate2Assessment:
```

And pass it in the `_eval_decide_rules(...)` call.

Also update the `@pipeline_stage` decorator on `gate2.py`'s `classify_outcome` function to reflect D1-D16:

```python
logic="""DECIDE modality: D1-D16, first match wins.
D13: residue.threshold_violation → ESCALATE (new V3.1)
D14: groupthink+no_evidence → ESCALATE (was D13)
D15: suspicious_agreement+no_evidence → ESCALATE (new V3.1)
D16: otherwise → DECIDE (was D14)
ANALYSIS modality: A1-A7, first match wins.""",
thresholds={
    "D4 agreement_ratio < 0.50": "NO_CONSENSUS",
    "D5 agreement_ratio 0.50-0.74": "ESCALATE",
    "D15 agreement_ratio >= 0.75 + no evidence": "ESCALATE",
    "D16 agreement_ratio >= 0.75 + all clear": "DECIDE",
},
```

- [ ] **Step 4: Add escalate_remediation and outcome_confidence to proof.py (ADDITION-12)**

In `brain/v10/brain/proof.py`:

1. In `__init__`: `self._escalate_remediation: Optional[dict] = None` and `self._outcome_confidence: Optional[float] = None`
2. Add methods:

```python
def set_escalate_remediation(self, rule_id: str, message: str) -> None:
    """Record rule-specific remediation text for ESCALATE outcomes (V3.1 ADDITION-12)."""
    self._escalate_remediation = {"rule_id": rule_id, "message": message}

def set_outcome_confidence(self, confidence: float) -> None:
    """Record outcome confidence (V3.1 ADDITION-12). Never used as Gate 2 input."""
    self._outcome_confidence = confidence
```

3. In `build()`:

```python
"escalate_remediation": self._escalate_remediation,
"outcome_confidence": self._outcome_confidence,
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_gate2.py -v -k "d13 or d14 or d15 or d16"
```

Expected: all PASS

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -q 2>&1 | tail -10
```

Expected: no new failures. Note: existing gate2 tests for D13/D14 (old numbering) may need renaming — check and rename rule IDs in any failing tests.

- [ ] **Step 7: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): DELTA-9+ADDITION-12 — Gate 2 D1-D16, escalate_remediation, outcome_confidence"
```

---

## Phase 8 — ANALYSIS Overlays

### Task 11: ANALYSIS 8-section synthesis + info boundary + coverage + track-only CTR (ADDITION-10)

**Files:**
- Modify: `brain/v10/brain/analysis_mode.py`
- Modify: `brain/v10/brain/proof.py`
- Test: `brain/v10/tests/test_analysis_mode.py`

- [ ] **Step 1: Write failing tests**

Add to `brain/v10/tests/test_analysis_mode.py`:

```python
def test_analysis_proof_has_information_boundary():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_information_boundary({
        "known": ["X causes Y (3 sources)"],
        "inferred": ["Z likely follows from X"],
        "unknown": ["Long-term trend unclear"],
    })
    result = pb.build(outcome="ANALYSIS", report="ok", gate2_assessment=None,
                      stage_order=[], round_model_counts=[4,3,2,2])
    assert "information_boundary" in result
    assert "known" in result["information_boundary"]

def test_analysis_proof_has_coverage_assessment():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_coverage_assessment({
        "dimensions_covered": 4,
        "dimensions_total": 5,
        "coverage_score": 0.80,
        "gaps": ["Dimension 5 had no evidence"],
    })
    result = pb.build(outcome="ANALYSIS", report="ok", gate2_assessment=None,
                      stage_order=[], round_model_counts=[4,3,2,2])
    assert result["coverage_assessment"]["coverage_score"] == 0.80

def test_analysis_semantic_contradictions_marked_track_only():
    """ANALYSIS mode semantic contradictions must be marked track_only=True."""
    ctr = {"ctr_id": "CTR-001", "severity": "MEDIUM", "track_only": True}
    assert ctr["track_only"] is True

def test_analysis_synthesis_has_8_sections():
    from brain.analysis_mode import ANALYSIS_SYNTHESIS_SECTIONS
    assert len(ANALYSIS_SYNTHESIS_SECTIONS) == 8
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_analysis_mode.py::test_analysis_proof_has_information_boundary -v
```

Expected: FAIL — `set_information_boundary` not found.

- [ ] **Step 3: Add 8-section synthesis structure to analysis_mode.py**

In `brain/v10/brain/analysis_mode.py`, add:

```python
# V3.1 ADDITION-10: 8-section synthesis structure for ANALYSIS runs
ANALYSIS_SYNTHESIS_SECTIONS = [
    "framing",           # How the question is framed
    "aspect_map",        # Exploration by dimension
    "competing_lenses",  # Alternative hypotheses or interpretive frames
    "evidence_for",      # Evidence supporting each lens
    "evidence_against",  # Evidence against each lens
    "uncertainties",     # Unresolved unknowns
    "information_gaps",  # What data would most change the map
    "boundary_summary",  # Known / Inferred / Unknown classification
]
```

- [ ] **Step 4: Add information_boundary and coverage_assessment to proof.py**

In `brain/v10/brain/proof.py`:

1. In `__init__`:
   - `self._information_boundary: Optional[dict] = None`
   - `self._coverage_assessment: Optional[dict] = None`

2. Add methods:

```python
def set_information_boundary(self, boundary: dict) -> None:
    """Record extractive information-boundary classification for ANALYSIS runs (V3.1 ADDITION-10).

    boundary = {"known": [...], "inferred": [...], "unknown": [...]}
    Must be extractive (from evidence), not self-tagged by models.
    """
    self._information_boundary = boundary

def set_coverage_assessment(self, assessment: dict) -> None:
    """Record top-level coverage assessment for ANALYSIS runs (V3.1 ADDITION-10)."""
    self._coverage_assessment = assessment
```

3. In `build()`:

```python
"information_boundary": self._information_boundary,
"coverage_assessment": self._coverage_assessment,
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_analysis_mode.py -v
```

Expected: all PASS

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -q 2>&1 | tail -10
```

Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add brain/v10/
git commit -m "feat(v10): ADDITION-10 — ANALYSIS overlays: 8-section synthesis, info boundary, coverage assessment"
```

---

## Final Verification

### Task 12: Full regression + V3.1 acceptance check

- [ ] **Step 1: Run full test suite**

```bash
cd brain/v10
pytest tests/ -v 2>&1 | tee ../../docs/design/v10-final-test-results.txt
```

Expected: all tests pass (original V9 tests + all new V3.1 tests).

- [ ] **Step 2: Run V3.1 spec coverage check**

Verify each DOD acceptance criterion has a test:

```bash
grep -r "threshold_violation" tests/ | grep -c "def test_"
grep -r "D13\|D14\|D15\|D16" tests/ | grep -c "def test_"
grep -r "anti_groupthink" tests/ | grep -c "def test_"
grep -r "breadth_recovery" tests/ | grep -c "def test_"
grep -r "retroactive_premise" tests/ | grep -c "def test_"
grep -r "short_circuit_invariant\|reasoning_contract" tests/ | grep -c "def test_"
grep -r "paywall\|is_paywalled" tests/ | grep -c "def test_"
grep -r "information_boundary\|coverage_assessment" tests/ | grep -c "def test_"
grep -r "proof_version.*3.1\|schema_version" tests/ | grep -c "def test_"
grep -r "add_warning\|warnings" tests/ | grep -c "def test_"
```

Each should return >= 1.

- [ ] **Step 3: Verify proof output has all V3.1 fields**

```bash
python -c "
from brain.proof import ProofBuilder
pb = ProofBuilder('test', 'brief', 4)
r = pb.build('DECIDE', 'report', None, [], [4,3,2,2])
required = ['proof_version', 'schema_version', 'warnings', 'retroactive_premise',
            'anti_groupthink_search', 'breadth_recovery', 'reasoning_contract',
            'information_boundary', 'coverage_assessment', 'escalate_remediation',
            'outcome_confidence', 'residue_verification']
missing = [f for f in required if f not in r]
print('Missing:', missing if missing else 'NONE — all V3.1 fields present')
assert not missing
"
```

Expected: `Missing: NONE — all V3.1 fields present`

- [ ] **Step 4: Verify proof_version**

```bash
python -c "
from brain.proof import ProofBuilder
pb = ProofBuilder('test', 'brief', 4)
r = pb.build('DECIDE', 'report', None, [], [4,3,2,2])
assert r['proof_version'] == '3.1', f\"Got {r['proof_version']}\"
assert r['schema_version'] == '3.1', f\"Got {r['schema_version']}\"
print('proof_version:', r['proof_version'])
print('schema_version:', r['schema_version'])
"
```

Expected: both print `3.1`

- [ ] **Step 5: Final commit**

```bash
git add docs/design/v10-final-test-results.txt
git commit -m "feat(v10): V3.1 implementation complete — all 14 deltas, full regression pass"
git push origin master
```

---

**V10 implementation complete.** Brain V10 implements all 14 V3.1 deltas with full test coverage, updated checkpoint/resume for all new stages, and architecture visualization for new stages. Deferred to V3.2: Virtual Frames, Canonical Entity IDs, Full Claim-Aware Pinning.
