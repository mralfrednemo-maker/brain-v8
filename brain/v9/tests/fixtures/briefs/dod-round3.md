# Brain V8 DoD v3.0 — Definition of Done from Scratch
## Round 3: Write the DoD based on the agreed design

---

## GOAL

---

Brain V8 is a multi-model deliberation pipeline for OpenClaw (a team of AI agents). It removes the human operator as the decision bottleneck. The platform has been redesigned through two rounds of facilitation (Brain V8 + ChatGPT in Round 1, ChatGPT + Gemini in Round 2).

**This round writes the Definition of Done from scratch.** Not a patch on the old DoD. A clean sheet based on the agreed design below.

The DoD must be:
- **Complete**: every requirement the implementation must satisfy
- **Testable**: every section has at least one automated test
- **Unambiguous**: no room for interpretation on pass/fail
- **Zero-tolerance**: works fully or stops with ERROR

---

## THE AGREED DESIGN (Rounds 1+2 — locked decisions)

---

### 1. Platform Purpose

Brain V8 serves two use cases:
- **Decision**: Agent needs a decision to act on. Pipeline deliberates, converges or escalates.
- **Analysis**: Agent or human needs deep understanding. No decision required. Pipeline produces a structured multi-perspective map.

The platform must embody:
- Common sense like a human (calibrate effort, detect broken premises, reject trivially broken questions)
- Out-of-the-box thinking (alternative framings, adversarial positions, cross-domain analogies)
- Know what it doesn't know (detect insufficient context early, tell the requester what's missing)
- Zero tolerance on infrastructure (LLM/search unavailable = ERROR, full stop)

### 2. Outcome Taxonomy (nested by modality)

**DECIDE modality** (verdict-seeking):
- DECIDE — models converged, answer backed by complete proof trail
- ESCALATE — partial consensus or unresolved blockers, human review required
- NO_CONSENSUS — models fundamentally disagree after full deliberation, irreducible disagreement

**ANALYSIS modality** (map-seeking):
- ANALYSIS — structured multi-perspective map produced
- ANALYSIS substatus codes: FRAME_COLLAPSE, MAP_INSUFFICIENT, OPEN_WORLD_RESIDUAL, FRAGMENTED_EXPLANATION, CONTEXT_UNDERSPECIFIED_LATE

**Universal** (all paths):
- NEED_MORE — pre-admission rejection, returned before any run begins
- ERROR — infrastructure failure only (LLM unavailable, search unavailable). Not data integrity, not logic errors. Zero tolerance, full stop.

ESCALATE and NO_CONSENSUS exist only under DECIDE modality. They have no meaning in ANALYSIS context.

### 3. Pipeline Architecture

Single engine, shared front-end, modality-specific flow:

**Shared front-end:**
1. Gate 1 — Pre-admission (is the question answerable?)
2. Intent Classification — Dual-source (requester flag + pipeline audit). Pipeline has authority to override. Default to ANALYSIS on low confidence.
3. Assumption & Framing Audit (AFA) — Context sufficiency detection. Classifies gaps:
   - Type A (requester-fixable): block → NEED_MORE
   - Type B (unknown/unknowable): inject as explicit unknowns into R1
   - Type C (framing delusion): append reframing context to R1
4. Problem Definition Record (PDR) — Canonical normalized question shared by all downstream stages. Fields: problem_id, requested_modality, final_modality, question_type, decision_object or analysis_subject, time_horizon, stakeholders, constraints, evaluation_criteria, known_inputs, missing_inputs, forbidden_assumptions, allowed_reframings.
5. Post-AFA modality validation — Second check before modality lock. Auto-downgrade DECIDE→ANALYSIS if no well-formed decision object.

**DECIDE path:**
- R1 (4 models, independent) → Search → R2 (3 models, evidence debate) → R3 (2 models, narrowing) → R4 (2 models, closing) → Decision Gate 2 → Synthesis → proof.json

**ANALYSIS path:**
- R1 (4 models, frame generation) → Search by frame → R2 (4 models, frame development + evidence) → R3 (3 models, frame survival/kill) → R4 (2 models, compression audit) → Analysis Gate 2 → Synthesis → proof.json
- Graph Consolidation Step runs before Gate 2 (semantic deduplication of claim nodes)

### 4. Common Sense Audit (extended from v2.1)

Runs after Gate 1, before Intent Classification. Emits:
- Stakes classification (LOW / STANDARD / HIGH)
- Question classification (TRIVIAL / WELL_ESTABLISHED / OPEN / AMBIGUOUS / INVALID)
- Effort tier (SHORT_CIRCUIT / STANDARD / ELEVATED)
- Premise flags (INTERNAL_CONTRADICTION / UNSUPPORTED_ASSUMPTION / AMBIGUITY / IMPOSSIBLE_REQUEST / FRAMING_DEFECT)
- Groupthink detection (fast consensus + no evidence = warning)
- DIRECT_ANSWER fast-path for trivial questions
- Category-error detection

### 5. Assumption & Framing Audit (AFA) — new

Four components:
1. Context Graph — Extract required slots (object, actor, time_horizon, geography, decision_target, evaluation_metric, constraints, stakeholders). Each slot has materiality_to_answer score.
2. Assumption Ledger — For each missing/implicit slot: assumption_id, description, source, confidence, materiality.
3. Framing Tests — Four deterministic checks: category error, temporal mismatch, stakeholder omission, premise contradiction.
4. Usefulness Classifier — For each gap, classify as Type A (block), Type B (inject), or Type C (reframe). Only blocks when a missing item is both requester-suppliable AND material.

### 6. Out-of-the-Box Thinking

Merged design: Frame Registry (state) + Technique Injection (action).

**Frame Registry**: first-class tracked objects. Fields per frame: frame_id, parent_frame_id, originating_round, originating_technique, core_premise, decision_relevance, status (active/killed/merged), kill_reason, supporting_claim_ids, opposing_claim_ids, transfer_break_conditions.

**Technique policy per round:**
- R2: inversion / null-hypothesis reversal
- R3: constraint relaxation or constraint swap
- R4: domain transplant (as transfer hypothesis with break conditions)

**Rules:**
- At least one R1 model assigned adversarial/reframing role
- Every non-default frame must be registered
- Every killed frame must carry deterministic kill reason
- Every surviving frame must have evidence-backed claims
- Frame drop requires ≥2 model votes with traceable rebuttals
- Silent frame disappearance → ERROR

### 7. Gate 2 — Modality-specific

**Decision Gate 2** (deterministic, no LLM call):
1. Fatal integrity failure → ERROR
2. agreement_ratio < 0.50 → NO_CONSENSUS
3. agreement_ratio < 0.75 → ESCALATE
4. Unresolved critical argument or blocker → ESCALATE
5. Decisive claims lack evidence support → ESCALATE
6. Critical evidence contradictions unresolved → ESCALATE
7. Missing CSA on non-short-circuit path → ERROR
8. Missing adversarial slot or framing pass → ERROR
9. Unresolved CRITICAL premise flag → ESCALATE
10. Material alternative frame ACTIVE/CONTESTED without rebuttal → ESCALATE
11. fast_consensus_allowed=false AND fast unanimity AND no evidence → ESCALATE
12. Otherwise → DECIDE

**Analysis Gate 2** (deterministic, no LLM call):
1. Fatal integrity failure → ERROR
2. Structural completeness — required sections exist in output
3. Frame coverage — ≥2 distinct frames survived, OR exactly 1 frame survived with all alternatives explicitly killed
4. Traceability — every material claim points to evidence_ids or upstream claim_ids
5. Contradiction accounting — all material contradictions represented (resolved / bounded / high-impact)
6. Unknown honesty — high-impact unknowns surfaced, no claim depending on unknown presented as settled
7. Usefulness threshold — map answers at least one of: what is likely true / what is contested / what would discriminate / what input is missing
8. All checks pass → ANALYSIS (with appropriate substatus)
9. Fails usefulness due to requester-fixable missing context → NEED_MORE
10. Infrastructure failure → ERROR

### 8. proof.json — Claim-level directed graph

Evolved from flat structure to claim-level graph for Chamber integration.

Each claim node: {id, modality, technique_used, depends_on: [claim_ids, evidence_ids], round_origin, model_origin}

Graph Consolidation Step (before Gate 2): semantic deduplication of equivalent claim nodes, merging depends_on edges, preserving model lineage.

Backward-compatible summary field preserved during transition to claim-level governance.

ANALYSIS-specific payload: frame_registry, claims, open_questions, missing_context, confidence_by_frame, analysis_substatus.

DECIDE-specific payload: outcome_rationale, agreement_ratio, decisive_claims with evidence bindings, blocker resolutions.

### 9. Intent Misclassification Recovery

Two-check modality lock:
- Checkpoint 1: Pre-run (requester flag + pipeline audit)
- Checkpoint 2: Post-AFA (is there a decision object? are there eval criteria?)

Recovery rules:
- DECIDE without well-formed decision object → auto-downgrade to ANALYSIS
- ANALYSIS with clean decision object + criteria → may auto-upgrade to DECIDE (before lock only)
- After lock, no switching

Payload always includes: requested_modality, inferred_modality, final_modality, override_reason, confidence, replay_recommendation (ready_for_decide, missing_decision_fields).

### 10. Zero Tolerance

- LLM unavailable → ERROR
- Search unavailable (when search is required) → ERROR
- Any invited model fails to respond → ERROR
- Timeout expiry → ERROR
- No degraded mode. No partial results. No silent continuation.
- ERROR = infrastructure only. Not data integrity, not logic errors.

---

## TASK

---

**Write the Definition of Done v3.0 from scratch.** Use the design above as the requirements. The DoD must define what "done" means for an implementation of this design.

For each section of the DoD:
1. State the requirement clearly and unambiguously
2. Define pass/fail criteria
3. List at least one automated test that verifies the requirement
4. Identify any open question that the DoD cannot resolve (flag these explicitly)

Organize the DoD into numbered sections. Cover at minimum:
- Outcome contract (taxonomy, substatus codes, terminal_reason_codes)
- Pipeline gates (Gate 1, CSA, AFA, Intent Classification, PDR, Decision Gate 2, Analysis Gate 2)
- Minimum viable deliberation (topology, quorum, model independence)
- Evidence acquisition and traceability
- Argument and frame lineage
- proof.json contract (claim graph, modality-specific payloads)
- Fatal error semantics
- Checkpoint and resume
- Reproducibility
- Determinism policy
- Test requirements
- Deferred scope (Chamber, Mission Controller)

Do NOT include implementation details (code, class names, method signatures). The DoD defines WHAT, not HOW.

---

This is a CLOSED REVIEW. Do not search the web. All context needed is in this brief.
