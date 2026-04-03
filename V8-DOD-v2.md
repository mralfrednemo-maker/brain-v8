# Brain V8 — Definition of Done v2.0

**Date:** 2026-03-31
**Scope:** Brain engine only. Chamber and Mission Controller are explicitly deferred (Section 17).
**Status:** Agreed by Brain V8 deliberation + ChatGPT review
**Philosophy:** Zero tolerance. Works fully or stops with ERROR. No partial results, no degraded mode, no silent failures.

---

## Section 1 — Authoritative Outcome Contract

The only valid top-level business outcomes produced by Brain V8 are:

| Outcome | Meaning |
|---------|---------|
| DECIDE | Models converged. Answer is backed by a complete proof trail. |
| ESCALATE | Partial consensus or unresolved blockers. Human review required. |
| NO_CONSENSUS | Models fundamentally disagree. Cannot be resolved automatically. |
| ERROR | Pipeline failure. No business result was produced or emitted. |

**Requirements:**
- No other top-level outcome state may exist or be emitted.
- `ACCEPTED_WITH_WARNINGS` is a subordinate internal annotation only. It must be explicitly mapped to one of the four outcomes above and must never appear as a top-level result.
- Gate 1's `NEED_MORE` is a **pre-deliberation admission result** returned to the caller before a Brain V8 run begins. It is not a top-level Brain V8 outcome.
- Any system that emits any other top-level state fails this DoD.

---

## Section 2 — Outcome Decision Rules

Gate 2 must determine the outcome deterministically using the following rules in strict order:

1. **Fatal integrity failure detected** → ERROR
   *(corrupted evidence references, orphaned decisive claims, broken proof linkage, invalid round lineage, unrecoverable BrainError)*
2. **agreement_ratio < 0.50** → NO_CONSENSUS
3. **agreement_ratio < 0.75** → ESCALATE
4. **Any unresolved critical argument or blocker** → ESCALATE
5. **Decisive claims lack required evidence support** → ESCALATE
6. **Critical evidence contradictions unresolved** → ESCALATE
7. **Otherwise** → DECIDE

**Requirements:**
- All thresholds (0.50, 0.75) are configurable in `BrainConfig` with documented defaults. Allowed override ranges must be defined. Threshold overrides must be recorded in the proof artifact.
- Gate 2 must be **fully deterministic**: no LLM call. Same proof state always produces the same outcome.
- `ignored_arguments` count alone is not sufficient to classify outcome. Arguments must be classified as critical or non-critical. Only unresolved critical arguments gate DECIDE.
- Fatal integrity failures (rule 1) must produce ERROR, not ESCALATE.

---

## Section 3 — Minimum Viable Deliberation

**Requirements:**
- Minimum models invited: R1 = 4, R2 = 3, R3 = 2, R4 = 2. Topology narrowing is explicit and permitted.
- The invited set for each round is fixed before the round starts. Narrowing is a deliberate controller action, not silent dropout.
- **Any invited model fails to respond → ERROR** (zero tolerance, no partial rounds).
- Minimum valid responses required for a round to count: **2 independent models**.
- **DECIDE cannot be produced** unless at least **3 independent model responses** are present in the decisive round (R4 by default).
- Models must be from **at least 2 different provider APIs** to satisfy the independence requirement.
- Models must be distinct named models. No duplicate aliases of the same underlying model family.
- **Quorum failure = ERROR.** No partial round is eligible for a business outcome.

---

## Section 4 — Model Independence and Isolation

**Requirements:**
- Each model's response in a round must be a **separate, isolated inference call**.
- No model may see another model's response within the same round.
- Prior-round views may only be re-injected via the **defined round prompt mechanism**.
- No hidden shared scratchpad, shared synthesis buffer, or untracked controller-written interpretation of one model's position may be injected into another model outside the defined mechanism.
- Each model's position must be recorded individually per round with its source model identity.
- Response attribution must be preserved through the full proof trail.

---

## Section 5 — Pipeline Gates

All core pipeline gates must be documented in this DoD. Gate additions require a DoD update before implementation.

| Gate | Type | Purpose | Pass Condition | Fail Action |
|------|------|---------|---------------|-------------|
| Gate 1 | LLM (Sonnet) | Pre-run admission + search decision | Brief is specific, contains sufficient context, has clear deliverable | NEED_MORE pre-run rejection to caller |
| Gate 2 | Deterministic | Outcome classification | See Section 2 rules | Outcome classified per Section 2 |

**Requirements:**
- Gate 1 is a **pre-deliberation admission gate**. If it fails, no Brain V8 run begins. NEED_MORE is not a top-level Brain V8 outcome.
- Gate 1 must also output a **search recommendation** (YES/NO) with one-sentence reasoning. This recommendation drives the search decision unless overridden (see Section 6).
- Gate 1 pass/fail criteria: brief must have a specific question, identified scope, and clear deliverable. Vague, contradictory, or missing-context briefs fail.
- Gate 1 **unparseable LLM response → fail-closed**: produce a controlled pre-run rejection, do not silently proceed.
- Any gate failure must be recorded in the proof artifact.

---

## Section 6 — Evidence Acquisition and Source Policy

**Requirements:**
- **Search is mandatory** when Gate 1 recommends it and the brief contains factual claims, regulatory references, statistics, or current-information dependencies.
- **Search is optional** for pure reasoning/strategy/design briefs with no external factual claims (Gate 1 decides, recorded in proof).
- CLI override (`--search` / `--no-search`) is permitted **only when recorded** in proof with source, actor, and reason. Override cannot enable DECIDE where evidence/search requirements are otherwise unmet.
- **One primary search provider per run.** Provider is fixed at run start. Mid-run switching is forbidden. Provider failure = ERROR (no silent fallback).
- Each search result must record: URL, title, fetch timestamp, source domain.
- **Admissible sources**: publicly reachable web pages. Login-walled, broken, or inaccessible pages are not admissible evidence sources.
- Full page content must be fetched (not snippet only) for evidence extraction.
- LLM-based extraction must produce **structured fact units** linked to a source URL and, where possible, a quoted span or text anchor.
- **Evidence definition:** a specific fact, number, date, or regulatory reference extracted from an admissible web source at fetch time. Unverifiable assertions are not evidence.
- Contradictory evidence must be **flagged and retained**, not silently discarded.

---

## Section 7 — Claim-Level Evidence Traceability

**Requirements:**
- Each **decisive claim** in a DECIDE output must reference at least one specific evidence ID.
- Evidence IDs must be **stable and unique** across the full run. IDs may not be reused after eviction.
- The proof artifact must contain an **explicit claim-to-evidence mapping** for all decisive claims, including source URL provenance chain.
- An untraceable decisive claim must be marked as **model-opinion**. Model-opinion claims may not carry decisive factual load in a DECIDE outcome.
- If a decisive conclusion depends on an untraceable claim, **DECIDE is disallowed**.
- A claim tied to a contradicted evidence item is not verified. DECIDE requires that contradictions on decisive evidence are either resolved or explicitly disclosed and non-decisive.
- **A run using zero evidence → ESCALATE or NO_CONSENSUS, not DECIDE.**

---

## Section 8 — Argument, Position, and Objection Lineage

**Requirements:**
- All arguments extracted from each round must be tracked with **round-prefixed IDs** (R1-ARG-N). IDs are stable across the full run.
- **No argument may disappear without an explicit lineage status.** Arguments may be merged or superseded by synthesis, but only with recorded lineage.
- Every argument from round N must be classified in round N+1 (or at synthesis) as: ADDRESSED / MENTIONED / IGNORED.
- Arguments are classified as **critical** or **non-critical**. Only unresolved critical arguments affect Gate 2 (see Section 2, rule 4).
- Any argument marked as a **critical blocker (BLK-N)** must record: origin round, reason for blocker status, resolution evidence or reasoning. Unresolved critical blockers prevent DECIDE.
- Per-model, per-round positions must be extracted, tracked, and preserved in the proof artifact.
- Position changes across rounds must be recorded.

---

## Section 9 — Proof Artifact Contract

`proof.json` is **complete** if and only if it contains all of the following:

- `run_id`, `timestamp`, `protocol_version`, `proof_schema_version`
- `brief` (full text)
- Model identities and **exact version strings** for every model used
- Gate 1: pass/fail, reasoning, search recommendation, search_decision (source/value/reasoning)
- Gate 2: outcome, thresholds used, agreement_ratio, ignored_arguments count
- Per round: models invited, models responded, models failed
- Per round: all arguments extracted with IDs and classifications
- Per round: all positions extracted per model
- Evidence ledger: all evidence items with URL, source domain, fetch timestamp, extracted fact, score, source provenance chain
- Claim-to-evidence bindings for all decisive claims
- Final outcome (DECIDE / ESCALATE / NO_CONSENSUS / ERROR) and outcome rationale
- Invariant violations and severities
- Synthesis residue omissions (if any)
- Config snapshot: thresholds, topology, model IDs, search provider
- Input fingerprint: `hash(brief + config + topology + model_ids + provider)` — **distinct from run_id**

**On ERROR path:** `proof.json` must still be written and must contain: ERROR status, stage of failure, error message, last successful stage, full config snapshot, and an explicit statement that no business result was produced.

---

## Section 10 — Fatal Error Semantics and Failure Artifact

**Requirements:**
- Any failure in any pipeline stage → BrainError → pipeline stops → ERROR outcome.
- **No degraded mode. No partial results. No silent continuation.**
- No business result (DECIDE, ESCALATE, NO_CONSENSUS) may be emitted from a failed run.
- A **machine-readable failure artifact** (proof.json ERROR path, Section 9) must be produced on all ERRORs.
- Operator-aborted runs and pre-run Gate 1 rejections are distinct from ERROR and must be recorded accordingly.

---

## Section 11 — Checkpoint and Resume Integrity

**Requirements:**
- Checkpointing is permitted **only at clean round boundaries**.
- On resume: schema version must match. **Mismatch → ERROR. Do not resume.**
- Resume must restore **all accumulated state**: arguments (with classifications), positions, evidence ledger (including scores and confidence), search decisions, unaddressed arguments, contradiction counter, current round pointer, pending invited model set, and all deterministic counters affecting Gate 2.
- Prior accepted state must not be recomputed differently on resume unless fully replaying from the original inputs.
- **Resume equivalence** is defined as: same authoritative outcome, same gate decisions, same deliberation topology, same preserved lineage and evidence state, no missing proof fields, no state corruption.
- **Checkpoints may not produce a partial business result.** A resumed run must reach a terminal outcome (DECIDE / ESCALATE / NO_CONSENSUS / ERROR).

---

## Section 12 — Reproducibility and Replayability

**Requirements:**
- Every `proof.json` must contain an **input fingerprint**: `hash(brief + config + topology + model_ids + provider)`. This is separate from `run_id` (which is unique per execution).
- Every `proof.json` must contain a complete **config snapshot** sufficient to replay the pipeline logic: model IDs (exact version strings), topology, thresholds, search provider, and brief.
- Raw LLM responses and fetched web content must be **captured and linked** from the proof artifact (may live in linked artifacts rather than embedded in core `proof.json`).
- Two runs with identical brief and config must produce proof artifacts that differ **only in**: LLM response text, web content, fetch timestamps, evidence scores, and run instance IDs. Pipeline logic, gate decisions, and outcome classification must be identical given the same inputs.
- Allowed variability between identical-input runs must be **explicitly enumerated** in this DoD.

**Explicitly allowed variability between identical-input runs:**
- LLM response text (non-deterministic model output)
- Web page content (live fetch)
- Fetch timestamps
- Evidence scores derived from content
- `run_id`, `timestamp`

---

## Section 13 — Credibility Requirements

"Credible" is defined operationally as:

**Requirements:**
- No unsupported decisive claim in DECIDE output. All decisive claims must be backed by evidence or explicitly marked as model-opinion with model-opinion claims excluded from decisive factual load.
- All unresolved conflicts between models must be **disclosed** in the synthesis report.
- Evidence defects (unreachable source, contradicted claim, failed fetch) must be **recorded** in `proof.json`. Defects are classified as:
  - **Disclosable:** recorded in proof, does not block outcome
  - **Escalating:** forces ESCALATE
  - **Fatal:** forces ERROR
- Gate 2 cannot produce DECIDE if critical evidence contradictions are unresolved.
- **No hidden heuristic overrides.** All scoring and threshold decisions must be recorded in proof.
- DECIDE requires contributions from the minimum quorum defined in Section 3 (at least 3 independent model responses in the decisive round).

---

## Section 14 — Determinism Policy for Gates

**Requirements:**
- Gate 2 must be **fully deterministic**: given the same proof state, it must always produce the same outcome.
- All Gate 2 thresholds must be in `BrainConfig`, not hardcoded. DoD defines required defaults. Allowed override ranges must be documented. Threshold overrides must be recorded in proof.
- Gate 1 uses an LLM (acceptable), but its output must be **parsed deterministically**. Unparseable Gate 1 response → **fail-closed**: produce a pre-run rejection, do not silently proceed.
- No gate may introduce **unrecorded randomness**.

---

## Section 15 — Contradiction Handling Policy

**Requirements:**
- Contradiction detection must be tested against a **labeled corpus** with:
  - Precision ≥ 0.90 at the defined keyword/semantic threshold
  - Recall ≥ 0.75, or a documented and justified precision-first bias with explicit trade-off statement
- "No false positives" is not an acceptable DoD criterion and must not appear.
- A detected contradiction must be recorded with a **stable ID** (CTR-N). IDs are unique and monotonic per run. The contradiction counter must not be reset between pipeline stages.
- Contradiction scope must be defined. The system distinguishes:
  - **Factual contradiction**: conflicting facts from evidence or model claims
  - **Recommendation contradiction**: conflicting conclusions or proposals
  - **Confidence-only disagreement**: same conclusion, different confidence — not a contradiction
- How contradictions feed Gate 2 must be explicit:
  - Factual contradictions on decisive claims → contribute to ESCALATE gate (Section 2, rule 6)
  - Recommendation contradictions → contribute to agreement_ratio calculation
  - Unresolved factual contradictions → may create blockers (BLK-N)

---

## Section 16 — Test and Verification Requirements

Every section of this DoD must have at least one automated test that verifies the **requirement**, not just the implementation. Required tests:

| Test | Requirement Verified |
|------|---------------------|
| Proof schema validation | S9: proof.json complete on any run |
| Gate 1 outcome on labeled briefs | S5: pass/fail criteria |
| Gate 2 determinism | S14: same proof state = same outcome |
| All 4 outcomes producible | S1: DECIDE, ESCALATE, NO_CONSENSUS, ERROR each tested |
| Quorum failure → ERROR | S3: any invited model failure stops pipeline |
| Decisive-round quorum enforced | S3: DECIDE requires ≥3 model responses |
| Resume equivalence | S11: resumed run = same outcome as uninterrupted |
| Evidence traceability | S7: DECIDE with no evidence IDs fails validation |
| Unauthorized state detection | S1: non-approved top-level states fail |
| Critical evidence contradiction blocks DECIDE | S13: unresolved contradiction → ESCALATE |
| Model-opinion cannot carry decisive load | S13: untraceable decisive claim → DECIDE blocked |
| Gate 1 fail-closed | S14: unparseable LLM response → pre-run rejection, not proceed |
| Contradiction ID monotonicity | S15: CTR-N stable and non-resetting |

---

## Section 17 — Out of Scope (Deferred to Chamber / Mission Controller)

The following requirements are explicitly deferred and do not weaken Brain V8's core guarantees:

| Item | Description | Why Deferred | Brain V8 Impact |
|------|-------------|-------------|-----------------|
| D5 | Controller/synthesis mismatch detection | No Mission Controller exists yet | Brain's own synthesis is internally consistent by Section 8/9 |
| D6 | Mission Controller inspects Brain invariants | No Mission Controller exists yet | Brain's own invariant validator (Section 15 equivalent) covers this internally |
| D8 | Chamber proof artifact format | Chamber not built yet | Brain produces `proof.json` per Section 9; Chamber format is additive |
| P1 | Mission Controller test coverage | Not built yet | Does not affect Brain V8 pipeline testing |
| P4 | Chamber search parity | Chamber not built yet | Brain's search policy is defined in Section 6 |

---

## Section 18 — Release Evidence Appendix

*(Not part of the release contract — implementation reference only)*

This appendix documents what was built. It does not define what "done" means. The items below are evidence of implementation, not acceptance criteria.

- Test counts and coverage by module
- Known limitations and deferred bugs
- Resolved bug list (V8-B1 through V8-B4)
- Implementation notes for each feature (V8-F1 through V8-F6)
- Session history and change log
- All "DONE this session" items from the prior DoD v1.0

---

## Zero-Tolerance and Timeout Policy

*(Applies across all sections)*

**Requirements:**
- Any failure in any pipeline stage → BrainError → ERROR (see Section 10).
- All model calls must have **explicit, generous-but-bounded timeouts**:
  - Thinking models (R1, Reasoner): **720s hard timeout**
  - Non-thinking models (GLM-5, Kimi): **480s hard timeout**
  - Sonnet (Gate 1, argument tracking, synthesis): **120s hard timeout**
- Timeout expiry is a failure → BrainError → ERROR.
- "No wall clock limits" is not permitted. Generous but bounded is the rule.
- Token limits serve as **quality floors, not budget caps**:
  - Thinking models: 30,000 max_tokens
  - Non-thinking models: 16,000 max_tokens
  - Sonnet: 16,000 max_tokens
- These values are the required defaults. They may be configurable in `BrainConfig` but may not be reduced below the stated defaults without a DoD update.
