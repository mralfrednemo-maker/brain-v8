# Brain V8 — DoD v3.0 Brief

**Date:** 2026-04-02
**Type:** DoD authoring — CLOSED REVIEW. Do not search the web.

---

## WHAT THIS IS

Brain V8 has a confirmed design document (DESIGN-V3.md) produced by a two-pass multi-platform deliberation. The design introduces four major expansions: prescriptive preflight assessment, multi-aspect exploration mechanisms, six pipeline gap fixes, and ANALYSIS mode.

The current DoD is v2.1 (attached for format reference). DoD v3.0 must be written FROM SCRATCH — not as a patch to v2.1, but as a complete, self-contained document that covers the entire expanded platform.

---

## TASK

Write DoD v3.0 for Brain V8. For every mechanism in DESIGN-V3.md, specify:

1. **Testable acceptance criteria** — what "done" means, stated as verifiable assertions (not descriptions)
2. **Gate 2 rules** — numbered, deterministic, ordered. Every rule must be evaluable from proof.json state alone (no LLM call at Gate 2)
3. **proof.json schema requirements** — every field that must exist, its type, and when it is required
4. **Failure modes** — what happens when each mechanism fails, and the expected outcome (ERROR, ESCALATE, NEED_MORE)

Additional requirements:
- The DoD must be self-contained. A reader should understand every requirement without needing to read DESIGN-V3.md.
- Every section must trace back to at least one of the 5 base requirements: R0 (enough context), R1 (multiple opinions), R2 (grounded in evidence), R3 (honest about disagreement), R4 (knows when it can't decide).
- Gate 2 must remain fully deterministic. Same proof state = same outcome. No LLM call.
- ERROR = infrastructure only (LLM/search unavailable) + fatal integrity failures (missing mandatory pipeline stages). Not for bad user questions.
- Round topology is FIXED: 4->3->2->2. Do not propose changes.
- Outcome taxonomy: DECIDE modality (DECIDE/ESCALATE/NO_CONSENSUS), ANALYSIS modality (ANALYSIS), Universal (NEED_MORE, ERROR).

---

## LOCKED DESIGN DECISIONS (from DESIGN-V3.md)

These are confirmed and must not be reopened:

1. Gate 1 + CS Audit merged into single PreflightAssessment stage
2. Typed defect routing: requester-fixable→NEED_MORE, manageable→inject+blocker, framing→inject reframe, fatal premise→NEED_MORE with fatal_premise flag
3. SHORT_CIRCUIT path with strict guardrails (full topology, reduced search, high-authority evidence required)
4. Ungrounded Stat Detector wired into proactive search
5. Dimension Seeder (pre-R1) generating 3-5 mandatory exploration dimensions
6. Perspective Cards (5 structured fields per R1 model output)
7. Frame survival: 3-vote drop in R2, CONTESTED in R3/R4 (not dropped, not frozen)
8. R2 frame enforcement (adopt one, rebut one, generate one)
9. Exploration stress trigger (agreement_ratio > 0.75 on OPEN/HIGH → seed frames)
10. Two-tier evidence ledger (Active Working Set capped at 10 + Immutable Archive uncapped)
11. Synthesis receives controller-curated state bundle (not just R4 outputs)
12. Semantic contradiction detection (Sonnet-based, on shortlisted pairs)
13. Argument resolution status (ORIGINAL/REFINED/SUPERSEDED_BY[ID])
14. Search provenance tracking (model_claim/premise_defect/frame_test/evidence_gap/ungrounded_stat)
15. Structured residue verification (disposition objects, not string matching)
16. Gate 2 stability tests (conclusion/reason/assumption stability)
17. ANALYSIS mode: shared pipeline, forked controller contract, ~80% reuse
18. ANALYSIS Gate 2 rules: A1-A5 (coverage-based, not consensus-based)
19. ANALYSIS implementation staged with DEBUG flag
20. Dynamic token budgeting by effort_tier

---

## CONTEXT DOCUMENTS

Two documents are attached:

1. **DESIGN-V3.md** — The confirmed design. Primary input. Every mechanism described here needs DoD coverage.
2. **V8-DOD-v2.1-patch.md** — The current DoD (v2.1 patch format). Use as FORMAT REFERENCE ONLY — v3.0 is a full rewrite, not a patch. Note the style: numbered sections, testable assertions, proof.json field tables, Gate 2 rule ordering.

Read both before writing the DoD.
