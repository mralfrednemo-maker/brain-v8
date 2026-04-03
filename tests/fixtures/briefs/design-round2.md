# Design Facilitation Brief — Thinker Platform Expansion
## Round 2: Stress-Test and Refine the Design

---

## GOAL

---

Brain V8 is a multi-model deliberation pipeline built for OpenClaw (a team of AI agents). It removes the human operator as the decision bottleneck. It takes questions from agents, runs them through multiple LLM rounds with adversarial framing and evidence search, and produces structured outcomes with a full audit trail in proof.json.

The platform is being expanded with five requirements:

1. **ANALYSIS mode** — new top-level modality for queries seeking understanding, not a decision
2. **Common sense like a human** — calibrate effort, reject broken questions early, detect flawed premises
3. **Out-of-the-box thinking** — generate and test alternative framings, adversarial positions, cross-domain analogies
4. **Know what it doesn't know** — detect insufficient context early and tell the requester what's missing
5. **Zero tolerance on infrastructure** — LLM/search unavailable = ERROR, full stop

Round 1 (Brain V8 + ChatGPT) produced strong consensus on the design. This round stress-tests and refines that design.

---

## DECISIONS ALREADY MADE (Round 1 consensus — not up for debate)

The following are settled. Do not propose alternatives to these. Focus your analysis on strengthening, finding gaps, and refining implementation details.

### 1. Nested outcome taxonomy (DECIDED)

The outcome taxonomy is nested by modality, not flat:

- **DECIDE modality** (verdict-seeking): sub-outcomes are DECIDE, ESCALATE, NO_CONSENSUS
- **ANALYSIS modality** (map-seeking): outcome is ANALYSIS
- **Universal** (all paths): NEED_MORE (pre-admission), ERROR (infrastructure-only)

ESCALATE and NO_CONSENSUS exist only in verdict-seeking context. "ANALYSIS with NO_CONSENSUS" is logically incoherent — you can't fail to reach consensus on an exploration that never sought one.

ERROR is strictly infrastructure: LLM unavailable or search unavailable. Not data integrity, not logic errors.

### 2. Single engine, dual modality flow (DECIDED)

One pipeline engine with a shared front-end and modality-specific flow behaviors. Not two separate pipelines.

### 3. Intent classification is a first-class stage (DECIDED)

Dual-source: requester provides an intent flag; pipeline independently audits and can override. Default to ANALYSIS on low classifier confidence — ANALYSIS is a safer failure mode than a forced artificial verdict.

### 4. proof.json evolves to claim-level directed graph (DECIDED)

For Chamber integration. Each claim node: {id, modality, technique, depends_on: [claim_ids, evidence_ids]}. Backward-compatible summary field preserved during transition.

### 5. v2.1 CSA is insufficient (DECIDED)

Must be extended. A new Assumption & Framing Audit (AFA) stage is needed for context sufficiency detection. The AFA classifies gaps:
- **Type A** (requester-fixable): block → NEED_MORE
- **Type B** (unknown/unknowable): inject as explicit unknowns into R1
- **Type C** (framing delusion): append reframing context to R1 briefing

### 6. No mid-run interactivity (DECIDED)

Fire-and-forget. Type A gaps trigger early NEED_MORE before R1. Types B and C are injected. No iterative loops during execution.

---

## TASK

---

**This is a design stress-test. The core decisions above are locked. Your job is to find weaknesses, missing pieces, and implementation risks.**

Answer the following questions:

**1. Taxonomy edge cases**
The nested taxonomy says ESCALATE/NO_CONSENSUS only exist under DECIDE modality. But what happens when an ANALYSIS run encounters: (a) a critical infrastructure gap mid-run (not LLM/search outage — e.g., evidence contradicts the entire analysis frame), (b) a situation where the models cannot produce a coherent analysis map (all frames are equally weak)? What outcomes should these produce? Are there ANALYSIS-specific failure modes not covered?

**2. ANALYSIS topology**
Round 1 produced two proposals: 4→4→3→3 (Brain V8) vs 4→4→3→2 (ChatGPT). The difference is R4: 3 models (more exploration) vs 2 models (tighter synthesis). Which is better and why? Should ANALYSIS even have an R4, or should it terminate at R3 with a longer synthesis stage?

**3. AFA design — the hardest problem**
The Assumption & Framing Audit must detect context the requester didn't know they needed to provide. Round 1 proposed these mechanisms:
- Brain V8: Assumption Mining, Framing Autopsy, Stakeholder Sweep, Temporal Embedding
- ChatGPT: Context Graph (slot extraction), Assumption Ledger, Usefulness Risk Report

Which approach is more robust? Can they be merged? What is the minimum viable AFA that catches the 80% case without over-blocking? Give a concrete example of each gap type (A, B, C) and how the AFA would handle it.

**4. Reasoning technique injection vs Frame Registry**
Round 1 produced two approaches to out-of-the-box thinking:
- Brain V8: Mandatory per-round technique injection (R2: inversion, R3: constraint relaxation, R4: domain transplant). Techniques tracked in claim nodes.
- ChatGPT: First-class Frame Registry with kill criteria and frame inversion. Cross-domain analogies as transfer hypotheses with break conditions.

Are these complementary or competing? What is the right design — one, the other, or a merge?

**5. Gate 2 for ANALYSIS mode**
Decision mode Gate 2 evaluates convergence (did models agree on a verdict?). ANALYSIS mode needs different logic. Both Round 1 participants agreed it should evaluate "coverage quality" — but neither specified concrete criteria. Define: what exactly does Gate 2 check on an ANALYSIS path? What produces ANALYSIS vs what produces NEED_MORE (insufficient analysis) vs ERROR?

**6. Intent misclassification recovery**
The design defaults to ANALYSIS on low classifier confidence. But what if the pipeline gets it wrong?
- If a decision question runs as ANALYSIS: the output is a map, not an answer. The agent can't act on it.
- If an analysis question runs as DECIDE: the output forces a fake verdict on a question that doesn't have one.
Which failure mode is more dangerous? Is "default to ANALYSIS" actually the right policy? What recovery mechanism should exist?

**7. What is missing from this design?**
Looking at the full design (nested taxonomy, dual modality, AFA, claim-level proof.json, technique injection), what is the single most important thing that Round 1 missed? What gap will cause the most pain during implementation if not addressed now?

---

## CONTENT

---

### Architecture Design Spec (summary)

The Thinker V8 architecture:
- **Purpose**: Remove human bottleneck. Autonomous decisions when confident, escalate when not.
- **Pipeline**: Gate 1 → CS Audit → R1 (4 models, parallel, independent) → Search Phase → R2-R4 (debate with evidence, topology narrows) → Gate 2 → Synthesis → proof.json
- **Gate 1**: Pre-admission. Is the question answerable? NEED_MORE if not.
- **Gate 2**: Can we trust this answer? Deterministic, no LLM call.
- **5 Requirements**: R0 (enough context), R1 (multiple opinions), R2 (grounded in evidence), R3 (honest about disagreement), R4 (knows when it can't decide)
- **Zero tolerance**: Any failure → ERROR. No degraded mode.
- **Phase 1**: Brain only. Phase 2: Chamber plugs in for adversarial governance.

### Current DoD coverage (for reference only — not being revised this round)

DoD v2.0 (18 sections): outcome contract, Gate 2 rules, minimum viable deliberation (4→3→2→2), model independence, pipeline gates, evidence acquisition, claim-level traceability, argument lineage, proof.json contract, fatal error semantics, checkpoint/resume, reproducibility, credibility, determinism, contradiction handling, test requirements, deferred scope, zero-tolerance timeouts.

DoD v2.1 patch: Common Sense Audit (effort calibration, premise validation, groupthink detection), Out-of-the-Box Thinking / Divergent Framing (adversarial slots, frame survival tracking, cross-domain analogy tracking), Gate 2 rule extensions.

### Round 1 consensus (full detail)

**Brain V8 report (4-model deliberation, 0.88 agreement ratio):**

Key findings:
1. Nested dual-modality taxonomy is mandatory. Flat taxonomy creates logical contradictions.
2. Intent classification: dual-source (requester + pipeline), pipeline has authority, default to ANALYSIS on low confidence.
3. AFA is the concrete implementation of "common sense." Classifies gaps as Type A (block), B (inject), C (reframe).
4. v2.1 CSA must be extended with: DIRECT_ANSWER fast-path, category-error detection, counterexample heuristics, mandatory technique injection.
5. Mandatory per-round reasoning techniques prevent convergence syndrome. Tracked in claim nodes.
6. ANALYSIS topology: 4→4→3→3 (exploration-focused, diversity maintained).
7. proof.json must evolve to claim-level directed graph for Chamber. Node: {id, modality, technique, depends_on}.
8. AFA latency (~3s) acceptable given R1 warm-up concurrency.
9. ANALYSIS claim explosion risk managed at synthesis (≥85% overlap consolidation).
10. ERROR = infrastructure-only. Unchanged.

**ChatGPT recommendations:**

Key proposals:
1. Keep 5 flat outcomes + terminal_reason_code subtyping. (OVERRIDDEN by nested taxonomy decision)
2. ANALYSIS: Intent Router + different closure gate (coverage/honesty). Topology: 4→4→3→2. Proof payload: frame_registry, claims, open_questions, missing_context, confidence_by_frame.
3. CS Audit → run-configuring planner. Decision-object extraction, premise repair, usefulness test, answer-shape selection. Problem Definition Record reconfigures the run.
4. Frame Registry with kill criteria. Frame inversion mandatory for high-stakes. Transfer hypotheses with break conditions.
5. Shared front-end (InfraPreflight → IntentRouter → ContextInterrogator → PremiseAudit → RunPlanner) + two controller paths.
6. Context detection: Context Graph (slot extraction), Assumption Ledger, Usefulness Risk Report.
7. Chamber: schema-first interoperability. proof.json is the typed product.

---

This is a CLOSED REVIEW. Do not search the web. All context needed is in this brief.
