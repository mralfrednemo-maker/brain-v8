# Brain V10 Design Spec

**Date:** 2026-04-06
**Status:** Draft — pending user approval
**Baseline:** V3.0 Design + DOD (DESIGN-V3.md, DOD-V3.md) as implemented in Brain V9
**Delta source:** BRAIN-V10-DESIGN-DOD-DELTA.txt (V3.1 unified master delta)

---

## 1. Project Scope

Two deliverables:

1. **Repo restructuring** — reorganize the thinker ecosystem into a clean multi-platform, multi-version layout
2. **Brain V10 implementation** — apply 14 V3.1 deltas to a copy of V9 using copy-then-evolve strategy

### 1.1 Out of Scope

- Chamber code changes (moved but not modified)
- Ein code changes (moved, paths updated, not modified)
- Mission Controller changes (moved but not modified)
- Virtual Frames, Canonical Entity IDs, Full Claim-Aware Pinning (deferred to V3.2)
- Structural refactoring of V9 code (splitting brain.py, renaming modules) — not in V3.1 spec

---

## 2. Repo Restructuring

### 2.1 Target Layout

```
thinker/                              # repo (rename from brain-v8)
├── brain/
│   ├── v9/
│   │   ├── brain/                    # renamed from thinker/ (V9 module)
│   │   ├── tests/
│   │   ├── output/                   # run outputs, design sessions
│   │   ├── pyproject.toml
│   │   ├── auto-heal.sh, brain-debug.sh, monitor-brain.sh
│   │   ├── build_self_review.py, build_self_review_v9.py
│   │   ├── HANDOFF.md, HANDOFF-NEXT.md, HANDOVER-BRAIN-V8-NEXT.md
│   │   ├── OPERATIONS.md
│   │   └── V8-DOD*.md
│   ├── v10/
│   │   ├── brain/                    # V10 Python module (copy of v9/brain/, then evolved)
│   │   ├── tests/                    # V10 tests (copy of v9/tests/, then evolved)
│   │   └── pyproject.toml            # name = "brain-v10", version = "10.0.0"
│   └── legacy/
│       └── brain-v3-orchestrator.py
├── chamber/
│   └── v3/
│       ├── chamber/                  # consensus_runner_v3.py restructured as module
│       └── tests/                    # 3 test files
├── controller/
│   ├── mission_controller.py
│   ├── validate_bundle.py
│   └── run-e2e-tests.sh
├── ein/
│   ├── ein-parallel.py               # paths updated
│   ├── ein-parallel-ledger.py
│   ├── ein-design.py                 # paths updated
│   ├── ein-design-ledger.py
│   ├── ein-selenium.py
│   ├── ein-selenium-ledger.py
│   ├── README.md                     # updated refs
│   └── cross4-final-position-lock-prompt.txt
├── tools/
│   └── browser-automation/
├── briefs/                           # 7 E2E test briefs
├── docs/
│   ├── design/                       # DESIGN-V3.md, DOD-V3.md, MASTER docs, V10 delta
│   ├── protocols/                    # three-way-deliberation.md
│   └── archive/                      # THINKER-DOD-AND-PLAN.md, older docs
├── CLAUDE.md                         # updated for new structure
└── README.md                         # architecture overview
```

### 2.2 Source → Destination Mapping

**Brain:**
- `_audit_thinker/thinker-v8/thinker/` → `brain/v9/brain/` (rename module)
- `_audit_thinker/thinker-v8/tests/` → `brain/v9/tests/`
- `_audit_thinker/thinker-v8/pyproject.toml` → `brain/v9/pyproject.toml`
- `_audit_thinker/thinker-v8/output/` → `brain/v9/output/`
- `_audit_thinker/thinker-v8/*.md` + scripts → `brain/v9/`
- `the-thinker/brain-v3-orchestrator.py` → `brain/legacy/`
- `brain/v9/brain/` + `brain/v9/tests/` → copied to `brain/v10/brain/` + `brain/v10/tests/`

**Chamber:**
- `the-thinker/consensus_runner_v3.py` → `chamber/v3/chamber/`
- `the-thinker/tests/test_explicit_options.py` → `chamber/v3/tests/`
- `the-thinker/tests/test_search_gate.py` → `chamber/v3/tests/`
- `the-thinker/tests/test_slp.py` → `chamber/v3/tests/`

**Controller:**
- `the-thinker/mission_controller.py` → `controller/`
- `the-thinker/validate_bundle.py` → `controller/`
- `the-thinker/run-e2e-tests.sh` → `controller/`

**Ein:**
- `the-thinker/ein/` → `ein/` (update hardcoded paths in ein-design.py, ein-parallel.py)
- `the-thinker/three-way-deliberation.md` → `docs/protocols/`
- `the-thinker/protocols/` → `docs/protocols/`

**Tools:**
- `the-thinker/browser-automation/` → `tools/browser-automation/`

**Docs:**
- `_audit_thinker/thinker-v8/output/design-session/*.md` → `docs/design/`
- `_audit_thinker/docs/` → `docs/`
- `_audit_thinker/THINKER-DOD-AND-PLAN.md` → `docs/archive/`

**Briefs:**
- `the-thinker/briefs/` → `briefs/`

### 2.3 Post-Move Fixes

1. **Ein hardcoded paths**: `_audit_thinker/thinker-v8/` → `brain/v9/` in ein-design.py
2. **Ein README**: `browser-automation/` → `tools/browser-automation/`
3. **V9 module rename**: all internal imports `from thinker.X` → `from brain.X` in v9/brain/ and v9/tests/
4. **V10 module**: same import rename applied to the V10 copy
5. **pyproject.toml**: V9 keeps `name = "brain-v9"`, V10 gets `name = "brain-v10", version = "10.0.0"`

### 2.4 Constraints

- No files deleted from source repos — this is additive (copies, not moves)
- V9 is a reference copy — import breakage from rename is acceptable, it is not actively run
- V10 must be independently installable via `pip install -e brain/v10/`

---

## 3. Brain V10 — V3.1 Delta Implementation

### 3.1 Approach

**Copy-then-evolve:** V10 starts as a working copy of V9. Each of the 14 deltas is applied incrementally. Every intermediate state should be testable.

### 3.2 Preserved V9 Features (Mandatory in V10)

These V9 features must survive all deltas intact:

**Step-by-step execution (checkpoint/resume):**
- `PipelineState` dataclass in `checkpoint.py` — serializable pipeline state
- `_checkpoint(stage_id)` in `brain.py` — saves state after each stage, checks stop condition
- `_stage_done(stage_id)` — skips completed stages on resume
- `_restore_trackers()` — rebuilds ArgumentTracker, PositionTracker, EvidenceLedger from checkpoint
- `_debug_pause(stage_id)` — interactive inspection at each stage with stage-specific context display
- CLI flags: `--stop-after`, `--resume`, `--full-run` (default is step-by-step)
- `STAGE_ORDER` list in checkpoint.py — must be updated to include new V3.1 stages
- `CHECKPOINT_VERSION` — must be bumped to "3.0" (V3.1 schema adds new fields to PipelineState)

**Architecture visualization (HTML diagram):**
- `@pipeline_stage` decorator in `pipeline.py` — registers stage metadata
- `STAGE_REGISTRY` — populated by decorated functions across all modules
- `generate_architecture_html()` — renders interactive diagram from registry + run events
- `RunLog` + `StageEvent` in `debug.py` — captures structured events per stage
- New V3.1 stages must be decorated with `@pipeline_stage` and emit `StageEvent`s
- Color scheme: gates=orange, rounds=blue, tracks=pink, search=purple, synthesis=cyan, deterministic=green

**Other preserved features:**
- Fixed 4→3→2→2 topology
- Two-modality engine (DECIDE / ANALYSIS)
- Two-tier evidence ledger (active capped at 10 + uncapped archive)
- Deterministic Gate 2 (no LLM)
- BrainError with FATAL_INTEGRITY for zero-tolerance failures
- Dual synthesis output (markdown + JSON + dispositions)
- All existing ANALYSIS A1-A7 rules

### 3.3 Implementation Phases

#### Phase 1 — Schema Foundation

**DELTA-2: Schema transition (proof_version + schema_version = "3.1")**

Files: `proof.py`, `config.py`

- `proof.py`: emit `proof_version = "3.1"` and `schema_version = "3.1"`
- Add backward parse support: accept V3.0 proofs during transition (missing V3.1 fields = warning, not error)
- `config.py`: add `schema_version` field to BrainConfig
- `CHECKPOINT_VERSION`: bump to `"3.0"` (new PipelineState fields)

Acceptance:
- All new runs emit both `proof_version` and `schema_version` = "3.1"
- V3.0 proofs parse without ERROR during transition
- Missing mandatory V3.1 fields after transition = ERROR

**DELTA-1: Three-tier failure taxonomy**

Files: `proof.py`, `brain.py`, `types.py`

- `proof.py`: add `proof.warnings[]` array
- `types.py`: add `WarningRecord` dataclass (warning_id, tier, stage, detail)
- `brain.py`: non-terminal suboptimal states log warnings via `proof.add_warning()` instead of silently disappearing
- Existing LOW-severity `proof.add_violation()` calls reclassified as warnings
- WARNINGs never change terminal outcome
- A detected warning that is not logged is itself a fatal integrity defect (ERROR)

Acceptance:
- Every failure mode maps to exactly one of ERROR, ESCALATE, WARNING
- WARNING never changes terminal outcome
- Unlogged warning = ERROR

**DELTA-13: Formalize undocumented behavior**

Files: `types.py`, `proof.py`, `brain.py`

- ANALYSIS-only frame statuses (EXPLORED/NOTED/UNEXPLORED): add DOD schema coverage
- `Blocker.to_dict()` DROPPED→DEFERRED normalization: document explicitly in types.py
- `BrainResult.gate1`: remove field entirely (dead code)
- `PerspectiveCard.field_provenance`: specify full schema and acceptance rules in proof

Acceptance:
- Every emitted field has schema coverage
- Serialized blocker status contract is explicit
- ANALYSIS frame statuses are explicit
- `BrainResult.gate1` is removed

#### Phase 2 — Preflight Enrichment

**DELTA-3: Reformulation metadata**

Files: `types.py`, `preflight.py`, `proof.py`

- `PreflightResult`: add `original_brief`, `reformulated_brief`, `reformulation_reason` (all Optional)
- `proof.py`: persist under `proof.preflight` when present
- `brain.py`: no second admission stage, no silent rewrite-and-proceed
- `PipelineState`: add reformulation fields for checkpoint support

Acceptance:
- Reformulation metadata is logged when present
- Silent reformulation is forbidden
- Requester-fixable defects still return NEED_MORE from preflight

#### Phase 3 — Post-R1 Pipeline Additions

**ADDITION-4: Retroactive premise escalation**

Files: `brain.py`, `types.py`, `proof.py`, `argument_tracker.py`

- `types.py`: add `argument_type: Optional[str]` to Argument dataclass; add `RetroactivePremiseResult` dataclass
- `argument_tracker.py`: identify `premise_challenge` arguments during extraction
- `brain.py`: after track1, scan for `>= 2` independent models flagging the same premise → rerun preflight once
- `proof.py`: add `proof.retroactive_premise`
- State guard: `_retroactive_escalation_consumed` boolean in PipelineState (one-shot cap)
- Effort tier can only ratchet upward on rerun, never downward
- **Checkpoint**: new stage `retroactive_premise_scan` added to `STAGE_ORDER` after `track1`
- **Visualization**: `@pipeline_stage` decorator on scan function; `RunLog` event emitted

Acceptance:
- Scan runs after R1 on all admitted DECIDE runs
- Trigger: >= 2 independent models on the same flawed premise. "Same premise" = semantic similarity >= 0.7 via LLM extractor (not string match). "Independent" = different model IDs in the same round.
- Rerun happens at most once
- Fatal/requester-fixable rerun outcomes cannot be ignored

**ADDITION-7: Anti-groupthink search**

Files: `brain.py`, `types.py`, `proof.py`, `search.py`

- `brain.py`: after R1, if `agreement_ratio > 0.80` AND question is OPEN/AMBIGUOUS or HIGH stakes → issue one adversarial search query against apparent consensus
- `types.py`: extend search query provenance with `anti_groupthink`
- `proof.py`: add `proof.anti_groupthink_search`
- Evidence flows into R2 via normal evidence injection
- **Checkpoint**: new stage `anti_groupthink_search` added to `STAGE_ORDER` after `framing_pass`
- **Visualization**: `@pipeline_stage` decorator; `RunLog` event

Acceptance:
- Evaluation after R1 is mandatory
- Exactly one adversarial query issued when threshold met
- Query is logged and its evidence flows into R2

#### Phase 4 — Post-R2 Addition

**ADDITION-6: Breadth-Recovery Pulse**

Files: `brain.py`, `proof.py`

- `brain.py`: after track2, compute ignored ratio for R1 arguments in R2; if `> 0.40` → inject mandatory recovery instructions into R3 prompt
- `proof.py`: add `proof.breadth_recovery`
- Depends on stable argument tracking (already exists)
- If argument lineage is broken → fail closed (ERROR)
- **Checkpoint**: new stage `breadth_recovery_eval` added to `STAGE_ORDER` after `frame_survival_r2`
- **Visualization**: `@pipeline_stage` decorator; `RunLog` event

Acceptance:
- Evaluation after R2 is mandatory
- Trigger: `ignored_ratio > 0.40`
- If triggered, R3 injection is mandatory and logged

#### Phase 5 — SHORT_CIRCUIT Contract

**DELTA-5: 5-invariant reasoning contract**

Files: `brain.py`, `proof.py`, `rounds.py`

- `rounds.py` or `brain.py`: after each round on SHORT_CIRCUIT runs, validate that model responses contain:
  1. Premise check
  2. Confidence basis
  3. Known unknowns
  4. One counter-consideration
  5. Machine-readable compression reason
- `proof.py`: add `proof.reasoning_contract`
- Missing any invariant on a compressed run = ERROR
- Fallback to full deliberation logged if it occurs

Acceptance:
- SHORT_CIRCUIT never changes topology
- Missing any invariant on a compressed run = ERROR
- If fallback occurs, it is logged

#### Phase 6 — Evidence Quality

**ADDITION-11: Paywall detection + cross-domain filter**

Files: `page_fetch.py`, `evidence.py`

- `page_fetch.py`: detect paywalled pages before extraction (string/pattern matching); log skipped pages
- `evidence.py`: change cross-domain compatibility from strict match to non-empty intersection

Acceptance:
- Paywalled pages are skipped and logged
- Hybrid-domain evidence is admitted when there is non-empty domain overlap

**DELTA-14: Forensic eviction overlay**

Files: `types.py`, `evidence.py`, `proof.py`

- `types.py`: extend `EvictionEvent` with optional `linked_contradiction_id`, `linked_blocker_id`, `contradiction_severity`
- `proof.py`: emit richer eviction records
- Residue/synthesis path: explain orphaned high-authority evidence explicitly

Acceptance:
- Every eviction is logged
- High-authority orphaned evidence gets explicit non-decisive explanation
- Evicted contradiction-linked evidence is visible in proof for audit

#### Phase 7 — Residue + Gate 2

**DELTA-8: Explicit residue threshold**

Files: `proof.py`, `residue.py`, `config.py`

- `residue.py`: set `threshold_violation = true` when omissions exceed configured threshold
- `proof.py`: extend `proof.residue_verification` with `threshold_violation` field
- `config.py`: add `residue_omission_threshold` (default 0.25), configurable
- Deep scan still triggers at `> 0.20`

Acceptance:
- `omission_rate > 0.20` triggers deep scan
- `threshold_violation = true` is explicit in proof
- Threshold default is 0.25, configurable, and recorded

**DELTA-9: Gate 2 D1-D16**

File: `gate2.py`

Current D1-D14 → new D1-D16:
- D1-D12: unchanged (renumber as needed)
- D13: `residue.threshold_violation = true` → ESCALATE (new)
- D14: `groupthink_warning = true AND independent_evidence_present = false` → ESCALATE (was D13)
- D15: `agreement_ratio >= 0.75 AND effort_tier != SHORT_CIRCUIT AND evidence_count == 0` → ESCALATE (new)
- D16: otherwise → DECIDE (was D14)

Rule order is fixed, deterministic, first-match-wins. Same proof state = same outcome.
- **Visualization**: gate2 `@pipeline_stage` decorator updated with new D-rules in `thresholds` dict

Acceptance:
- Rule order is fixed and deterministic
- Rule trace is mandatory
- Same proof state yields same outcome

**ADDITION-12: Remediation + confidence telemetry**

Files: `proof.py`, `gate2.py`

- `gate2.py`: when ESCALATE, emit rule-specific remediation text
- `proof.py`: add `proof.escalate_remediation`, `proof.outcome_confidence`
- `outcome_confidence` is recorded but never used as a Gate 2 input

Acceptance:
- Every ESCALATE outcome includes remediation
- `outcome_confidence` is recorded but never used by Gate 2

#### Phase 8 — ANALYSIS Overlays

**ADDITION-10: ANALYSIS enhancements**

Files: `analysis_mode.py`, `proof.py`, `synthesis.py`

- `analysis_mode.py`: emit 8-section synthesis structure for ANALYSIS runs
- `proof.py`: add `proof.information_boundary`, `proof.coverage_assessment`
- ANALYSIS semantic contradictions: mark `track_only: true`
- Must NOT replace `analysis_map` or `A1-A7`

Acceptance:
- Every ANALYSIS run still satisfies A1-A7
- Every ANALYSIS run also emits:
  - 8-section synthesis
  - Extractive information-boundary classification
  - Top-level coverage assessment
  - Track-only semantic contradiction records

### 3.4 Updated Pipeline Sequence (V3.1)

```
Preflight → Dimensions → R1 → Track1
  → RetroactivePremiseScan (conditional, one-shot)         # NEW
  → PerspectiveCards → FramingPass
  → AntiGroupthinkSearch (conditional)                      # NEW
  → UngroundedR1 → Search(R1)
  → R2 → Track2 → FrameSurvivalR2
  → BreadthRecoveryEval (conditional)                       # NEW
  → UngroundedR2 → Search(R2)
  → R3 → Track3 → FrameSurvivalR3
  → R4 → Track4
  → SemanticContradiction → DecisiveClaims → SynthesisPacket
  → Synthesis → ResidueVerification → Stability → Gate2
```

### 3.5 Updated STAGE_ORDER (checkpoint.py)

```python
STAGE_ORDER = [
    "preflight", "dimensions",
    "r1", "track1",
    "retroactive_premise_scan",          # NEW
    "perspective_cards", "framing_pass",
    "anti_groupthink_search",            # NEW
    "ungrounded_r1", "search1",
    "r2", "track2", "frame_survival_r2",
    "breadth_recovery_eval",             # NEW
    "ungrounded_r2", "search2",
    "r3", "track3", "frame_survival_r3",
    "r4", "track4",
    "semantic_contradiction", "decisive_claims", "synthesis_packet",
    "synthesis", "residue_verification", "stability", "gate2",
]
```

`CHECKPOINT_VERSION = "3.0"` — V3.0 checkpoints are not compatible (new fields in PipelineState).

### 3.6 Updated PipelineState Fields

New fields added to PipelineState for V3.1 checkpoint support:

```python
# DELTA-3: Reformulation
original_brief: str = ""
reformulated_brief: str = ""
reformulation_reason: str = ""

# ADDITION-4: Retroactive premise
retroactive_escalation_consumed: bool = False
retroactive_premise_result: dict = field(default_factory=dict)

# ADDITION-7: Anti-groupthink
anti_groupthink_search: dict = field(default_factory=dict)

# ADDITION-6: Breadth recovery
breadth_recovery: dict = field(default_factory=dict)

# DELTA-1: Warnings
warnings: list[dict] = field(default_factory=list)
```

### 3.7 Visualization Updates

All new stages must:
1. Be decorated with `@pipeline_stage(...)` specifying name, description, stage_type, order, provider, inputs, outputs, logic, thresholds, failure_mode
2. Emit `StageEvent` via `RunLog` with timing and summary data
3. Appear in the pipeline bar flow in `generate_architecture_html()`
4. Have their run data visible in the interactive detail panels

New stages and their visualization metadata:

| Stage | Type | Provider | Color |
|-------|------|----------|-------|
| RetroactivePremiseScan | gate | sonnet | orange |
| AntiGroupthinkSearch | search | brave/sonar | purple |
| BreadthRecoveryEval | track | deterministic | green |

### 3.8 New V3.1 Proof Fields

On top of V3.0:

- `schema_version` (string, root level, always)
- `warnings` (array, always)
- `reasoning_contract` (object, SHORT_CIRCUIT runs)
- `preflight.original_brief` (string, when reformulation present)
- `preflight.reformulated_brief` (string, when reformulation present)
- `preflight.reformulation_reason` (string, when reformulation present)
- `retroactive_premise` (object, admitted DECIDE runs)
- `breadth_recovery` (object, admitted runs)
- `anti_groupthink_search` (object, admitted runs)
- `residue_verification.threshold_violation` (boolean)
- `information_boundary` (object, ANALYSIS runs)
- `coverage_assessment` (object, ANALYSIS runs)
- `outcome_confidence` (float, always)
- `escalate_remediation` (object, when outcome = ESCALATE)

### 3.9 New V3.1 Failure Modes

- Untiered condition or warning not logged → ERROR
- Silent reformulation → ERROR
- Retroactive premise trigger met but rerun skipped → ERROR
- Compressed invariant missing → ERROR
- Breadth recovery trigger met but injection omitted → ERROR
- Anti-groupthink trigger met but query omitted/unlogged → ERROR
- `threshold_violation = true` → ESCALATE (via D13)
- Suspicious high-agreement/no-evidence on non-SHORT_CIRCUIT → ESCALATE (via D15)
- ANALYSIS information boundary missing or self-tagged → ERROR
- ANALYSIS coverage assessment missing → ERROR
- ANALYSIS semantic contradictions not `track_only` → ERROR

### 3.10 Test Strategy

- V9's 349 tests are copied into V10 and adapted (import rename `thinker` → `brain`)
- Phase 1 (schema changes) may require test fixture updates for new proof fields
- Each subsequent phase adds tests for its specific delta's acceptance criteria
- After all phases: full regression + new acceptance tests per DOD section
- Gate 2 tests: verify all 16 D-rules and 7 A-rules produce correct outcomes for given proof states

### 3.11 Deferred to V3.2

- Virtual Frames
- Canonical Cross-Round Entity Registry
- Full Claim-Aware Pinning + Pin-Cap Gate 2 Rule
- Split Gate 1 + CS Audit (rejected)
- ANALYSIS A1-A3 replacement (rejected)
- Rotating Adversarial Role (rejected)

---

## 4. Success Criteria

1. Repo restructured with all platforms in versioned directories
2. `brain/v10/` is independently installable and runnable
3. All 14 V3.1 deltas implemented with acceptance criteria met
4. All V9 tests pass (adapted for import rename) + new V3.1 tests
5. Step-by-step execution works with new stages (stop/resume at any V3.1 stage)
6. Architecture visualization shows all new stages with metadata and run data
7. `proof_version = "3.1"` and `schema_version = "3.1"` on all V10 outputs
8. Gate 2 D1-D16 deterministic and traceable
9. No regressions in existing V3.0 behavior (topology, modality, evidence ledger, etc.)
