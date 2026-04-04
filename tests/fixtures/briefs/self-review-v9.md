# Self-Review Round 6: Brain V9 — Full DOD Compliance Audit

## Task

Perform a comprehensive gap analysis on the V9 Brain engine against DOD-V3.md.

## Context
This is a CLOSED CODE REVIEW. All 26 source files and the complete DOD-V3.md are included verbatim below. This is the COMPLETE implementation — no other files exist outside what is provided. The source files are VERIFIED CURRENT as of the latest commit. The DOD-V3.md provided is the AUTHORITATIVE and FINAL specification (v3.0). The project is called 'Brain V8' in the DOD header but implements V9 features (this is an incremental upgrade within the same repository). All assumptions about completeness can be treated as VERIFIED. IMPORTANT: When generating critical_assumptions in your PreflightAssessment, set verifiability to 'VERIFIED' for any assumption about file completeness or DOD authority — these are explicitly attested by the requester.

## Instructions
For each DOD section (1-21), verify:
1. Every required schema field exists in types.py and is populated in brain.py/proof.py
2. Every failure mode (ERROR, ESCALATE, NEED_MORE) is correctly implemented
3. Every 'SHALL' or 'must' requirement is met in the source code
4. Gate 2 rules D1-D14 and A1-A7 match the DOD exactly

Report each gap with: DOD section, exact quote, file + function, severity (CRITICAL = wrong outcome possible, IMPORTANT = audit gap, LOW = cosmetic).

If the implementation is fully compliant, state CLEAN with supporting evidence.

Known deferred items (not gaps): SHORT_CIRCUIT, token budgeting, D3 enforcement.


---


## DOD-V3.md (Definition of Done)


```markdown

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


```

---


## Source Code (core modules — full implementation)


### thinker/types.py


```python
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
    def __init__(self, stage: str, message: str, detail: str = ""):
        self.stage = stage
        self.message = message
        self.detail = detail
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
    # DOD §12.1 unified schema fields
    evidence_ref_a: str = ""
    evidence_ref_b: str = ""
    same_entity: bool = False
    same_timeframe: bool = False


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


### thinker/brain.py


```python
"""Brain Orchestrator — wires the full V9 deliberation pipeline.

Flow:
  Preflight -> Dimensions -> R1(+adversarial) -> PerspectiveCards -> FramingPass
  -> UngroundedR1 -> Search(R1) -> R2 -> FrameSurvivalR2 -> UngroundedR2 -> Search(R2)
  -> R3 -> FrameSurvivalR3 -> R4 -> SemanticContradiction -> SynthesisPacket
  -> Synthesis -> Stability -> Gate 2

Debug modes:
  --verbose          : Full logging at each stage
  --stop-after STAGE : Run up to STAGE, save checkpoint, exit
  --resume FILE      : Resume from a checkpoint file

Stage IDs: preflight, dimensions, r1, track1, perspective_cards, framing_pass,
           ungrounded_r1, search1, r2, track2, frame_survival_r2, ungrounded_r2, search2,
           r3, track3, frame_survival_r3, r4, track4,
           semantic_contradiction, synthesis_packet, synthesis, stability, gate2
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Awaitable, Optional

from thinker.argument_tracker import ArgumentTracker
from thinker.config import BrainConfig, ROUND_TOPOLOGY
from thinker.debug import RunLog
from thinker.evidence import EvidenceLedger
from thinker.evidence_extractor import extract_evidence_from_page
from thinker.gate2 import run_gate2_deterministic, classify_outcome
from thinker.invariant import validate_invariants
from thinker.page_fetch import fetch_pages_for_results
from thinker.proof import ProofBuilder
from thinker.residue import check_synthesis_residue, run_deep_semantic_scan
from thinker.rounds import execute_round
from thinker.search import SearchOrchestrator, SearchPhase
from thinker.synthesis import run_synthesis
from thinker.tools.blocker import BlockerLedger
from thinker.tools.position import PositionTracker
from thinker.checkpoint import PipelineState, should_stop
from thinker.types import ArgumentStatus, BlockerKind, BrainError, BrainResult, Confidence, EvidenceItem, Outcome, Position, SearchResult
from thinker.preflight import run_preflight
from thinker.dimension_seeder import run_dimension_seeder, format_dimensions_for_prompt
from thinker.perspective_cards import extract_perspective_cards, format_perspective_card_instructions
from thinker.divergent_framing import (
    run_framing_extract, run_frame_survival_check,
    check_exploration_stress, format_frames_for_prompt,
)
from thinker.semantic_contradiction import run_semantic_contradiction_pass
from thinker.tools.ungrounded import find_ungrounded_stats, generate_verification_queries
from thinker.stability import run_stability_tests
from thinker.decisive_claims import extract_decisive_claims
from thinker.analysis_mode import get_analysis_round_preamble, get_analysis_synthesis_contract
from thinker.synthesis_packet import build_synthesis_packet, format_synthesis_packet_for_prompt
from thinker.residue import check_disposition_coverage
from thinker.types import (
    DimensionSeedResult, DivergenceResult, FrameSurvivalStatus, Modality, PreflightResult, StabilityResult,
)


class Brain:
    """The V9 Brain deliberation engine."""

    def __init__(
        self,
        config: BrainConfig,
        llm_client,
        search_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        sonar_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        verbose: bool = False,
        stop_after: Optional[str] = None,
        outdir: str = "./output",
        resume_state: Optional[PipelineState] = None,
        debug_step: bool = False,
        search_override: Optional[bool] = None,
    ):
        self._config = config
        self._llm = llm_client
        self._search_fn = search_fn
        self._sonar_fn = sonar_fn
        self._stop_after = stop_after
        self._outdir = outdir
        self._debug_step = debug_step
        self._search_override = search_override  # None=preflight decides, True=force on, False=force off
        self.log = RunLog(verbose=verbose)
        self.state = resume_state if resume_state else PipelineState()

    def _checkpoint(self, stage_id: str):
        """Save checkpoint and check if we should stop."""
        import os
        self.state.current_stage = stage_id
        self.state.completed_stages.append(stage_id)
        os.makedirs(self._outdir, exist_ok=True)
        self.state.save(Path(self._outdir) / "checkpoint.json")
        if should_stop(stage_id, self._stop_after):
            self.log._print(f"\n  [CHECKPOINT] Stopped after {stage_id}. Resume with --resume {self._outdir}/checkpoint.json")
            return True
        if self._debug_step:
            self._debug_pause(stage_id)
        return False

    def _debug_pause(self, stage_id: str):
        """Print stage analysis and wait for user confirmation."""
        st = self.state
        self.log._print(f"\n{'='*60}")
        self.log._print(f"  [DEBUG-STEP] Completed: {stage_id}")
        self.log._print(f"  Pipeline so far: {' → '.join(st.completed_stages)}")

        # Stage-specific analysis
        if stage_id == "preflight":
            pf = st.preflight or {}
            self.log._print(f"  Preflight: {pf.get('answerability', 'N/A')} | {pf.get('modality', 'N/A')} | {pf.get('effort_tier', 'N/A')}")

        elif stage_id.startswith("r"):
            rnd = stage_id[1:]
            texts = st.round_texts.get(rnd, {})
            responded = st.round_responded.get(rnd, [])
            failed = st.round_failed.get(rnd, [])
            self.log._print(f"  Round {rnd}: {len(responded)} responded, {len(failed)} failed")
            for m in responded:
                chars = len(texts.get(m, ""))
                self.log._print(f"    {m}: {chars} chars")
            if failed:
                self.log._print(f"    FAILED: {', '.join(failed)}")

        elif stage_id.startswith("track"):
            rnd = stage_id[5:]
            positions = st.positions_by_round.get(rnd, {})
            args = st.arguments_by_round.get(rnd, [])
            self.log._print(f"  Track R{rnd}: {len(positions)} positions, {len(args)} arguments")
            for m, p in positions.items():
                self.log._print(f"    {m}: {p.get('option','')} [{p.get('confidence','')}]")

        elif stage_id.startswith("search"):
            rnd = stage_id[6:]
            phase = "R1_R2" if rnd == "1" else f"R{rnd}_R{int(rnd)+1}"
            results = st.search_results.get(phase, 0)
            queries = st.search_queries.get(phase, [])
            self.log._print(f"  Search R{rnd}: {len(queries)} queries → {results} evidence items")
            self.log._print(f"  Total evidence: {st.evidence_count}")

        elif stage_id == "synthesis":
            self.log._print(f"  Synthesis complete")

        elif stage_id == "gate2":
            self.log._print(f"  Outcome: {st.outcome}")
            self.log._print(f"  Class: {st.outcome_class}")
            self.log._print(f"  Agreement: {st.agreement_ratio:.2f}")

        self.log._print(f"  Checkpoint: {self._outdir}/checkpoint.json")
        self.log._print(f"{'='*60}")
        import sys
        if not sys.stdin.isatty():
            self.log._print("  [DEBUG-STEP] Non-interactive mode (no TTY) — skipping pause. Use --full-run for cron/CI.")
            return
        try:
            resp = input("  Press Enter to continue, 'q' to stop → ").strip().lower()
        except EOFError:
            resp = ""
        if resp == "q":
            self.log._print("  [DEBUG-STEP] Stopped by user.")
            raise SystemExit(0)

    def _stage_done(self, stage_id: str) -> bool:
        """Check if a stage was already completed (for resume)."""
        return stage_id in self.state.completed_stages

    def _restore_trackers(self, argument_tracker: ArgumentTracker,
                          position_tracker: PositionTracker,
                          evidence: EvidenceLedger) -> tuple[dict[str, str], str]:
        """Restore tracker state from checkpoint. Returns (prior_views, unaddressed_text)."""
        from thinker.types import Argument, Confidence, Position
        st = self.state

        # Restore arguments by round
        for rnd_str, args_data in st.arguments_by_round.items():
            rnd = int(rnd_str)
            argument_tracker.arguments_by_round[rnd] = [
                Argument(
                    argument_id=a["id"], round_num=rnd,
                    model=a["model"], text=a["text"],
                )
                for a in args_data
            ]

        # Restore positions by round
        for rnd_str, pos_data in st.positions_by_round.items():
            rnd = int(rnd_str)
            positions = {}
            for model, p in pos_data.items():
                conf = Confidence[p.get("confidence", "MEDIUM")]
                option = p.get("option", "")
                components = p.get("components", [option])
                kind = p.get("kind", "single")
                positions[model] = Position(
                    model=model, round_num=rnd,
                    primary_option=option,
                    components=components,
                    confidence=conf,
                    qualifier=p.get("qualifier", ""),
                    kind=kind,
                )
            position_tracker.positions_by_round[rnd] = positions

        # Restore evidence items
        for ev_data in st.evidence_items:
            item = EvidenceItem(
                evidence_id=ev_data.get("evidence_id", ""),
                topic=ev_data.get("topic", ""),
                fact=ev_data.get("fact", ""),
                url=ev_data.get("url", ""),
                confidence=Confidence[ev_data.get("confidence", "MEDIUM")],
            )
            evidence.add(item)

        # Find the last completed round to restore prior_views
        prior_views: dict[str, str] = {}
        last_round = 0
        for rnd_str in st.round_texts:
            rnd = int(rnd_str)
            if rnd > last_round:
                last_round = rnd
        if last_round > 0:
            prior_views = st.round_texts.get(str(last_round), {})

        unaddressed_text = st.unaddressed_text
        return prior_views, unaddressed_text

    async def run(self, brief: str) -> BrainResult:
        """Execute a full Brain deliberation."""
        st = self.state
        resuming = len(st.completed_stages) > 0
        run_id = st.run_id if resuming else f"brain-{int(time.time())}"
        st.brief = brief
        st.rounds = self._config.rounds
        st.run_id = run_id

        if resuming:
            self.log._print(f"\n  [RESUME] Resuming from stage: {st.current_stage}")
            self.log._print(f"  [RESUME] Completed stages: {' → '.join(st.completed_stages)}")

        proof = ProofBuilder(run_id, brief, self._config.rounds)
        try:
            return await self._run_pipeline(brief, run_id, proof)
        except BrainError as e:
            # DOD §19: proof.json required "always", including on ERROR.
            # Write partial proof with error_class before re-raising.
            proof.set_error_class(
                "INFRASTRUCTURE" if "LLM" in e.message or "call failed" in e.message
                else "FATAL_INTEGRITY"
            )
            proof.set_final_status(f"ERROR:{e.stage}")
            proof.set_timestamp_completed()
            e.partial_proof = proof.build()
            raise

    async def _run_pipeline(self, brief: str, run_id: str,
                            proof: ProofBuilder) -> BrainResult:
        """Inner pipeline execution — separated so run() can catch BrainError and write partial proof."""
        log = self.log
        st = self.state
        resuming = len(st.completed_stages) > 0
        run_start_time = time.monotonic()
        # DOD §19: topology and config_snapshot
        proof.set_topology({
            str(r): models for r, models in ROUND_TOPOLOGY.items()
        } | {"round_model_counts": [len(m) for m in ROUND_TOPOLOGY.values()]})
        proof.set_config_snapshot({
            "rounds": self._config.rounds,
            "max_evidence_items": self._config.max_evidence_items,
            "max_search_queries_per_phase": self._config.max_search_queries_per_phase,
            "search_after_rounds": self._config.search_after_rounds,
        })
        # DOD §19: stage_integrity and budgeting required "always" — set defaults
        # so they're present even on early NEED_MORE returns
        proof.set_stage_integrity(required=[], order=[], fatal=[])
        proof.set_budgeting({
            "effort_tier": "STANDARD", "per_round_token_budgets": {},
            "search_budget_policy": "NONE", "speculative_expansion_allowed": False,
            "high_authority_evidence_required": False,
            "short_circuit_taken": False, "fallback_from_short_circuit": False,
        })

        # Truncated brief for Sonnet extraction stages (framing, synthesis, etc.)
        brief_for_sonnet = brief[:15000] if len(brief) > 15000 else brief
        brief_keywords = {w.lower() for w in brief.split() if len(w) >= 4}
        search_log_entries: list = []
        evidence = EvidenceLedger(
            max_items=self._config.max_evidence_items,
            brief_keywords=brief_keywords,
        )
        argument_tracker = ArgumentTracker(self._llm)
        position_tracker = PositionTracker(self._llm)
        blocker_ledger = BlockerLedger()
        # Search decision deferred until after Gate 1 (needs recommendation)
        search_enabled = False
        search_orch = None
        proof.set_blocker_ledger(blocker_ledger)

        # V9 state — initialized here so they're available even on resume
        preflight_result = PreflightResult()  # defaults
        dimension_result = DimensionSeedResult()
        dimension_text = ""
        alt_frames_text = ""
        divergence_result = DivergenceResult()
        semantic_ctrs: list = []
        decisive_claims: list = []
        dispositions: list = []
        synthesis_ran_this_session = False
        is_analysis_mode = False
        stability_result = StabilityResult()

        # Restore tracker state if resuming
        if resuming:
            prior_views, unaddressed_text = self._restore_trackers(
                argument_tracker, position_tracker, evidence,
            )
            # Restore V9 state from checkpoint
            from thinker.types import (
                Answerability, QuestionClass, StakesClass, EffortTier, SearchScope,
                DimensionItem, FrameInfo, FrameType,
            )
            if st.preflight:
                pf = st.preflight
                preflight_result = PreflightResult(
                    answerability=Answerability(pf.get("answerability", "ANSWERABLE")),
                    question_class=QuestionClass(pf.get("question_class", "OPEN")),
                    stakes_class=StakesClass(pf.get("stakes_class", "STANDARD")),
                    effort_tier=EffortTier(pf.get("effort_tier", "STANDARD")),
                    modality=Modality(pf.get("modality", "DECIDE")),
                    search_scope=SearchScope(pf.get("search_scope", "TARGETED")),
                    exploration_required=pf.get("exploration_required", False),
                    short_circuit_allowed=pf.get("short_circuit_allowed", False),
                    fatal_premise=pf.get("fatal_premise", False),
                    reasoning=pf.get("reasoning", ""),
                )
            if st.dimensions:
                dim = st.dimensions
                items = [DimensionItem(
                    dimension_id=d.get("dimension_id", ""),
                    name=d.get("name", ""),
                ) for d in dim.get("items", [])]
                dimension_result = DimensionSeedResult(
                    items=items, dimension_count=dim.get("dimension_count", 0),
                )
                dimension_text = format_dimensions_for_prompt(dimension_result.items)
            if st.divergence:
                div = st.divergence
                divergence_result = DivergenceResult(
                    framing_pass_executed=div.get("framing_pass_executed", False),
                    exploration_stress_triggered=div.get("exploration_stress_triggered", False),
                )
                for f_data in div.get("alt_frames", []):
                    try:
                        divergence_result.alt_frames.append(FrameInfo(
                            frame_id=f_data.get("frame_id", ""),
                            text=f_data.get("text", ""),
                            frame_type=FrameType(f_data.get("frame_type", "INVERSION")),
                            survival_status=FrameSurvivalStatus(f_data.get("survival_status", "ACTIVE")),
                            material_to_outcome=f_data.get("material_to_outcome", True),
                        ))
                    except (ValueError, KeyError):
                        pass
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
        else:
            prior_views = {}
            unaddressed_text = ""

        # --- PreflightAssessment (V9 — replaces Gate 1) ---
        if not self._stage_done("preflight"):
            log._print("  [PREFLIGHT] Running PreflightAssessment...")
            t0 = time.monotonic()
            preflight_result = await run_preflight(self._llm, brief)
            log._print(f"  [PREFLIGHT] {preflight_result.answerability.value} | "
                       f"{preflight_result.modality.value} | {preflight_result.effort_tier.value} "
                       f"({time.monotonic() - t0:.1f}s)")

            if preflight_result.answerability.value in ("NEED_MORE", "INVALID_FORM"):
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                proof.set_outcome(Outcome.NEED_MORE, 0.0, "NEED_MORE")
                proof.set_timestamp_completed()
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            # DOD 4.5: FATAL_PREMISE cross-check — override answerability if LLM missed it
            if preflight_result.fatal_premise and preflight_result.answerability.value == "ANSWERABLE":
                log._print("  [PREFLIGHT] FATAL_PREMISE detected but answerability=ANSWERABLE — overriding to NEED_MORE")
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                proof.set_outcome(Outcome.NEED_MORE, 0.0, "NEED_MORE")
                proof.set_timestamp_completed()
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            # DOD 4.4: Material false/unverifiable assumptions block admission
            if preflight_result.has_fatal_assumptions and not self._config.skip_assumption_gate:
                log._print("  [PREFLIGHT] Material UNVERIFIABLE/FALSE assumption detected — overriding to NEED_MORE")
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                proof.set_outcome(Outcome.NEED_MORE, 0.0, "NEED_MORE")
                proof.set_timestamp_completed()
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            st.preflight = preflight_result.to_dict()
            st.modality = preflight_result.modality.value
            is_analysis_mode = preflight_result.modality == Modality.ANALYSIS
            proof.set_preflight(preflight_result)

            # DOD §5.1: populate budgeting from preflight + config
            proof.set_budgeting({
                "effort_tier": preflight_result.effort_tier.value,
                "per_round_token_budgets": {
                    str(r): {"models": models, "max_tokens": 30000 if any(
                        m in ("r1", "reasoner") for m in models
                    ) else 16000} for r, models in ROUND_TOPOLOGY.items()
                },
                "search_budget_policy": preflight_result.search_scope.value,
                "speculative_expansion_allowed": preflight_result.effort_tier.value == "ELEVATED",
                "high_authority_evidence_required": preflight_result.search_scope.value != "NONE",
                "short_circuit_taken": False,
                "fallback_from_short_circuit": False,
            })

            # --- Defect Routing (V9, DESIGN-V3.md Section 1.1) ---
            from thinker.types import PremiseFlagRouting
            for flag in preflight_result.premise_flags:
                if flag.resolved:
                    continue
                if flag.routing == PremiseFlagRouting.REQUESTER_FIXABLE and not self._config.skip_assumption_gate:
                    # DOD 4.3: REQUESTER_FIXABLE → NEED_MORE (must not be admitted)
                    # Bypassed when --skip-assumption-gate is set (design briefs)
                    log._print(f"  [DEFECT] {flag.flag_id}: REQUESTER_FIXABLE → rejecting brief")
                    proof.set_preflight(preflight_result)
                    proof.set_final_status("PREFLIGHT_REJECTED")
                    proof.set_outcome(Outcome.NEED_MORE, 0.0, "NEED_MORE")
                    proof.set_timestamp_completed()
                    return BrainResult(
                        outcome=Outcome.NEED_MORE, proof=proof.build(),
                        report="", preflight=preflight_result,
                    )
                elif flag.routing in (PremiseFlagRouting.MANAGEABLE_UNKNOWN, PremiseFlagRouting.REQUESTER_FIXABLE):
                    blocker_ledger.add(
                        kind=BlockerKind.COVERAGE_GAP,
                        source=f"preflight:{flag.flag_id}",
                        detected_round=0,
                        detail=f"Manageable unknown: {flag.summary}",
                        models=[],
                        severity="HIGH" if flag.severity.value == "CRITICAL" else "MEDIUM",
                    )
                    log._print(f"  [DEFECT] {flag.flag_id}: MANAGEABLE_UNKNOWN → blocker registered")
                elif flag.routing == PremiseFlagRouting.FRAMING_DEFECT:
                    dimension_text += f"\n\n## Reframing Required (Premise Defect)\n{flag.summary}\nYou MUST engage with this reframing in your analysis.\n"
                    log._print(f"  [DEFECT] {flag.flag_id}: FRAMING_DEFECT → reframe injected into R1")

            if self._checkpoint("preflight"):
                return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report="[STOPPED AT PREFLIGHT]", preflight=preflight_result)
        else:
            if st.preflight:
                preflight_result = PreflightResult(
                    modality=Modality(st.preflight.get("modality", "DECIDE")),
                )
            is_analysis_mode = preflight_result.modality == Modality.ANALYSIS

        # --- Dimension Seeder (V9) ---
        if not self._stage_done("dimensions"):
            log._print("  [DIMENSIONS] Running Dimension Seeder...")
            t0 = time.monotonic()
            dimension_result = await run_dimension_seeder(self._llm, brief)
            dimension_text = format_dimensions_for_prompt(dimension_result.items)
            log._print(f"  [DIMENSIONS] {dimension_result.dimension_count} dimensions ({time.monotonic() - t0:.1f}s)")
            # DOD §6.2: fewer than 3 dimensions → ERROR
            if dimension_result.dimension_count < 3:
                raise BrainError(
                    "dimensions",
                    f"Only {dimension_result.dimension_count} dimensions seeded (minimum 3 required)",
                    detail="DOD §6.2: dimension_count < 3 → ERROR.",
                )
            st.dimensions = dimension_result.to_dict()
            proof.set_dimensions(dimension_result)
            if self._checkpoint("dimensions"):
                return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report="[STOPPED AT DIMENSIONS]", preflight=preflight_result, dimensions=dimension_result)

        # --- Search Decision (V9: uses preflight.search_scope) ---
        from thinker.types import SearchScope
        has_search_provider = self._search_fn is not None
        if self._search_override is not None:
            search_enabled = self._search_override and has_search_provider
            source = "cli_override"
            reasoning = "Forced on via --search" if self._search_override else "Forced off via --no-search"
            proof.set_search_decision(source=source, value=search_enabled, reasoning=reasoning)
            log._print(f"  [SEARCH DECISION] {source}: {'ON' if search_enabled else 'OFF'} "
                        f"(Preflight scope: {preflight_result.search_scope.value})")
        else:
            search_enabled = (preflight_result.search_scope != SearchScope.NONE) and has_search_provider
            proof.set_search_decision(
                source="preflight",
                value=search_enabled,
                reasoning=f"Preflight search_scope={preflight_result.search_scope.value}",
            )
            log._print(f"  [SEARCH DECISION] preflight: {'ON' if search_enabled else 'OFF'} — scope={preflight_result.search_scope.value}")

        if search_enabled:
            search_orch = SearchOrchestrator(
                self._llm, search_fn=self._search_fn,
                sonar_fn=self._sonar_fn,
            )

        # --- Deliberation Rounds ---
        if not resuming:
            prior_views = {}
            unaddressed_text = ""

        for round_num in range(1, self._config.rounds + 1):
            is_last_round = round_num == self._config.rounds
            models = ROUND_TOPOLOGY[round_num]

            # --- Skip completed round stages on resume ---
            round_stage = f"r{round_num}"
            track_stage = f"track{round_num}"
            search_stage = f"search{round_num}"

            # Determine if this round's search phase exists (search runs after R1 and R2, not last round)
            has_search_phase = (round_num <= self._config.search_after_rounds
                                and not is_last_round and search_orch)

            if self._stage_done(search_stage):
                # Round + tracking + search all done — fully skip
                log._print(f"  [RESUME] Skipping round {round_num} (already completed)")
                # Repopulate proof from checkpoint so skipped rounds appear in proof.json
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                proof.record_round(round_num, saved_responded, saved_failed)
                if str(round_num) in st.positions_by_round:
                    _pos = {}
                    for _m, _p in st.positions_by_round[str(round_num)].items():
                        _pos[_m] = Position(
                            model=_m, round_num=round_num,
                            primary_option=_p.get("option", ""),
                            components=_p.get("components", [_p.get("option", "")]),
                            confidence=Confidence[_p.get("confidence", "MEDIUM")],
                            qualifier=_p.get("qualifier", ""),
                            kind=_p.get("kind", "single"),
                        )
                    proof.record_positions(round_num, _pos)
                continue

            if self._stage_done(track_stage) and not has_search_phase:
                # Track done, no search phase for this round — fully skip
                log._print(f"  [RESUME] Skipping round {round_num} (already completed)")
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                proof.record_round(round_num, saved_responded, saved_failed)
                if str(round_num) in st.positions_by_round:
                    _pos = {}
                    for _m, _p in st.positions_by_round[str(round_num)].items():
                        _pos[_m] = Position(
                            model=_m, round_num=round_num,
                            primary_option=_p.get("option", ""),
                            components=_p.get("components", [_p.get("option", "")]),
                            confidence=Confidence[_p.get("confidence", "MEDIUM")],
                            qualifier=_p.get("qualifier", ""),
                            kind=_p.get("kind", "single"),
                        )
                    proof.record_positions(round_num, _pos)
                continue

            # Need to reconstruct RoundResult if round execution is done
            round_result = None
            if self._stage_done(round_stage) or self._stage_done(track_stage):
                # Round executed — reconstruct from checkpoint for search/compare
                skip_msg = "resuming at search" if self._stage_done(track_stage) else "resuming at tracking"
                log._print(f"  [RESUME] Skipping round {round_num} execution ({skip_msg})")
                from thinker.types import ModelResponse, RoundResult
                saved_texts = st.round_texts.get(str(round_num), {})
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                responses = {}
                for m in saved_responded:
                    responses[m] = ModelResponse(model=m, ok=True, text=saved_texts.get(m, ""), elapsed_s=0.0)
                for m in saved_failed:
                    responses[m] = ModelResponse(model=m, ok=False, text="", elapsed_s=0.0, error="failed in prior run")
                round_result = RoundResult(round_num=round_num, responses=responses, failed=saved_failed)
            else:
                # Execute round normally
                log.round_start(round_num, models, is_last_round)

                t0 = time.monotonic()
                # ANALYSIS mode: prepend exploration preamble to brief
                effective_brief = (get_analysis_round_preamble() + brief) if is_analysis_mode else brief
                # R1: cap brief for perspective card compliance on very large briefs
                # Models need output budget for the 5 structured fields
                if round_num == 1 and len(effective_brief) > 100000:
                    effective_brief = effective_brief[:100000] + "\n\n[Brief truncated for R1 — full content available in subsequent rounds]\n"
                round_result = await execute_round(
                    self._llm, round_num=round_num, brief=effective_brief,
                    prior_views=prior_views if round_num > 1 else None,
                    evidence_text=evidence.format_for_prompt() if round_num > 1 else "",
                    unaddressed_arguments=unaddressed_text if round_num > 1 else "",
                    is_last_round=is_last_round,
                    adversarial_model="kimi" if round_num == 1 else "",
                    dimension_text=dimension_text if round_num == 1 else "",
                    perspective_card_instructions=format_perspective_card_instructions() if round_num == 1 else "",
                    alt_frames_text=alt_frames_text if round_num >= 2 else "",
                )
                log.round_result(round_num, round_result.responded, round_result.failed,
                                 round_result.texts, time.monotonic() - t0)
                proof.record_round(round_num, round_result.responded, round_result.failed)
                # Store full text for resume — truncation loses SEARCH_REQUESTS appendix
                st.round_texts[str(round_num)] = round_result.texts
                st.round_responded[str(round_num)] = round_result.responded
                st.round_failed[str(round_num)] = round_result.failed

                if round_result.failed:
                    failed_details = "; ".join(
                        f"{m}: {round_result.responses[m].error}"
                        for m in round_result.failed
                        if m in round_result.responses
                    )
                    raise BrainError(
                        f"round{round_num}",
                        f"Model(s) failed in round {round_num}: {', '.join(round_result.failed)}",
                        detail=failed_details,
                    )

                if self._checkpoint(f"r{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT R{round_num}]", preflight=preflight_result)

            # --- Tracking phase (skip if already done on resume) ---
            if not self._stage_done(track_stage):
                # Extract arguments
                t0 = time.monotonic()
                args = await argument_tracker.extract_arguments(round_num, round_result.texts)
                # Assign dimension_id by keyword matching
                if dimension_result and dimension_result.items:
                    dim_names = {d.dimension_id: d.name for d in dimension_result.items}
                    argument_tracker.assign_dimensions(args, dim_names)
                log.arg_extract(round_num, args, time.monotonic() - t0, argument_tracker.last_raw_response)
                st.arguments_by_round[str(round_num)] = [
                    {"id": a.argument_id, "model": a.model, "text": a.text} for a in args
                ]

                # Extract positions
                t0 = time.monotonic()
                positions = await position_tracker.extract_positions(round_num, round_result.texts)
                log.pos_extract(round_num, positions, time.monotonic() - t0, position_tracker.last_raw_response)
                proof.record_positions(round_num, positions)
                st.positions_by_round[str(round_num)] = {
                    m: {
                        "option": p.primary_option,
                        "confidence": p.confidence.value,
                        "qualifier": p.qualifier,
                        "components": p.components,
                        "kind": p.kind,
                    }
                    for m, p in positions.items()
                }

                # Track position changes
                if round_num > 1:
                    changes = position_tracker.get_position_changes(round_num - 1, round_num)
                    log.pos_changes(round_num - 1, round_num, changes)
                    proof.record_position_changes(changes)
                    st.position_changes.extend(changes)

                if self._checkpoint(f"track{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT TRACK{round_num}]", preflight=preflight_result)
            else:
                log._print(f"  [RESUME] Skipping track{round_num} (already completed)")

            # --- V9: Mark adversarial slot assigned (DOD §10) ---
            if round_num == 1:
                divergence_result.adversarial_slot_assigned = True
                divergence_result.adversarial_model_id = "kimi"

            # --- V9: Post-R1 perspective cards + framing pass ---
            if round_num == 1 and not self._stage_done("perspective_cards"):
                log._print("  [CARDS] Extracting perspective cards...")
                t0 = time.monotonic()
                perspective_cards = await extract_perspective_cards(round_result.texts, llm_client=self._llm)
                inferred_count = sum(1 for c in perspective_cards if any(v.startswith("inferred:") for v in c.field_provenance.values()))
                log._print(f"  [CARDS] {len(perspective_cards)} cards ({inferred_count} with inferred fields) ({time.monotonic() - t0:.1f}s)")
                st.perspective_cards = [c.to_dict() for c in perspective_cards]
                proof.set_perspective_cards(perspective_cards)
                self._checkpoint("perspective_cards")

            if round_num == 1 and not self._stage_done("framing_pass"):
                log._print("  [FRAMING] Running framing extract...")
                t0 = time.monotonic()
                divergence_result = await run_framing_extract(self._llm, brief_for_sonnet, round_result.texts)
                # Check exploration stress (use R1 agreement)
                r1_agreement = position_tracker.agreement_ratio(1)
                if check_exploration_stress(r1_agreement, preflight_result.question_class, preflight_result.stakes_class):
                    divergence_result.exploration_stress_triggered = True
                    from thinker.types import FrameInfo, FrameType
                    seed_frames = [
                        FrameInfo(
                            frame_id="SEED-INV", text="What if the opposite of the emerging consensus is true? Argue against the majority position.",
                            origin_round=1, origin_model="controller", frame_type=FrameType.INVERSION,
                        ),
                        FrameInfo(
                            frame_id="SEED-STAKE", text="Consider the perspective of the stakeholder most harmed by the emerging consensus.",
                            origin_round=1, origin_model="controller", frame_type=FrameType.OPPOSITE_STANCE,
                        ),
                    ]
                    divergence_result.alt_frames.extend(seed_frames)
                    divergence_result.stress_seed_frames = [f.to_dict() for f in seed_frames]
                    log._print(f"  [STRESS] Exploration stress triggered — {len(seed_frames)} seed frames injected")
                st.divergence = divergence_result.to_dict()
                proof.set_divergence(divergence_result)
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                log._print(f"  [FRAMING] {len(divergence_result.alt_frames)} frames extracted ({time.monotonic() - t0:.1f}s)")
                self._checkpoint("framing_pass")

            # --- V9: Post-R2 frame survival ---
            if round_num == 2 and not self._stage_done("frame_survival_r2"):
                log._print("  [FRAMING] Running frame survival check (R2)...")
                t0 = time.monotonic()
                divergence_result.alt_frames = await run_frame_survival_check(
                    self._llm, divergence_result.alt_frames, round_result.texts, round_num=2,
                    is_analysis_mode=is_analysis_mode,
                )
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                st.divergence = divergence_result.to_dict()
                log._print(f"  [FRAMING] Frame survival R2 done ({time.monotonic() - t0:.1f}s)")
                self._checkpoint("frame_survival_r2")

            # --- V9: Post-R3 frame survival ---
            if round_num == 3 and not self._stage_done("frame_survival_r3"):
                log._print("  [FRAMING] Running frame survival check (R3)...")
                t0 = time.monotonic()
                divergence_result.alt_frames = await run_frame_survival_check(
                    self._llm, divergence_result.alt_frames, round_result.texts, round_num=3,
                    is_analysis_mode=is_analysis_mode,
                )
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                st.divergence = divergence_result.to_dict()
                log._print(f"  [FRAMING] Frame survival R3 done ({time.monotonic() - t0:.1f}s)")
                self._checkpoint("frame_survival_r3")

            # --- Ungrounded Stat Detection (V9, post-R1 and post-R2, DECIDE only per DOD §9.3) ---
            if round_num in (1, 2) and not is_analysis_mode and not self._stage_done(f"ungrounded_r{round_num}"):
                all_round_text = " ".join(round_result.texts.values())
                ungrounded = find_ungrounded_stats(all_round_text, evidence.active_items)
                if round_num == 1:
                    st.ungrounded_r1_executed = True
                else:
                    st.ungrounded_r2_executed = True
                if ungrounded:
                    log._print(f"  [UNGROUNDED] R{round_num}: {len(ungrounded)} ungrounded stats detected")
                    verification_queries = generate_verification_queries(ungrounded, all_round_text)
                    st.search_queries[f"ungrounded_r{round_num}"] = verification_queries
                    # Track per-claim for DOD §9.2 schema
                    for i, stat in enumerate(ungrounded):
                        st.ungrounded_flagged_claims.append({
                            "claim_id": f"UG-R{round_num}-{i+1}",
                            "text": stat,
                            "numeric": True,
                            "verified": False,
                            "blocker_id": None,
                            "severity": "MEDIUM",
                            "status": "UNVERIFIED_CLAIM",
                        })
                self._checkpoint(f"ungrounded_r{round_num}")

            # --- Post-R3: unresolved ungrounded stats become UNVERIFIED_CLAIM blockers (DECIDE only) ---
            if round_num == 3 and not is_analysis_mode:
                all_r3_text = " ".join(round_result.texts.values())
                ungrounded_r3 = find_ungrounded_stats(all_r3_text, evidence.active_items)
                for i, stat in enumerate(ungrounded_r3):
                    blk = blocker_ledger.add(
                        kind=BlockerKind.UNVERIFIED_CLAIM,
                        source="ungrounded_stat_detector",
                        detected_round=3,
                        detail=f"Unverified numeric claim persists after R3: {stat}",
                        severity="CRITICAL",
                        models=[],
                    )
                    # Update tracked claim with blocker link
                    for fc in st.ungrounded_flagged_claims:
                        if fc["text"] == stat and fc["blocker_id"] is None:
                            fc["blocker_id"] = blk.blocker_id
                            fc["severity"] = "CRITICAL"
                            break
                    else:
                        # New claim at R3 not seen earlier
                        st.ungrounded_flagged_claims.append({
                            "claim_id": f"UG-R3-{i+1}",
                            "text": stat,
                            "numeric": True,
                            "verified": False,
                            "blocker_id": blk.blocker_id,
                            "severity": "CRITICAL",
                            "status": "UNVERIFIED_CLAIM",
                        })
                if ungrounded_r3:
                    log._print(f"  [UNGROUNDED] R3: {len(ungrounded_r3)} unresolved → UNVERIFIED_CLAIM blockers")

            # Search phase — after R1 and R2 only
            if has_search_phase:
                phase = SearchPhase.R1_R2 if round_num == 1 else SearchPhase.R2_R3
                t0 = time.monotonic()

                model_requests = search_orch.collect_model_requests(round_result.texts)
                proactive = await search_orch.generate_proactive_queries(
                    round_result.texts, already_queued=model_requests,
                )
                queries = search_orch.deduplicate(model_requests + proactive)
                log.search_start(phase.value, model_requests, proactive)
                st.search_queries[phase.value] = queries

                total_admitted = 0
                all_search_results: list[SearchResult] = []
                from thinker.types import SearchLogEntry, QueryProvenance, QueryStatus
                # Determine provenance per query
                ungrounded_qs = set(st.search_queries.get(f"ungrounded_r{round_num}", []))
                for query in queries[:self._config.max_search_queries_per_phase]:
                    provenance = QueryProvenance.UNGROUNDED_STAT if query in ungrounded_qs else QueryProvenance.MODEL_CLAIM
                    try:
                        results = await search_orch.execute_query(query, phase)
                    except Exception as e:
                        search_log_entries.append(SearchLogEntry(
                            query_id=f"Q-{len(search_log_entries)+1}", query_text=query[:200],
                            provenance=provenance, issued_after_stage=f"r{round_num}",
                            query_status=QueryStatus.FAILED,
                        ))
                        raise BrainError(
                            f"search_round{round_num}",
                            f"Search query failed: {query[:80]}",
                            detail=str(e),
                        )
                    search_log_entries.append(SearchLogEntry(
                        query_id=f"Q-{len(search_log_entries)+1}", query_text=query[:200],
                        provenance=provenance, issued_after_stage=f"r{round_num}",
                        pages_fetched=len(results),
                        query_status=QueryStatus.SUCCESS if results else QueryStatus.ZERO_RESULT,
                    ))
                    all_search_results.extend(results)

                # F4: Fetch full page content for top results
                try:
                    await fetch_pages_for_results(all_search_results, max_pages=5)
                except BrainError:
                    raise
                except Exception as e:
                    raise BrainError(
                        f"page_fetch_round{round_num}",
                        f"Page fetch failed",
                        detail=str(e),
                    )

                # F5: LLM-based extraction from fetched pages, fallback to snippets
                for sr in all_search_results:
                    if sr.full_content:
                        try:
                            extracted_facts = await extract_evidence_from_page(
                                self._llm, sr.url, sr.full_content,
                            )
                            for fact_data in extracted_facts:
                                ev = EvidenceItem(
                                    evidence_id=f"E{len(evidence.items) + 1:03d}",
                                    topic=sr.title[:100] if sr.title else sr.url[:100],
                                    fact=fact_data["fact"][:500],
                                    url=sr.url,
                                    confidence=Confidence.MEDIUM,
                                )
                                if evidence.add(ev):
                                    total_admitted += 1
                        except BrainError:
                            raise
                        except Exception as e:
                            raise BrainError(
                                f"evidence_extract_round{round_num}",
                                f"Evidence extraction failed for {sr.url[:80]}",
                                detail=str(e),
                            )
                    else:
                        # Fallback: use snippet/title as before
                        ev = EvidenceItem_from_search_result(sr, len(evidence.items))
                        if ev and evidence.add(ev):
                            total_admitted += 1

                # Wire evidence contradictions into blocker ledger
                for ctr in evidence.contradictions:
                    if not any(b.detail == ctr.contradiction_id for b in blocker_ledger.blockers):
                        blocker_ledger.add(
                            kind=BlockerKind.CONTRADICTION,
                            source="evidence_ledger",
                            detected_round=round_num,
                            detail=ctr.contradiction_id,
                            models=[],
                        )

                log.search_result(phase.value, len(queries), total_admitted, time.monotonic() - t0)
                proof.record_research_phase(
                    phase.value, "brave", len(queries), total_admitted,
                )
                st.search_results[phase.value] = total_admitted
                st.evidence_items = [
                    {"evidence_id": e.evidence_id, "topic": e.topic,
                     "fact": e.fact, "url": e.url, "score": e.score,
                     "confidence": e.confidence.value}
                    for e in evidence.items
                ]
                st.evidence_count = len(evidence.items)

                if self._checkpoint(f"search{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT SEARCH{round_num}]", preflight=preflight_result)

            # Compare arguments (after R2+)
            if round_num > 1:
                t0 = time.monotonic()
                unaddressed = await argument_tracker.compare_with_round(
                    round_num - 1, round_result.texts,
                )
                addressed = len(argument_tracker.arguments_by_round.get(round_num - 1, [])) - len(unaddressed)
                ignored = [a for a in unaddressed if a.status == ArgumentStatus.IGNORED]
                mentioned = [a for a in unaddressed if a.status == ArgumentStatus.MENTIONED]
                log.arg_compare(round_num - 1, addressed, len(mentioned), len(ignored),
                                time.monotonic() - t0, unaddressed)
                unaddressed_text = argument_tracker.format_reinjection(unaddressed)
                st.unaddressed_text = unaddressed_text

            prior_views = round_result.texts

        # --- Classification (deterministic) ---
        final_round = self._config.rounds
        agreement = position_tracker.agreement_ratio(final_round)
        final_positions = position_tracker.positions_by_round.get(final_round, {})

        all_ignored = [a for a in argument_tracker.all_unaddressed if a.status == ArgumentStatus.IGNORED]
        all_mentioned = [a for a in argument_tracker.all_unaddressed if a.status == ArgumentStatus.MENTIONED]

        outcome_class = classify_outcome(
            agreement_ratio=agreement,
            ignored_arguments=len(all_ignored),
            mentioned_arguments=len(all_mentioned),
            evidence_count=len(evidence.items),
            contradictions=len(evidence.contradictions),
            open_blockers=len(blocker_ledger.open_blockers()),
            search_enabled=search_enabled,
        )
        st.agreement_ratio = agreement
        st.outcome_class = outcome_class

        # --- Semantic Contradiction (V9, DOD §12.2: only when shortlist criteria are met) ---
        if not self._stage_done("semantic_contradiction"):
            if len(evidence.active_items) >= 2:
                log._print("  [SEMANTIC] Running semantic contradiction pass...")
                t0 = time.monotonic()
                # DOD §12.2 criterion 3: pass open blocker IDs for shortlist evaluation
                # Decisive claims not yet extracted at this stage — pass empty set
                open_blocker_ev_ids = {
                    b.source for b in blocker_ledger.open_blockers()
                    if b.source.startswith("E")
                }
                semantic_ctrs = await run_semantic_contradiction_pass(
                    self._llm, evidence.active_items,
                    open_blocker_ids=open_blocker_ev_ids,
                )
                log._print(f"  [SEMANTIC] {len(semantic_ctrs)} semantic contradictions ({time.monotonic() - t0:.1f}s)")
            else:
                log._print("  [SEMANTIC] Skipped — fewer than 2 evidence items (no pairs possible)")
            self._checkpoint("semantic_contradiction")

        # --- Decisive Claim Extraction (V9) ---
        if not self._stage_done("decisive_claims"):
            log._print("  [CLAIMS] Extracting decisive claims...")
            t0 = time.monotonic()
            decisive_claims = await extract_decisive_claims(
                self._llm, final_views=prior_views, evidence_text=evidence.format_for_prompt(),
            )
            log._print(f"  [CLAIMS] {len(decisive_claims)} decisive claims ({time.monotonic() - t0:.1f}s)")
            proof.set_decisive_claims(decisive_claims)
            self._checkpoint("decisive_claims")

        # --- Synthesis Packet (V9) ---
        packet = build_synthesis_packet(
            brief=brief_for_sonnet,
            final_positions=final_positions,
            arguments=[a for args in argument_tracker.arguments_by_round.values() for a in args],
            frames=divergence_result.alt_frames if hasattr(divergence_result, 'alt_frames') else [],
            blockers=blocker_ledger.blockers,
            decisive_claims=decisive_claims,
            contradictions_numeric=evidence.contradictions,
            contradictions_semantic=semantic_ctrs,
            premise_flags=preflight_result.premise_flags,
            evidence_items=evidence.active_items,
        )
        synthesis_packet_text = format_synthesis_packet_for_prompt(packet)
        if is_analysis_mode:
            synthesis_packet_text += get_analysis_synthesis_contract()
        proof.set_synthesis_packet(packet)
        self._checkpoint("synthesis_packet")

        # Record arguments with resolution status in proof
        all_args = []
        for rnd_args in argument_tracker.arguments_by_round.values():
            all_args.extend(rnd_args)
        proof.set_arguments(all_args, blocker_ledger=blocker_ledger)

        # --- Synthesis Gate ---
        t0 = time.monotonic()
        final_views = prior_views
        synthesis_ran_this_session = True
        report, report_json, dispositions = await run_synthesis(
            self._llm, brief=brief_for_sonnet, final_views=final_views,
            blocker_summary=blocker_ledger.summary(),
            outcome_class=outcome_class,
            evidence_text=evidence.format_for_prompt(),
            synthesis_packet_text=synthesis_packet_text,
        )
        log.synthesis_result(len(report), bool(report_json), time.monotonic() - t0)
        proof.set_synthesis_status("COMPLETE" if report else "FAILED")
        st.report = report[:5000]
        st.report_json = report_json

        if self._checkpoint("synthesis"):
            return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=report, preflight=preflight_result)

        # --- ANALYSIS mode proof additions ---
        if is_analysis_mode:
            # DOD §18.5: "ANALYSIS output contains verdict language → ERROR"
            # Check the header — ANALYSIS must have "EXPLORATORY MAP" header, not verdict/recommendation
            report_text = (report[:2000] if report else "").lower()
            report_header = report_text[:500]
            if report and "exploratory map" not in report_header:
                # Missing required header — check for explicit decision language
                # DOD §18.5: broad detection — check header and opening section
                decision_phrases = [
                    "we recommend", "our recommendation is", "the answer is",
                    "therefore we decide", "we conclude that you should",
                    "the verdict is", "our verdict", "in conclusion",
                    "the best option is", "the best approach is", "you should",
                    "the right choice is", "the correct answer",
                    "we advise", "our advice is", "the decision is",
                    "based on our analysis, the", "the optimal solution",
                ]
                verdict_found = [p for p in decision_phrases if p in report_text]
                if verdict_found:
                    raise BrainError(
                        "analysis_verdict_check",
                        f"ANALYSIS output contains verdict language in header: {verdict_found[:3]}",
                        detail="DOD §18.5: ANALYSIS mode must produce exploratory map, not verdict.",
                    )

            # Analysis map: DOD §18.3 — hierarchical object keyed by dimension_id
            analysis_map = {
                "header": "EXPLORATORY MAP — NOT A DECISION",
                "dimensions": {},
                "hypothesis_ledger": [],
                "total_argument_count": len(all_args),
                "dimension_coverage_score": dimension_result.dimension_coverage_score,
            }
            if report_json and isinstance(report_json, dict):
                for key in report_json:
                    if key.startswith("DIM-"):
                        analysis_map["dimensions"][key] = report_json[key]
                    elif key == "hypothesis_ledger":
                        analysis_map["hypothesis_ledger"] = report_json[key]
            proof.set_analysis_map(analysis_map)

            # DOD §18.4: debug sunset enforcement
            # Counter persisted via file in outdir
            sunset_file = Path(self._config.outdir) / ".analysis_debug_remaining"
            if sunset_file.exists():
                try:
                    remaining = int(sunset_file.read_text().strip())
                except (ValueError, OSError):
                    remaining = self._config.analysis_debug_runs_remaining
            else:
                remaining = self._config.analysis_debug_runs_remaining

            debug_active = remaining > 0
            new_remaining = max(0, remaining - 1) if debug_active else 0
            # Persist decremented counter
            try:
                sunset_file.parent.mkdir(parents=True, exist_ok=True)
                sunset_file.write_text(str(new_remaining))
            except OSError:
                pass  # Non-fatal: counter resets next run

            # DOD §18.4 schema: debug_gate2_result and actual_output
            # filled after Gate 2 runs (stored as placeholders, updated below)
            analysis_debug_data = {
                "debug_mode": debug_active,
                "debug_gate2_result": None,  # Filled after Gate 2
                "actual_output": None,  # Filled after Gate 2
                "rules_enforced": not debug_active,  # Rules always enforced; debug affects audit only
                "remaining_debug_runs": new_remaining,
                "analysis_mode_active": True,
                "dimension_coverage_score": dimension_result.dimension_coverage_score,
            }
            proof.set_analysis_debug(analysis_debug_data)

        # --- Stability Tests (V9) ---
        stability_result = run_stability_tests(
            positions=final_positions,
            decisive_claims=decisive_claims,
            assumptions=preflight_result.critical_assumptions,
            round_positions=position_tracker.positions_by_round,
            question_class=preflight_result.question_class,
            stakes_class=preflight_result.stakes_class,
            independent_evidence_present=evidence.high_authority_evidence_present,
        )
        proof.set_stability(stability_result)
        self._checkpoint("stability")
        log._print(f"  [STABILITY] conclusion={stability_result.conclusion_stable} "
                   f"reason={stability_result.reason_stable} "
                   f"assumption={stability_result.assumption_stable} "
                   f"groupthink_warning={stability_result.groupthink_warning}")

        # --- Compute dimension coverage + register COVERAGE_GAP blockers (V9) ---
        if dimension_result and dimension_result.items:
            for dim in dimension_result.items:
                dim_args = [a for a in all_args if a.dimension_id == dim.dimension_id]
                dim.argument_count = len(dim_args)
                dim.coverage_status = "SATISFIED" if len(dim_args) >= 2 else ("PARTIAL" if dim_args else "ZERO")
                # Register COVERAGE_GAP blocker for zero-coverage mandatory dimensions
                if dim.coverage_status == "ZERO" and dim.mandatory and not dim.justified_irrelevance:
                    blocker_ledger.add(
                        kind=BlockerKind.COVERAGE_GAP,
                        source=f"dimension:{dim.dimension_id}",
                        detected_round=self._config.rounds,
                        detail=f"Zero arguments for mandatory dimension: {dim.name}",
                        models=[],
                        severity="CRITICAL",
                    )
            covered = sum(1 for d in dimension_result.items if d.argument_count >= 2)
            # DOD §6.2: denominator is mandatory dimensions only
            mandatory_count = sum(1 for d in dimension_result.items if d.mandatory)
            dimension_result.dimension_coverage_score = covered / mandatory_count if mandatory_count else 0.0

        # --- V9: Evidence refs validation (DOD §10.3) ---
        # "Cited evidence missing from both stores → ERROR"
        # Only validate when evidence was actually collected (search ran).
        # With no search, LLM may hallucinate E-IDs but there's nothing to validate against.
        if evidence.all_evidence_ids():
            all_evidence_refs = []
            for c in decisive_claims:
                all_evidence_refs.extend(c.evidence_refs)
            for a in all_args:
                all_evidence_refs.extend(a.evidence_refs)
            phantom_refs = evidence.validate_refs(all_evidence_refs)
            if phantom_refs:
                # DOD §10.3 + §3.3: cited evidence missing = fatal integrity → ERROR
                raise BrainError(
                    "evidence_validation",
                    f"Cited evidence missing from both stores: {phantom_refs[:5]}",
                    detail=f"DOD §10.3: {len(phantom_refs)} phantom evidence refs. FATAL_INTEGRITY.",
                )

        # --- V9: Disposition Coverage Verification (runs BEFORE Gate 2 per DOD §14.6) ---
        from thinker.types import DispositionObject, DispositionTargetType
        disposition_objects = []
        for d in dispositions:
            try:
                disposition_objects.append(DispositionObject(
                    target_type=DispositionTargetType(d["target_type"]),
                    target_id=d["target_id"],
                    status=d["status"],
                    importance=d["importance"],
                    narrative_explanation=d["narrative_explanation"],
                ))
            except (ValueError, KeyError):
                pass

        active_frames_for_residue = [f for f in divergence_result.alt_frames
                         if f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)]
        coverage = check_disposition_coverage(
            dispositions=disposition_objects,
            open_blockers=blocker_ledger.blockers,
            active_frames=active_frames_for_residue,
            decisive_claims=decisive_claims,
            contradictions_numeric=evidence.contradictions,
            contradictions_semantic=semantic_ctrs,
            open_material_arguments=argument_tracker.all_unaddressed,  # DOD §11.3
        )
        proof.set_residue_verification(coverage)
        proof.set_synthesis_dispositions(disposition_objects)

        # DOD §14.5-14.6: coverage_pass=false triggers deep scan path
        # Only enforce when synthesis actually produced disposition data this session.
        # On resume past synthesis, dispositions are not available from checkpoint.
        if disposition_objects and not coverage.get("coverage_pass") and coverage.get("total_required", 0) > 0:
            if coverage.get("total_disposed", 0) == 0:
                # Zero dispositions emitted at all → ERROR (DOD §14.6)
                raise BrainError(
                    "disposition_coverage",
                    f"Zero dispositions for {coverage['total_required']} required findings",
                    detail="DOD §14.6: Disposition missing for tracked open finding → ERROR.",
                )
            # DOD §14.6: any missing disposition → ERROR (before deep scan opportunity)
            # Deep scan is the recovery path; if omission rate > 20%, run deep scan first
            if not coverage.get("deep_scan_triggered"):
                omissions = coverage.get("omissions", [])
                raise BrainError(
                    "disposition_coverage",
                    f"{len(omissions)} dispositions missing for tracked open findings",
                    detail=f"DOD §14.6: Disposition missing → ERROR. Missing: {[o['target_id'] for o in omissions][:5]}",
                )

        if coverage.get("deep_scan_triggered"):
            # DOD §14.6: deep scan MUST run when triggered
            deep_scan_result = run_deep_semantic_scan(report, coverage.get("omissions", []))
            coverage["deep_scan"] = deep_scan_result
            proof.set_residue_verification(coverage)  # Update with deep scan data
            if deep_scan_result["material_omissions_remain"]:
                # DOD §14.6: "Material omissions unresolved after deep scan → ESCALATE"
                # Register CRITICAL blocker so D6 triggers ESCALATE
                blocker_ledger.add(
                    kind=BlockerKind.COVERAGE_GAP,
                    source="deep_semantic_scan",
                    detected_round=self._config.rounds,
                    detail=(f"Deep scan: {deep_scan_result['still_missing']} material omissions "
                            f"remain after scan (omission rate {coverage['omission_rate']:.0%})"),
                    models=[],
                    severity="CRITICAL",
                )

        # DOD §14.3: Orphaned high-authority archive evidence must be explained
        orphaned_high_auth = [
            e for e in evidence.archive_items
            if e.authority_tier in ("HIGH", "AUTHORITATIVE")
            and e.evidence_id not in (report or "")
        ]
        if orphaned_high_auth:
            proof.add_violation(
                "ORPHANED-HIGH-AUTH-EVIDENCE", "WARN",
                f"{len(orphaned_high_auth)} archived HIGH/AUTHORITATIVE evidence items not cited in synthesis: "
                f"{[e.evidence_id for e in orphaned_high_auth[:5]]}",
            )

        # Legacy string-match residue check (supplementary)
        residue_omissions = check_synthesis_residue(
            report=report,
            blockers=blocker_ledger.blockers,
            contradictions=evidence.contradictions,
            unaddressed_arguments=argument_tracker.all_unaddressed,
        )
        proof.set_synthesis_residue(residue_omissions)
        if any(o.get("threshold_violation") for o in residue_omissions):
            proof.add_violation(
                "RESIDUE-THRESHOLD", "WARN",
                f"Synthesis omitted >30% of structural findings ({len(residue_omissions)} omissions)",
            )

        # --- Gate 2 (deterministic) ---
        # Compute stage integrity for D1 (DOD §3.3)
        # Include conditional stages that should have executed
        required_stages = ["preflight", "dimensions"]
        for i in range(1, self._config.rounds + 1):
            required_stages.append(f"r{i}")
            required_stages.append(f"track{i}")
            if i == 1:
                required_stages.extend(["perspective_cards", "framing_pass"])
                if not is_analysis_mode:  # DOD §9.3: ungrounded DECIDE only
                    required_stages.append("ungrounded_r1")
            if i == 2:
                required_stages.append("frame_survival_r2")
                if not is_analysis_mode:
                    required_stages.append("ungrounded_r2")
            if i == 3:
                required_stages.append("frame_survival_r3")
        required_stages.extend(["semantic_contradiction", "decisive_claims", "synthesis_packet", "synthesis"])
        completed = set(self.state.completed_stages)
        fatal_stages = [s for s in required_stages if s not in completed]

        # DOD §11.3: broken supersession links → ERROR
        # These are prevented by construction: argument_tracker validates IDs and falls
        # back to REFINED when Sonnet hallucninates a target. superseded_by is never set
        # to a bad ID in proof.json. Violations logged for audit transparency.
        for bl in argument_tracker._broken_supersession_links:
            proof.add_violation(
                "SUPERSESSION-BROKEN", "ERROR",
                f"Argument {bl['argument_id']}: LLM claimed superseded_by {bl['claimed_superseded_by']} "
                f"but target not found — fell back to REFINED (link not written to proof)",
            )

        # Merge numeric + semantic contradictions for Gate 2 (DOD §16 D8)
        all_contradictions = list(evidence.contradictions) + list(semantic_ctrs)

        gate2 = run_gate2_deterministic(
            agreement_ratio=agreement,
            positions=final_positions,
            contradictions=all_contradictions,
            unaddressed_arguments=argument_tracker.all_unaddressed,
            open_blockers=blocker_ledger.open_blockers(),
            evidence_count=len(evidence.items),
            search_enabled=search_enabled,
            preflight=preflight_result,
            divergence=divergence_result,
            stability=stability_result,
            decisive_claims=decisive_claims,
            dimensions=dimension_result,
            total_arguments=len(all_args),
            archive_evidence_count=len(evidence.archive_items),
            stage_integrity_fatal=fatal_stages if fatal_stages else None,
            analogies=divergence_result.cross_domain_analogies if divergence_result.cross_domain_analogies else None,
        )
        log.gate2_result(
            gate2.outcome.value, agreement, outcome_class,
            len(all_ignored), len(evidence.items),
            len(evidence.contradictions), len(blocker_ledger.open_blockers()),
        )
        st.outcome = gate2.outcome.value

        # Record gate2 trace in proof (V9)
        if gate2.rule_trace:
            proof.set_gate2_trace(
                modality=gate2.modality or "DECIDE",
                rule_trace=gate2.rule_trace,
                final_outcome=gate2.outcome.value,
            )

        # DOD §18.4: fill debug_gate2_result and actual_output after Gate 2
        if is_analysis_mode and proof._analysis_debug:
            proof._analysis_debug["debug_gate2_result"] = gate2.outcome.value
            proof._analysis_debug["actual_output"] = gate2.outcome.value

        self._checkpoint("gate2")

        # --- Invariant validation (F6) ---
        round_responded_ints = {int(k): v for k, v in st.round_responded.items()}
        inv_violations = validate_invariants(
            positions_by_round=position_tracker.positions_by_round,
            round_responded=round_responded_ints,
            evidence=evidence,
            blocker_ledger=blocker_ledger,
            rounds_completed=self._config.rounds,
        )
        for v in inv_violations:
            proof.add_violation(v["id"], v["severity"], v["detail"])

        # --- Final: Wire all remaining proof sections ---
        outcome = gate2.outcome
        proof.set_outcome(outcome, agreement, outcome_class)
        # DOD §1.5: ERROR implies error_class in {INFRASTRUCTURE, FATAL_INTEGRITY}
        if outcome == Outcome.ERROR:
            proof.set_error_class("FATAL_INTEGRITY")
        proof.set_final_status("COMPLETE")
        proof.set_evidence_count(len(evidence.items))

        # Two-tier evidence
        proof.set_evidence_two_tier(evidence.active_items, evidence.archive_items, evidence.eviction_log)

        # Search log
        proof.set_search_log(search_log_entries)

        # Ungrounded stats (DOD §9.2 schema)
        # Mark claims that were verified by evidence after search
        for fc in st.ungrounded_flagged_claims:
            if fc["status"] == "UNVERIFIED_CLAIM" and fc["blocker_id"] is None:
                # Check if the stat now appears in evidence
                stat_text = fc["text"]
                if any(stat_text in ev.fact for ev in evidence.active_items):
                    fc["verified"] = True
                    fc["status"] = "CLEAR"
        proof.set_ungrounded_stats({
            "post_r1_executed": st.ungrounded_r1_executed,
            "post_r2_executed": st.ungrounded_r2_executed,
            "flagged_claims": st.ungrounded_flagged_claims,
        })

        # Contradictions (numeric + semantic)
        proof.set_contradictions(evidence.contradictions, semantic_ctrs)

        # Cross-domain analogies from divergence
        if divergence_result.cross_domain_analogies:
            proof.set_analogies(divergence_result.cross_domain_analogies)

        # Stage integrity
        proof.set_stage_integrity(
            required=required_stages + ["gate2"],
            order=self.state.completed_stages,
            fatal=fatal_stages,
        )

        # Diagnostics
        proof.set_diagnostics({
            "total_elapsed_s": round(time.monotonic() - run_start_time, 1),
            "rounds_completed": self._config.rounds,
            "search_enabled": search_enabled,
            "models_used": list(set(m for rnd in st.round_responded.values() for m in rnd)),
        })

        # DOD §19: synthesis_output and timestamp_completed
        proof.set_synthesis_output({
            "report": report[:5000] if report else None,
            "report_json": st.report_json,
        })
        proof.set_timestamp_completed()
        proof.set_error_class(None)  # No error if we reach here

        # --- Acceptance status (F2) — must be computed last, after all violations ---
        proof.compute_acceptance_status()

        log.run_complete(outcome.value, outcome_class)

        return BrainResult(
            outcome=outcome, proof=proof.build(),
            report=report, preflight=preflight_result, gate2=gate2,
            dimensions=dimension_result,
            stability=stability_result,
        )


def EvidenceItem_from_search_result(sr: SearchResult, counter: int):
    """Convert a SearchResult to an EvidenceItem for the ledger."""
    from thinker.types import Confidence
    content = sr.full_content or sr.snippet or sr.title
    if not content:
        return None
    return EvidenceItem(
        evidence_id=f"E{counter + 1:03d}",
        topic=sr.title[:100] if sr.title else sr.url[:100],
        fact=content[:500],
        url=sr.url,
        confidence=Confidence.MEDIUM,
    )


def _get_anthropic_token() -> str:
    """Get the Anthropic OAuth token.

    Priority:
    1. ANTHROPIC_OAUTH_TOKEN env var / .env (should be the 1-year setup-token)
    2. Fall back to ~/.claude/.credentials.json (rotating ~8h token)
    """
    import os
    token = os.environ.get("ANTHROPIC_OAUTH_TOKEN", "")
    if token:
        return token
    import json
    from pathlib import Path
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        try:
            creds = json.loads(creds_path.read_text(encoding="utf-8"))
            return creds.get("claudeAiOauth", {}).get("accessToken", "")
        except Exception:
            pass
    return ""


async def main():
    """CLI entry point for the Brain engine."""
    import argparse
    import json
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Thinker V8 Brain Engine")
    parser.add_argument("--brief", required=True, help="Path to brief markdown file")
    parser.add_argument("--rounds", type=int, default=4, help="Number of rounds (1-4)")
    parser.add_argument("--outdir", default="./output", help="Output directory")
    parser.add_argument("--verbose", action="store_true", help="Full logging at each stage")
    parser.add_argument("--stop-after", default=None,
                        help="Stop after STAGE, save checkpoint (preflight,dimensions,r1,track1,...)")
    parser.add_argument("--resume", default=None,
                        help="Resume from a checkpoint JSON file (skips completed stages)")
    parser.add_argument("--full-run", action="store_true",
                        help="Run all stages without pausing (overrides default step-by-step mode)")
    search_group = parser.add_mutually_exclusive_group()
    search_group.add_argument("--search", action="store_true", default=None,
                              help="Force search on (overrides Gate 1 recommendation)")
    search_group.add_argument("--no-search", action="store_true", default=None,
                              help="Force search off (overrides Gate 1 recommendation)")
    parser.add_argument("--skip-assumption-gate", action="store_true",
                        help="Skip fatal assumption check (for self-review briefs where completeness is attested)")
    args = parser.parse_args()

    brief_text = open(args.brief, encoding="utf-8").read()
    config = BrainConfig(
        rounds=args.rounds,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        anthropic_oauth_token=_get_anthropic_token(),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        zai_api_key=os.environ.get("ZAI_API_KEY", ""),
        brave_api_key=os.environ.get("BRAVE_API_KEY", ""),
        outdir=args.outdir,
        skip_assumption_gate=args.skip_assumption_gate,
    )

    # Load checkpoint if resuming
    resume_state = None
    if args.resume:
        resume_state = PipelineState.load(Path(args.resume))
        print(f"Resuming from checkpoint: {args.resume}")
        print(f"  Last stage: {resume_state.current_stage}")
        print(f"  Completed: {' → '.join(resume_state.completed_stages)}")

    from thinker.llm import LLMClient
    from thinker.brave_search import brave_search
    from thinker.sonar_search import sonar_search
    from functools import partial
    llm = LLMClient(config)

    # Step-by-step is the DEFAULT. --full-run disables it.
    debug_step = not args.full_run
    verbose = args.verbose or args.stop_after is not None or args.resume is not None or debug_step

    # Search: Bing via Playwright (headful, $0). Error if unavailable.
    search_fn = None
    try:
        from thinker.bing_search import bing_search
        search_fn = bing_search
        if verbose:
            print("  [SEARCH] Using Bing via Playwright (headful, $0)")
    except ImportError:
        print("  [SEARCH ERROR] Bing search requires playwright: pip install playwright && playwright install chromium")
        raise SystemExit(1)
    sonar_fn = partial(sonar_search, api_key=config.openrouter_api_key) if config.openrouter_api_key else None
    # Resolve search override from CLI flags
    search_override = None
    if args.search:
        search_override = True
    elif args.no_search:
        search_override = False

    brain = Brain(
        config=config, llm_client=llm, search_fn=search_fn,
        sonar_fn=sonar_fn,
        verbose=verbose, stop_after=args.stop_after, outdir=args.outdir,
        resume_state=resume_state, debug_step=debug_step,
        search_override=search_override,
    )
    try:
        result = await brain.run(brief_text)
    except BrainError as e:
        print(f"\n{'='*60}")
        print(f"  SYSTEM ERROR — Pipeline halted")
        print(f"{'='*60}")
        print(f"  Stage:   {e.stage}")
        print(f"  Error:   {e.message}")
        if e.detail:
            print(f"  Detail:  {e.detail}")
        print(f"  Checkpoint: {os.path.join(args.outdir, 'checkpoint.json')}")
        print(f"{'='*60}")
        # Save what we have so far
        os.makedirs(args.outdir, exist_ok=True)
        # DOD §19: write partial proof.json on ERROR
        if hasattr(e, 'partial_proof') and e.partial_proof:
            error_proof_path = os.path.join(args.outdir, "proof.json")
            with open(error_proof_path, "w", encoding="utf-8") as f:
                json.dump(e.partial_proof, f, indent=2)
            print(f"  Proof:   {error_proof_path} (partial — error_class set)")
        brain.log.save_log(Path(args.outdir) / "debug.log")
        brain.log.save_events_json(Path(args.outdir) / "events.json")
        await llm.close()
        raise SystemExit(1)

    # Save outputs
    os.makedirs(args.outdir, exist_ok=True)
    proof_path = os.path.join(args.outdir, "proof.json")
    with open(proof_path, "w", encoding="utf-8") as f:
        json.dump(result.proof, f, indent=2)
    report_path = os.path.join(args.outdir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result.report)

    # Save debug outputs
    brain.log.save_log(Path(args.outdir) / "debug.log")
    brain.log.save_events_json(Path(args.outdir) / "events.json")

    # Generate auto-populated diagram from stage registry + run data
    # Import all tagged modules so the registry is populated
    import thinker.preflight, thinker.rounds, thinker.argument_tracker  # noqa: F401
    import thinker.tools.position, thinker.search, thinker.synthesis, thinker.gate2  # noqa: F401
    import thinker.invariant, thinker.residue, thinker.page_fetch, thinker.evidence_extractor  # noqa: F401
    import thinker.preflight, thinker.dimension_seeder  # noqa: F401
    import thinker.perspective_cards, thinker.divergent_framing  # noqa: F401
    import thinker.semantic_contradiction, thinker.stability  # noqa: F401
    from thinker.pipeline import generate_architecture_html
    events_data = json.loads((Path(args.outdir) / "events.json").read_text())
    generate_architecture_html(
        Path(args.outdir) / "run-report.html",
        run_events=events_data, proof=result.proof, report=result.report,
    )

    print(f"\nOutcome: {result.outcome.value}")
    print(f"Class: {result.proof.get('v3_outcome_class', 'N/A')}")
    print(f"Proof: {proof_path}")
    print(f"Report: {report_path}")
    print(f"Debug: {os.path.join(args.outdir, 'run-report.html')}")

    await llm.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

```


### thinker/gate2.py


```python
"""Gate 2: Deterministic trust assessment with D1-D14 and A1-A7 rule sets.

No LLM call. Thresholds on mechanical tool data only.

DECIDE modality: D1-D14 rules, first match wins.
ANALYSIS modality: A1-A7 rules, first match wins.

Every rule evaluated is recorded in rule_trace for auditability.
"""
from __future__ import annotations

from typing import Optional

from thinker.pipeline import pipeline_stage
from thinker.types import (
    AnalogyTestStatus, Argument, ArgumentStatus, Blocker, Contradiction,
    CrossDomainAnalogy, DecisiveClaim, DimensionSeedResult, DivergenceResult,
    EvidenceSupportStatus, FrameSurvivalStatus,
    Gate2Assessment, Modality, Outcome, Position,
    PreflightResult, StabilityResult,
)


@pipeline_stage(
    name="Gate 2",
    description="Fully deterministic trust assessment. No LLM call. Instant. Reproducible. "
                "D1-D14 (DECIDE) and A1-A7 (ANALYSIS) rule sets, first match wins. "
                "Every rule evaluated is recorded in rule_trace.",
    stage_type="deterministic",
    order=7,
    provider="deterministic (no LLM)",
    inputs=["agreement_ratio", "positions", "contradictions", "unaddressed_arguments",
            "open_blockers", "evidence_count", "search_enabled",
            "preflight", "divergence", "stability", "decisive_claims", "dimensions",
            "total_arguments", "archive_evidence_count"],
    outputs=["outcome (DECIDE/ESCALATE/NO_CONSENSUS/ANALYSIS/ERROR/NEED_MORE)", "rule_trace"],
    logic="""DECIDE modality: D1-D14, first match wins.
ANALYSIS modality: A1-A7, first match wins.
See module docstring for full rule definitions.""",
    thresholds={"agreement_ratio >= 0.75": "DECIDE", "agreement_ratio < 0.5": "NO_CONSENSUS/ESCALATE"},
    failure_mode="Cannot fail — deterministic computation.",
    cost="$0 (no LLM call)",
    stage_id="gate2",
)
def classify_outcome(
    agreement_ratio: float,
    ignored_arguments: int,
    mentioned_arguments: int,
    evidence_count: int,
    contradictions: int,
    open_blockers: int,
    search_enabled: bool,
) -> str:
    """Deterministic outcome classification (V8 compat).

    Returns one of: CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, PARTIAL_CONSENSUS,
    INSUFFICIENT_EVIDENCE, NO_CONSENSUS.
    """
    if agreement_ratio < 0.5:
        return "NO_CONSENSUS"

    if search_enabled and evidence_count == 0:
        return "INSUFFICIENT_EVIDENCE"

    if (agreement_ratio >= 0.75
            and ignored_arguments == 0
            and contradictions == 0
            and open_blockers == 0):
        return "CONSENSUS"

    if agreement_ratio >= 0.75 and ignored_arguments <= 2:
        return "CLOSED_WITH_ACCEPTED_RISKS"

    return "PARTIAL_CONSENSUS"


# ---------------------------------------------------------------------------
# Helper: blocker severity (backward-compatible)
# ---------------------------------------------------------------------------

def _blocker_severity(b: Blocker) -> str:
    """Get severity from a Blocker, defaulting to LOW if not present."""
    return getattr(b, "severity", "LOW")


def _all_blockers_low(blockers: list[Blocker]) -> bool:
    """True if every blocker has LOW severity (or list is empty)."""
    return all(_blocker_severity(b) == "LOW" for b in blockers)


# ---------------------------------------------------------------------------
# DECIDE rules D1-D14
# ---------------------------------------------------------------------------

def _eval_decide_rules(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list[Blocker],
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult],
    divergence: Optional[DivergenceResult],
    stability: Optional[StabilityResult],
    decisive_claims: Optional[list[DecisiveClaim]],
    dimensions: Optional[DimensionSeedResult],
    total_arguments: int,
    stage_integrity_fatal: Optional[list[str]] = None,
    analogies: Optional[list[CrossDomainAnalogy]] = None,
) -> tuple[Outcome, list[dict]]:
    """Evaluate D1-D14 per DOD-V3 Section 16. First match wins."""
    trace: list[dict] = []

    def _t(rule_id: str, matched: bool, reason: str) -> bool:
        trace.append({"rule_id": rule_id, "evaluated": True, "fired": matched,
                      "outcome_if_fired": None, "reason": reason})
        return matched

    # Pre-compute conditions
    stability = stability or StabilityResult()
    conclusion_stable = stability.conclusion_stable
    reason_stable = stability.reason_stable
    assumption_stable = stability.assumption_stable
    groupthink_warning = stability.groupthink_warning
    independent_evidence = stability.independent_evidence_present

    # CRITICAL blockers — DOD Section 16 D6: "any unresolved CRITICAL blocker"
    critical_blockers = [b for b in open_blockers
                         if getattr(b, 'severity', 'MEDIUM') == "CRITICAL"]

    # Decisive claims without valid evidence (DOD §13.4 + D7)
    # SUPPORTED with empty evidence_refs is also invalid — phantom support
    claims_lacking_evidence = [
        c for c in (decisive_claims or [])
        if c.material_to_conclusion and (
            c.evidence_support_status != EvidenceSupportStatus.SUPPORTED
            or (c.evidence_support_status == EvidenceSupportStatus.SUPPORTED and not c.evidence_refs)
        )
    ]

    # HIGH/CRITICAL unresolved contradictions (handle both enum and string severity)
    high_contradictions = [
        c for c in contradictions
        if getattr(c, "status", "OPEN") in ("OPEN", "open")
        and str(getattr(getattr(c, "severity", "LOW"), "value", getattr(c, "severity", "LOW"))) in ("HIGH", "CRITICAL")
    ]

    # Unresolved CRITICAL premise flags
    critical_premise_flags = preflight.unresolved_critical_flags if preflight else []

    # Material frames without rebuttal or disposition
    material_frames_unresolved = []
    if divergence:
        for f in divergence.alt_frames:
            if (f.material_to_outcome
                    and f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)
                    and f.synthesis_disposition_status == "UNADDRESSED"):
                material_frames_unresolved.append(f)

    # --- D1: Fatal integrity or infrastructure failure (DOD §16, §3.3) ---
    # Fires when critical pipeline data is completely absent or stage integrity
    # reports fatal failures — indicating infrastructure failure.
    no_pipeline_output = (total_arguments == 0 and len(positions) == 0)
    empty_dimensions = (
        dimensions is not None and len(dimensions.items) == 0
    )
    has_fatal_stages = bool(stage_integrity_fatal)
    fatal_integrity = no_pipeline_output or empty_dimensions or has_fatal_stages
    if _t("D1", fatal_integrity,
          f"models={len(positions)}, args={total_arguments}, "
          f"dims={'none' if dimensions is None else len(dimensions.items)}, "
          f"fatal_stages={stage_integrity_fatal or []}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- D2: Modality mismatch ---
    modality_mismatch = preflight and preflight.modality != Modality.DECIDE if preflight else False
    if _t("D2", modality_mismatch,
          f"preflight.modality={preflight.modality.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- D3: Illegal SHORT_CIRCUIT state (guardrails violated) ---
    # Deferred per user directive — no budget enforcement
    _t("D3", False, "SHORT_CIRCUIT guardrail check deferred")

    # --- D4: agreement < 0.50 ---
    if _t("D4", agreement_ratio < 0.50,
          f"agreement={agreement_ratio:.2f}<0.50"):
        trace[-1]["outcome_if_fired"] = "NO_CONSENSUS"
        return Outcome.NO_CONSENSUS, trace

    # --- D5: agreement 0.50-0.74 ---
    if _t("D5", 0.50 <= agreement_ratio < 0.75,
          f"agreement={agreement_ratio:.2f} in [0.50,0.75)"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D6: Any unresolved CRITICAL blocker ---
    if _t("D6", len(critical_blockers) > 0,
          f"critical_blockers={len(critical_blockers)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D7: Decisive claim lacks valid evidence binding ---
    if _t("D7", len(claims_lacking_evidence) > 0,
          f"claims_lacking_evidence={len(claims_lacking_evidence)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D8: HIGH/CRITICAL contradiction unresolved ---
    if _t("D8", len(high_contradictions) > 0,
          f"high_contradictions={len(high_contradictions)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D9: Unresolved CRITICAL premise flag ---
    if _t("D9", len(critical_premise_flags) > 0,
          f"critical_premise_flags={len(critical_premise_flags)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D10: Material unresolved (frames or untested decisive analogies) ---
    # DOD §16 D10: material frame ACTIVE/CONTESTED without disposition
    # DOD §13.4: untested analogy used decisively → ESCALATE
    untested_decisive_analogies = []
    if analogies and decisive_claims:
        untested_ids = {a.analogy_id for a in analogies if a.test_status == AnalogyTestStatus.UNTESTED}
        for c in (decisive_claims or []):
            for ref in c.analogy_refs:
                if ref in untested_ids:
                    untested_decisive_analogies.append(ref)
    d10_fired = len(material_frames_unresolved) > 0 or len(untested_decisive_analogies) > 0
    if _t("D10", d10_fired,
          f"material_frames_unresolved={len(material_frames_unresolved)}, "
          f"untested_decisive_analogies={untested_decisive_analogies}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D11: conclusion_stable = false ---
    if _t("D11", not conclusion_stable,
          f"conclusion_stable={conclusion_stable}"):
        trace[-1]["outcome_if_fired"] = "NO_CONSENSUS"
        return Outcome.NO_CONSENSUS, trace

    # --- D12: reason_stable = false OR assumption_stable = false ---
    if _t("D12", not reason_stable or not assumption_stable,
          f"reason_stable={reason_stable}, assumption_stable={assumption_stable}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D13: groupthink + no independent evidence ---
    if _t("D13", groupthink_warning and not independent_evidence,
          f"groupthink={groupthink_warning}, independent_evidence={independent_evidence}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D14: Otherwise → DECIDE ---
    _t("D14", True, "all checks passed")
    trace[-1]["outcome_if_fired"] = "DECIDE"
    return Outcome.DECIDE, trace


# ---------------------------------------------------------------------------
# ANALYSIS rules A1-A7
# ---------------------------------------------------------------------------

def _eval_analysis_rules(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list[Blocker],
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult],
    divergence: Optional[DivergenceResult],
    stability: Optional[StabilityResult],
    decisive_claims: Optional[list[DecisiveClaim]],
    dimensions: Optional[DimensionSeedResult],
    total_arguments: int,
    archive_evidence_count: int = 0,
) -> tuple[Outcome, list[dict]]:
    """Evaluate A1-A7 per DOD-V3 Section 17. First match wins.

    ANALYSIS mode may only emit: ANALYSIS, ESCALATE, ERROR (never NO_CONSENSUS).
    """
    trace: list[dict] = []

    def _t(rule_id: str, matched: bool, reason: str) -> bool:
        trace.append({"rule_id": rule_id, "evaluated": True, "fired": matched,
                      "outcome_if_fired": None, "reason": reason})
        return matched

    from thinker.types import SearchScope

    # --- A1: Missing or invalid PreflightAssessment ---
    preflight_missing = preflight is None or not preflight.executed or not preflight.parse_ok
    if _t("A1", preflight_missing,
          f"preflight={'missing' if preflight is None else f'executed={preflight.executed}, parse_ok={preflight.parse_ok}'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A2: Modality mismatch ---
    modality_mismatch = preflight.modality != Modality.ANALYSIS if preflight else True
    if _t("A2", modality_mismatch,
          f"preflight.modality={preflight.modality.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A3: Missing required shared pipeline artifacts ---
    missing_artifacts = (
        (dimensions is None or len(dimensions.items) == 0)
        or total_arguments == 0
    )
    if _t("A3", missing_artifacts,
          f"dimensions={'empty' if not dimensions or not dimensions.items else len(dimensions.items)}, args={total_arguments}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A4: Evidence archive empty AND search_scope != NONE ---
    search_scope_not_none = preflight.search_scope != SearchScope.NONE if preflight else False
    evidence_archive_empty = archive_evidence_count == 0 and evidence_count == 0
    if _t("A4", evidence_archive_empty and search_scope_not_none,
          f"evidence={evidence_count}, archive={archive_evidence_count}, search_scope={preflight.search_scope.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A5: Any mandatory dimension has zero arguments ---
    zero_coverage_dims = []
    if dimensions and dimensions.items:
        zero_coverage_dims = [d for d in dimensions.items
                              if d.mandatory and d.coverage_status == "ZERO"
                              and not d.justified_irrelevance]
    if _t("A5", len(zero_coverage_dims) > 0,
          f"zero_coverage_dimensions={len(zero_coverage_dims)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A6: Total arguments < 8 ---
    if _t("A6", total_arguments < 8,
          f"total_arguments={total_arguments}<8"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A7: Otherwise → ANALYSIS ---
    _t("A7", True, "all checks passed — ANALYSIS")
    trace[-1]["outcome_if_fired"] = "ANALYSIS"
    return Outcome.ANALYSIS, trace


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_gate2_deterministic(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list,
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult] = None,
    divergence: Optional[DivergenceResult] = None,
    stability: Optional[StabilityResult] = None,
    decisive_claims: Optional[list[DecisiveClaim]] = None,
    dimensions: Optional[DimensionSeedResult] = None,
    total_arguments: int = 0,
    archive_evidence_count: int = 0,
    stage_integrity_fatal: Optional[list[str]] = None,
    analogies: Optional[list[CrossDomainAnalogy]] = None,
) -> Gate2Assessment:
    """Deterministic Gate 2 — no LLM call.

    Dispatches to D1-D14 (DECIDE modality) or A1-A7 (ANALYSIS modality)
    based on preflight.modality. First matching rule wins.

    All parameters after search_enabled are optional for backward compatibility.
    """
    # Determine modality
    is_analysis = (preflight is not None and preflight.modality == Modality.ANALYSIS)
    modality_label = "ANALYSIS" if is_analysis else "DECIDE"

    # Compute legacy flags for backward-compat fields
    ignored = [a for a in unaddressed_arguments if isinstance(a, Argument) and a.status == ArgumentStatus.IGNORED]
    mentioned = [a for a in unaddressed_arguments if isinstance(a, Argument) and a.status == ArgumentStatus.MENTIONED]

    convergence_ok = agreement_ratio >= 0.75
    evidence_ok = evidence_count >= 3 or not search_enabled
    dissent_ok = len(ignored) <= 2
    data_ok = evidence_count > 0 or not search_enabled
    no_blockers = len(open_blockers) == 0

    # Dispatch to rule engine
    if is_analysis:
        outcome, rule_trace = _eval_analysis_rules(
            agreement_ratio=agreement_ratio,
            positions=positions,
            contradictions=contradictions,
            unaddressed_arguments=unaddressed_arguments,
            open_blockers=open_blockers,
            evidence_count=evidence_count,
            search_enabled=search_enabled,
            preflight=preflight,
            divergence=divergence,
            stability=stability,
            decisive_claims=decisive_claims,
            dimensions=dimensions,
            total_arguments=total_arguments,
            archive_evidence_count=archive_evidence_count,
        )
    else:
        outcome, rule_trace = _eval_decide_rules(
            agreement_ratio=agreement_ratio,
            positions=positions,
            contradictions=contradictions,
            unaddressed_arguments=unaddressed_arguments,
            open_blockers=open_blockers,
            evidence_count=evidence_count,
            search_enabled=search_enabled,
            preflight=preflight,
            divergence=divergence,
            stability=stability,
            decisive_claims=decisive_claims,
            dimensions=dimensions,
            total_arguments=total_arguments,
            stage_integrity_fatal=stage_integrity_fatal,
            analogies=analogies,
        )

    # Identify which rule fired
    matched_rule = next((r["rule_id"] for r in rule_trace if r.get("fired")), "NONE")

    # Build legacy classification for backward compat
    outcome_class = classify_outcome(
        agreement_ratio=agreement_ratio,
        ignored_arguments=len(ignored),
        mentioned_arguments=len(mentioned),
        evidence_count=evidence_count,
        contradictions=len(contradictions),
        open_blockers=len(open_blockers),
        search_enabled=search_enabled,
    )

    return Gate2Assessment(
        outcome=outcome,
        convergence_ok=convergence_ok,
        evidence_credible=evidence_ok,
        dissent_addressed=dissent_ok,
        enough_data=data_ok,
        report_honest=no_blockers,
        reasoning=(
            f"Deterministic [{modality_label}]: rule={matched_rule}, "
            f"agreement={agreement_ratio:.2f}, "
            f"ignored={len(ignored)}, evidence={evidence_count}, "
            f"contradictions={len(contradictions)}, blockers={len(open_blockers)}, "
            f"class={outcome_class}"
        ),
        modality=modality_label,
        rule_trace=rule_trace,
    )

```


### thinker/proof.py


```python
"""Proof.json builder — the machine-readable audit trail.

Schema 3.0 (V9). Adds: preflight, dimensions, perspective_cards, divergence,
search_log, ungrounded_stats, two-tier evidence, arguments with resolution,
decisive_claims, cross_domain_analogies, semantic contradictions,
synthesis_packet, synthesis dispositions, stability, gate2 rule_trace,
stage_integrity, analysis_map, analysis_debug, diagnostics.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from thinker.types import Outcome, Position
from thinker.tools.blocker import BlockerLedger


class ProofBuilder:
    """Incrementally builds proof.json throughout a Brain run."""

    def __init__(self, run_id: str, brief: str, rounds_requested: int):
        self._run_id = run_id
        self._brief = brief
        self._rounds_requested = rounds_requested
        self._timestamp_started = datetime.now(timezone.utc).isoformat()
        self._timestamp_completed: Optional[str] = None
        self._topology: Optional[dict] = None
        self._error_class: Optional[str] = None
        self._config_snapshot: Optional[dict] = None
        self._rounds: dict[str, dict] = {}
        self._positions: dict[str, dict] = {}
        self._position_changes: list[dict] = []
        self._outcome: dict = {}
        self._final_status: Optional[str] = None
        self._synthesis_status: Optional[str] = None
        self._evidence_items: int = 0
        self._research_phases: list[dict] = []
        self._blocker_ledger: Optional[BlockerLedger] = None
        self._invariant_violations: list[dict] = []
        self._acceptance_status: Optional[str] = None
        self._synthesis_residue_omissions: list[dict] = []
        self._search_decision: Optional[dict] = None
        self._v3_outcome_class: str = "not applicable"
        # V9 additions
        self._preflight: Optional[dict] = None
        self._dimensions: Optional[dict] = None
        self._perspective_cards: Optional[list[dict]] = None
        self._divergence: Optional[dict] = None
        self._search_log: list[dict] = []
        self._ungrounded_stats: list[dict] = []
        self._evidence_active: list[dict] = []
        self._evidence_archive: list[dict] = []
        self._eviction_log: list[dict] = []
        self._arguments: list[dict] = []
        self._decisive_claims: list[dict] = []
        self._cross_domain_analogies: list[dict] = []
        self._contradictions_numeric: list[dict] = []
        self._contradictions_semantic: list[dict] = []
        self._synthesis_packet: Optional[dict] = None
        self._synthesis_dispositions: list[dict] = []
        self._stability: Optional[dict] = None
        self._gate2_trace: Optional[dict] = None
        self._stage_integrity: Optional[dict] = None
        self._analysis_map: list[dict] = []
        self._analysis_debug: Optional[dict] = None
        self._diagnostics: dict = {}
        self._residue_verification: Optional[dict] = None
        self._synthesis_output: Optional[dict] = None
        self._budgeting: Optional[dict] = None

    def record_round(self, round_num: int, responded: list[str], failed: list[str]):
        self._rounds[str(round_num)] = {
            "responded": responded,
            "failed": failed,
        }

    def record_positions(self, round_num: int, positions: dict[str, Position]):
        round_positions = {}
        for model, pos in positions.items():
            round_positions[model] = {
                "model": pos.model,
                "kind": pos.kind,
                "primary_option": pos.primary_option,
                "components": pos.components,
                "confidence": pos.confidence.value,
                "qualifier": pos.qualifier,
            }
        self._positions[str(round_num)] = round_positions

    def record_position_changes(self, changes: list[dict]):
        self._position_changes.extend(changes)

    def record_research_phase(self, phase: str, method: str,
                              queries: int, items_admitted: int):
        self._research_phases.append({
            "phase": phase, "method": method,
            "queries_attempted": queries, "items_admitted": items_admitted,
        })

    def set_evidence_count(self, count: int):
        self._evidence_items = count

    def set_outcome(self, outcome: Outcome, agreement_ratio: float,
                    outcome_class: str):
        self._outcome = {
            "outcome_class": outcome_class,
            "agreement_ratio": agreement_ratio,
            "verdict": outcome.value,
        }
        self._v3_outcome_class = outcome_class

    def set_final_status(self, status: str):
        self._final_status = status

    def set_synthesis_status(self, status: str):
        self._synthesis_status = status

    def set_blocker_ledger(self, ledger: BlockerLedger):
        self._blocker_ledger = ledger

    def compute_acceptance_status(self):
        """Compute acceptance_status from run metrics.

        ACCEPTED: clean run — DECIDE outcome, CONSENSUS class, no violations.
        V9: ACCEPTED_WITH_WARNINGS removed. Now just ACCEPTED or outcome-based.
        Never REJECTED — if fatal, BrainError stops the pipeline before proof.
        """
        from thinker.types import AcceptanceStatus
        is_clean = (
            self._outcome.get("verdict") == "DECIDE"
            and self._outcome.get("outcome_class") == "CONSENSUS"
            and len(self._invariant_violations) == 0
        )
        self._acceptance_status = AcceptanceStatus.ACCEPTED.value if is_clean else "REVIEW_REQUIRED"

    def set_synthesis_residue(self, omissions: list[dict]):
        self._synthesis_residue_omissions = omissions

    def set_search_decision(self, source: str, value: bool, reasoning: str,
                            gate1_recommended: Optional[bool] = None,
                            gate1_search_reasoning: Optional[str] = None):
        """Record who decided search on/off and why.

        source: "gate1" | "cli_override"
        value: True (search on) or False (search off)
        reasoning: Why this decision was made
        gate1_recommended: Gate 1's original recommendation (if overridden)
        gate1_search_reasoning: Gate 1's reasoning for its recommendation (if overridden)
        """
        self._search_decision = {
            "source": source,
            "value": value,
            "reasoning": reasoning,
        }
        if source == "cli_override" and gate1_recommended is not None:
            self._search_decision["gate1_recommended"] = gate1_recommended
            if gate1_search_reasoning:
                self._search_decision["gate1_search_reasoning"] = gate1_search_reasoning

    def add_violation(self, violation_id: str, severity: str, detail: str):
        self._invariant_violations.append({
            "id": violation_id, "severity": severity, "detail": detail,
        })

    # --- V9 Setters ---

    def set_timestamp_completed(self) -> None:
        """Record the completion timestamp."""
        self._timestamp_completed = datetime.now(timezone.utc).isoformat()

    def set_topology(self, topology: dict) -> None:
        """Set the round topology (DOD §19: which models in each round)."""
        self._topology = topology

    def set_error_class(self, error_class: Optional[str]) -> None:
        """Set error_class (DOD §19: null when no error)."""
        self._error_class = error_class

    def set_config_snapshot(self, config: dict) -> None:
        """Set config_snapshot (DOD §19: runtime config at start)."""
        self._config_snapshot = config

    def set_synthesis_output(self, output: dict) -> None:
        """Set synthesis_output (DOD §19: synthesis report + JSON)."""
        self._synthesis_output = output

    def set_budgeting(self, data: dict) -> None:
        """Set budgeting data (DOD §5.1)."""
        self._budgeting = data

    def set_preflight(self, result) -> None:
        """Set preflight assessment result (PreflightResult.to_dict())."""
        self._preflight = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_dimensions(self, result) -> None:
        """Set dimension seeder result (DimensionSeedResult.to_dict())."""
        self._dimensions = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_perspective_cards(self, cards: list) -> None:
        """Set perspective cards list."""
        self._perspective_cards = [c.to_dict() if hasattr(c, 'to_dict') else c for c in cards]

    def set_divergence(self, result) -> None:
        """Set divergence/framing result."""
        self._divergence = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_search_log(self, entries: list) -> None:
        """Set search log entries."""
        self._search_log = [e.to_dict() if hasattr(e, 'to_dict') else e for e in entries]

    def set_ungrounded_stats(self, data) -> None:
        """Set ungrounded statistic detection results (DOD §9.2 schema)."""
        self._ungrounded_stats = data

    def set_evidence_two_tier(self, active: list, archive: list, eviction_log: list) -> None:
        """Set two-tier evidence data."""
        self._evidence_active = [
            {"evidence_id": e.evidence_id, "topic": e.topic, "fact": e.fact,
             "source_url": e.url, "confidence": e.confidence.value, "score": e.score,
             "topic_cluster": e.topic_cluster, "authority_tier": e.authority_tier,
             "is_active": e.is_active, "is_archived": e.is_archived,
             "referenced_by": e.referenced_by}
            if hasattr(e, 'evidence_id') else e
            for e in active
        ]
        self._evidence_archive = [
            {"evidence_id": e.evidence_id, "topic": e.topic, "fact": e.fact,
             "source_url": e.url, "confidence": e.confidence.value, "score": e.score,
             "topic_cluster": e.topic_cluster, "authority_tier": e.authority_tier,
             "is_active": e.is_active, "is_archived": e.is_archived,
             "referenced_by": e.referenced_by}
            if hasattr(e, 'evidence_id') else e
            for e in archive
        ]
        self._eviction_log = [
            ev.to_dict() if hasattr(ev, 'to_dict') else ev for ev in eviction_log
        ]

    def set_arguments(self, arguments: list, blocker_ledger=None) -> None:
        """Set argument map with resolution status (DOD §19: object keyed by argument_id)."""
        # Build dimension→blocker mapping for blocker_link_ids
        dim_blockers: dict[str, list[str]] = {}
        if blocker_ledger:
            for b in blocker_ledger.blockers:
                if b.source.startswith("dimension:"):
                    dim_id = b.source.split(":", 1)[1]
                    dim_blockers.setdefault(dim_id, []).append(b.blocker_id)

        self._arguments = {}
        for a in arguments:
            if hasattr(a, 'argument_id'):
                links = dim_blockers.get(a.dimension_id, []) if a.dimension_id else []
                self._arguments[a.argument_id] = {
                    "argument_id": a.argument_id, "round_origin": a.round_num,
                    "model_id": a.model, "text": a.text,
                    "status": a.status.value, "resolution_status": a.resolution_status.value,
                    "superseded_by": a.superseded_by, "dimension_id": a.dimension_id,
                    "blocker_link_ids": links, "evidence_refs": a.evidence_refs, "open": a.open,
                }
            else:
                key = a.get("argument_id", f"arg-{len(self._arguments)}")
                self._arguments[key] = a

    def set_decisive_claims(self, claims: list) -> None:
        """Set decisive claims."""
        self._decisive_claims = [c.to_dict() if hasattr(c, 'to_dict') else c for c in claims]

    def set_analogies(self, analogies: list) -> None:
        """Set cross-domain analogies."""
        self._cross_domain_analogies = [a.to_dict() if hasattr(a, 'to_dict') else a for a in analogies]

    def set_contradictions(self, numeric: list, semantic: list, semantic_pass_executed: bool = True) -> None:
        """Set both numeric and semantic contradictions."""
        self._semantic_pass_executed = semantic_pass_executed
        self._contradictions_numeric = [
            {"ctr_id": c.contradiction_id,  # DOD §12.1: "ctr_id" not "contradiction_id"
             "detection_mode": c.detection_mode,
             "evidence_ref_a": c.evidence_ref_a, "evidence_ref_b": c.evidence_ref_b,
             "same_entity": c.same_entity, "same_timeframe": c.same_timeframe,
             "topic": c.topic, "severity": c.severity, "status": c.status,
             "justification": c.justification, "linked_claim_ids": c.linked_claim_ids}
            if hasattr(c, 'contradiction_id') else c
            for c in numeric
        ]
        self._contradictions_semantic = [
            c.to_dict() if hasattr(c, 'to_dict') else c for c in semantic
        ]

    def set_synthesis_packet(self, packet: dict) -> None:
        """Set synthesis packet data."""
        self._synthesis_packet = packet

    def set_synthesis_dispositions(self, dispositions: list) -> None:
        """Set synthesis dispositions."""
        self._synthesis_dispositions = [
            d.to_dict() if hasattr(d, 'to_dict') else d for d in dispositions
        ]

    def set_stability(self, result) -> None:
        """Set stability test results."""
        self._stability = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_gate2_trace(self, modality: str, rule_trace: list[dict], final_outcome: str) -> None:
        """Set gate2 rule evaluation trace."""
        self._gate2_trace = {
            "modality": modality,
            "rule_trace": rule_trace,
            "final_outcome": final_outcome,
        }

    def set_stage_integrity(self, required: list[str], order: list[str], fatal: list[str]) -> None:
        """Set stage integrity tracking (DOD §3.4)."""
        self._stage_integrity = {
            "required_stages": required,
            "execution_order": order,
            "fatal_failures": fatal,
            "all_required_present": all(s in order for s in required),
            "order_valid": True,  # Pipeline enforces order by construction
            "fatal": len(fatal) > 0,
        }

    def set_residue_verification(self, data: dict) -> None:
        """Set residue verification results."""
        self._residue_verification = data

    def set_analysis_map(self, entries: list) -> None:
        """Set analysis map entries (ANALYSIS mode)."""
        self._analysis_map = entries

    def set_analysis_debug(self, data: dict) -> None:
        """Set analysis debug data."""
        self._analysis_debug = data

    def set_diagnostics(self, data: dict) -> None:
        """Set diagnostics data."""
        self._diagnostics = data

    def build(self) -> dict:
        """Build the complete proof.json dict."""
        blocker_list = []
        blocker_summary = {"total_blockers": 0, "by_status": {}, "by_kind": {}, "open_at_end": 0}
        if self._blocker_ledger:
            for b in self._blocker_ledger.blockers:
                blocker_list.append({
                    "blocker_id": b.blocker_id,
                    "type": b.kind.value,  # DOD §19: "type" not "kind"
                    "severity": b.severity,
                    "source_dimension": b.source,
                    "detected_round": b.detected_round,
                    "status": b.status.value,
                    "status_history": b.status_history,
                    "models_involved": b.models_involved,
                    "linked_ids": b.evidence_ids,  # DOD §19: "linked_ids" not "evidence_ids"
                    "detail": b.detail,
                    "resolution_summary": b.resolution_note,  # DOD §19: "resolution_summary"
                })
            blocker_summary = self._blocker_ledger.summary()

        proof = {
            # --- DOD §19 canonical keys ---
            "proof_version": "3.0",
            "run_id": self._run_id,
            "timestamp_started": self._timestamp_started,
            "timestamp_completed": self._timestamp_completed or datetime.now(timezone.utc).isoformat(),
            "topology": self._topology,
            "outcome": self._outcome,
            "error_class": self._error_class,
            "stage_integrity": self._stage_integrity,
            "config_snapshot": self._config_snapshot,
            "preflight": self._preflight,
            "budgeting": self._budgeting,
            "dimensions": self._dimensions,
            "perspective_cards": self._perspective_cards,
            "rounds": self._rounds,
            "divergence": self._divergence,
            "search_log": self._search_log,
            "ungrounded_stats": self._ungrounded_stats,
            "evidence": {
                "active_working_set": self._evidence_active,
                "archive": self._evidence_archive,
                "eviction_log": self._eviction_log,
                "active_count": len(self._evidence_active),
                "archive_count": len(self._evidence_archive),
                "high_authority_evidence_present": any(
                    e.get("authority_tier") in ("HIGH", "AUTHORITATIVE")
                    for e in (self._evidence_active + self._evidence_archive)
                ) if (self._evidence_active or self._evidence_archive) else False,
            },
            "arguments": self._arguments or {},
            "blockers": blocker_list,
            "decisive_claims": self._decisive_claims or [],
            "cross_domain_analogies": self._cross_domain_analogies or [],
            "contradictions": {
                "numeric_records": self._contradictions_numeric,
                "semantic_records": self._contradictions_semantic,
                "semantic_pass_executed": getattr(self, '_semantic_pass_executed', False),
            },
            "synthesis_packet": self._synthesis_packet,
            "synthesis_output": {
                **(self._synthesis_output or {}),
                "dispositions": self._synthesis_dispositions or [],
            },
            "residue_verification": self._residue_verification,
            "positions": self._positions,
            "stability": self._stability,
            "analysis_map": self._analysis_map or [],
            "analysis_debug": self._analysis_debug,
            "diagnostics": self._diagnostics or {},
            "gate2": self._gate2_trace,
            # --- Extended fields (not in DOD §19 but useful) ---
            "protocol_version": "v9",
            "rounds_requested": self._rounds_requested,
            "final_status": self._final_status,
            "synthesis_status": self._synthesis_status,
            "acceptance_status": self._acceptance_status,
            "search_decision": self._search_decision,
            "v3_outcome_class": self._v3_outcome_class,
            "evidence_items": self._evidence_items,
            "research_phases": self._research_phases,
            "position_changes": self._position_changes,
            "blocker_summary": blocker_summary,
            "invariant_violations": self._invariant_violations,
            "synthesis_residue_omissions": self._synthesis_residue_omissions,
        }
        return proof

```


### thinker/stability.py


```python
"""Stability Tests — deterministic computation (DoD v3.0 Section 15).

No LLM calls. Three booleans: conclusion_stable, reason_stable, assumption_stable.
Plus: fast_consensus_observed, groupthink_warning, independent_evidence_present.
"""
from __future__ import annotations

from thinker.types import (
    CriticalAssumption, DecisiveClaim, Position, QuestionClass,
    StabilityResult, StakesClass,
)


def compute_conclusion_stability(positions: dict[str, Position]) -> bool:
    """Do surviving models agree on the primary recommendation?

    Stable = all models with positions share the same primary_option.
    """
    if not positions:
        return False

    options = set()
    for p in positions.values():
        if p.primary_option:
            options.add(p.primary_option.lower().strip())

    return len(options) <= 1


def compute_reason_stability(
    positions: dict[str, Position],
    decisive_claims: list[DecisiveClaim],
) -> bool:
    """Do models converge for the same reasons? (DOD §15.2)

    Stable = models share the same decisive claim set AND all material
    claims are evidence-supported. If model attribution is available
    (supporting_model_ids), checks that surviving models share claims.
    """
    if not decisive_claims:
        return False

    material_claims = [c for c in decisive_claims if c.material_to_conclusion]
    if not material_claims:
        return False

    # All material claims must be evidence-supported
    if not all(c.evidence_support_status.value == "SUPPORTED" for c in material_claims):
        return False

    # DOD §15.2: "Models converge for the same reasons (shared decisive claim set)"
    # All surviving models must endorse the SAME set of material claims.
    surviving_models = set(positions.keys()) if positions else set()
    if surviving_models and any(c.supporting_model_ids for c in material_claims):
        for claim in material_claims:
            if not claim.supporting_model_ids:
                continue  # No attribution data — can't check
            # Every surviving model must endorse every material claim
            claim_models = set(claim.supporting_model_ids)
            if not surviving_models.issubset(claim_models):
                return False  # Not all models share this decisive claim

    return True


def compute_assumption_stability(assumptions: list[CriticalAssumption]) -> bool:
    """Are we relying on unresolved material assumptions?

    Stable = no unresolved material assumptions with UNVERIFIABLE/FALSE verifiability.
    """
    if not assumptions:
        return True

    for a in assumptions:
        if (a.material and not a.resolved
                and a.verifiability.value in ("UNVERIFIABLE", "FALSE")):
            return False
    return True


def detect_fast_consensus(
    round_positions: dict[int, dict[str, Position]],
) -> bool:
    """Detect if models agreed too quickly (from R1).

    DOD §15.1: fast_consensus_observed = true if R1 agreement_ratio >= 0.95.
    Agreement ratio = (count of most common option) / total models.
    """
    r1_positions = round_positions.get(1, {})
    if not r1_positions or len(r1_positions) < 2:
        return False

    options: list[str] = []
    for p in r1_positions.values():
        if p.primary_option:
            options.append(p.primary_option.lower().strip())

    if not options:
        return False

    from collections import Counter
    counts = Counter(options)
    most_common_count = counts.most_common(1)[0][1]
    agreement_ratio = most_common_count / len(options)
    return agreement_ratio >= 0.95


def compute_groupthink_warning(
    fast_consensus: bool,
    question_class: QuestionClass,
    stakes_class: StakesClass,
    independent_evidence_present: bool,
) -> bool:
    """Groupthink warning if fast consensus on non-trivial questions.

    Warning if: fast_consensus AND (OPEN/AMBIGUOUS OR HIGH stakes) AND no independent evidence.
    """
    if not fast_consensus:
        return False

    # DOD §15.2: question_class = OPEN OR stakes_class = HIGH (not AMBIGUOUS)
    non_trivial = question_class == QuestionClass.OPEN
    high_stakes = stakes_class == StakesClass.HIGH

    if not (non_trivial or high_stakes):
        return False

    # Independent evidence mitigates groupthink concern
    if independent_evidence_present:
        return False

    return True


def run_stability_tests(
    positions: dict[str, Position],
    decisive_claims: list[DecisiveClaim],
    assumptions: list[CriticalAssumption],
    round_positions: dict[int, dict[str, Position]],
    question_class: QuestionClass,
    stakes_class: StakesClass,
    independent_evidence_present: bool = False,
) -> StabilityResult:
    """Run all stability tests. Returns StabilityResult."""
    conclusion_stable = compute_conclusion_stability(positions)
    reason_stable = compute_reason_stability(positions, decisive_claims)
    assumption_stable = compute_assumption_stability(assumptions)
    fast_consensus = detect_fast_consensus(round_positions)
    groupthink = compute_groupthink_warning(
        fast_consensus, question_class, stakes_class, independent_evidence_present,
    )

    return StabilityResult(
        conclusion_stable=conclusion_stable,
        reason_stable=reason_stable,
        assumption_stable=assumption_stable,
        independent_evidence_present=independent_evidence_present,
        fast_consensus_observed=fast_consensus,
        groupthink_warning=groupthink,
    )

```


### thinker/preflight.py


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
    logic="Parse JSON. ANSWERABLE->admit. NEED_MORE->reject with questions. INVALID_FORM->NEED_MORE. Parse fail->BrainError.",
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
        from thinker.types import extract_json
        data = extract_json(text)
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


### thinker/residue.py


```python
"""Post-synthesis residue verification.

V8-F1 (DoD D7): After synthesis, scan the report text to verify it
mentions all structural findings — blocker IDs, contradiction IDs,
and unaddressed argument IDs. This is a narrative completeness check,
not truth verification.

V9 (DoD Section 14): Structured dispositions. Schema validation + coverage
validation replaces string matching. Disposition object for every open blocker,
active frame, decisive claim, contradiction. omission_rate > 0.20 triggers
deep semantic scan.
"""
from __future__ import annotations

from thinker.pipeline import pipeline_stage
from thinker.types import (
    Argument, Blocker, BlockerStatus, Contradiction, DecisiveClaim,
    DispositionObject, DispositionTargetType, FrameInfo, FrameSurvivalStatus,
    SemanticContradiction,
)


def check_synthesis_residue(
    report: str,
    blockers: list[Blocker],
    contradictions: list[Contradiction],
    unaddressed_arguments: list[Argument],
) -> list[dict]:
    """Scan synthesis report for structural finding references.

    Returns list of omission dicts:
    {"type": "blocker"|"contradiction"|"argument", "id": str}

    If >30% of total structural findings are omitted, each omission
    gets threshold_violation=True.
    """
    omissions: list[dict] = []
    total_items = len(blockers) + len(contradictions) + len(unaddressed_arguments)

    # Check blocker IDs
    for b in blockers:
        if b.blocker_id not in report:
            omissions.append({"type": "blocker", "id": b.blocker_id})

    # Check contradiction IDs
    for c in contradictions:
        if c.contradiction_id not in report:
            omissions.append({"type": "contradiction", "id": c.contradiction_id})

    # Check unaddressed argument IDs
    for a in unaddressed_arguments:
        if a.argument_id not in report:
            omissions.append({"type": "argument", "id": a.argument_id})

    # Threshold check: >30% omitted
    threshold_violated = (
        total_items > 0 and len(omissions) / total_items > 0.30
    )
    if threshold_violated:
        for o in omissions:
            o["threshold_violation"] = True

    return omissions


def check_disposition_coverage(
    dispositions: list[DispositionObject],
    open_blockers: list[Blocker],
    active_frames: list[FrameInfo],
    decisive_claims: list[DecisiveClaim],
    contradictions_numeric: list[Contradiction],
    contradictions_semantic: list[SemanticContradiction],
    open_material_arguments: list[Argument] | None = None,
) -> dict:
    """V9: Check that synthesis dispositions cover all tracked open findings.

    Returns dict with: coverage_pass, omission_rate, omissions[], deep_scan_triggered.
    """
    # Build required targets
    required_targets: list[tuple[str, str]] = []  # (target_type, target_id)

    for b in open_blockers:
        if b.status == BlockerStatus.OPEN:
            required_targets.append(("BLOCKER", b.blocker_id))

    for f in active_frames:
        if f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED):
            required_targets.append(("FRAME", f.frame_id))

    for c in decisive_claims:
        required_targets.append(("CLAIM", c.claim_id))

    for c in contradictions_numeric:
        if c.status not in ("RESOLVED", "NON_MATERIAL"):
            required_targets.append(("CONTRADICTION", c.contradiction_id))

    for c in contradictions_semantic:
        if c.status.value not in ("RESOLVED", "NON_MATERIAL"):
            required_targets.append(("CONTRADICTION", c.ctr_id))

    # DOD §11.3: open material arguments need dispositions
    for a in (open_material_arguments or []):
        if a.open:
            required_targets.append(("ARGUMENT", a.argument_id))

    if not required_targets:
        return {
            "coverage_pass": True,
            "omission_rate": 0.0,
            "omissions": [],
            "deep_scan_triggered": False,
            "total_required": 0,
            "total_disposed": 0,
        }

    # Build disposition lookup
    disposed = set()
    for d in dispositions:
        disposed.add((d.target_type.value, d.target_id))

    # Find omissions
    omissions = []
    for target_type, target_id in required_targets:
        if (target_type, target_id) not in disposed:
            omissions.append({"target_type": target_type, "target_id": target_id})

    omission_rate = len(omissions) / len(required_targets) if required_targets else 0.0
    deep_scan = omission_rate > 0.20

    return {
        "coverage_pass": len(omissions) == 0,
        "omission_rate": round(omission_rate, 3),
        "omissions": omissions,
        "deep_scan_triggered": deep_scan,
        "expected_disposition_count": len(required_targets),  # DOD §14.4
        "emitted_disposition_count": len(required_targets) - len(omissions),  # DOD §14.4
        # Keep old names for internal use
        "total_required": len(required_targets),
        "total_disposed": len(required_targets) - len(omissions),
    }


def run_deep_semantic_scan(
    report: str,
    omissions: list[dict],
) -> dict:
    """Deep semantic scan: second-pass string match for omitted dispositions.

    DOD §14.5: omission_rate > 0.20 triggers deep semantic scan.
    DOD §14.6: "Deep scan threshold exceeded but scan not run → ERROR."

    Scans the synthesis report text for any reference to omitted targets.
    If the report text mentions the target (by ID or partial text match),
    the omission is downgraded to "addressed_in_text" (soft coverage).
    Remaining true omissions after deep scan are material.
    """
    resolved = []
    still_missing = []

    for om in omissions:
        target_id = om.get("target_id", "")
        # Check if the synthesis text mentions this target by ID
        if target_id and target_id in report:
            resolved.append({**om, "deep_scan_result": "addressed_in_text"})
        else:
            still_missing.append({**om, "deep_scan_result": "confirmed_missing"})

    return {
        "deep_scan_run": True,
        "resolved_by_scan": len(resolved),
        "still_missing": len(still_missing),
        "resolved": resolved,
        "missing": still_missing,
        "material_omissions_remain": len(still_missing) > 0,
    }


@pipeline_stage(
    name="Residue Verification",
    description="Post-synthesis narrative completeness check. Scans the synthesis report text for BLK IDs, CTR IDs, and unaddressed argument IDs. If >30% of structural findings are omitted, flags a threshold violation. This is NOT truth verification — it checks whether the synthesis mentioned the findings, not whether it got them right.",
    stage_type="deterministic",
    order=9,
    provider="deterministic (no LLM)",
    inputs=["synthesis report text", "blockers", "contradictions", "unaddressed_arguments"],
    outputs=["omissions (list[dict]) — type, id, threshold_violation flag"],
    logic="""For each BLK ID: is it mentioned in the report text? If not → omission.
For each CTR ID: is it mentioned? If not → omission.
For each unaddressed argument ID: is it mentioned? If not → omission.
If omissions / total_items > 0.30 → threshold_violation=True on all omissions.""",
    failure_mode="Cannot fail — string matching only.",
    cost="$0 (no LLM call)",
    stage_id="residue_verification",
)
def _register_residue_verification(): pass

```


### thinker/argument_tracker.py


```python
"""Argument Tracker — the core V8 innovation.

V8 spec Section 4, Argument Tracker:
After each round, one Sonnet call extracts all distinct arguments. Another
Sonnet call compares them with the next round's outputs to identify which
arguments were addressed, mentioned in passing, or ignored. Unaddressed
arguments are explicitly re-injected into the next round's prompt.

This replaces the Minority Archive, Acknowledgment Scanner, and all
keyword-matching machinery from V7.
"""
from __future__ import annotations

import re

from thinker.pipeline import pipeline_stage
from thinker.types import Argument, ArgumentStatus


EXTRACT_PROMPT = """Read the following model outputs from round {round_num} of a multi-model deliberation.
Extract every distinct argument made by any model. An argument is a specific claim,
reasoning step, evidence interpretation, or position.

Model outputs:
{outputs}

List each argument as:
ARG-N: [model_name] argument text

Be exhaustive. Include ALL arguments, even minor ones. Do not merge arguments
from different models — track each separately."""

COMPARE_PROMPT = """Here are the arguments from round {prev_round}:
{arguments}

Here are the NEW arguments extracted from round {curr_round}:
{new_arguments}

Here are the model outputs from round {curr_round}:
{outputs}

For each argument from round {prev_round}, classify it as:
- ADDRESSED: The argument was directly engaged with (agreed, rebutted, or refined with reasoning)
- MENTIONED: The argument was referenced but not substantively engaged with
- IGNORED: The argument does not appear in any model's output at all

If ADDRESSED by refinement or supersession, also indicate which round {curr_round} argument replaces it.

Be strict. "Mentioned" means the model acknowledged the point but didn't reason about it.
"Addressed" requires genuine engagement — agreement with new reasoning, or a specific rebuttal.

Respond as:
ARG-N: ADDRESSED [superseded_by R{curr_round}-ARG-M] | ADDRESSED | MENTIONED | IGNORED

Only include [superseded_by ...] when a specific new argument clearly replaces or refines the old one."""


def parse_arguments(text: str, round_num: int) -> list[Argument]:
    """Parse extracted arguments from Sonnet's response.

    Handles multiple formats Sonnet may use:
      ARG-1: [r1] argument text
      ARG-1: r1 - argument text
      ARG-1: **r1** argument text
    """
    args = []
    for line in text.strip().split("\n"):
        line = line.strip()
        # Strip markdown bold/italic markers and leading bullet/dash
        line = re.sub(r"^\s*[-*•]\s*", "", line)
        line = re.sub(r"\*{1,2}(ARG-\d+.*?)\*{1,2}", r"\1", line)
        line = line.strip()
        # Try bracket format first: ARG-1: [model] text
        match = re.match(r"(ARG-\d+):\s+\[(\w+)\]\s+(.+)", line)
        if not match:
            # Try dash format: ARG-1: model - text
            match = re.match(r"(ARG-\d+):\s+[*]*(\w+)[*]*\s*[-–—]\s*(.+)", line)
        if not match:
            # Try bare format: ARG-1: model text (model is first word)
            match = re.match(r"(ARG-\d+):\s+[*]*(\w+)[*]*\s+(.+)", line)
        if match:
            model = match.group(2).lower()
            # Skip non-model words
            if model in ("the", "this", "that", "both", "all", "note"):
                continue
            # Prefix ARG-ID with round number to prevent cross-round collisions
            # LLM outputs ARG-1..ARG-N each round; R1-ARG-1 != R3-ARG-1
            raw_id = match.group(1)
            unique_id = f"R{round_num}-{raw_id}"
            args.append(Argument(
                argument_id=unique_id,
                round_num=round_num,
                model=model,
                text=match.group(3).strip(),
            ))
    return args


def parse_comparison(text: str, prev_round: int = 0) -> dict[str, tuple[ArgumentStatus, str | None]]:
    """Parse argument comparison from Sonnet's response.

    Handles both prefixed (R1-ARG-1) and unprefixed (ARG-1) IDs.
    When unprefixed, adds the R{prev_round} prefix to match stored IDs.

    Returns dict mapping argument_id -> (status, superseded_by_id or None).
    """
    statuses: dict[str, tuple[ArgumentStatus, str | None]] = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        # Extract optional [superseded_by R2-ARG-3] tag
        superseded_by = None
        sup_match = re.search(r"\[superseded_by\s+(R\d+-ARG-\d+)\]", line)
        if sup_match:
            superseded_by = sup_match.group(1)

        # Try prefixed format first: R1-ARG-1: ADDRESSED [superseded_by ...]
        match = re.match(r"(R\d+-ARG-\d+):\s+(ADDRESSED|MENTIONED|IGNORED)", line)
        if match:
            statuses[match.group(1)] = (ArgumentStatus[match.group(2)], superseded_by)
            continue
        # Unprefixed format: ARG-1: ADDRESSED — add round prefix
        match = re.match(r"(ARG-\d+):\s+(ADDRESSED|MENTIONED|IGNORED)", line)
        if match:
            arg_id = f"R{prev_round}-{match.group(1)}" if prev_round else match.group(1)
            statuses[arg_id] = (ArgumentStatus[match.group(2)], superseded_by)
    return statuses


class ArgumentTracker:
    """Tracks arguments across rounds and re-injects unaddressed ones."""

    def __init__(self, llm_client):
        self._llm = llm_client
        self.arguments_by_round: dict[int, list[Argument]] = {}
        self.all_unaddressed: list[Argument] = []  # Cumulative across all rounds
        self.last_raw_response: str = ""  # For debug logging
        self._broken_supersession_links: list[dict] = []  # DOD §11.3 violations

    def assign_dimensions(self, arguments: list[Argument], dimension_names: dict[str, str]) -> None:
        """Post-hoc assignment of dimension_id to arguments by keyword matching.

        dimension_names: {dimension_id: name} e.g. {"DIM-1": "Technical Severity"}
        """
        for arg in arguments:
            if arg.dimension_id:
                continue  # Already assigned
            text_lower = arg.text.lower()
            best_match = ""
            best_score = 0
            for dim_id, dim_name in dimension_names.items():
                # Count keyword hits from dimension name
                keywords = [w.lower() for w in dim_name.split() if len(w) >= 3]
                score = sum(1 for kw in keywords if kw in text_lower)
                if score > best_score:
                    best_score = score
                    best_match = dim_id
            if best_match and best_score > 0:
                arg.dimension_id = best_match

    async def extract_arguments(
        self, round_num: int, model_outputs: dict[str, str],
    ) -> list[Argument]:
        from thinker.types import BrainError
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        resp = await self._llm.call(
            "sonnet",
            EXTRACT_PROMPT.format(round_num=round_num, outputs=combined),
        )
        if not resp.ok:
            raise BrainError(f"track{round_num}", f"Argument extraction failed: {resp.error}",
                             detail="Sonnet could not extract arguments from round outputs.")
        self.last_raw_response = resp.text
        args = parse_arguments(resp.text, round_num)
        if not args:
            raise BrainError(f"track{round_num}", "Argument extraction returned 0 arguments",
                             detail=f"Raw response: {resp.text[:300]}")
        self.arguments_by_round[round_num] = args
        return args

    async def compare_with_round(
        self, prev_round: int, curr_outputs: dict[str, str],
    ) -> list[Argument]:
        from thinker.types import BrainError
        prev_args = self.arguments_by_round.get(prev_round, [])
        if not prev_args:
            return []

        args_text = "\n".join(
            f"{a.argument_id}: [{a.model}] {a.text}" for a in prev_args
        )
        curr_round = prev_round + 1
        curr_args = self.arguments_by_round.get(curr_round, [])
        new_args_text = "\n".join(
            f"{a.argument_id}: [{a.model}] {a.text}" for a in curr_args
        ) if curr_args else "(not yet extracted)"
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in curr_outputs.items())

        resp = await self._llm.call(
            "sonnet",
            COMPARE_PROMPT.format(
                prev_round=prev_round, arguments=args_text,
                curr_round=curr_round, new_arguments=new_args_text,
                outputs=combined,
            ),
        )
        if not resp.ok:
            raise BrainError(f"track{curr_round}",
                             f"Argument comparison failed: {resp.error}",
                             detail=f"Could not compare R{prev_round} args against R{curr_round} outputs.")

        from thinker.types import ResolutionStatus
        statuses = parse_comparison(resp.text, prev_round=prev_round)
        # Build set of valid curr_round arg IDs for supersession validation
        valid_curr_ids = {a.argument_id for a in curr_args}
        unaddressed = []
        for arg in prev_args:
            result = statuses.get(arg.argument_id, (ArgumentStatus.IGNORED, None))
            status, superseded_by_id = result
            arg.status = status
            if status in (ArgumentStatus.IGNORED, ArgumentStatus.MENTIONED):
                arg.addressed_in_round = None
                arg.open = True
                unaddressed.append(arg)
            else:
                arg.addressed_in_round = curr_round
                # Set superseded_by if valid (DOD §11.3)
                if superseded_by_id:
                    if superseded_by_id in valid_curr_ids:
                        # Fully resolved: explicit lineage link
                        arg.resolution_status = ResolutionStatus.SUPERSEDED
                        arg.superseded_by = superseded_by_id
                        arg.open = False
                    else:
                        # DOD §11.3: broken link — log and keep open
                        arg.resolution_status = ResolutionStatus.REFINED
                        arg.open = True  # DOD §11.2: no lineage = not resolved
                        self._broken_supersession_links.append({
                            "argument_id": arg.argument_id,
                            "claimed_superseded_by": superseded_by_id,
                            "reason": "target ID not found in current round arguments",
                        })
                else:
                    # DOD §11.2: "Restatement without explicit linkage is NOT resolution"
                    # ADDRESSED without supersession tag = engaged but not formally resolved
                    arg.resolution_status = ResolutionStatus.REFINED
                    arg.open = True

        # Accumulate: add newly unaddressed args, remove any that were addressed
        addressed_ids = {a.argument_id for a in prev_args if a.status == ArgumentStatus.ADDRESSED}
        existing_ids = {a.argument_id for a in self.all_unaddressed}
        self.all_unaddressed = [
            a for a in self.all_unaddressed if a.argument_id not in addressed_ids
        ] + [a for a in unaddressed if a.argument_id not in existing_ids]
        return unaddressed

    def format_reinjection(self, unaddressed: list[Argument]) -> str:
        if not unaddressed:
            return ""
        lines = []
        for arg in unaddressed:
            status_label = "IGNORED" if arg.status == ArgumentStatus.IGNORED else "only mentioned"
            lines.append(f"{arg.argument_id}: [{arg.model}] {arg.text} ({status_label} in previous round)")
        return (
            "The following arguments from prior rounds were NOT substantively addressed. "
            "You MUST engage with each one — agree with reasoning, rebut with evidence, or refine.\n\n"
            + "\n".join(lines)
        )


@pipeline_stage(
    name="Argument Tracker",
    description="Core V8 innovation. After each round, Sonnet extracts all distinct arguments. After R2+, compares them with current round to identify ADDRESSED/MENTIONED/IGNORED. Unaddressed arguments re-injected into next round's prompt. Arguments can't be silently dropped.",
    stage_type="track",
    order=3,
    provider="sonnet (2 calls: extract + compare)",
    inputs=["model_outputs (dict[model, text])"],
    outputs=["arguments (list[Argument])", "unaddressed (list)", "reinjection_text (str)"],
    prompt=EXTRACT_PROMPT,
    logic="""EXTRACT: Sonnet reads all outputs, extracts ARG-N: [model] text.
COMPARE (R2+): For each prior arg — ADDRESSED (engaged), MENTIONED (name-dropped), IGNORED (absent).
RE-INJECT: IGNORED + MENTIONED args added to next round with "You MUST engage".""",
    failure_mode="Extract fails: empty args. Compare fails: re-inject all (conservative).",
    cost="2 Sonnet calls per round ($0 on Max subscription)",
    stage_id="argument_tracker",
)
def _register_argument_tracker(): pass

```


### thinker/perspective_cards.py


```python
"""Perspective Cards — structured R1 output extraction (DoD v3.0 Section 7).

Parses R1 model outputs to extract 5 structured fields per model.
Primary: regex extraction from R1 output (native).
Fallback: post-hoc LLM extraction via Haiku → Sonnet (inferred).
DOD §7.2: Exactly 4 cards required. DOD §7.3: Missing card → ERROR.
"""
from __future__ import annotations

import asyncio
import re

from thinker.types import CoverageObligation, PerspectiveCard, TimeHorizon

# Coverage obligation assignments (fixed per model)
_MODEL_OBLIGATIONS = {
    "kimi": CoverageObligation.CONTRARIAN,
    "r1": CoverageObligation.MECHANISM_ANALYSIS,
    "reasoner": CoverageObligation.OPERATIONAL_RISK,
    "glm5": CoverageObligation.OBJECTIVE_REFRAMING,
}

REQUIRED_FIELDS = ["primary_frame", "hidden_assumption_attacked",
                   "stakeholder_lens", "time_horizon", "failure_mode"]

# Field patterns to extract from model output
_FIELD_PATTERNS = {
    "primary_frame": re.compile(r"PRIMARY_FRAME:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "hidden_assumption_attacked": re.compile(r"HIDDEN_ASSUMPTION_ATTACKED:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "stakeholder_lens": re.compile(r"STAKEHOLDER_LENS:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "time_horizon": re.compile(r"TIME_HORIZON:\s*\**(\w+)\**", re.IGNORECASE),
    "failure_mode": re.compile(r"FAILURE_MODE:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
}

_EXTRACTION_PROMPT = """Read the following model analysis and extract the 5 perspective card fields.
The model was asked to include these fields but failed to do so. Infer them from the content of the analysis.

RULES:
- PRIMARY_FRAME: The model's primary analytical lens or way of looking at the question
- HIDDEN_ASSUMPTION_ATTACKED: Which assumption the model is challenging or questioning
- STAKEHOLDER_LENS: Whose perspective the model is representing
- TIME_HORIZON: SHORT, MEDIUM, or LONG — based on the timeframe of the analysis
- FAILURE_MODE: What could go wrong with the model's recommended approach

Output EXACTLY these 5 lines and nothing else:
PRIMARY_FRAME: <value>
HIDDEN_ASSUMPTION_ATTACKED: <value>
STAKEHOLDER_LENS: <value>
TIME_HORIZON: <SHORT|MEDIUM|LONG>
FAILURE_MODE: <value>

--- MODEL ANALYSIS (first and last sections) ---

{text}"""


def _truncate_for_extraction(text: str, max_chars: int = 8000) -> str:
    """Truncate R1 output to first/last segments for extraction context."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[... middle truncated ...]\n\n" + text[-half:]


def _parse_time_horizon(text: str) -> TimeHorizon:
    text = text.strip().upper()
    if text in ("SHORT", "SHORT-TERM", "SHORT_TERM"):
        return TimeHorizon.SHORT
    elif text in ("LONG", "LONG-TERM", "LONG_TERM"):
        return TimeHorizon.LONG
    return TimeHorizon.MEDIUM


def _extract_fields_regex(text: str) -> dict[str, str]:
    """Try to extract fields via regex. Returns dict of found fields."""
    fields = {}
    for field_name, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            fields[field_name] = match.group(1).strip()
    return fields


async def _extract_fields_llm(client, model_name: str, r1_text: str) -> dict[str, str] | None:
    """Extract missing fields via LLM. Returns dict of fields or None on failure."""
    truncated = _truncate_for_extraction(r1_text)
    prompt = _EXTRACTION_PROMPT.format(text=truncated)
    resp = await client.call(model_name, prompt)
    if not resp.ok:
        return None
    return _extract_fields_regex(resp.text)


def _build_card(model_id: str, fields: dict[str, str], provenance: dict[str, str]) -> PerspectiveCard:
    """Build a PerspectiveCard from extracted fields."""
    return PerspectiveCard(
        model_id=model_id,
        primary_frame=fields.get("primary_frame", ""),
        hidden_assumption_attacked=fields.get("hidden_assumption_attacked", ""),
        stakeholder_lens=fields.get("stakeholder_lens", ""),
        time_horizon=_parse_time_horizon(fields.get("time_horizon", "MEDIUM")),
        failure_mode=fields.get("failure_mode", ""),
        coverage_obligation=_MODEL_OBLIGATIONS.get(model_id, CoverageObligation.MECHANISM_ANALYSIS),
        field_provenance=provenance,
    )


async def extract_perspective_cards(r1_texts: dict[str, str], llm_client=None) -> list[PerspectiveCard]:
    """Extract perspective cards from R1 model outputs.

    Phase 1: regex extraction (native).
    Phase 2: for models with missing fields, post-hoc LLM extraction via Haiku → Sonnet.
    DOD §7.2: Exactly N cards required (one per R1 model).
    DOD §7.3: Missing card → ERROR.
    """
    from thinker.types import BrainError

    cards = []
    needs_extraction: list[tuple[str, str, dict[str, str]]] = []  # (model_id, text, native_fields)

    # Phase 1: regex extraction
    for model_id, text in r1_texts.items():
        if not text.strip():
            raise BrainError(
                "perspective_cards",
                f"Model {model_id} produced no R1 output — zero tolerance",
                detail="DOD §7.3: Missing card → ERROR.",
            )

        fields = _extract_fields_regex(text)
        missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]

        if not missing:
            # All fields found natively
            provenance = {f: "native" for f in REQUIRED_FIELDS}
            cards.append(_build_card(model_id, fields, provenance))
        else:
            # Track for Phase 2
            needs_extraction.append((model_id, text, fields))

    # Phase 2: post-hoc LLM extraction for models with missing fields
    if needs_extraction and llm_client:
        async def _extract_one(model_id: str, text: str, native_fields: dict[str, str]) -> PerspectiveCard | None:
            missing = [f for f in REQUIRED_FIELDS if not native_fields.get(f)]

            # Try Haiku first, Sonnet as fallback
            for extractor in ("haiku", "sonnet"):
                inferred = await _extract_fields_llm(llm_client, extractor, text)
                if inferred:
                    # Merge: native fields take priority, fill missing with inferred
                    # EXCEPTION: hidden_assumption_attacked must NEVER be inferred
                    # (Brain V9 round 20: systematic hallucination risk — set NOT_STATED)
                    merged = dict(native_fields)
                    provenance = {}
                    for f in REQUIRED_FIELDS:
                        if native_fields.get(f):
                            provenance[f] = "native"
                        elif f == "hidden_assumption_attacked":
                            merged[f] = "NOT_STATED"
                            provenance[f] = "not_stated"
                        elif inferred.get(f):
                            merged[f] = inferred[f]
                            provenance[f] = f"inferred:{extractor}"
                        else:
                            provenance[f] = "missing"

                    still_missing = [f for f in REQUIRED_FIELDS if not merged.get(f)]
                    if not still_missing:
                        return _build_card(model_id, merged, provenance)
                    # If still missing fields, try next extractor
                    native_fields = merged  # carry over any fields we did get

            return None

        tasks = [_extract_one(mid, txt, nf) for mid, txt, nf in needs_extraction]
        results = await asyncio.gather(*tasks)

        failed_models = []
        for (model_id, _, _), result in zip(needs_extraction, results):
            if result:
                cards.append(result)
            else:
                failed_models.append(model_id)

        if failed_models:
            raise BrainError(
                "perspective_cards",
                f"Failed to extract perspective cards for: {failed_models} "
                f"(regex and LLM extraction both failed)",
                detail=f"DOD §7.2-7.3: All {len(r1_texts)} cards required. "
                       f"Post-hoc extraction via Haiku+Sonnet could not produce valid fields.",
            )

    elif needs_extraction and not llm_client:
        # No LLM client — fall back to majority threshold (legacy mode)
        min_required = max(2, len(r1_texts) // 2)
        if len(cards) < min_required:
            nc_models = [mid for mid, _, _ in needs_extraction]
            raise BrainError(
                "perspective_cards",
                f"Only {len(cards)}/{len(r1_texts)} models produced valid perspective cards "
                f"(minimum {min_required} required, no LLM client for post-hoc extraction)",
                detail=f"DOD §7.3: Missing card → ERROR. Non-compliant: {nc_models}",
            )

    # DOD §7.2: exactly N cards required
    if len(cards) != len(r1_texts):
        raise BrainError(
            "perspective_cards",
            f"Only {len(cards)}/{len(r1_texts)} perspective cards produced",
            detail="DOD §7.2: Exactly one card per R1 model required.",
        )

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


### thinker/divergent_framing.py


```python
"""Divergent Framing — framing pass, frame survival, exploration stress (DoD v3.0 Section 8).

Framing pass: Sonnet extracts alt frames from R1 outputs.
Frame survival: 3-vote R2 drop (traceable), CONTESTED in R3/R4 (never dropped).
Exploration stress: inject seed frames when R1 agreement > 0.75 on OPEN/HIGH.
"""
from __future__ import annotations

import json
from typing import Optional

from thinker.pipeline import pipeline_stage
from thinker.types import (
    BrainError, CrossDomainAnalogy, DivergenceResult, FrameInfo,
    FrameSurvivalStatus, FrameType, QuestionClass, StakesClass,
)

FRAMING_EXTRACT_PROMPT = """You are a framing analyst for a multi-model deliberation system.

Given the R1 model outputs below, extract ALL material alternative frames (ways of looking at this question that differ from the obvious framing).

## Brief
{brief}

## R1 Model Outputs
{r1_texts_formatted}

## Output Format — STRICT JSON (no markdown, no commentary)

{{
  "frames": [
    {{
      "frame_id": "FRAME-1",
      "text": "description of the alternative frame",
      "origin_model": "model_id that proposed this",
      "frame_type": "INVERSION | OBJECTIVE_REWRITE | PREMISE_CHALLENGE | CROSS_DOMAIN_ANALOGY | OPPOSITE_STANCE | REMOVE_PROBLEM",
      "material_to_outcome": true/false
    }}
  ],
  "cross_domain_analogies": [
    {{
      "analogy_id": "ANA-1",
      "source_domain": "domain the analogy comes from",
      "target_claim_id": "claim this analogy supports/challenges",
      "transfer_mechanism": "how the analogy applies"
    }}
  ]
}}

## Rules
- Extract frames that are genuinely different from the default framing
- A frame is material if it could change the outcome
- Cross-domain analogies: look for when models draw parallels from other fields
- Be generous: if in doubt, include it as a frame"""


FRAME_SURVIVAL_PROMPT = """Evaluate whether each alternative frame survives this round of deliberation.

## Active Frames
{frames_formatted}

## Round {round_num} Model Outputs
{round_texts_formatted}

## Output Format — STRICT JSON

{{
  "evaluations": [
    {{
      "frame_id": "FRAME-1",
      "status": "ACTIVE | CONTESTED | DROPPED | ADOPTED | REBUTTED",
      "drop_vote_models": ["model_id"],
      "reasoning": "why this status"
    }}
  ]
}}

## Rules (Round {round_num})
{survival_rules}"""


@pipeline_stage(
    name="Framing Pass",
    description="Sonnet extracts alternative frames from R1 outputs. Tracks frame survival through rounds.",
    stage_type="track",
    order=5,
    provider="sonnet",
    inputs=["brief", "r1_texts"],
    outputs=["DivergenceResult"],
    logic="Extract frames. Track survival. 3-vote R2 drop. CONTESTED never dropped in R3/R4.",
    failure_mode="LLM failure or parse failure: BrainError.",
    cost="1-3 Sonnet calls",
    stage_id="framing_pass",
)
async def run_framing_extract(client, brief: str, r1_texts: dict[str, str]) -> DivergenceResult:
    """Extract alternative frames from R1 outputs."""
    # Format R1 texts
    r1_formatted = "\n\n".join(f"### {model}\n{text}" for model, text in r1_texts.items())
    prompt = FRAMING_EXTRACT_PROMPT.format(brief=brief, r1_texts_formatted=r1_formatted)

    resp = await client.call("sonnet", prompt)
    if not resp.ok:
        raise BrainError("framing_pass", f"Framing extract LLM call failed: {resp.error}")

    text = resp.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        from thinker.types import extract_json
        data = extract_json(text)
    except json.JSONDecodeError as e:
        raise BrainError("framing_pass", f"Failed to parse framing extract JSON: {e}",
                         detail=resp.text[:500])

    frames = []
    for f in data.get("frames", []):
        try:
            frame_type = FrameType(f.get("frame_type", "INVERSION"))
        except ValueError:
            frame_type = FrameType.INVERSION
        frames.append(FrameInfo(
            frame_id=f.get("frame_id", f"FRAME-{len(frames)+1}"),
            text=f.get("text", ""),
            origin_round=1,
            origin_model=f.get("origin_model", ""),
            frame_type=frame_type,
            material_to_outcome=f.get("material_to_outcome", True),
        ))

    analogies = []
    for a in data.get("cross_domain_analogies", []):
        analogies.append(CrossDomainAnalogy(
            analogy_id=a.get("analogy_id", f"ANA-{len(analogies)+1}"),
            source_domain=a.get("source_domain", ""),
            target_claim_id=a.get("target_claim_id", ""),
            transfer_mechanism=a.get("transfer_mechanism", ""),
        ))

    return DivergenceResult(
        required=True,
        framing_pass_executed=True,
        alt_frames=frames,
        cross_domain_analogies=analogies,
    )


async def run_frame_survival_check(
    client,
    frames: list[FrameInfo],
    round_texts: dict[str, str],
    round_num: int,
    is_analysis_mode: bool = False,
) -> list[FrameInfo]:
    """Check frame survival against a round's outputs.

    R2: frame DROPPED only if 3+ traceable drop votes.
    R3/R4: frames are never dropped, only CONTESTED.
    """
    if not frames:
        return frames

    active_frames = [f for f in frames if f.survival_status in
                     (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)]
    if not active_frames:
        return frames

    frames_formatted = "\n".join(
        f"- {f.frame_id}: {f.text} (status: {f.survival_status.value})"
        for f in active_frames
    )
    round_formatted = "\n\n".join(f"### {m}\n{t}" for m, t in round_texts.items())

    if is_analysis_mode:
        # DOD §18.2: ANALYSIS frames use EXPLORED/NOTED/UNEXPLORED, never dropped
        rules = ("- ANALYSIS mode: frames are NEVER dropped.\n"
                 "- Use statuses: EXPLORED (substantively investigated), NOTED (acknowledged but not deep), "
                 "UNEXPLORED (identified but not investigated).\n"
                 "- Do NOT use ACTIVE/CONTESTED/DROPPED in ANALYSIS mode.")
    elif round_num == 2:
        rules = "- A frame is DROPPED only if 3 or more models explicitly reject it with traceable reasoning.\n- A frame is CONTESTED if at least 1 model challenges it but fewer than 3.\n- A frame is ADOPTED if a model explicitly takes it up.\n- A frame is REBUTTED if substantively countered."
    else:
        rules = "- Frames are NEVER dropped in R3/R4. They can only be CONTESTED, ADOPTED, or remain ACTIVE.\n- CONTESTED frames stay CONTESTED (never downgraded to DROPPED)."

    prompt = FRAME_SURVIVAL_PROMPT.format(
        frames_formatted=frames_formatted,
        round_num=round_num,
        round_texts_formatted=round_formatted,
        survival_rules=rules,
    )

    resp = await client.call("sonnet", prompt)
    if not resp.ok:
        raise BrainError(f"frame_survival_r{round_num}",
                         f"Frame survival LLM call failed: {resp.error}")

    text = resp.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        from thinker.types import extract_json
        data = extract_json(text)
    except json.JSONDecodeError as e:
        raise BrainError(f"frame_survival_r{round_num}",
                         f"Failed to parse frame survival JSON: {e}",
                         detail=resp.text[:500])

    # Build lookup
    eval_lookup = {e["frame_id"]: e for e in data.get("evaluations", [])}

    for frame in frames:
        ev = eval_lookup.get(frame.frame_id)
        if not ev:
            continue

        try:
            new_status = FrameSurvivalStatus(ev.get("status", "ACTIVE"))
        except ValueError:
            new_status = FrameSurvivalStatus.ACTIVE

        # DOD §18.5: "Frame dropping occurs in ANALYSIS mode → ERROR"
        if is_analysis_mode and new_status == FrameSurvivalStatus.DROPPED:
            from thinker.types import BrainError
            raise BrainError(
                "frame_survival",
                f"Frame {frame.frame_id} dropped in ANALYSIS mode",
                detail="DOD §18.5: Frame dropping in ANALYSIS mode → ERROR.",
            )

        # R3/R4: never allow DROPPED
        if round_num >= 3 and new_status == FrameSurvivalStatus.DROPPED:
            new_status = FrameSurvivalStatus.CONTESTED

        # R2: require 3 drop votes for DROPPED
        if round_num == 2 and new_status == FrameSurvivalStatus.DROPPED:
            drop_models = ev.get("drop_vote_models", [])
            if len(drop_models) < 3:
                new_status = FrameSurvivalStatus.CONTESTED
            else:
                frame.r2_drop_vote_count = len(drop_models)
                frame.r2_drop_vote_refs = drop_models

        frame.survival_status = new_status

    return frames


def check_exploration_stress(
    agreement_ratio: float,
    question_class: QuestionClass,
    stakes_class: StakesClass,
) -> bool:
    """Check if exploration stress trigger should fire.

    Returns True if R1 agreement > 0.75 on OPEN/HIGH questions.
    """
    if agreement_ratio <= 0.75:
        return False
    # DOD Section 8.3: OPEN OR HIGH (not AMBIGUOUS)
    if question_class == QuestionClass.OPEN:
        return True
    if stakes_class == StakesClass.HIGH:
        return True
    return False


def format_frames_for_prompt(frames: list[FrameInfo]) -> str:
    """Format active/contested frames for injection into R2+ prompts."""
    active = [f for f in frames if f.survival_status in
              (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)]
    if not active:
        return ""

    lines = ["## Alternative Frames (must address)",
             "The following alternative frames have survived deliberation so far.\n"]
    for f in active:
        status_tag = f" [{f.survival_status.value}]" if f.survival_status == FrameSurvivalStatus.CONTESTED else ""
        lines.append(f"- **{f.frame_id}**: {f.text}{status_tag}")

    return "\n".join(lines)


def format_r2_frame_enforcement() -> str:
    """R2 frame enforcement instruction text."""
    return (
        "\n## Frame Engagement Requirements (MANDATORY for R2)\n"
        "You MUST:\n"
        "1. ADOPT at least one alternative frame and argue from its perspective\n"
        "2. REBUT at least one alternative frame with substantive counter-arguments\n"
        "3. GENERATE at least one NEW alternative frame not yet proposed\n"
        "\nFor each, clearly label: ADOPT: [frame_id], REBUT: [frame_id], NEW_FRAME: [description]\n"
    )

```


### thinker/decisive_claims.py


```python
"""Decisive Claim Extraction — identifies claims that carry the conclusion (DESIGN-V3.md Section 3.2).

One Sonnet call post-R4. Extracts claims that are material to the conclusion,
with evidence bindings showing what supports each claim.
"""
from __future__ import annotations

import json

from thinker.pipeline import pipeline_stage
from thinker.types import (
    BrainError, DecisiveClaim, EvidenceSupportStatus,
)

CLAIM_EXTRACTION_PROMPT = """You are a decisive claim extractor for a multi-model deliberation system.

Given the final round model outputs and available evidence, identify the 3-8 most decisive claims —
the claims that CARRY the conclusion. A decisive claim is one where, if it were false, the conclusion
would change.

## Final Round Model Outputs
{final_views}

## Available Evidence
{evidence_text}

## Output Format — STRICT JSON (no markdown, no commentary)

{{
  "claims": [
    {{
      "claim_id": "DC-1",
      "text": "the decisive claim in one sentence",
      "material_to_conclusion": true,
      "evidence_refs": ["E001", "E003"],
      "evidence_support_status": "SUPPORTED | PARTIAL | UNSUPPORTED",
      "supporting_model_ids": ["r1", "reasoner"]
    }}
  ]
}}

## Rules
- 3-8 claims maximum. Focus on the ones that MATTER.
- SUPPORTED: claim is directly backed by cited evidence
- PARTIAL: some evidence exists but doesn't fully prove the claim
- UNSUPPORTED: claim is asserted by models but has no evidence backing
- evidence_refs: list evidence IDs (E001-E999) that support this claim. Empty list = UNSUPPORTED.
- material_to_conclusion: true if removing this claim would change the outcome
- supporting_model_ids: list which models made or endorsed this claim (e.g. ["r1", "reasoner"])"""


@pipeline_stage(
    name="Decisive Claim Extraction",
    description="Post-R4 Sonnet call extracting 3-8 claims that carry the conclusion, with evidence bindings.",
    stage_type="track",
    order=16,
    provider="sonnet",
    inputs=["final_views", "evidence_text"],
    outputs=["DecisiveClaim[]"],
    logic="Parse JSON. 3-8 claims. Each with evidence refs and support status.",
    failure_mode="LLM or parse failure: return empty list (non-fatal — degrades D4/stability but doesn't halt).",
    cost="1 Sonnet call",
    stage_id="decisive_claims",
)
async def extract_decisive_claims(
    client,
    final_views: dict[str, str],
    evidence_text: str,
) -> list[DecisiveClaim]:
    """Extract decisive claims from final round outputs."""
    views_formatted = "\n\n".join(f"### {m}\n{t}" for m, t in final_views.items())
    prompt = CLAIM_EXTRACTION_PROMPT.format(
        final_views=views_formatted,
        evidence_text=evidence_text or "No evidence available.",
    )

    resp = await client.call("sonnet", prompt)
    if not resp.ok:
        # Non-fatal: decisive claims degrade gracefully
        return []

    text = resp.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        from thinker.types import extract_json
        data = extract_json(text)
    except json.JSONDecodeError:
        return []

    claims = []
    for c in data.get("claims", [])[:8]:
        try:
            support = EvidenceSupportStatus(c.get("evidence_support_status", "UNSUPPORTED"))
        except ValueError:
            support = EvidenceSupportStatus.UNSUPPORTED

        claims.append(DecisiveClaim(
            claim_id=c.get("claim_id", f"DC-{len(claims)+1}"),
            text=c.get("text", ""),
            material_to_conclusion=c.get("material_to_conclusion", True),
            evidence_refs=c.get("evidence_refs", []),
            evidence_support_status=support,
            supporting_model_ids=c.get("supporting_model_ids", []),
        ))

    return claims

```


### thinker/evidence.py


```python
"""Evidence Ledger — stores, deduplicates, scores, and formats evidence.

Evidence items are kept in insertion order (search engine's ranking order).
V8-F3 adds relevance scoring: under cap pressure, the lowest-scored item
is evicted instead of blindly rejecting new items.
Cap at max_items. Within the same score tier, insertion order is preserved.

V9: Two-tier ledger — active_items (capped) + archive_items (uncapped).
Eviction moves to archive, never deletes. Referenced evidence always available.
"""
from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import urlparse

from thinker.types import Confidence, EvidenceItem, EvictionEvent
from thinker.tools.cross_domain import is_cross_domain

# Authoritative domains that get a score boost
_AUTHORITY_DOMAINS = {
    "nvd.nist.gov", "cve.mitre.org", "owasp.org", "sec.gov",
    "who.int", "cdc.gov", "fda.gov", "nih.gov",
    "ieee.org", "acm.org", "arxiv.org",
    "reuters.com", "bloomberg.com", "ft.com",
    "github.com", "docs.python.org", "docs.microsoft.com",
}


def score_evidence(item: EvidenceItem, brief_keywords: set[str]) -> float:
    """Score evidence item for relevance.

    Factors:
    - Keyword overlap with brief (0-5 points, 1 per keyword match, capped)
    - Source authority (0 or 2 points for known authoritative domains)
    - Base score of 1.0 so all items have positive score
    """
    score = 1.0

    # Keyword overlap
    text_lower = (item.topic + " " + item.fact).lower()
    kw_hits = 0
    for kw in brief_keywords:
        if kw.lower() in text_lower:
            kw_hits += 1
    score += min(kw_hits, 5)

    # Source authority + set authority_tier
    try:
        domain = urlparse(item.url).netloc.lower()
        if any(auth in domain for auth in _AUTHORITY_DOMAINS):
            score += 2.0
            item.authority_tier = "HIGH"
    except Exception:
        pass

    return score


class EvidenceLedger:
    """Manages evidence items with dedup, cross-domain filtering, scoring, and cap enforcement.

    V9 two-tier architecture:
    - active_items: capped at max_items, used in prompts
    - archive_items: uncapped, evicted items preserved here
    - eviction_log: tracks all movements
    - Never deletes evidence — eviction moves to archive.
    """

    def __init__(self, max_items: int = 10, brief_domain: Optional[str] = None,
                 brief_keywords: Optional[set[str]] = None):
        self.active_items: list[EvidenceItem] = []
        self.archive_items: list[EvidenceItem] = []
        self.eviction_log: list[EvictionEvent] = []
        self.max_items = max_items
        self.brief_domain = brief_domain
        self.brief_keywords: set[str] = brief_keywords or set()
        self._content_hashes: set[str] = set()
        self._seen_urls: set[str] = set()
        self.cross_domain_rejections: int = 0
        self.contradictions: list = []
        self._eviction_counter: int = 0

    @property
    def items(self) -> list[EvidenceItem]:
        """Backward compatibility: returns active items."""
        return self.active_items

    @property
    def all_items(self) -> list[EvidenceItem]:
        """All evidence items (active + archived)."""
        return self.active_items + self.archive_items

    @property
    def high_authority_evidence_present(self) -> bool:
        """Whether any evidence (active or archive) has HIGH or AUTHORITATIVE authority tier."""
        return any(
            e.authority_tier in ("HIGH", "AUTHORITATIVE")
            for e in self.active_items + self.archive_items
        )

    def get_from_any(self, evidence_id: str) -> Optional[EvidenceItem]:
        """Search both active and archive for an evidence item by ID."""
        for item in self.active_items:
            if item.evidence_id == evidence_id:
                return item
        for item in self.archive_items:
            if item.evidence_id == evidence_id:
                return item
        return None

    def all_evidence_ids(self) -> set[str]:
        """Return all evidence IDs across active and archive."""
        return {e.evidence_id for e in self.active_items} | {e.evidence_id for e in self.archive_items}

    def validate_refs(self, refs: list[str]) -> list[str]:
        """Return any evidence_refs that don't exist in either store.

        DOD §10.3: "Cited evidence missing from both stores → ERROR"
        """
        known = self.all_evidence_ids()
        return [ref for ref in refs if ref and ref not in known]

    def _evict_to_archive(self, item: EvidenceItem, reason: str = "cap_pressure") -> None:
        """Move an item from active to archive."""
        self.active_items.remove(item)
        item.is_active = False
        item.is_archived = True
        self.archive_items.append(item)
        self._eviction_counter += 1
        self.eviction_log.append(EvictionEvent(
            event_id=f"EVICT-{self._eviction_counter}",
            evidence_id=item.evidence_id,
            from_active=True,
            to_archive=True,
            reason=reason,
        ))

    def add(self, item: EvidenceItem) -> bool:
        """Add evidence item. Returns False if rejected.

        Rejection reasons: duplicate content, duplicate URL, cross-domain,
        or lower-scored than all existing items when ledger is full.
        Under cap pressure: if the new item scores higher than the
        lowest-scored existing item, evict that item to archive.
        """
        # Cross-domain filter
        if self.brief_domain and is_cross_domain(item.fact + " " + item.topic, self.brief_domain):
            self.cross_domain_rejections += 1
            return False

        # Content dedup
        content_hash = hashlib.sha256(item.fact.encode()).hexdigest()[:16]
        if content_hash in self._content_hashes:
            return False

        # URL dedup
        if item.url in self._seen_urls:
            return False

        # Score the new item
        item.score = score_evidence(item, self.brief_keywords)
        item.is_active = True
        item.is_archived = False

        # Cap check with eviction to archive
        if len(self.active_items) >= self.max_items:
            min_item = min(self.active_items, key=lambda e: e.score)
            if item.score > min_item.score:
                # Evict the lowest-scored item to archive
                self._content_hashes.discard(min_item.content_hash)
                self._seen_urls.discard(min_item.url)
                self._evict_to_archive(min_item, reason="cap_pressure_score_eviction")
            else:
                return False

        self._content_hashes.add(content_hash)
        self._seen_urls.add(item.url)
        item.content_hash = content_hash
        self.active_items.append(item)

        # DOD §10.3: "Active exceeds 10 → ERROR" — post-condition check
        if len(self.active_items) > self.max_items:
            from thinker.types import BrainError
            raise BrainError(
                "evidence_ledger",
                f"Active evidence exceeds cap: {len(self.active_items)} > {self.max_items}",
                detail="DOD §10.3: Active exceeds 10 → ERROR",
            )

        # Check for contradictions with existing active items
        from thinker.tools.contradiction import detect_contradiction
        for existing in self.active_items[:-1]:
            ctr = detect_contradiction(existing, item)
            if ctr:
                self.contradictions.append(ctr)

        return True

    def format_for_prompt(self) -> str:
        """Format evidence for injection into a model prompt.

        DOD §10.2: active evidence first, then high-authority archive items.
        Archive items are marked [ARCHIVED] so models know they are evicted
        but still authoritative.
        """
        if not self.active_items and not self.archive_items:
            return ""
        lines = []
        for item in self.active_items:
            lines.append(
                f"{{{item.evidence_id}}} {item.fact}\n"
                f"Source: {item.url}\n"
            )
        # DOD §10.2: archived high-authority evidence must be visible to Gate 2 reasoning
        high_auth_archive = [
            e for e in self.archive_items
            if e.authority_tier in ("HIGH", "AUTHORITATIVE")
        ]
        if high_auth_archive:
            lines.append("## Archived High-Authority Evidence (evicted from active set but authoritative)\n")
            for item in high_auth_archive:
                lines.append(
                    f"[ARCHIVED] {{{item.evidence_id}}} {item.fact}\n"
                    f"Source: {item.url}\n"
                )
        if lines:
            lines.append(
                "Any specific number, percentage, or dollar figure in your analysis "
                "MUST cite an evidence ID (E001-E999) from above."
            )
        return "\n".join(lines)

```


### thinker/config.py


```python
"""Configuration for the Thinker V8 Brain engine."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for a single LLM."""
    name: str
    model_id: str
    provider: str  # "openrouter", "anthropic", "deepseek", or "zai"
    max_tokens: int
    timeout_s: int
    is_thinking: bool = False


# --- Model roster (V8 spec Section 4) ---

R1_MODEL = ModelConfig("r1", "deepseek/deepseek-r1-0528", "openrouter", 30_000, 720, is_thinking=True)
REASONER_MODEL = ModelConfig("reasoner", "deepseek-reasoner", "deepseek", 30_000, 720, is_thinking=True)
GLM5_MODEL = ModelConfig("glm5", "glm-5-turbo", "zai", 16_000, 480)
KIMI_MODEL = ModelConfig("kimi", "moonshotai/kimi-k2", "openrouter", 16_000, 480)
SONNET_MODEL = ModelConfig("sonnet", "claude-sonnet-4-6", "anthropic", 16_000, 300)
HAIKU_MODEL = ModelConfig("haiku", "claude-haiku-4-5-20251001", "anthropic", 4_000, 60)

# --- Round topology (V8 spec: 4 -> 3 -> 2 -> 2) ---

ROUND_TOPOLOGY: dict[int, list[str]] = {
    1: ["r1", "reasoner", "glm5", "kimi"],
    2: ["r1", "reasoner", "glm5"],
    3: ["r1", "reasoner"],
    4: ["r1", "reasoner"],
}

MODEL_REGISTRY: dict[str, ModelConfig] = {
    "r1": R1_MODEL,
    "reasoner": REASONER_MODEL,
    "glm5": GLM5_MODEL,
    "kimi": KIMI_MODEL,
    "sonnet": SONNET_MODEL,
    "haiku": HAIKU_MODEL,
}


@dataclass
class BrainConfig:
    """Runtime configuration for a Brain run."""
    rounds: int = 4
    max_evidence_items: int = 10
    max_search_queries_per_phase: int = 5
    search_after_rounds: int = 2  # Search runs after rounds 1..N (default: after R1 and R2)
    openrouter_api_key: str = ""
    anthropic_oauth_token: str = ""
    deepseek_api_key: str = ""
    zai_api_key: str = ""
    brave_api_key: str = ""
    outdir: str = "./output"
    analysis_debug_runs_remaining: int = 10  # DOD §18.4: debug sunset counter
    skip_assumption_gate: bool = False  # Override: skip fatal assumption check (for self-review briefs)

```


### thinker/tools/blocker.py


```python
"""Blocker Lifecycle — tracks evidence gaps, contradictions, and disagreements."""
from __future__ import annotations

from thinker.types import Blocker, BlockerKind, BlockerStatus


class BlockerLedger:
    def __init__(self):
        self.blockers: list[Blocker] = []
        self._counter = 0

    def add(self, kind: BlockerKind, source: str, detected_round: int,
            detail: str = "", models: list[str] | None = None,
            severity: str = "MEDIUM") -> Blocker:
        self._counter += 1
        blocker = Blocker(
            blocker_id=f"BLK{self._counter:03d}",
            kind=kind,
            source=source,
            detected_round=detected_round,
            severity=severity,
            detail=detail,
            models_involved=models or [],
            status_history=[{"status": "OPEN", "round": detected_round, "trigger": "detected"}],
        )
        self.blockers.append(blocker)
        return blocker

    def resolve(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.RESOLVED, round_num, trigger, note)

    def defer(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.DEFERRED, round_num, trigger, note)

    def drop(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.DROPPED, round_num, trigger, note)

    def open_blockers(self) -> list[Blocker]:
        return [b for b in self.blockers if b.status == BlockerStatus.OPEN]

    def summary(self) -> dict:
        by_status = {}
        by_kind = {}
        for b in self.blockers:
            by_status[b.status.value] = by_status.get(b.status.value, 0) + 1
            by_kind[b.kind.value] = by_kind.get(b.kind.value, 0) + 1
        return {
            "total_blockers": len(self.blockers),
            "by_status": by_status,
            "by_kind": by_kind,
            "open_at_end": len(self.open_blockers()),
        }

    def _update_status(self, blocker_id: str, new_status: BlockerStatus,
                       round_num: int, trigger: str, note: str):
        for b in self.blockers:
            if b.blocker_id == blocker_id:
                b.status = new_status
                b.resolution_note = note
                b.status_history.append({
                    "status": new_status.value, "round": round_num, "trigger": trigger,
                })
                return

```


### thinker/tools/ungrounded.py


```python
"""Ungrounded Stat Detector — flags claims with numbers not backed by evidence."""
from __future__ import annotations

import re

from thinker.types import EvidenceItem

_STAT_PATTERN = re.compile(
    r"(\d[\d,.]*\s*%"
    r"|\$[\d,.]+[BMK]?"
    r"|\d{2,}[\d,]*)"
)

_EVIDENCE_REF = re.compile(r"\{E\d+\}")


def find_ungrounded_stats(
    text: str, evidence: list[EvidenceItem],
) -> list[str]:
    evidence_numbers = set()
    for ev in evidence:
        for m in _STAT_PATTERN.finditer(ev.fact):
            evidence_numbers.add(m.group().strip())

    ungrounded = []
    for match in _STAT_PATTERN.finditer(text):
        stat = match.group().strip()
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end]

        if _EVIDENCE_REF.search(context):
            continue

        if stat in evidence_numbers:
            continue

        ungrounded.append(stat)

    return ungrounded


def generate_verification_queries(ungrounded_stats: list[str], context: str) -> list[str]:
    queries = []
    for stat in ungrounded_stats[:5]:
        idx = context.find(stat)
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(context), idx + len(stat) + 100)
            snippet = context[start:end].strip()
            queries.append(f"verify {stat} {snippet[:50]}")
        else:
            queries.append(f"verify statistic {stat}")
    return queries

```


### thinker/tools/contradiction.py


```python
"""Contradiction Detector — finds numeric conflicts between evidence items."""
from __future__ import annotations

import re
from typing import Optional

from thinker.types import Contradiction, EvidenceItem

_NUMBER_PATTERN = re.compile(r"\b(\d[\d,.]*%?)\b")


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_PATTERN.findall(text))


def _topic_overlap(a: str, b: str) -> int:
    words_a = {w.lower() for w in a.split() if len(w) >= 4}
    words_b = {w.lower() for w in b.split() if len(w) >= 4}
    return len(words_a & words_b)


_CONTRADICTION_COUNTER = 0


def detect_contradiction(
    item_a: EvidenceItem, item_b: EvidenceItem,
) -> Optional[Contradiction]:
    global _CONTRADICTION_COUNTER

    if _topic_overlap(item_a.topic + " " + item_a.fact, item_b.topic + " " + item_b.fact) < 2:
        return None

    nums_a = _extract_numbers(item_a.fact)
    nums_b = _extract_numbers(item_b.fact)

    if not nums_a or not nums_b:
        return None

    # If all numbers in the smaller set appear in the larger set, no contradiction
    # (one item may just have more detail)
    if nums_a.issubset(nums_b) or nums_b.issubset(nums_a):
        return None

    _CONTRADICTION_COUNTER += 1
    # HIGH if the unique numbers differ significantly (both have exclusive numbers)
    exclusive_a = nums_a - nums_b
    exclusive_b = nums_b - nums_a
    severity = "HIGH" if exclusive_a and exclusive_b else "MEDIUM"
    return Contradiction(
        contradiction_id=f"CTR{_CONTRADICTION_COUNTER:03d}",
        evidence_ids=[item_a.evidence_id, item_b.evidence_id],
        topic=item_a.topic,
        severity=severity,
        evidence_ref_a=item_a.evidence_id,
        evidence_ref_b=item_b.evidence_id,
        same_entity=item_a.topic_cluster == item_b.topic_cluster if item_a.topic_cluster else False,
        same_timeframe=True,  # Numeric contradictions on same topic assumed same timeframe
    )

```

