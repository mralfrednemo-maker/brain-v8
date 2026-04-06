# Brain V8 Expanded Design — Dispute Resolution Brief

**Date:** 2026-04-02
**Type:** Dispute resolution — CLOSED REVIEW. Do not search the web.
**Context:** This is the second pass of a multi-platform deliberation. Four platforms (Claude, Brain V8 run #1, ChatGPT 5.4, Gemini Pro) independently evaluated the Brain V8 expanded design brief. They reached strong consensus on most points but diverged on five specific disputes. Your task is to evaluate ONLY these disputes and deliver a verdict with reasoning for each.

---

## LOCKED DECISIONS (do not debate these)

- Nested outcome taxonomy: DECIDE modality (DECIDE/ESCALATE/NO_CONSENSUS), ANALYSIS modality (ANALYSIS), Universal (NEED_MORE, ERROR)
- Round topology fixed: 4→3→2→2. Cannot be bypassed, shortened, or restructured.
- ERROR = infrastructure only (LLM/search unavailable)

---

## DISPUTE 1: SHORT_CIRCUIT behavior for trivial/well-established questions

**The question:** When CS Audit classifies a question as TRIVIAL or WELL_ESTABLISHED with effort_tier SHORT_CIRCUIT, what should the pipeline do?

**Position A (Gemini):** Bypass Rounds 1-4 entirely. Proceed directly to a single-model Synthesis. Running a 4-model adversarial debate on a settled fact is a failure of system intelligence. Label outcome DECIDE (DIRECT).

**Position B (Brain V8 run #1 + Claude):** The round topology 4→3→2→2 is LOCKED and cannot be bypassed. Instead, operate within the fixed topology by using compressed prompts, no search-request sections, one-paragraph synthesis, and lower token budgets. The topology runs, but with reduced substance per round.

**Position C (ChatGPT):** Create a binding "execution contract" from CS Audit that all downstream stages must obey. The contract specifies reasoning regime (prompt depth, search obligations, consensus requirements) but does not bypass any stages.

**Key tension:** Position A violates the locked topology. Positions B and C respect it but differ on mechanism (compressed prompts vs. binding contract).

**Evaluate:** Which approach is correct given the locked topology constraint? If Position A violates the constraint, say so explicitly. Between B and C, which produces better outcomes?

---

## DISPUTE 2: Gate restructuring — merge Gate 1 + CS Audit or keep separate?

**The question:** Should Gate 1 and CS Audit be merged into a single unified admission surface, or kept as separate stages?

**Position A (ChatGPT):** Merge them into a unified "Admission + Assumption + Modality Router" that decides, before R1, whether the brief belongs in DECIDE or ANALYSIS mode, whether it is runnable, what uncertainty must be injected, and what search burden is mandatory. This produces one coherent admission decision instead of two fragmented ones.

**Position B (Brain V8 run #1):** Keep them separate. Explicitly rejected additional front-gate LLM calls. Zero-tolerance policy makes each new failure point costly. The CS Audit already runs after Gate 1; merging them adds complexity without clear benefit. Retroactive safety nets (post-R1 premise re-check) are safer than front-loading more logic.

**Position C (Claude):** Gate 1 should classify question modality (DECIDE vs ANALYSIS) early, but not necessarily via a merge. The modality decision needs to happen before R1 so prompts can be tailored.

**Key tension:** Unified admission (cleaner governance, single decision point) vs. separate stages (less blast radius per failure, existing architecture preserved).

**Evaluate:** Which approach better serves the zero-tolerance architecture? Consider: failure modes, latency, auditability, and whether modality routing needs to happen before R1.

---

## DISPUTE 3: Evidence architecture for DC-5 fix

**The question:** How should the DC-5 bug (evidence eviction orphaning contradictions) be fixed?

**Position A (ChatGPT):** Fundamental architecture change — make evidence append-only with active/archive states. Never hard-evict. Split "working set for prompts" from "forensic ledger for proof." This eliminates the entire class of eviction bugs.

**Position B (Brain V8 run #1):** Targeted fix within existing architecture — on eviction, check if item is in any contradiction record. If yes, mark contradiction EVIDENCE_EVICTED, preserve evicted content in proof.json under `evicted_evidence`, count HIGH-severity evicted contradictions as unresolved for Gate 2 rule 6, penalize scoring (score -= 3).

**Position C (Gemini):** Pin rule — any evidence item involved in an OPEN contradiction or blocker cannot be evicted until resolved or run ends. Evict the next-lowest item that is not part of a conflict.

**Key tension:** Architectural overhaul (A) vs. targeted fix (B) vs. simple pin rule (C). Trade-off between completeness of fix, implementation complexity, and risk of breaking existing behavior.

**Evaluate:** Which approach best fixes DC-5 while respecting zero-tolerance? Consider: does each approach fully prevent contradiction orphaning? What are the failure modes of each?

---

## DISPUTE 4: ANALYSIS mode R3/R4 behavior

**The question:** In ANALYSIS mode, should Rounds 3 and 4 behave differently from DECIDE mode?

**Position A (Gemini):** Repurpose R3 and R4 fundamentally. R3 becomes "Clustering" (group arguments into themes). R4 becomes "Sensitivity Analysis" (explain how the answer changes if assumptions are tweaked). This changes what the rounds DO, not just how they're prompted.

**Position B (Brain V8 run #1 + ChatGPT):** Same round structure, different prompts. In DECIDE, later rounds narrow toward a verdict. In ANALYSIS, R3/R4 prompts shift to: compress the map, structure the explanatory product, identify what is settled vs. contested vs. unknown. The engine is the same; the scoring function and terminal contract differ.

**Position C (Claude):** Keep rounds but shift Gate 2 from convergence checking to completeness checking. The rounds themselves don't need fundamental repurposing — the output evaluation changes.

**Key tension:** Structural repurposing of rounds (A) vs. prompt-level differentiation (B) vs. evaluation-level differentiation (C).

**Evaluate:** Which approach produces the best ANALYSIS output while maintaining pipeline consistency? Consider: does repurposing rounds break argument tracking, position tracking, or other tools that expect standard round behavior?

---

## DISPUTE 5: ANALYSIS outcome labels

**The question:** Should ANALYSIS mode use different outcome labels than the locked taxonomy?

**Position A (Gemini):** Replace DECIDE/NO_CONSENSUS with COMPREHENSIVE (all aspects explored) or GAPPED (significant evidence missing). These better reflect what ANALYSIS mode is trying to achieve.

**Position B (Brain V8 run #1 + ChatGPT + Claude):** The outcome taxonomy is LOCKED. ANALYSIS is the outcome for ANALYSIS-mode questions. Quality checks (dimension coverage, residue) determine whether the run succeeds (→ ANALYSIS) or needs more work (→ ESCALATE or NEED_MORE). No new outcome labels.

**Key tension:** Position A proposes new labels that may better describe ANALYSIS results. Position B says the taxonomy is a locked decision and cannot be changed.

**Evaluate:** Is Position A a violation of the locked taxonomy? If so, can Gemini's intent (distinguishing comprehensive from gapped analysis) be achieved within the locked taxonomy?

---

## TASK

For each of the 5 disputes above:
1. State which position you endorse (A, B, or C) or propose a synthesis
2. Explain WHY with specific reasoning
3. Flag any position that violates a locked decision
4. If you propose a synthesis, be concrete about the mechanism
