# Brain V8 — DoD v2.1 Patch: Common Sense and Out-of-the-Box Thinking

**Date:** 2026-03-31
**Based on:** Multi-platform facilitation (Brain V8 × 4 models, ChatGPT, Claude)
**Adds to:** V8-DOD-v2.md (18 sections)
**Status:** Draft — agreed definitions, pending implementation review

---

## Summary of Changes

| Change | Affects |
|--------|---------|
| New Section 19: Common Sense Audit | Gate structure, proof.json, Section 14 |
| New Section 20: Out-of-the-Box Thinking | Round topology, argument tracking, proof.json |
| Section 1 extension | SHORT_CIRCUIT outcome mapping |
| Section 2 extension | Gate 2 rules extended (rules 8–13 added) |
| Section 5 extension | CS Audit added as mandatory pre-R1 step |
| Section 8 extension | Divergent Framing Pass added to argument lineage |
| Section 9 extension | commonsense.* and divergence.* proof fields |
| Section 14 extension | LLM determinism carve-out for CS Audit |
| Section 16 extension | New required tests for Sections 19 and 20 |

---

## Section 1 Extension — Authoritative Outcome Contract

Add the following note to Section 1:

> **SHORT_CIRCUIT** is not a separate top-level outcome. When the Common Sense Audit determines that a question is trivially settled (question_class = TRIVIAL or WELL_ESTABLISHED, stakes_class = LOW, no CRITICAL premise flags), the pipeline MAY short-circuit to DECIDE via an abbreviated path. The outcome emitted is DECIDE with `commonsense.short_circuit_taken = true` recorded in proof.json. All existing DECIDE requirements apply. No new outcome code is introduced.

---

## Section 2 Extension — Updated Gate 2 Outcome Decision Rules

Replace existing rules 1–7 with this extended ordered rule set. Existing rules 1–7 are preserved as rules 1–7 and new rules 8–13 are added:

1. **Fatal integrity failure detected** → ERROR *(unchanged)*
2. **agreement_ratio < 0.50** → NO_CONSENSUS *(unchanged)*
3. **agreement_ratio < 0.75** → ESCALATE *(unchanged)*
4. **Any unresolved critical argument or blocker** → ESCALATE *(unchanged)*
5. **Decisive claims lack required evidence support** → ESCALATE *(unchanged)*
6. **Critical evidence contradictions unresolved** → ESCALATE *(unchanged)*
7. **Otherwise** → DECIDE *(replaced by rule 13 below — rule 7 becomes the fallthrough)*

New rules (inserted between existing rule 6 and the final DECIDE):

8. **Missing Common Sense Audit on any non-short-circuit path** → ERROR *(fatal — audit is mandatory)*
9. **Missing adversarial slot or Divergent Framing Pass on any required path** → ERROR *(fatal — OOTB is mandatory for non-trivial questions)*
10. **Any unresolved CRITICAL premise flag** → ESCALATE *(flag not rebutted or resolved by synthesis)*
11. **Any material alternative frame remains ACTIVE or CONTESTED without explicit rebuttal** → ESCALATE
12. **fast_consensus_allowed = false AND fast unanimity observed AND no independent evidence** → ESCALATE *(fast consensus is warning, not proof)*
13. **Otherwise** → DECIDE

**Requirements:**
- Rules 8 and 9 produce ERROR (not ESCALATE) because missing mandatory pipeline stages are integrity failures, not deliberation outcomes.
- Frame drop votes (divergence.alt_frames[].drop_vote_count) are SEPARATE from the main agreement_ratio calculation. Frame drop voting does NOT feed into agreement_ratio. This is explicit to prevent conflict between rule 3 and the two-vote drop rule in Section 20.
- Rule 12 does not block DECIDE if fast consensus is observed AND corroborated by independent evidence (evidence_items > 0 and evidence cited in decisive claims).

---

## Section 5 Extension — Pipeline Gates

Add CS Audit to the gate table:

| Gate | Type | Purpose | Pass Condition | Fail Action |
|------|------|---------|---------------|-------------|
| Gate 1 | LLM (Sonnet) | Pre-run admission + search decision | Brief is specific, has context, has deliverable | NEED_MORE pre-run rejection |
| CS Audit | LLM (Sonnet) | Effort calibration + premise validation | Brief classified; outputs emitted | Missing outputs → ERROR; question_class=INVALID → ERROR |
| Gate 2 | Deterministic | Outcome classification | See Section 2 rules (updated) | Outcome classified per Section 2 |

**Requirements:**
- CS Audit executes exactly once, after Gate 1 PASS and before any R1 model is invoked.
- CS Audit MUST NOT be skipped on any path unless the run itself was rejected at Gate 1.
- CS Audit MUST emit all required outputs or the run produces ERROR.
- CS Audit output is parsed deterministically (same rule as Gate 1 per Section 14).

---

## Section 8 Extension — Argument, Position, and Objection Lineage

Add the following requirements after the existing Section 8 requirements:

**Divergent Framing Pass:**
- After R1 and before R2, the controller MUST execute a Divergent Framing Pass.
- The pass extracts and registers all material alternative frames surfaced in R1.
- Each alternative frame is a first-class tracked object with a stable ID (FRAME-N).
- Alternative frames exist in the divergence.alt_frames[] ledger, SEPARATE from the argument ledger (R1-ARG-N). Frame tracking does not replace argument tracking.

**Frame survival rules:**
- A material alternative frame MUST NOT be marked DROPPED unless at least two distinct models have cast explicit drop votes with traceable rebuttal references.
- A single drop vote sets survival_status = CONTESTED and MUST NOT drop the frame.
- A drop vote without a cited argument reference or rebuttal MUST NOT count.
- A frame marked ACTIVE or CONTESTED at synthesis MUST be addressed (adopted, rebutted, or explicitly noted as unresolved) in the synthesis output.

**Cross-domain analogy tracking:**
- Any material cross-domain analogy used to support a decisive claim MUST be tracked as a structured object with source_domain, target_claim, transfer_mechanism, and test_status.
- An analogy with test_status = UNTESTED MUST NOT carry decisive factual load.

---

## Section 9 Extension — Proof Artifact Contract

Add the following fields to the proof.json completeness contract:

### commonsense object (required on all runs)

| Field | Type | Required | Notes |
|-------|------|---------|-------|
| commonsense.executed | bool | always | must be true on non-Gate1-rejected runs |
| commonsense.stakes_class | enum | always | LOW / STANDARD / HIGH |
| commonsense.question_class | enum | always | TRIVIAL / WELL_ESTABLISHED / OPEN / AMBIGUOUS / INVALID |
| commonsense.required_effort_tier | enum | always | SHORT_CIRCUIT / STANDARD / ELEVATED |
| commonsense.fast_consensus_allowed | bool | always | |
| commonsense.short_circuit_taken | bool | always | true only if TRIVIAL/WELL_ESTABLISHED + LOW stakes + no CRITICAL flags |
| commonsense.fast_consensus_observed | bool | always | true if R1 agreement_ratio >= 0.95 |
| commonsense.groupthink_warning | bool | always | true if fast_consensus_observed AND fast_consensus_allowed = false |
| commonsense.settlement_assessment | enum | always | WELL_ESTABLISHED_FACT / GENUINE_UNCERTAINTY / INVALIDATED_PREMISE / UNRESOLVED |
| commonsense.premise_flags | array | always | see sub-fields below |

Each commonsense.premise_flags[] item:

| Field | Type | Required |
|-------|------|---------|
| flag_id | string | PFLAG-N format |
| flag_type | enum | INTERNAL_CONTRADICTION / UNSUPPORTED_ASSUMPTION / AMBIGUITY / IMPOSSIBLE_REQUEST / FRAMING_DEFECT |
| severity | enum | INFO / WARNING / CRITICAL |
| summary | string | one sentence |
| blocking | bool | true if CRITICAL and unresolved |
| resolved | bool | |
| resolved_by | string | stage that resolved it, or null |

### divergence object (required on non-SHORT_CIRCUIT runs)

| Field | Type | Required | Notes |
|-------|------|---------|-------|
| divergence.required | bool | always | false only on SHORT_CIRCUIT path |
| divergence.adversarial_slot_assigned | bool | when required | must be true on non-short-circuit |
| divergence.adversarial_model_id | string | when assigned | which model got the adversarial prompt |
| divergence.adversarial_assignment_type | enum | when assigned | CONTRARIAN / REFRAMER / PREMISE_CHALLENGER / CROSS_DOMAIN |
| divergence.framing_pass_executed | bool | when required | |
| divergence.material_unrebutted_frame_count | int | always | frames remaining ACTIVE or CONTESTED at Gate 2 |
| divergence.gate2_blocked_by_divergence | bool | always | true if ESCALATE was triggered by rule 11 |
| divergence.alt_frames | array | when required | |
| divergence.cross_domain_analogies | array | always | may be empty |

Each divergence.alt_frames[] item:

| Field | Type | Required |
|-------|------|---------|
| frame_id | string | FRAME-N format |
| frame_type | enum | INVERSION / OBJECTIVE_REWRITE / PREMISE_CHALLENGE / CROSS_DOMAIN_ANALOGY / OPPOSITE_STANCE / REMOVE_PROBLEM |
| owner_model | string | model that generated it |
| survival_status | enum | ACTIVE / CONTESTED / DROPPED / ADOPTED |
| drop_vote_count | int | 0–N; ≥2 required for DROPPED |
| rebuttal_refs | array | argument IDs or evidence IDs supporting drop |
| material_to_outcome | bool | true if frame affects or could affect the final verdict |
| considered_at_gate2 | bool | |

Each divergence.cross_domain_analogies[] item:

| Field | Type | Required |
|-------|------|---------|
| analogy_id | string | ANALOGY-N format |
| source_domain | string | |
| target_claim | string | the claim the analogy supports |
| transfer_mechanism | string | why the analogy is valid for this domain |
| test_status | enum | UNTESTED / SUPPORTED / REJECTED |

---

## Section 14 Extension — Determinism Policy for Gates

Add the following requirement after the existing Section 14 requirements:

> **Common Sense Audit uses an LLM (acceptable, same as Gate 1).** The same determinism rule applies: the CS Audit's LLM output must be parsed deterministically into the required enum fields. Unparseable or missing CS Audit output → fail-closed → ERROR. The CS Audit does not introduce new unrecorded randomness because all outputs are recorded in proof.json with full config snapshot. Threshold overrides for effort calibration must be in BrainConfig and recorded in proof.

---

## New Section 19 — Common Sense Audit

**Purpose:** Calibrate the pipeline's behavior to the actual nature of the question before deliberation begins.

**Requirements:**

19.1 The controller SHALL execute a Common Sense Audit after Gate 1 PASS and before any R1 prompt is issued.

19.2 The CS Audit SHALL emit all required fields listed in the Section 9 commonsense object. Missing or malformed fields constitute a fatal integrity failure → ERROR.

19.3 Stakes classification (stakes_class):
- LOW: question involves no regulatory, financial, safety, or reputational consequences
- STANDARD: question involves moderate consequence, uncertainty exists
- HIGH: question involves regulatory, financial, safety, or reputational consequence, or broad impact

19.4 Question classification (question_class):
- TRIVIAL: settled by common knowledge, no deliberation needed
- WELL_ESTABLISHED: settled by documented consensus (scientific, legal, technical) — evidence may exist but deliberation adds little
- OPEN: genuine uncertainty; deliberation is the appropriate path
- AMBIGUOUS: brief's framing is unclear or could mean multiple things
- INVALID: brief contains a fundamental defect (impossible request, self-contradictory)

19.5 Effort tier (required_effort_tier):
- SHORT_CIRCUIT is permitted only when ALL of the following are true: question_class ∈ {TRIVIAL, WELL_ESTABLISHED}; stakes_class = LOW; no CRITICAL premise_flags; no mandatory DoD requirement elsewhere requires elevated search, evidence, or quorum.
- ELEVATED is required when: stakes_class = HIGH; or question_class ∈ {AMBIGUOUS, INVALID}; or any CRITICAL premise_flag exists.
- SHORT_CIRCUIT MUST NOT be used to bypass mandatory evidence requirements for decisive claims.

19.6 Groupthink detection:
- If commonsense.fast_consensus_observed = true AND commonsense.fast_consensus_allowed = false, the controller SHALL set commonsense.groupthink_warning = true.
- A groupthink warning MUST be propagated to synthesis and recorded in proof.json.
- Fast consensus alone MUST NOT justify DECIDE when fast_consensus_allowed = false (see Section 2, rule 12).

19.7 Premise validation:
- The CS Audit SHALL check the brief for: internal contradictions, unsupported embedded assumptions, ambiguity that changes the decision target, impossible or malformed requests, framing defects likely to distort deliberation.
- Each detected defect SHALL be recorded as a premise_flag with the fields in Section 9.
- A CRITICAL premise_flag that is not resolved by synthesis prevents DECIDE (Section 2, rule 10).

19.8 question_class = INVALID AND defect is not repairable from the brief as given → ERROR (not NEED_MORE — the brief was admitted by Gate 1 but the CS Audit found it fundamentally defective).

---

## New Section 20 — Out-of-the-Box Thinking / Divergent Framing

**Purpose:** Ensure the pipeline generates and tests credible non-default frames, adversarial positions, and cross-domain analogies.

**Applicability:** All non-SHORT_CIRCUIT paths. These requirements do NOT apply on SHORT_CIRCUIT paths (trivial questions do not benefit from frame diversity).

**Requirements:**

20.1 Adversarial slot:
- At least one R1 model SHALL be assigned an explicit adversarial or reframing role via controller-driven prompt modification.
- The assignment MUST NOT be implicit. The adversarial model ID and assignment type SHALL be recorded in divergence.adversarial_model_id and divergence.adversarial_assignment_type.
- The adversarial role SHALL do at least one of: argue the strongest credible contrarian answer; challenge the brief's default framing; propose a materially different interpretation of what should be decided.
- The adversarial role MUST NOT invent implausible disagreement to satisfy coverage. Adversarial positions must be credible.

20.2 Adversarial role and model isolation (Section 4):
- The adversarial model's prompt modification (role assignment) is not a violation of Section 4 (model isolation). Prompt-level role assignment is permitted. What is forbidden is sharing another model's R1 output within the same round. The adversarial model receives a different prompt framing, not another model's answer.

20.3 Divergent Framing Pass:
- After R1 and before any R2 model is invoked, the controller SHALL execute a Divergent Framing Pass.
- The pass SHALL extract and register all material alternative frames from R1 into divergence.alt_frames[].
- A material alternative frame is one that, if correct, would change the verdict or expose a significant risk not addressed by the default framing.
- Each alternative frame SHALL be assigned a stable FRAME-N ID. IDs are unique per run and are not reused.

20.4 Frame survival tracking:
- A material alternative frame MUST NOT be marked DROPPED unless ≥2 distinct models have cast explicit drop votes, each with traceable rebuttal references (argument IDs or evidence IDs).
- A single drop vote sets survival_status = CONTESTED. CONTESTED frames are not dropped.
- A drop vote without a traceable rebuttal reference does not count.
- Frame drop votes are recorded in divergence.alt_frames[].drop_vote_count. This counter does NOT feed into the main agreement_ratio.
- A frame with survival_status = ACTIVE or CONTESTED at synthesis MUST be explicitly addressed in the synthesis output: either adopted, rebutted with evidence, or flagged as unresolved.
- Silent disappearance of a material alternative frame from lineage → ERROR.

20.5 Cross-domain analogy tracking:
- Any material cross-domain analogy used to support a decisive claim SHALL be registered in divergence.cross_domain_analogies[] with source_domain, target_claim, transfer_mechanism, and test_status.
- An analogy with test_status = UNTESTED MUST NOT carry decisive factual load.
- Untested analogies MAY remain in discussion as non-decisive support.

20.6 Gate 2 interaction:
- DECIDE MUST NOT occur if divergence.required = true AND adversarial_slot_assigned = false.
- DECIDE MUST NOT occur if divergence.required = true AND framing_pass_executed = false.
- DECIDE MUST NOT occur if any material alternative frame remains ACTIVE or CONTESTED without rebuttal (see Section 2, rule 11).

---

## Section 16 Extension — Test and Verification Requirements

Add the following tests to the Section 16 table:

| Test | Requirement Verified |
|------|---------------------|
| CS Audit trivial brief short-circuit | S19: trivial + low-stakes → SHORT_CIRCUIT, fast_consensus_allowed=true |
| CS Audit high-stakes brief elevation | S19: high-stakes brief → ELEVATED effort, fast_consensus_allowed=false |
| CS Audit CRITICAL premise flag blocks DECIDE | S19+S2: unresolved CRITICAL flag → ESCALATE, not DECIDE |
| CS Audit missing output → ERROR | S19: missing required audit fields → ERROR |
| Fast consensus groupthink warning | S19: R1 unanimous + fast_consensus_allowed=false → groupthink_warning=true |
| Adversarial slot assigned and recorded | S20: non-trivial brief → adversarial_slot_assigned=true in proof.json |
| Single drop vote → CONTESTED not DROPPED | S20: one drop vote → survival_status=CONTESTED, DECIDE blocked |
| Two drop votes → DROPPED | S20: two traceable drop votes → survival_status=DROPPED |
| Missing adversarial slot → ERROR | S20: adversarial slot required but missing → ERROR |
| Untested analogy cannot carry decisive load | S20: UNTESTED analogy in decisive claim → ESCALATE |
| Frame drop votes do not affect agreement_ratio | S20+S2: verify drop_vote_count is isolated from agreement_ratio |

---

## Open Questions (for implementation review)

1. **SHORT_CIRCUIT path evidence requirements:** On a SHORT_CIRCUIT path, what is the minimum evidence standard? The current DoD (Section 7) says "a run using zero evidence → ESCALATE or NO_CONSENSUS, not DECIDE." Does SHORT_CIRCUIT DECIDE require at least one evidence item, or can it be pure model knowledge? Proposed resolution: allow zero evidence on SHORT_CIRCUIT path when question_class = WELL_ESTABLISHED_FACT and evidence is optional by Gate 1 recommendation (search: NO). Needs explicit carve-out in Section 7.

2. **CS Audit as LLM call — cost and topology:** The CS Audit is a second Sonnet call pre-R1. Does this need to be reflected in the config snapshot and cost estimate? Proposed: yes, add to BrainConfig as commonsense_model with default = Sonnet.

3. **When does "material alternative frame" require adversarial slot?** The DoD says adversarial slot is required on all non-SHORT_CIRCUIT paths, but what if the brief genuinely admits no credible alternative framing (e.g., pure factual analysis with no strategic ambiguity)? Proposed: adversarial slot is always required; the adversarial model may find no credible alternative, in which case it records assignment_type=PREMISE_CHALLENGER and alt_frames=[] with reasoning. The record of the attempt is what matters, not the production of an alternative.
