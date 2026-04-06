# Brain V8 DoD Revision — Phase A Facilitation Brief

**Date:** 2026-04-01
**Purpose:** Revise the Brain V8 Definition of Done to incorporate four new platform requirements.
**Instruction:** This is a CLOSED REVIEW. Do not search the web. All context is in this brief.

---

## GOAL

Brain V8 is a multi-model deliberation platform that removes a human operator (Christos) as a decision bottleneck for a team of AI agents (OpenClaw). The platform receives questions from agents and produces credible, auditable outcomes.

**The goal is being expanded.** The platform must now serve two use cases:

1. **Decision use case** — Agent needs a decision to act on. Pipeline deliberates, converges or escalates. Same as before.
2. **Analysis use case** — Agent or human needs to understand a topic deeply. No decision required. The platform must produce a structured, multi-model analysis without forcing a DECIDE/ESCALATE frame onto a question that doesn't require one.

Additionally, the platform must embody four design principles that must be reflected explicitly in the DoD:

1. **Common sense like a human** — The pipeline must reason the way a smart human would: calibrate effort to the actual difficulty of the question, reject trivial questions without burning full deliberation resources, and detect when a question is fundamentally broken before starting.
2. **Out-of-the-box thinking** — The pipeline must generate and test alternative framings and adversarial positions, not just converge on the obvious answer.
3. **Know what it doesn't know** — The pipeline must be able to tell the requester clearly and early what context is missing or insufficient, rather than running to completion on a broken question.
4. **Zero tolerance on infrastructure failures** — LLM unavailable or search unavailable = ERROR and stop. No degraded mode, no partial results, no silent continuation. This applies universally.

---

## TASK

Review the current DoD (provided in the CONTENT section below) and answer the following questions. For each question, give a specific, actionable recommendation — not a general observation.

1. **ANALYSIS outcome**: The platform now needs a fifth top-level outcome: ANALYSIS. This is for queries where the requester seeks understanding, not a decision. How should ANALYSIS be defined in the outcome contract (Section 1)? What are its Gate 2 rules — what conditions produce ANALYSIS vs DECIDE vs ESCALATE? What must proof.json contain on an ANALYSIS path?

2. **NO_CONSENSUS**: With ANALYSIS added, does NO_CONSENSUS still make sense as a separate outcome? Or should it be merged into ESCALATE (human review needed) or absorbed differently? What is the right outcome taxonomy for the new dual-purpose platform?

3. **ACCEPTED_WITH_WARNINGS**: The current DoD (Section 1) defines this as a subordinate internal annotation that must never appear as a top-level outcome. Given that the system is zero-tolerance, ERROR is only for LLM/search infrastructure failures, and no code path currently produces this status, should ACCEPTED_WITH_WARNINGS be removed from the DoD entirely? What is the risk of keeping vs removing it?

4. **Gate 1 and context sufficiency**: The current Gate 1 (Section 5) handles pre-run admission and NEED_MORE. Is this sufficient for the "know what it doesn't know" requirement? What specific changes, if any, are needed to make Gate 1 robustly enforce context sufficiency — not just for vague briefs, but for briefs that appear specific but are missing critical unstated assumptions?

5. **Common Sense Audit (Section 19 in v2.1 patch)**: This section already addresses effort calibration and premise validation. Does it fully satisfy the "common sense like a human" requirement? What is missing or needs strengthening?

6. **ANALYSIS path and evidence requirements**: Section 7 says "a run using zero evidence → ESCALATE or NO_CONSENSUS, not DECIDE." On an ANALYSIS path, should the same evidence requirements apply? Or does analysis allow for model-knowledge synthesis without external evidence?

7. **Infrastructure zero tolerance**: The zero-tolerance policy is distributed across Sections 3, 6, and 10. Should there be a dedicated, single-location "Infrastructure Failure Policy" section that explicitly states: LLM unavailability = ERROR, search unavailability = ERROR, no degraded mode, no partial results? Or is the current distribution sufficient?

8. **Overall DoD gaps**: Looking at the full current DoD, what is the single most important gap that the new goal (dual-purpose: decisions + analysis) exposes? What is the minimum change needed to address it?

---

## CONTENT

### Document 1 — Original Architecture Design Spec

```
# The Thinker V8 — Architecture Design Spec

Date: 2026-03-26
Status: Approved through brainstorming

## 1. The Problem
Christos runs a team of AI agents (OpenClaw). Every decision flows through him — he is the bottleneck.
He needs a brain that can take decisions independently when confident, and escalate to him when it can't.
The Thinker is that brain: a credible, logical decision maker.

## 2. The Contract
The Thinker receives a question from any agent. It produces one of three outcomes:
- DECIDE: Models converged, evidence supports it, dissent addressed → Answer + proof. Agent can act.
- ESCALATE: Models disagree, evidence weak, or confidence low → Full picture sent to Christos. Human decides.
- NEED MORE: Question too vague or key data missing after search → Specific questions sent back to the requesting agent.

## 3. The 5 Requirements
R0: Enough context to reason about
R1: Multiple independent opinions
R2: Grounded in evidence
R3: Honest about disagreement
R4: Knows when it can't decide

## 4. Architecture Flow
Gate 1 → R1 (4 models, independent) → Search Phase → R2-R4 (debate with evidence) → Gate 2 → Synthesis

Gate 2 is LLM judgment backed by mechanical tool data. Tools provide DATA. LLM provides JUDGMENT.

## 5. Engine Strategy
Phase 1: Brain only. Get Brain stable, all trust mechanisms working.
Phase 2: Chamber plugs in. Chamber adds adversarial governance for recommendation-type questions.

## 10. Design Principles
1. Never assume. If context is missing, ask the requester.
2. Fail cheap. Gate 1 catches garbage before we spend $2 and 15 minutes.
3. Fail honest. Gate 2 catches weak answers after deliberation. Escalate, don't fake it.
4. Use the toolbox.
5. Test with mocks.
6. Models drive the search.
7. Full page content.
8. One engine first.
```

---

### Document 2 — Current DoD v2.0

```
# Brain V8 — Definition of Done v2.0

Date: 2026-03-31
Philosophy: Zero tolerance. Works fully or stops with ERROR. No partial results, no degraded mode, no silent failures.

## Section 1 — Authoritative Outcome Contract

The only valid top-level business outcomes produced by Brain V8 are:

| Outcome     | Meaning                                                               |
|-------------|-----------------------------------------------------------------------|
| DECIDE      | Models converged. Answer is backed by a complete proof trail.         |
| ESCALATE    | Partial consensus or unresolved blockers. Human review required.      |
| NO_CONSENSUS| Models fundamentally disagree. Cannot be resolved automatically.      |
| ERROR       | Pipeline failure. No business result was produced or emitted.         |

Requirements:
- No other top-level outcome state may exist or be emitted.
- ACCEPTED_WITH_WARNINGS is a subordinate internal annotation only. It must be explicitly mapped to one of the four outcomes above and must never appear as a top-level result.
- Gate 1's NEED_MORE is a pre-deliberation admission result returned to the caller before a Brain V8 run begins. It is not a top-level Brain V8 outcome.
- Any system that emits any other top-level state fails this DoD.

## Section 2 — Outcome Decision Rules (Gate 2, strict order)

1. Fatal integrity failure detected → ERROR
2. agreement_ratio < 0.50 → NO_CONSENSUS
3. agreement_ratio < 0.75 → ESCALATE
4. Any unresolved critical argument or blocker → ESCALATE
5. Decisive claims lack required evidence support → ESCALATE
6. Critical evidence contradictions unresolved → ESCALATE
7. Otherwise → DECIDE

Requirements:
- All thresholds (0.50, 0.75) are configurable in BrainConfig.
- Gate 2 must be fully deterministic: no LLM call.
- Fatal integrity failures (rule 1) must produce ERROR, not ESCALATE.

## Section 3 — Minimum Viable Deliberation

- Minimum models invited: R1=4, R2=3, R3=2, R4=2.
- Any invited model fails to respond → ERROR (zero tolerance, no partial rounds).
- DECIDE cannot be produced unless at least 3 independent model responses are present in the decisive round.
- Models must be from at least 2 different provider APIs.
- Quorum failure = ERROR.

## Section 5 — Pipeline Gates

| Gate   | Type          | Purpose                            | Pass Condition                                          | Fail Action                     |
|--------|---------------|------------------------------------|---------------------------------------------------------|---------------------------------|
| Gate 1 | LLM (Sonnet)  | Pre-run admission + search decision| Brief is specific, has context, has clear deliverable   | NEED_MORE pre-run rejection     |
| Gate 2 | Deterministic | Outcome classification             | See Section 2 rules                                     | Outcome classified per Section 2|

- Gate 1 also outputs a search recommendation (YES/NO) with reasoning.
- Gate 1 unparseable LLM response → fail-closed.

## Section 6 — Evidence Acquisition

- Search is mandatory when Gate 1 recommends it and brief contains factual claims.
- One primary search provider per run. Provider failure = ERROR (no silent fallback).
- Contradictory evidence must be flagged and retained, not silently discarded.

## Section 7 — Claim-Level Evidence Traceability

- Each decisive claim in a DECIDE output must reference at least one specific evidence ID.
- Evidence IDs must be stable and unique across the full run. IDs may not be reused after eviction.
- A run using zero evidence → ESCALATE or NO_CONSENSUS, not DECIDE.

## Section 8 — Argument, Position, and Objection Lineage

- All arguments tracked with round-prefixed IDs (R1-ARG-N). Stable across full run.
- No argument may disappear without an explicit lineage status.
- Every argument from round N must be classified in round N+1 as: ADDRESSED / MENTIONED / IGNORED.

## Section 9 — Proof Artifact Contract

proof.json is complete if and only if it contains:
- run_id, timestamp, protocol_version, proof_schema_version
- brief (full text), model identities and exact version strings
- Gate 1: pass/fail, reasoning, search recommendation, search_decision
- Gate 2: outcome, thresholds, agreement_ratio, ignored_arguments count
- Per round: models invited/responded/failed, all arguments with IDs and classifications, all positions per model
- Evidence ledger: all items with URL, source domain, fetch timestamp, extracted fact, score
- Claim-to-evidence bindings for all decisive claims
- Final outcome and outcome rationale
- Config snapshot: thresholds, topology, model IDs, search provider
- Input fingerprint: hash(brief + config + topology + model_ids + provider)
- On ERROR path: proof.json must still be written with ERROR status, stage of failure, error message, last successful stage.

## Section 10 — Fatal Error Semantics

- Any failure in any pipeline stage → BrainError → pipeline stops → ERROR outcome.
- No degraded mode. No partial results. No silent continuation.
- No business result may be emitted from a failed run.

## Section 11 — Checkpoint and Resume Integrity

- Checkpointing permitted only at clean round boundaries.
- On resume: schema version must match. Mismatch → ERROR.
- Prior accepted state must not be recomputed differently on resume.

## Section 13 — Credibility Requirements

- No unsupported decisive claim in DECIDE output.
- All unresolved conflicts between models must be disclosed in synthesis report.
- Gate 2 cannot produce DECIDE if critical evidence contradictions are unresolved.

## Section 14 — Determinism Policy for Gates

- Gate 2 must be fully deterministic. Same proof state always produces same outcome.
- Gate 1 uses LLM (acceptable), but output must be parsed deterministically.
- No gate may introduce unrecorded randomness.

## Section 15 — Contradiction Handling Policy

- Contradiction detection must be tested against labeled corpus: Precision ≥ 0.90, Recall ≥ 0.75.
- Detected contradiction recorded with stable ID (CTR-N). Counter does not reset between stages.
- Contradiction types: Factual / Recommendation / Confidence-only (last is NOT a contradiction).

## Zero-Tolerance and Timeout Policy

- Any failure in any pipeline stage → BrainError → ERROR.
- Thinking models (R1, Reasoner): 720s hard timeout, 30,000 max_tokens.
- Non-thinking models (GLM-5, Kimi): 480s hard timeout, 16,000 max_tokens.
- Sonnet (Gate 1, argument tracking, synthesis): 120s hard timeout, 16,000 max_tokens.
- Timeout expiry is a failure → BrainError → ERROR.
```

---

### Document 3 — DoD v2.1 Patch (Common Sense and Out-of-the-Box Thinking)

```
# Brain V8 — DoD v2.1 Patch

Date: 2026-03-31
Adds to: V8-DOD-v2.md

## Section 1 Extension — Authoritative Outcome Contract

SHORT_CIRCUIT is not a separate top-level outcome. When the Common Sense Audit determines that a
question is trivially settled (question_class = TRIVIAL or WELL_ESTABLISHED, stakes_class = LOW,
no CRITICAL premise flags), the pipeline MAY short-circuit to DECIDE via an abbreviated path.
The outcome emitted is DECIDE with commonsense.short_circuit_taken = true. No new outcome code is introduced.

## Section 2 Extension — Updated Gate 2 Outcome Decision Rules

New rules added (between existing rule 6 and final DECIDE):

8. Missing Common Sense Audit on any non-short-circuit path → ERROR (fatal)
9. Missing adversarial slot or Divergent Framing Pass on any required path → ERROR (fatal)
10. Any unresolved CRITICAL premise flag → ESCALATE
11. Any material alternative frame remains ACTIVE or CONTESTED without explicit rebuttal → ESCALATE
12. fast_consensus_allowed=false AND fast unanimity observed AND no independent evidence → ESCALATE
13. Otherwise → DECIDE

## Section 5 Extension — CS Audit Gate

| Gate    | Type         | Purpose                             | Pass Condition          | Fail Action                |
|---------|--------------|-------------------------------------|-------------------------|----------------------------|
| CS Audit| LLM (Sonnet) | Effort calibration + premise validation | All required fields emitted | Missing outputs → ERROR |

- CS Audit executes exactly once, after Gate 1 PASS and before any R1 model is invoked.
- CS Audit MUST NOT be skipped on any non-Gate1-rejected path.
- CS Audit MUST emit all required outputs or the run produces ERROR.

## New Section 19 — Common Sense Audit

Purpose: Calibrate pipeline behavior to the actual nature of the question before deliberation begins.

19.1 Execute CS Audit after Gate 1 PASS and before R1.
19.2 CS Audit must emit all required fields. Missing or malformed → ERROR.
19.3 Stakes classification: LOW / STANDARD / HIGH
19.4 Question classification: TRIVIAL / WELL_ESTABLISHED / OPEN / AMBIGUOUS / INVALID
19.5 Effort tier:
     - SHORT_CIRCUIT: only when question_class ∈ {TRIVIAL, WELL_ESTABLISHED} AND stakes_class=LOW AND no CRITICAL flags
     - ELEVATED: when stakes_class=HIGH OR question_class ∈ {AMBIGUOUS, INVALID} OR any CRITICAL flag
19.6 Groupthink detection: fast unanimity without evidence AND fast_consensus_allowed=false → groupthink_warning=true
19.7 Premise validation: check for internal contradictions, unsupported assumptions, ambiguity, impossible requests
19.8 question_class=INVALID AND not repairable → ERROR (not NEED_MORE)

## New Section 20 — Out-of-the-Box Thinking / Divergent Framing

Purpose: Ensure the pipeline generates and tests credible non-default frames and adversarial positions.

Applicability: All non-SHORT_CIRCUIT paths.

20.1 Adversarial slot: at least one R1 model assigned explicit adversarial/reframing role.
     Assignment type: CONTRARIAN / REFRAMER / PREMISE_CHALLENGER / CROSS_DOMAIN.
     Adversarial positions must be credible. Must NOT invent implausible disagreement.
20.3 Divergent Framing Pass: after R1, before R2. Extract and register all material alternative frames.
     Material frame = one that, if correct, would change the verdict or expose significant risk.
20.4 Frame survival: MUST NOT be marked DROPPED unless ≥2 distinct models cast drop votes with traceable refs.
     Single drop vote → CONTESTED (not dropped).
     Silent disappearance of material alternative frame → ERROR.
20.5 Cross-domain analogy tracking: UNTESTED analogy MUST NOT carry decisive factual load.
20.6 Gate 2 interaction:
     DECIDE blocked if adversarial_slot_assigned=false (when required).
     DECIDE blocked if framing_pass_executed=false (when required).
     DECIDE blocked if any material frame ACTIVE or CONTESTED without rebuttal.
```

---

*End of brief. No web search is needed or permitted for this task.*
