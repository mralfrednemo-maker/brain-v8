# Brain V8 — Definition of Done v3.0

**Date:** 2026-04-02
**Status:** Draft — pending multi-platform synthesis confirmation
**Scope:** Full rewrite. Self-contained. Covers the entire expanded platform.
**Source:** DESIGN-V3.md + two-pass multi-platform deliberation (Brain V8 + ChatGPT + Gemini + Claude)
**proof_version:** "3.0"

---

## 1. Authoritative Outcome Contract

### 1.1 Allowed Outcomes

Brain V8 SHALL emit only these outcomes:

| Outcome | Modality | Meaning |
|---|---|---|
| DECIDE | DECIDE | Models converged, evidence supports it, stability verified |
| ESCALATE | DECIDE / ANALYSIS | Partial consensus, unresolved material issues, or insufficient coverage |
| NO_CONSENSUS | DECIDE | Fundamental disagreement — irreducible split |
| ANALYSIS | ANALYSIS | Exploratory map complete with sufficient coverage |
| NEED_MORE | Universal (pre-run) | Brief lacks context — returned by PreflightAssessment only |
| ERROR | Universal | Infrastructure failure or fatal integrity violation |

### 1.2 Modality Contract

- DECIDE modality may emit: DECIDE, ESCALATE, NO_CONSENSUS, ERROR
- ANALYSIS modality may emit: ANALYSIS, ESCALATE, ERROR
- NEED_MORE is emitted only by PreflightAssessment, never by Gate 2
- ERROR is reserved exclusively for: (a) infrastructure failures (LLM/search unavailable), (b) fatal integrity violations (missing mandatory stages, unparseable outputs, schema corruption)
- ERROR SHALL NOT be used for bad user questions, invalid briefs, or malformed requests

### 1.3 SHORT_CIRCUIT Contract

SHORT_CIRCUIT is not a top-level outcome. It is an effort tier and execution policy within DECIDE modality. A successful short-circuit run emits DECIDE with `short_circuit_taken: true` in proof.json.

### 1.4 Fixed Topology

All admitted runs SHALL preserve the round topology 4→3→2→2 regardless of effort tier or modality.

### 1.5 Acceptance Criteria

- proof.outcome is one of the six allowed values
- proof.preflight.modality is DECIDE or ANALYSIS
- proof.topology.round_model_counts = [4, 3, 2, 2] on every admitted run
- NEED_MORE implies no R1 model was invoked
- ERROR implies proof.error_class in {INFRASTRUCTURE, FATAL_INTEGRITY}

### 1.6 Failure Modes

| Failure | Outcome |
|---|---|
| Outcome outside allowed taxonomy | ERROR |
| Admitted run violates 4→3→2→2 | ERROR |
| NEED_MORE emitted after R1 begins | ERROR |
| SHORT_CIRCUIT treated as top-level outcome | ERROR |
| Modality mismatch (DECIDE rules applied to ANALYSIS run or vice versa) | ERROR |

**Traceability:** R4

---

## 2. Base Requirements

| Req | Meaning | Enforced by |
|---|---|---|
| R0 | Enough context to reason about | PreflightAssessment, hidden_context_gaps, critical_assumptions, fatal_premise routing |
| R1 | Multiple independent opinions | 4→3→2→2 topology, Dimension Seeder, Perspective Cards, R2 frame enforcement |
| R2 | Grounded in evidence | Search, evidence ledger, claim bindings, contradiction detection, ungrounded stat detection |
| R3 | Honest about disagreement | Frame survival, blocker lifecycle, contradiction ledger, argument resolution status, stability tests |
| R4 | Knows when it can't decide | NEED_MORE routing, ESCALATE/NO_CONSENSUS rules, ANALYSIS branch |

Every section in this DoD traces to at least one of R0–R4.

---

## 3. Determinism and Stage Integrity

### 3.1 Determinism Rule

Given identical proof.json state, Gate 2 MUST emit the same outcome. Gate 2 SHALL NOT invoke an LLM.

### 3.2 Mandatory Stages (admitted runs)

PreflightAssessment → DimensionSeeder → R1 → R2 → R3 → R4 → Synthesis → Gate2

Additional mandatory stages when applicable:
- DivergentFramingPass: when proof.divergence.required = true
- SemanticContradictionPass: when shortlist criteria are met
- UngroundedStatDetector: after R1 and after R2 on DECIDE runs

### 3.3 Fatal Integrity Definition

A fatal integrity failure exists if any of:
- Required stage missing or executed out of order
- Required stage output absent or unparseable
- Round count mismatch against 4→3→2→2
- Branch-required proof object missing
- Synthesis disposition objects missing for tracked open findings
- Proof schema invalid for any field used by Gate 2

### 3.4 Acceptance Criteria

- proof.stage_integrity.all_required_present = true
- proof.stage_integrity.order_valid = true
- proof.stage_integrity.fatal = false on all non-ERROR runs

### 3.5 Failure Modes

| Failure | Outcome |
|---|---|
| Missing required stage | ERROR |
| Invalid stage order | ERROR |
| Missing branch-required proof object | ERROR |
| Round count mismatch | ERROR |
| Unparseable required stage output | ERROR |

**Traceability:** R1, R4

---

## 4. PreflightAssessment

### 4.1 Purpose

Single merged stage replacing Gate 1 + CS Audit. Handles admission, modality selection, effort calibration, defect typing, hidden-context discovery, assumption surfacing, and search scope selection.

### 4.2 Required Output Schema

proof.preflight SHALL contain:

| Field | Type | Required | Notes |
|---|---|---|---|
| executed | bool | always | true on all runs |
| parse_ok | bool | always | false → ERROR |
| answerability | enum | always | ANSWERABLE, NEED_MORE, INVALID_FORM |
| question_class | enum | always | TRIVIAL, WELL_ESTABLISHED, OPEN, AMBIGUOUS |
| stakes_class | enum | always | LOW, STANDARD, HIGH |
| effort_tier | enum | always | SHORT_CIRCUIT, STANDARD, ELEVATED |
| modality | enum | always | DECIDE, ANALYSIS |
| search_scope | enum | always | NONE, TARGETED, BROAD |
| exploration_required | bool | always | |
| short_circuit_allowed | bool | always | |
| fatal_premise | bool | always | |
| follow_up_questions | array[string] | when NEED_MORE | specific, user-addressable |
| premise_flags | array[object] | always | may be empty |
| hidden_context_gaps | array[object] | always | may be empty |
| critical_assumptions | array[object] | always | 3-5 items on admitted runs |

Each premise_flags[] item:

| Field | Type |
|---|---|
| flag_id | string (PFLAG-N) |
| flag_type | enum (INTERNAL_CONTRADICTION, UNSUPPORTED_ASSUMPTION, AMBIGUITY, IMPOSSIBLE_REQUEST, FRAMING_DEFECT) |
| severity | enum (INFO, WARNING, CRITICAL) |
| summary | string |
| routing | enum (REQUESTER_FIXABLE, MANAGEABLE_UNKNOWN, FRAMING_DEFECT, FATAL_PREMISE) |
| blocking | bool |
| resolved | bool |
| resolved_stage | string or null |

Each hidden_context_gaps[] item:

| Field | Type |
|---|---|
| gap_id | string |
| description | string |
| impact_if_unresolved | string |
| material | bool |
| resolved | bool |

Each critical_assumptions[] item:

| Field | Type |
|---|---|
| assumption_id | string |
| text | string |
| verifiability | enum (VERIFIABLE, UNVERIFIABLE, FALSE, UNKNOWN) |
| material | bool |
| resolved | bool |

### 4.3 Defect Routing

- REQUESTER_FIXABLE → NEED_MORE with specific follow_up_questions
- MANAGEABLE_UNKNOWN → inject as debate obligation + register as blocker
- FRAMING_DEFECT → inject reframed version into R1, force engagement
- FATAL_PREMISE → NEED_MORE with fatal_premise: true
- INVALID_FORM is a diagnostic label; its outcome is always NEED_MORE, never ERROR

### 4.4 Admission Guards

- short_circuit_allowed = true ONLY when: question_class in {TRIVIAL, WELL_ESTABLISHED} AND stakes_class = LOW AND no CRITICAL premise flags AND no material unresolved hidden_context_gaps
- effort_tier = ELEVATED when: stakes_class = HIGH OR question_class = AMBIGUOUS OR any CRITICAL premise flag exists
- Any critical_assumption with verifiability in {UNVERIFIABLE, FALSE} and material = true prevents admission → NEED_MORE

### 4.5 Failure Modes

| Failure | Outcome |
|---|---|
| Missing/unparseable preflight output | ERROR |
| Requester-fixable defect admitted to deliberation | ERROR |
| Fatal premise not returned as NEED_MORE | ERROR |
| Invalid brief mapped to ERROR without infrastructure failure | ERROR |
| Material false/unverifiable assumption admitted | NEED_MORE |

**Traceability:** R0, R4

---

## 5. Effort Policy and SHORT_CIRCUIT

### 5.1 Dynamic Token Budgeting

proof.budgeting SHALL contain:

| Field | Type | Required |
|---|---|---|
| effort_tier | enum | always |
| per_round_token_budgets | object | always |
| search_budget_policy | enum | always |
| speculative_expansion_allowed | bool | always |
| high_authority_evidence_required | bool | always |
| short_circuit_taken | bool | always |
| fallback_from_short_circuit | bool | always |

### 5.2 SHORT_CIRCUIT Requirements

When short_circuit_taken = true:
- Topology remains 4→3→2→2
- Search budget is reduced; speculative expansion is disabled
- Every round is instructed to either confirm the trivial answer or surface a hidden defect
- DECIDE is permitted ONLY if high_authority_evidence_required is satisfied (at least one high-authority evidence item in archive when search_scope != NONE)
- If search_scope = NONE AND question_class = TRIVIAL, zero evidence is acceptable
- If high-authority evidence is absent when required, run falls back to full deliberation

### 5.3 Failure Modes

| Failure | Outcome |
|---|---|
| SHORT_CIRCUIT changes topology | ERROR |
| SHORT_CIRCUIT taken with violated guardrails (wrong class/stakes/flags) | ERROR |
| SHORT_CIRCUIT DECIDE without required evidence | ESCALATE |

**Traceability:** R0, R2, R4

---

## 6. Dimension Seeder

### 6.1 Required Schema

proof.dimensions SHALL contain:

| Field | Type | Required |
|---|---|---|
| seeded | bool | always on admitted runs |
| parse_ok | bool | always |
| items | array[object] | always |
| dimension_count | int | always |
| dimension_coverage_score | float | always |

Each dimensions.items[] entry:

| Field | Type |
|---|---|
| dimension_id | string |
| name | string |
| mandatory | bool |
| coverage_status | enum (ZERO, PARTIAL, SATISFIED) |
| argument_count | int |
| justified_irrelevance | bool |

### 6.2 Requirements

- Seeder generates 3–5 mandatory dimensions. Fewer than 3 → ERROR.
- All dimensions injected into all R1 prompts.
- A dimension counts as covered if: argument_count > 0 OR justified_irrelevance = true with recorded explanation. Silent omission is a blocker.
- dimension_coverage_score = (dimensions with argument_count ≥ 2) / (total mandatory dimensions)

### 6.3 Failure Modes

| Failure | Outcome |
|---|---|
| Seeder missing on admitted run | ERROR |
| Fewer than 3 dimensions | ERROR |
| Mandatory dimension ZERO coverage without irrelevance justification | ESCALATE (via COVERAGE_GAP blocker) |

**Traceability:** R1, R4

---

## 7. Perspective Cards (R1)

### 7.1 Required Schema

proof.perspective_cards SHALL contain one entry per R1 model:

| Field | Type |
|---|---|
| model_id | string |
| primary_frame | string |
| hidden_assumption_attacked | string |
| stakeholder_lens | string |
| time_horizon | enum (SHORT, MEDIUM, LONG) |
| failure_mode | string |
| coverage_obligation | enum (CONTRARIAN, MECHANISM_ANALYSIS, OPERATIONAL_RISK, OBJECTIVE_REFRAMING) |
| dimensions_addressed | array[string] |

### 7.2 Requirements

- Exactly 4 R1 cards exist (one per R1 model)
- All 5 structured fields present on each card
- Distinct coverage_obligation assigned across the 4 models

### 7.3 Failure Modes

| Failure | Outcome |
|---|---|
| Missing card or field | ERROR |
| Coverage obligation not assigned | ERROR |

**Traceability:** R1, R3

---

## 8. Divergence, Frame Survival, and Exploration Stress

### 8.1 Required Schema

proof.divergence SHALL contain:

| Field | Type | Required |
|---|---|---|
| required | bool | always |
| adversarial_slot_assigned | bool | always |
| adversarial_model_id | string or null | always |
| adversarial_assignment_type | enum or null | always |
| framing_pass_executed | bool | always |
| exploration_stress_triggered | bool | always |
| stress_seed_frames | array[object] | always |
| material_unrebutted_frame_count | int | always |

Each alt_frames[] item:

| Field | Type |
|---|---|
| frame_id | string (FRAME-N) |
| text | string |
| origin_round | int |
| origin_model | string |
| frame_type | enum (INVERSION, OBJECTIVE_REWRITE, PREMISE_CHALLENGE, CROSS_DOMAIN_ANALOGY, OPPOSITE_STANCE, REMOVE_PROBLEM) |
| material_to_outcome | bool |
| survival_status | enum (ACTIVE, CONTESTED, DROPPED, ADOPTED, REBUTTED) |
| r2_drop_vote_count | int |
| r2_drop_vote_refs | array[string] |
| rebuttal_status | enum (NONE, PARTIAL, REBUTTED) |
| synthesis_disposition_status | enum (ADDRESSED, UNADDRESSED) |

**Material frame definition:** A frame is material if: (a) it is linked to a Dimension Seeder output, OR (b) it is adopted by ≥2 models in R2.

### 8.2 Frame Survival Rules

- R2: frame DROPPED only if all 3 R2 models cast traceable drop votes (each citing an argument_id or evidence_id). r2_drop_vote_count < 3 → frame stays non-dropped.
- R3/R4: frames CANNOT be dropped. Status moves to CONTESTED if not rebutted.
- R2 frame enforcement: each R2 model MUST adopt one frame, rebut one frame, and generate one new frame.
- Drop votes do NOT feed into agreement_ratio.

### 8.3 Exploration Stress Trigger

Condition: R1 agreement_ratio > 0.75 AND (question_class = OPEN OR stakes_class = HIGH) — this is a union, not intersection.

When triggered:
- 2-3 seed frames injected into R2 prompts
- exploration_stress_triggered = true in proof

### 8.4 Failure Modes

| Failure | Outcome |
|---|---|
| Divergence required but adversarial slot missing | ERROR |
| Divergence required but framing pass missing | ERROR |
| Frame dropped with < 3 traceable R2 votes | ERROR |
| Material frame disappears from lineage | ERROR |
| Material frame ACTIVE/CONTESTED without rebuttal at synthesis | ESCALATE |
| Stress trigger met but no seed frames injected | ERROR |
| R2 adopt/rebut/generate obligation missing | ERROR |

**Traceability:** R1, R3, R4

---

## 9. Search, Provenance, and Ungrounded Stat Detection

### 9.1 Search Log Schema

proof.search_log SHALL be an array:

| Field | Type |
|---|---|
| query_id | string |
| query_text | string |
| provenance | enum (model_claim, premise_defect, frame_test, evidence_gap, ungrounded_stat) |
| issued_after_stage | string |
| pages_fetched | int |
| evidence_yield_count | int |
| query_status | enum (SUCCESS, ZERO_RESULT, FAILED, SKIPPED) |

### 9.2 Ungrounded Stat Detector Schema

proof.ungrounded_stats SHALL contain:

| Field | Type | Required |
|---|---|---|
| post_r1_executed | bool | DECIDE admitted runs |
| post_r2_executed | bool | DECIDE admitted runs |
| flagged_claims | array[object] | always |

Each flagged_claims[] item:

| Field | Type |
|---|---|
| claim_id | string |
| text | string |
| numeric | bool |
| verified | bool |
| blocker_id | string or null |
| severity | enum |
| status | enum (CLEAR, UNVERIFIED_CLAIM) |

### 9.3 Requirements

- Every search query logged with provenance and query_status
- Zero-result queries still logged (query_status = ZERO_RESULT)
- Search subsystem failure → query_status = FAILED → ERROR if critical
- Ungrounded Stat Detector runs after R1 and R2 on DECIDE admitted runs
- Post-R3 unresolved material unverified numeric claim → UNVERIFIED_CLAIM blocker

### 9.4 Failure Modes

| Failure | Outcome |
|---|---|
| Query executed but not logged | ERROR |
| Missing provenance on query | ERROR |
| Ungrounded stat detector skipped on DECIDE run | ERROR |
| Search subsystem failure | ERROR |
| Material unverified claim unresolved at Gate 2 | ESCALATE |

**Traceability:** R2, R4

---

## 10. Two-Tier Evidence Ledger

### 10.1 Required Schema

proof.evidence SHALL contain:

| Field | Type | Required |
|---|---|---|
| active_working_set | array[object] | always |
| archive | array[object] | always |
| active_count | int | always |
| archive_count | int | always |
| eviction_log | array[object] | always |
| high_authority_evidence_present | bool | always |

Each evidence item (in both stores):

| Field | Type |
|---|---|
| evidence_id | string (E001, E002...) |
| source_url | string |
| topic_cluster | string |
| authority_tier | enum |
| is_active | bool |
| is_archived | bool |
| referenced_by | array[string] |

Each eviction_log[] item:

| Field | Type |
|---|---|
| event_id | string |
| evidence_id | string |
| from_active | bool |
| to_archive | bool |
| reason | string |

### 10.2 Requirements

- Active working set capped at 10
- Archive uncapped — never deletes anything
- Evidence moves from active to archive but never disappears from system
- Every cited evidence item exists in either active or archive
- Gate 2 reasons over archive-backed truth, not just active set

### 10.3 Failure Modes

| Failure | Outcome |
|---|---|
| Active exceeds 10 | ERROR |
| Evidence deleted rather than archived | ERROR |
| Cited evidence missing from both stores | ERROR |
| SHORT_CIRCUIT DECIDE without required high-authority evidence | ESCALATE |

**Traceability:** R2, R4

---

## 11. Argument Tracker and Resolution Status

### 11.1 Required Schema

proof.arguments SHALL be an object map keyed by argument_id:

| Field | Type |
|---|---|
| argument_id | string (R{round}-ARG-{n}) |
| round_origin | int |
| model_id | string |
| dimension_id | string |
| text | string |
| resolution_status | enum (ORIGINAL, REFINED, SUPERSEDED) |
| superseded_by | string or null |
| blocker_link_ids | array[string] |
| evidence_refs | array[string] |
| open | bool |

### 11.2 Requirements

- Every argument has a stable unique ID
- REFINED arguments link to the argument they refine
- SUPERSEDED arguments have superseded_by != null pointing to the replacing argument
- Restatement without explicit linkage is NOT resolution
- Open material arguments at synthesis require structured dispositions

### 11.3 Failure Modes

| Failure | Outcome |
|---|---|
| Argument disappears without resolution status | ERROR |
| Supersession link broken (superseded_by points to nonexistent ID) | ERROR |
| Open material argument omitted from synthesis disposition | ESCALATE |
| Restated argument treated as resolved without lineage | ESCALATE |

**Traceability:** R3, R4

---

## 12. Contradictions

### 12.1 Required Schema

proof.contradictions SHALL contain:

| Field | Type | Required |
|---|---|---|
| numeric_records | array[object] | always |
| semantic_records | array[object] | always |
| semantic_pass_executed | bool | always |

Each contradiction record:

| Field | Type |
|---|---|
| ctr_id | string (CTR-N) |
| detection_mode | enum (NUMERIC, SEMANTIC) |
| evidence_ref_a | string |
| evidence_ref_b | string |
| same_entity | bool |
| same_timeframe | bool |
| severity | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| status | enum (OPEN, RESOLVED, NON_MATERIAL) |
| justification | string |
| linked_claim_ids | array[string] |

### 12.2 Semantic Contradiction Shortlist Criteria

A pair is shortlisted when: same topic cluster AND (opposite polarity cues OR same entity + same timeframe) AND at least one member linked to a decisive claim, blocker, or open contradiction.

### 12.3 Failure Modes

| Failure | Outcome |
|---|---|
| Semantic pass required but skipped | ERROR |
| Unresolved HIGH/CRITICAL contradiction | ESCALATE |

**Traceability:** R2, R3

---

## 13. Blockers and Decisive Claims

### 13.1 Blocker Schema

proof.blockers[] items:

| Field | Type |
|---|---|
| blocker_id | string (BLK-N) |
| type | enum (EVIDENCE_GAP, CONTRADICTION, UNRESOLVED_DISAGREEMENT, CONTESTED_POSITION, COVERAGE_GAP, UNVERIFIED_CLAIM) |
| severity | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| status | enum (OPEN, RESOLVED, DEFERRED) |
| linked_ids | array[string] |
| resolution_summary | string or null |

### 13.2 Decisive Claims Schema (DECIDE only)

proof.decisive_claims[] items:

| Field | Type |
|---|---|
| claim_id | string |
| text | string |
| material_to_conclusion | bool |
| evidence_refs | array[string] |
| evidence_support_status | enum (SUPPORTED, PARTIAL, UNSUPPORTED) |
| analogy_refs | array[string] |

### 13.3 Cross-Domain Analogies

proof.cross_domain_analogies[] items:

| Field | Type |
|---|---|
| analogy_id | string |
| source_domain | string |
| target_claim_id | string |
| transfer_mechanism | string |
| test_status | enum (UNTESTED, SUPPORTED, REJECTED) |

An analogy with test_status = UNTESTED SHALL NOT carry decisive factual load.

### 13.4 Failure Modes

| Failure | Outcome |
|---|---|
| Decisive claim missing evidence_support_status | ERROR |
| Decisive claim SUPPORTED with zero evidence_refs | ERROR |
| Untested analogy used decisively | ESCALATE |
| Unresolved CRITICAL blocker at Gate 2 | ESCALATE |

**Traceability:** R2, R3, R4

---

## 14. Synthesis Packet and Residue Verification

### 14.1 Synthesis Packet Schema

proof.synthesis_packet SHALL contain:

| Field | Type | Required |
|---|---|---|
| final_positions | array[object] | DECIDE |
| argument_lifecycle | array[object] | always (max 20) |
| frame_summary | array[object] | always |
| blocker_summary | array[object] | always |
| decisive_claim_bindings | array[object] | DECIDE |
| contradiction_summary | array[object] | always |
| premise_flag_summary | array[object] | always |
| packet_complete | bool | always |

### 14.2 Structured Dispositions

proof.synthesis_output.dispositions SHALL contain arrays for: blockers, frames, claims, contradictions.

Each disposition object:

| Field | Type |
|---|---|
| target_type | enum (BLOCKER, FRAME, CLAIM, CONTRADICTION) |
| target_id | string |
| status | string |
| importance | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| narrative_explanation | string |
| evidence_refs | array[string] |

### 14.3 Orphaned Evidence Obligation

If archive contains evidence with authority_tier = HIGH that is NOT cited in any decisive claim, blocker, contradiction, or synthesis disposition, synthesis MUST explain why it was non-decisive.

### 14.4 Residue Verification Schema

proof.residue_verification SHALL contain:

| Field | Type |
|---|---|
| expected_disposition_count | int |
| emitted_disposition_count | int |
| omission_rate | float |
| deep_scan_triggered | bool |
| coverage_pass | bool |

### 14.5 Requirements

- Synthesis receives controller-curated state bundle (not just R4 outputs)
- Every tracked open finding gets a disposition object
- omission_rate > 0.20 triggers deep semantic scan
- coverage_pass = true required on all non-ERROR runs

### 14.6 Failure Modes

| Failure | Outcome |
|---|---|
| Synthesis packet missing controller-curated state | ERROR |
| Disposition missing for tracked open finding | ERROR |
| Deep scan threshold exceeded but scan not run | ERROR |
| Material omissions unresolved after deep scan | ESCALATE |

**Traceability:** R2, R3, R4

---

## 15. Stability Tests (DECIDE only)

### 15.1 Required Schema

proof.stability SHALL contain:

| Field | Type | Required |
|---|---|---|
| conclusion_stable | bool | DECIDE |
| reason_stable | bool | DECIDE |
| assumption_stable | bool | DECIDE |
| independent_evidence_present | bool | DECIDE |
| fast_consensus_observed | bool | DECIDE (true if R1 agreement_ratio ≥ 0.95) |
| groupthink_warning | bool | DECIDE |

### 15.2 Definitions

- **conclusion_stable:** Final surviving models converge on the same recommendation after supersession filtering
- **reason_stable:** Models converge for the same reasons (shared decisive claim set and evidence bindings)
- **assumption_stable:** Models rely on the same set of unresolved assumptions
- **groupthink_warning:** fast_consensus_observed = true AND (question_class = OPEN OR stakes_class = HIGH) AND independent_evidence_present = false

### 15.3 Requirements

- Stability fields are boolean Gate 2 inputs
- Computation method for each boolean is specified in the implementation spec, not the DoD
- All three stability booleans present on every DECIDE run

**Traceability:** R3, R4

---

## 16. Gate 2 — DECIDE Rules (D1–D14)

Evaluated in order. First match determines outcome.

| Rule | Condition | Outcome |
|---|---|---|
| D1 | Fatal integrity or infrastructure failure | ERROR |
| D2 | Modality mismatch (preflight.modality ≠ DECIDE) | ERROR |
| D3 | Illegal SHORT_CIRCUIT state (guardrails violated) | ERROR |
| D4 | agreement_ratio < 0.50 | NO_CONSENSUS |
| D5 | agreement_ratio ≥ 0.50 and < 0.75 | ESCALATE |
| D6 | Any unresolved CRITICAL blocker (includes COVERAGE_GAP, UNVERIFIED_CLAIM) | ESCALATE |
| D7 | Any decisive claim lacks valid evidence binding (evidence_support_status ≠ SUPPORTED) | ESCALATE |
| D8 | Any HIGH/CRITICAL contradiction unresolved | ESCALATE |
| D9 | Any unresolved CRITICAL premise flag | ESCALATE |
| D10 | Any material frame ACTIVE/CONTESTED without rebuttal and without synthesis disposition | ESCALATE |
| D11 | conclusion_stable = false | NO_CONSENSUS |
| D12 | reason_stable = false OR assumption_stable = false | ESCALATE |
| D13 | groupthink_warning = true AND independent_evidence_present = false | ESCALATE |
| D14 | Otherwise | DECIDE |

### Requirements

- Same proof state → same outcome (deterministic)
- Frame drop votes do NOT affect agreement_ratio
- Rule order is preserved exactly
- gate2.rule_trace[] records which rule fired

### Gate 2 Trace Schema

proof.gate2 SHALL contain:

| Field | Type |
|---|---|
| modality | enum (DECIDE, ANALYSIS) |
| rule_trace | array[{rule_id, evaluated, fired, outcome_if_fired}] |
| final_outcome | enum |

**Traceability:** R2, R3, R4

---

## 17. Gate 2 — ANALYSIS Rules (A1–A7)

Evaluated in order. First match determines outcome.

| Rule | Condition | Outcome |
|---|---|---|
| A1 | Missing or invalid PreflightAssessment | ERROR |
| A2 | Modality mismatch (preflight.modality ≠ ANALYSIS) | ERROR |
| A3 | Missing required shared pipeline artifacts (dimension seeder, evidence, analysis_map, synthesis) | ERROR |
| A4 | Evidence archive empty AND search_scope ≠ NONE | ESCALATE |
| A5 | Any mandatory dimension has zero arguments | ESCALATE |
| A6 | Total arguments < 8 | ESCALATE |
| A7 | Otherwise | ANALYSIS |

### ANALYSIS Coverage Threshold

dimension_coverage_score ≥ 0.8 is the recommended operational floor. If score < 0.8 but all mandatory dimensions have at least some arguments (rule A5 passes), ANALYSIS is still permitted — the score is recorded for diagnostic purposes.

**Traceability:** R1, R2, R4

---

## 18. ANALYSIS Mode Contract

### 18.1 Shared Pipeline

ANALYSIS reuses: PreflightAssessment, 4→3→2→2 topology, Search, Evidence Ledger, Argument Tracker, Divergent Framing Pass, Invariant Validator, proof.json base schema.

### 18.2 Modified Behavior

- Round prompts: "deepen exploration by dimension — identify knowns, inferred, unknowns. Do not seek agreement."
- Frame survival: dropping disabled entirely. Statuses: EXPLORED, NOTED, UNEXPLORED.
- Position Tracker runs diagnostically (proof.diagnostics.positions) — does NOT drive outcomes.
- Adversarial assignment not required (but frame tracking remains).

### 18.3 Analysis Map Schema

proof.analysis_map SHALL contain:

| Field | Type |
|---|---|
| header | string ("EXPLORATORY MAP — NOT A DECISION") |
| dimensions | object (keyed by dimension_id) |
| dimension_coverage_score | float |
| hypothesis_ledger | array[object] |
| total_argument_count | int |

Each dimension entry:

| Field | Type |
|---|---|
| knowns | array[string] |
| inferred | array[string] |
| unknowns | array[string] |
| evidence_for | array[string] |
| evidence_against | array[string] |
| competing_lenses | array[string] |
| argument_count | int |

Each hypothesis entry:

| Field | Type |
|---|---|
| hypothesis_id | string |
| dimension_id | string |
| text | string |
| evidence_refs | array[string] |
| status | enum (SUPPORTED, MIXED, WEAK, UNKNOWN) |

### 18.4 Implementation Staging

proof.analysis_debug SHALL contain (during staged rollout):

| Field | Type | Required |
|---|---|---|
| debug_mode | bool | always on staged runs |
| debug_gate2_result | enum or null | when debug_mode = true |
| actual_output | enum | when debug_mode = true |
| rules_enforced | bool | when debug_mode = true |
| remaining_debug_runs | int | when debug_mode = true |

**DEBUG sunset:** debug_mode automatically disables when remaining_debug_runs reaches 0. Leaving DEBUG on after counter expires → ERROR.

### 18.5 Failure Modes

| Failure | Outcome |
|---|---|
| ANALYSIS output contains verdict language instead of exploratory map | ERROR |
| Frame dropping occurs in ANALYSIS mode | ERROR |
| analysis_map missing on ANALYSIS run | ERROR |
| analysis_map.header ≠ "EXPLORATORY MAP — NOT A DECISION" | ERROR |
| Debug mode active after sunset | ERROR |

**Traceability:** R1, R4

---

## 19. proof.json Top-Level Schema

| Field | Type | Required |
|---|---|---|
| proof_version | string ("3.0") | always |
| run_id | string | always |
| timestamp_started | string | always |
| timestamp_completed | string | always |
| topology | object | always |
| outcome | object | always |
| error_class | enum or null | always |
| stage_integrity | object | always |
| config_snapshot | object | always |
| preflight | object | always |
| budgeting | object | always |
| dimensions | object | admitted runs |
| perspective_cards | array | admitted runs |
| rounds | object | admitted runs |
| divergence | object | admitted runs |
| search_log | array | admitted runs |
| ungrounded_stats | object | DECIDE admitted runs |
| evidence | object | admitted runs |
| arguments | object (map) | admitted runs |
| blockers | array | admitted runs |
| decisive_claims | array | DECIDE runs |
| cross_domain_analogies | array | admitted runs |
| contradictions | object | admitted runs |
| synthesis_packet | object | admitted runs |
| synthesis_output | object | admitted runs |
| residue_verification | object | admitted runs |
| positions | object | DECIDE runs |
| stability | object | DECIDE runs |
| analysis_map | object | ANALYSIS runs |
| analysis_debug | object | staged ANALYSIS runs |
| diagnostics | object | always (optional diagnostic data) |
| gate2 | object | admitted runs |

**Traceability:** R2, R4

---

## 20. Verification and Test Suite

| Test | Verifies |
|---|---|
| Preflight requester-fixable defect → NEED_MORE | Correct defect routing |
| Preflight fatal premise → NEED_MORE + fatal_premise=true | Fatal premise routing |
| Preflight INVALID_FORM → NEED_MORE, not ERROR | Taxonomy compliance |
| Missing preflight field → ERROR | Schema integrity |
| SHORT_CIRCUIT preserves 4→3→2→2 | Fixed topology |
| SHORT_CIRCUIT without high-authority evidence → ESCALATE | Evidence guardrail |
| SHORT_CIRCUIT with violated guardrails → ERROR | Integrity check |
| Seeder emits 3–5 dimensions; <3 → ERROR | Breadth seeding |
| Zero-covered mandatory dimension → blocker → ESCALATE | Coverage gap |
| Justified irrelevance counts as covered | Dimension coverage |
| All four R1 cards contain 5 structured fields | Perspective Card completeness |
| Divergence required but missing adversarial slot → ERROR | Mandatory divergence |
| Single or double R2 drop vote does not drop frame | 3-vote rule |
| Three R2 drop votes with traceable refs → DROPPED | Drop threshold |
| R3/R4 cannot drop frames (CONTESTED only) | Late-round reform |
| Exploration stress trigger (union: OPEN OR HIGH) injects 2–3 seed frames | Suspicious consensus |
| Query provenance + query_status logged for all queries including zero-result | Search auditability |
| Material unverified numeric claim unresolved → ESCALATE | Ungrounded stat enforcement |
| Active evidence capped at 10; evicted item in archive | Two-tier ledger |
| Cited evidence missing from both stores → ERROR | Audit integrity |
| Semantic contradiction pass required but absent → ERROR | Contradiction integrity |
| Untested analogy used decisively → ESCALATE | Analogy restriction |
| Restated argument without lineage not counted as resolution | Argument resolution |
| Orphaned high-relevance evidence requires synthesis explanation | Evidence accountability |
| Missing disposition for open material finding → ERROR | Residue verification |
| Omission rate >20% triggers deep scan | Residue depth |
| conclusion_stable=false → NO_CONSENSUS | Stability rule D11 |
| reason/assumption unstable → ESCALATE | Stability rule D12 |
| Groupthink warning + no independent evidence → ESCALATE | Stability rule D13 |
| ANALYSIS A5: zero-argument dimension → ESCALATE | Coverage rule |
| ANALYSIS A6: total arguments <8 → ESCALATE | Minimum floor |
| ANALYSIS frame dropping → ERROR | Mode contract |
| ANALYSIS debug mode records both debug and actual results | Staged rollout |
| Debug mode active after sunset → ERROR | Sunset enforcement |
| Same proof state twice → same Gate 2 result | Determinism |
| proof_version = "3.0" on all v3.0 runs | Schema versioning |
| Modality mismatch → ERROR | Controller contract |

**Traceability:** R0–R4

---

## 21. Consolidated Failure-Mode Matrix

| Mechanism | Failure | Outcome |
|---|---|---|
| PreflightAssessment | missing/unparseable | ERROR |
| Defect routing | requester-fixable or fatal premise admitted | ERROR / NEED_MORE |
| Assumptions | material false/unverifiable unresolved | NEED_MORE |
| SHORT_CIRCUIT | guardrails violated | ERROR |
| SHORT_CIRCUIT | no required evidence | ESCALATE |
| Token budgeting | policy missing | ERROR |
| Dimension Seeder | missing / <3 dimensions | ERROR |
| Perspective Cards | missing fields | ERROR |
| Divergent Framing | required but absent | ERROR |
| Frame survival | dropped with <3 R2 votes | ERROR |
| Material frame | ACTIVE/CONTESTED unaddressed | ESCALATE |
| Exploration stress | trigger met, no seed frames | ERROR |
| Search log | query not logged / missing provenance | ERROR |
| Search subsystem | infrastructure failure | ERROR |
| Ungrounded stats | material unverified claim unresolved | ESCALATE |
| Evidence ledger | evidence deleted / cited missing | ERROR |
| Synthesis packet | controller state absent | ERROR |
| Semantic contradiction | required but skipped | ERROR |
| Contradiction | HIGH/CRITICAL unresolved | ESCALATE |
| Argument tracking | restatement counted as resolution | ESCALATE |
| Argument tracking | supersession link broken | ERROR |
| Residue verification | material omissions | ESCALATE |
| Stability tests | conclusion unstable | NO_CONSENSUS |
| Stability tests | reason/assumption unstable | ESCALATE |
| ANALYSIS map | missing or wrong contract | ERROR |
| ANALYSIS coverage | empty evidence + search recommended / zero-arg dimension / <8 total | ESCALATE |
| Debug sunset | debug active after expiry | ERROR |

---

## 22. Definition of Done — Final Pass Condition

Brain V8 v3.0 is Done only if ALL of the following are true:

1. PreflightAssessment executes exactly once before R1 and routes all defects per typed routing rules
2. Every admitted run preserves topology 4→3→2→2
3. All mechanisms implemented and recorded in proof.json: PreflightAssessment, Dimension Seeder, Perspective Cards, frame survival reform, exploration stress trigger, two-tier evidence ledger, controller-curated synthesis, semantic contradiction detection, argument resolution status, search provenance, ungrounded stat detection, residue verification, stability tests, ANALYSIS mode, staged ANALYSIS Gate 2, dynamic token budgeting
4. Gate 2 is fully deterministic and evaluable from proof.json alone, with rule_trace recorded
5. ERROR is emitted only for infrastructure or fatal integrity failure
6. NEED_MORE is emitted only from PreflightAssessment
7. DECIDE runs cannot pass with unresolved material evidence, premise, frame, contradiction, or support defects
8. ANALYSIS runs cannot pass without minimum coverage under A1–A7
9. proof_version = "3.0" on all runs
10. The verification suite in Section 20 passes
11. The complete proof.json contract in Section 19 is satisfied
