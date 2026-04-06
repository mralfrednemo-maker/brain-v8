# Brain V8 — Expanded Design Brief

**Date:** 2026-04-01
**Type:** Design facilitation — CLOSED REVIEW. Do not search the web.

---

## WHAT BRAIN V8 IS

Brain V8 is a multi-model deliberation pipeline built for OpenClaw — a team of AI agents run by Christos. Its purpose is to remove Christos as the decision bottleneck. An agent sends a question, Brain V8 runs it through multiple AI models in adversarial debate with evidence, and produces a structured outcome with a full audit trail (proof.json).

**Current outcomes:**
- DECIDE — models converged, evidence supports it. Agent can act.
- ESCALATE — partial consensus or unresolved blockers. Christos reviews.
- NO_CONSENSUS — models fundamentally disagree. Irreducible split.
- ERROR — LLM or search unavailable. Full stop. No partial results.
- NEED_MORE — question too vague or missing context. Returned before the run starts.

**Current architecture flow:**
```
Gate 1 (Sonnet, ~5s) ── Is the question answerable? Search needed?
    │
    ▼
Round 1 (4 models, parallel) ── Independent opinions, no evidence yet
    │
    ▼
Search Phase ── Model-driven queries, full page fetch, fact extraction
    │
    ▼
Round 2 (3 models) ── Debate with evidence
    │
    ▼
Round 3 (2 models) ── Narrowing, resolve disagreements
    │
    ▼
Round 4 (2 models) ── Closing arguments
    │
    ▼
Gate 2 (Deterministic) ── Can we trust this? → DECIDE / ESCALATE / NO_CONSENSUS / ERROR
    │
    ▼
Synthesis ── Human-readable report + proof.json
```

**The 5 requirements every piece of code must serve:**
- R0: Enough context to reason about
- R1: Multiple independent opinions
- R2: Grounded in evidence
- R3: Honest about disagreement
- R4: Knows when it can't decide

**Zero tolerance:** Any failure in any stage → ERROR. No degraded mode. No silent continuation. LLM down = stop. Search down = stop.

**Round topology is FIXED:** 4→3→2→2. Do not propose changes to this.

---

## WHAT WE WANT TO ACHIEVE

Four expansions to the platform:

**1. Common sense reasoning** — The pipeline should reason like a smart human: calibrate effort to actual difficulty, detect when premises are flawed, reject trivially broken questions early, and not waste full deliberation on questions that don't need it.

**2. Multi-aspect exploration** — Models should look at an issue from multiple angles before converging. Currently they tend to converge quickly on the obvious answer. We need mechanisms that trigger broad exploration — different perspectives, different framings, different assumptions — before the pipeline narrows toward consensus.

**3. Insufficient context detection** — The pipeline must detect when a question looks specific but is built on unstated assumptions that will make the answer useless. A human would immediately ask "wait, what about X?" — the pipeline doesn't. This goes beyond Gate 1's current check (is the brief vague?).

**4. ANALYSIS mode** — A new outcome for questions that seek understanding, not a decision. ANALYSIS reuses the existing decision pipeline where possible. The question is: what do we keep, what do we omit, what do we expand — or is something totally new needed?

**Locked decision (user confirmed):** The outcome taxonomy is nested by modality:
- DECIDE modality (verdict-seeking): DECIDE, ESCALATE, NO_CONSENSUS
- ANALYSIS modality (map-seeking): ANALYSIS
- Universal: NEED_MORE, ERROR

---

## TASK

Answer these four questions. For each, give specific, actionable design recommendations — not general observations. Be concrete about mechanisms and pipeline changes.

1. **Can LLMs exhibit common sense reasoning? If yes, what concrete pipeline mechanisms make it happen?**

2. **How do we get models to explore multiple aspects of an issue? What triggers broad exploration?**

3. **Gap analysis: what's missing or suboptimal in the current pipeline design — everything except the LLM round topology (4→3→2→2), which is fixed?** Look at: Gate 1, Search, Gate 2, Synthesis, proof.json, argument tracking, evidence handling. What needs to change? Submit proposals only if they bring genuine value to the quality of the outcome.

4. **ANALYSIS reuses the decision pipeline. What do we keep, what do we omit, what do we expand — or is something totally new needed?**

---

## CONTEXT

Two additional documents are attached separately alongside this brief:

1. **brain-v8-technical-design.md** — Detailed technical design of the current Brain V8 implementation (from actual code, not the spec)
2. **brain-v8-toolbox-design.md** — Detailed design of every mechanical tool in the pipeline

Read both before answering the questions above.

This is a CLOSED REVIEW. Do not search the web. All context is in these documents.
