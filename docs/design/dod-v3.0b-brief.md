# Brain V8 — DoD V3.0B Brief

**Date:** 2026-04-02
**Type:** DoD writing — CLOSED REVIEW. Do not search the web.

---

## WHAT THIS IS

Write the Definition of Done V3.0B for Brain V8's expanded platform. This DoD must be based on DESIGN-V3.0B (attached below), which was produced through a multi-platform deliberation with full consensus.

There is an existing DOD-V3.md on disk, but it was based on a DIFFERENT design (DESIGN-V3.md) that made different architectural choices. Key differences where DOD-V3.0B must diverge from DOD-V3.md:

1. **Gate 1 + CS Audit remain SEPARATE stages** (DOD-V3.md merged them into "PreflightAssessment"). DOD-V3.0B must have separate acceptance criteria for Gate 1 and CS Audit.
2. **Claim-aware pinning with budget discipline** for DC-5 fix (DOD-V3.md used a two-tier active/archive evidence ledger — that approach was rejected in our design session). DOD-V3.0B must use the 3-pillar approach: claim-aware pinning + 15% context cap + forensic logging.
3. **Canonical cross-round entity IDs** — new mechanism not in DOD-V3.md.
4. **Minimal compressed-mode protocol** for SHORT_CIRCUIT — specific invariants that must be retained.
5. **R3 consolidation + R4 stress-test prompts** for ANALYSIS mode (more specific than DOD-V3.md's generic prompts).
6. **coverage_assessment metadata** field (COMPREHENSIVE/PARTIAL/GAPPED).
7. **Calibrated anti-groupthink search** and **moderated frame rebuttal** — new mechanisms.

## LOCKED DECISIONS

- Nested outcome taxonomy: DECIDE modality (DECIDE/ESCALATE/NO_CONSENSUS), ANALYSIS modality (ANALYSIS), Universal (NEED_MORE, ERROR)
- Round topology fixed: 4→3→2→2
- ERROR = infrastructure only (LLM/search unavailable)

## TASK

Write complete acceptance criteria for every mechanism in DESIGN-V3.0B. For each section:

1. **Required proof.json schema** — what fields must exist, their types, when they're required
2. **Acceptance criteria** — concrete, testable assertions (the kind you can write a unit test for)
3. **Failure modes** — what goes wrong → what outcome (ERROR, ESCALATE, etc.)
4. **Traceability** — which base requirement (R0-R4) this section serves

Follow the format of DOD-V3.md (sections with schemas + requirements + failure modes + traceability) but base ALL content on DESIGN-V3.0B, not DESIGN-V3.md.

Be specific. Every criterion must be testable. No vague requirements like "should be good" — concrete thresholds, boolean checks, schema validations.

---

## CONTEXT: DESIGN-V3.0B (full document follows)

