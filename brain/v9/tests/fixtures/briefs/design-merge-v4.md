# Brief: Merge Two Design Iterations into a Definitive Platform Design

## Platform Context

The Thinker is a multi-model deliberation platform. It takes a question or decision brief from a human requester and runs it through a structured pipeline of 4 rounds of debate between independent LLM models (DeepSeek-R1, DeepSeek-Reasoner, GLM-5, Kimi-K2). The platform exists because no single model can reliably handle complex, high-stakes questions alone — models hallucinate, exhibit groupthink, miss edge cases, and lack adversarial pressure. The Thinker solves this by:

1. **Forcing breadth** — multiple models explore the question from different angles before convergence is allowed
2. **Grounding in evidence** — a search phase fetches real-world evidence, and claims must bind to it
3. **Tracking disagreement honestly** — frames, arguments, blockers, and contradictions are tracked across rounds with auditable lineage
4. **Knowing when it can't decide** — a deterministic Gate 2 rule engine (no LLM) evaluates the proof state and emits DECIDE only when the evidence and convergence criteria are met; otherwise it escalates, flags no consensus, or errors

The output is a `proof.json` — a machine-readable, auditable artifact that records every stage's output, every argument's lifecycle, every piece of evidence, and the deterministic rule that produced the final outcome. An external auditor should be able to replay the proof and arrive at the same conclusion.

The platform operates in two modalities:
- **DECIDE** — the models converge toward a verdict (yes/no/option A/option B)
- **ANALYSIS** — the models produce an exploratory map of a problem space without seeking agreement

Both modalities share the same pipeline infrastructure but differ in their terminal contract and Gate 2 rules.

**Non-negotiable constraints:**
- Round topology is always 4→3→2→2 (4 models in R1, 3 in R2, 2 in R3, 2 in R4). This cannot be bypassed.
- Outcome taxonomy: DECIDE, ESCALATE, NO_CONSENSUS, ANALYSIS, NEED_MORE, ERROR. No other outcomes exist.
- ERROR is reserved for infrastructure failures only — never for bad questions or user errors.
- Zero tolerance for silent failures — any LLM failure, parsing failure, or missing stage halts the pipeline.

## Task

You are given two design documents for this platform, produced in sequence by multi-platform deliberation sessions:

- **DESIGN-V3.md** — the first iteration
- **DESIGN-V3.0B.md** — a second iteration produced after five disputes from V3.0 were resolved through additional debate rounds

Both documents describe the same platform and share the same locked constraints. They diverge on specific mechanisms — how to seed exploration, how to manage evidence, how to structure the front gate, how to handle ANALYSIS mode, and several other areas.

**Your job is to produce a single, definitive merged design document: DESIGN-V4.md.**

## Instructions

### Step 1 — Read both designs completely

Before comparing anything, read DESIGN-V3.md and DESIGN-V3.0B.md end to end. Understand:
- What problem each section is solving
- What mechanism each version proposes
- Where they agree and where they diverge
- What V3.0B added that V3.0 lacks
- What V3.0 has that V3.0B dropped or weakened

Do not begin the merge until you have a complete mental model of both documents.

### Step 2 — Compare and select

For every design area where the two versions differ, select the stronger version. "Stronger" means:
- More specific and enforceable (not vague aspirations)
- Better reasoned (addresses failure modes, not just happy path)
- More architecturally sound (doesn't create coupling problems or blast radius issues)
- More auditable (produces traceable proof artifacts)

Where both versions offer genuinely different mechanisms for the same goal, pick the one that better serves the platform's core purpose (breadth, evidence grounding, honest disagreement tracking, knowing when it can't decide).

Where one document has a feature the other lacks entirely, include it if it serves the platform's purpose and doesn't contradict a locked constraint. Exclude it only if it adds complexity without clear value.

### Step 3 — Produce DESIGN-V4.md

Write the full merged design document. For each section where you chose between V3.0 and V3.0B (or merged elements from both), include a one-line annotation:

`[SOURCE: V3.0 | V3.0B | MERGED — one sentence explaining why]`

### Specific comparison axes

These are the key areas where V3.0 and V3.0B diverge. Evaluate each explicitly:

| Area | V3.0 | V3.0B |
|------|------|-------|
| **Front gate** | Single merged PreflightAssessment | Separate Gate 1 + CS Audit (two stages, blast radius isolation) |
| **Dimension seeding** | Dimension Seeder: controller generates 3-5 mandatory exploration dimensions pre-R1 | Virtual Frames: Sonnet generates alternative frames pre-R1, NOT injected into model prompts |
| **R1 structured output** | Perspective Cards: 5 structured fields per model (primary_frame, hidden_assumption, stakeholder_lens, time_horizon, failure_mode) | Perspective Lenses: 4 role-based mandates (utility, risk, systems, contrarian) |
| **Frame survival** | 3-vote drop in R2, CONTESTED in R3/R4, adopt/rebut/generate mandate per R2 model | Same 3-vote concept + frame-argument coupling (reactivate frames whose arguments are systematically ignored) |
| **Exploration stress** | Trigger at R1 agreement > 0.75, union of OPEN or HIGH stakes, inject seed frames | Anti-groupthink search at > 0.80, plus breadth-recovery pulse when >40% arguments ignored |
| **Evidence management** | Two-tier ledger: active working set (capped 10) + immutable archive | Claim-aware pinning: pin at claim-contradiction level, 15% context cap, forensic eviction logging |
| **Synthesis input** | Controller-curated synthesis packet (positions, argument lifecycle, frames, blockers, decisive claims, contradictions, premise flags) | Full deliberation arc: R1 positions + argument evolution + frame lifecycle (zero new LLM calls) |
| **Semantic contradictions** | Sonnet pass on shortlisted pairs → hard ESCALATE on unresolved HIGH/CRITICAL | Capped at 5 Sonnet calls → soft penalty (lower agreement_ratio by 0.05 per unresolved) |
| **Argument tracking** | Resolution status (ORIGINAL/REFINED/SUPERSEDED) | Same + auto-promotion after 2 rounds ignored + breadth-recovery pulse injection |
| **ANALYSIS mode** | Top-down: Dimension Seeder drives coverage, A1-A7 Gate 2 rules, analysis_map output | Bottom-up: Dimension Tracker extracts dimensions from model outputs, A1-A3 rules, information boundary classification (EVIDENCED/EXTRAPOLATED/INFERRED) |
| **Error taxonomy** | Binary: ERROR (infrastructure) vs everything else | Three-tier: ERROR (infrastructure) / ESCALATE (mechanism failure) / WARNING (suboptimal, non-blocking) |
| **Retroactive premise escalation** | Not present | Post-R1: if ≥2 models flag same premise → re-run CS Audit |
| **Auto-reformulation** | Not present | Append fixable assumptions to brief instead of returning NEED_MORE; log both versions |
| **Rotating adversarial** | Not present (Kimi is fixed contrarian) | Post-round: reassign contrarian to model farthest from centroid (when agreement > 0.70) |
| **Canonical entity IDs** | Not present | Cross-round deterministic IDs for claims, arguments, frames, evidence bindings |
| **Cross-domain analogies** | Formal schema: analogy_refs, test_status, UNTESTED cannot carry decisive load | Distant-domain queries: optional Sonnet-generated cross-domain search queries |
| **Residue verification** | Structured dispositions per open finding, >20% omission triggers deep scan | Residue violation threshold (25%) blocks DECIDE via Gate 2 rule |
| **Paywall detection** | Not present | String-match for paywall phrases before extraction |
| **R1 space-mapping format** | Not present | Models must enumerate options, declare lean, state evidence needed to switch |
| **Moderated frame rebuttal** | Not present | At least one R2 model must test leading frame with explicit rebuttal |

### Rules for the merge

- **Locked constraints are non-negotiable.** 4→3→2→2 topology, outcome taxonomy, ERROR = infrastructure only.
- **Where both agree, carry forward without comment.**
- **Where they differ, pick the stronger one and explain why in one sentence.**
- **Where both are strong but complementary, merge them.** For example, V3.0's Dimension Seeder and V3.0B's Virtual Frames could coexist if they serve different purposes.
- **Do NOT invent new features.** Only combine what exists in the two documents.
- **Flag any irreconcilable conflicts** between the two designs that cannot be resolved by selection.

## Phase 2 (deferred — not for this run)

After DESIGN-V4.md is produced, a separate brief will ask you to evaluate DOD-V3.md and DOD-V3.0B.md against it and produce a merged DOD-V4.md. Do NOT attempt Phase 2 in this run.

---

## DESIGN-V3.md (complete text)

</content>