# Design Facilitation Brief — Thinker Platform Expansion
## Round 1: Define the Expanded Design

---

## GOAL

---

### What Brain V8 Is

Brain V8 is a multi-model deliberation pipeline built for OpenClaw — a team of AI agents run by Christos. Its purpose is to remove Christos as the decision bottleneck. It takes a question from any agent, runs it through multiple LLM rounds with adversarial framing and evidence-grounded debate, and produces a structured verdict with a full audit trail.

Current outcome contract: **DECIDE / ESCALATE / NO_CONSENSUS / ERROR** (top-level) + **NEED_MORE** (pre-admission gate).

Important context on how this evolved:
- The original architecture spec defined 3 outcomes: DECIDE, ESCALATE, NEED_MORE.
- The DoD v2.0 expanded to 4 top-level outcomes + 1 pre-admission: DECIDE, ESCALATE, NO_CONSENSUS, ERROR + NEED_MORE (pre-admission).
- **ERROR is strictly infrastructure-only**: LLM unavailability or search unavailability. Not data integrity, not logic errors. If the LLM or search is down, the run stops with ERROR.
- NO_CONSENSUS was added for cases where models fundamentally disagree and cannot be resolved — distinct from ESCALATE (which covers partial consensus or unresolved blockers).

All outcomes are accompanied by `proof.json` — a machine-readable audit trail covering all reasoning steps, evidence, argument lineage, and dissent.

### Why the Platform Is Being Expanded

The platform's goal is being expanded with five requirements:

**1. ANALYSIS mode**
The platform must support a new **top-level outcome**: ANALYSIS. This sits alongside DECIDE, ESCALATE, NO_CONSENSUS, and ERROR — it is not a flag or mode on an existing outcome, it is a first-class outcome in its own right. ANALYSIS is for queries where the requester (agent or human) seeks deep understanding of a topic, not a decision. Currently the pipeline forces every question into a DECIDE/ESCALATE frame. This is wrong for analysis-type questions — it produces artificial verdicts where none is warranted.

**2. Common sense like a human**
The pipeline must reason like a smart human: calibrate effort to actual difficulty, reject trivially broken questions early, detect when premises are flawed, and not waste full deliberation on questions that don't need it.

**3. Out-of-the-box thinking**
The pipeline must generate and test alternative framings, adversarial positions, and cross-domain analogies — not just converge on the obvious answer.

**4. Know what it doesn't know**
The pipeline must clearly and early tell the requester what context is missing or insufficient, rather than running to completion on a broken or incomplete question.

**5. Zero tolerance on infrastructure**
LLM unavailable or search unavailable = ERROR and full stop. No degraded mode, no partial results, no graceful degradation. This is already the design intent but must be explicitly codified in the expanded spec.

---

## TASK

---

**This is a DESIGN facilitation, not a DoD review. Define what the expanded platform should do. The DoD will be written separately based on this design.**

Answer the following questions:

**1. Outcome taxonomy**
What is the complete outcome taxonomy for the dual-purpose platform? Currently: DECIDE, ESCALATE, NO_CONSENSUS, ERROR (top-level) + NEED_MORE (pre-admission). Adding ANALYSIS. Should anything else change? Should NO_CONSENSUS be kept, merged, or renamed?

**2. ANALYSIS — concrete mechanics**
How does ANALYSIS work concretely? When is it triggered — by the requester (flag in brief), by the pipeline (Gate 1 / CS Audit classifies it), or both? What does an ANALYSIS outcome contain in proof.json? Does it go through the same R1–R4 rounds or a different path?

**3. Common sense — concrete pipeline behavior**
How should "common sense" translate to concrete pipeline behavior? The current v2.1 patch added a Common Sense Audit (effort calibration, premise validation, groupthink detection). Is this sufficient? What's missing?

**4. Out-of-the-box thinking — concrete pipeline behavior**
How should "out-of-the-box thinking" translate to concrete pipeline behavior? The current v2.1 patch added adversarial slots, divergent framing passes, and cross-domain analogy tracking. Is this sufficient? What's missing?

**5. Pipeline architecture changes**
What changes to the pipeline architecture are needed? Current flow: Gate 1 → CS Audit → R1 (4 models) → Search → R2–R4 (debate with evidence) → Gate 2 → Synthesis. Does ANALYSIS mode need a different flow? Different number of rounds? Different gate logic?

**6. Insufficient context detection — the core "common sense" problem**
How should the pipeline detect insufficient context beyond what Gate 1 currently does? Gate 1 checks if the brief is specific and has context. But it misses briefs that APPEAR specific but have unstated critical assumptions. A human would immediately ask "wait, what about X?" — the pipeline doesn't. This is the hardest problem to solve and the most important one. What concrete mechanism should detect: (a) missing context the requester didn't know they needed to provide, (b) assumptions embedded in the question that need to be surfaced, (c) framing that will lead to a useless answer even if the deliberation runs perfectly?

**7. Chamber integration — the single most important architectural decision**
What is the single most important architectural decision this design must get right for Chamber integration — the downstream governance engine that will consume Brain V8's output?

---

## CONTENT

---

### Architecture Design Spec

```
# The Thinker V8 — Architecture Design Spec

Date: 2026-03-26
Status: Approved through brainstorming
Scope: Brain engine rebuild with clean architecture. Chamber plugs in later.

## 1. The Problem
Christos runs a team of AI agents (OpenClaw). Every decision flows through him — he is the bottleneck.
He needs a brain that can take decisions independently when confident, and escalate to him when it can't.
The Thinker is that brain: a credible, logical decision maker.

## 2. The Contract
The Thinker receives a question from any agent. It produces one of three outcomes:
- DECIDE: Models converged, evidence supports it, dissent addressed → Answer + proof. Agent can act.
- ESCALATE: Models disagree, evidence weak, or confidence low → Full picture sent to Christos. Human decides.
- NEED MORE: Question too vague or key data missing after search → Specific questions sent back to the
  requesting agent.

## 3. The 5 Requirements
R0: Enough context to reason about — Would a smart human push back before starting?
R1: Multiple independent opinions — Did more than one model look at this?
R2: Grounded in evidence — Are claims backed by verifiable external data?
R3: Honest about disagreement — Does the answer show where models disagreed?
R4: Knows when it can't decide — Does it escalate instead of faking confidence?

## 4. Architecture Flow
Gate 1 (Sonnet, ~5s): Is the question answerable? Too vague/missing facts → push back with specific questions.
Round 1 (4 models, parallel): Independent opinions. No evidence yet.
Search Phase: Model-driven (reactive + proactive). Deduplicate queries. Full page content via Playwright.
Rounds 2-4: Debate with evidence. Models see prior arguments + evidence. Topology narrows: 4→3→2→2.
Argument Tracker: Between rounds, extract arguments, compare with next round, re-inject unaddressed ones.
Gate 2: Can we trust this answer? LLM judgment backed by mechanical tool data.
Synthesis: Hermes report (human-readable) + proof.json (machine-readable audit trail).

## 5. Engine Strategy
Phase 1: Brain only. Get Brain stable.
Phase 2: Chamber plugs in. Adds adversarial governance for recommendation-type questions.

## 10. Design Principles
1. Never assume. If context is missing, ask the requester.
2. Fail cheap. Gate 1 catches garbage before spending $2 and 15 minutes.
3. Fail honest. Gate 2 catches weak answers. Escalate, don't fake it.
4. Use the toolbox. Existing tools pulled in when problems appear.
5. Test with mocks. Fix bugs in seconds, not hours.
6. Models drive the search. They know what they need.
7. Full page content. Real articles, not snippets.
8. One engine first. Brain stable before Chamber plugs in.
```

---

### Current DoD Coverage Summary

**DoD v2.0** (18 sections) covers: outcome contract (DECIDE/ESCALATE/NO_CONSENSUS/ERROR), Gate 2 decision rules, minimum viable deliberation (4→3→2→2 topology), model independence, pipeline gates, evidence acquisition, claim-level traceability, argument lineage, proof.json contract, fatal error semantics, checkpoint/resume, reproducibility, credibility requirements, determinism policy, contradiction handling, test requirements, deferred scope, and zero-tolerance timeout policy.

**DoD v2.1 patch** adds: Common Sense Audit (Section 19 — effort calibration, premise validation, groupthink detection, question classification), Out-of-the-Box Thinking / Divergent Framing (Section 20 — adversarial slots, frame survival tracking, cross-domain analogy tracking), and corresponding Gate 2 rule extensions.

---

This is a CLOSED REVIEW. Do not search the web. All context needed is in this brief.
