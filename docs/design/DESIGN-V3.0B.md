# Brain V8 — Expanded Platform Design V3.0B

**Date:** 2026-04-02
**Process:** Multi-platform deliberation (Claude + Brain V8 + ChatGPT 5.4 + Gemini Pro)
**Outcome:** Full consensus across all participants after two debate rounds and dispute resolution.
**Brain V8 Run #1:** DECIDE / PARTIAL_CONSENSUS, 0.90 agreement
**Brain V8 Run #2:** All 5 disputes resolved, full consensus

---

## Locked Decisions (unchanged)

- **Outcome taxonomy (nested by modality):**
  - DECIDE modality: DECIDE, ESCALATE, NO_CONSENSUS
  - ANALYSIS modality: ANALYSIS
  - Universal: NEED_MORE, ERROR
- **Round topology:** 4→3→2→2 (fixed, cannot be bypassed or restructured)
- **ERROR:** Infrastructure only (LLM/search unavailable)
- **Zero tolerance:** Any failure → ERROR. No degraded mode.

---

## 1. Common Sense Reasoning

### Design Principle
Common sense is implemented as **controller policy**, not as an emergent model trait. The pipeline must calibrate effort to difficulty, validate premises, and detect when questions don't warrant full deliberation — all within the locked topology.

### 1.1 Retroactive Premise Escalation (post-R1)
After R1, the Argument Tracker scans for `premise_challenge` arguments. If **≥2 models independently** identify the same flawed premise, trigger a mid-pipeline re-run of the CS Audit. This catches premise defects that Gate 1 missed without adding any latency to the happy path.

### 1.2 Effort-Tier Calibration
CS Audit's `effort_tier` output becomes binding on downstream stages:

| Effort Tier | Prompt Depth | Search Scope | Evidence Cap | Synthesis |
|-------------|-------------|--------------|--------------|-----------|
| SHORT_CIRCUIT | Compressed (minimal protocol) | No search-request sections | Standard (10) | One-paragraph |
| STANDARD | Full | Full | Standard (10) | Full report |
| ELEVATED | Expanded + scrutiny sections | Expanded proactive queries | Raised (15) | Full report + extended |

### 1.3 Compressed-Mode Protocol (SHORT_CIRCUIT)
The locked topology runs in full, but under a compressed system prompt. **Fixed invariants that must be retained** even in compressed mode:
1. Premise check (did the model validate the premise?)
2. Confidence basis (what supports this answer?)
3. Known unknowns (what could change this?)
4. One counter-consideration (what argues against?)
5. Machine-readable reason for compression (why is this SHORT_CIRCUIT?)

This prevents prompt drift, silent under-exploration, and calibration opacity.

### 1.4 Auto-Reformulation for Reparable Flaws
When CS Audit detects a fixable missing assumption (repairable premise defect), append the assumption to the brief as explicit context and proceed. Do not return NEED_MORE for reparable flaws. Log both original and reformulated briefs in proof.json.

### 1.5 Gate 1 Modality Tag
Gate 1 emits a lightweight `DECIDE` or `ANALYSIS` modality tag in its output. CS Audit independently refines this. No merger of Gate 1 and CS Audit — they remain separate stages to limit failure blast radius.

### 1.6 Rejected Proposals
- **Additional front-gate LLM calls** (e.g., multi-model CS Audit, unified admission surface): Rejected. Zero-tolerance makes each new failure point costly. Retroactive safety nets are safer.
- **Topology bypass for SHORT_CIRCUIT** (e.g., skip rounds, single Sonnet response): Rejected. Violates locked topology.

---

## 2. Multi-Aspect Exploration

### Design Principle
Exploration is enforced through **prompt-level cognitive directives** and **controller-mandated deliverables**, not structural pipeline changes. Premature convergence is structural — agreement_ratio thresholds reward consensus, adversarial pressure ends after R1, and the Divergent Framing Pass depends on organic R1 diversity. The fix requires concurrent mechanisms.

### 2.1 Pre-R1 Virtual Frames
Before R1, a single Sonnet call generates 3-5 alternative frames (INVERSION, STAKEHOLDER, PREMISE_CHALLENGE, CROSS_DOMAIN_ANALOGY, etc.). These are **NOT injected into real model prompts** (independence preserved). They feed the Divergent Framing Pass as virtual outputs, guaranteeing frame diversity even if R1 converges naturally.

### 2.2 R1 Perspective Lenses
Assign differentiated exploration mandates to R1 models via system prompts. Four lenses:
1. **Utility/Efficiency** — focus on benefits, speed, cost
2. **Risk/Security** — focus on failure modes, attack surfaces, vulnerabilities
3. **Systems/Architecture** — focus on scalability, integration, maintainability
4. **Contrarian/Inversion** — focus on challenging premises, opposite stances (Kimi retains adversarial role)

Lenses are adapted based on CS Audit's `question_class`. Fallback to standard roles if mapping fails.

### 2.3 R1 Space-Mapping Format
R1 responses must include:
- Viable options enumerated
- A declared lean (preferred option)
- Evidence needed to switch from that lean

Position Tracker computes a diversity score from R1 outputs. Score <2 → proof.json warning.

### 2.4 Rotating Adversarial Role (R2-R4)
After each round, assign the contrarian role to the model farthest from the position centroid (using Position Tracker data). Maintains diversity pressure throughout deliberation without changing the roster or topology.

**Activation threshold:** Only when agreement_ratio > 0.70 (to limit ~8% token overhead). Requires load-testing.

### 2.5 Breadth-Recovery Pulse
If Argument Tracker shows >40% of R1 arguments IGNORED in R2, inject into R3 prompt: "Address at least 2 of the following ignored arguments before proceeding."

### 2.6 Frame-Argument Coupling
If arguments belonging to a frame are systematically ignored for ≥2 rounds, re-activate that frame (bump from CONTESTED back to ACTIVE).

### 2.7 Calibrated Anti-Groupthink Search
When non-trivial questions produce agreement_ratio >0.80 in R1, trigger one adversarial search query specifically looking for evidence that disproves or weakens the consensus. Not universal — triggered only for OPEN/HIGH-stakes questions.

### 2.8 Moderated Frame Rebuttal (R2)
In R2, at least one surviving model must explicitly test the leading frame with a rebuttal before supporting the majority position. Not rigid "everyone must rebut all frames" — one explicit challenge per leading frame.

### 2.9 Distant-Domain Analogical Queries (Optional)
For OPEN questions where R1 exploration is narrow, Sonnet generates 1-2 cross-domain search queries. Optional R1 tactic, never mandatory. Useful for stuck or over-narrow debates.

---

## 3. Pipeline Gap Fixes

### Priority Order (by severity)

### 3.1 DC-5 Fix: Claim-Aware Pinning + Budget Discipline + Forensic Logging

**Three-pillar approach:**

**Pillar 1 — Claim-aware pinning:** Pin at the **claim-contradiction unit** level, not raw evidence items. Any evidence involved in an OPEN contradiction or active blocker cannot be evicted until that contradiction is resolved or the run ends. This prevents both evidence-level and claim-level orphaning.

**Pillar 2 — Budget discipline:**
- Hard cap: max 15% of context window reserved for pinned items
- Pin decay: a pinned item loses protection only when the claim-level contradiction has been superseded, resolved, or explicitly archived — NOT based on naive model consensus about obsolescence
- If cap is reached, Gate 2 triggers ESCALATE rather than silently dropping contradictions

**Pillar 3 — Forensic logging:**
- Evicted evidence recorded in proof.json under `evicted_evidence`
- Each eviction logs: which contradiction was affected, whether severity was HIGH
- Contradiction type recorded: direct contradiction, scope narrowing, definitional conflict, conditional override
- HIGH-severity evicted contradictions count as unresolved for Gate 2 rule 6

### 3.2 Canonical Cross-Round Entity IDs

**High-leverage structural improvement.** Assign deterministic IDs at Gate 1/R1:
- `claim_{topic}_{nn}` for claims
- `arg_{round}_{nn}` for arguments (existing)
- `frame_{nn}` for frames (existing)
- `blk_{nn}` for blockers (existing)
- `evidence_binding_{nn}` for claim-to-evidence links

Subsequent rounds must explicitly cite these IDs when supporting, mutating, or rebutting. Transforms Position Tracker from fuzzy semantic matching to deterministic lineage graph. Makes forensic logging, claim-aware pinning, and cross-round traceability implementable.

### 3.3 Synthesis with Full Deliberation Arc
Feed synthesis prompt with:
- One-line R1 position per model (from Position Tracker)
- Argument evolution summary (from Argument Tracker)
- Frame lifecycle (from Divergent Framing Pass)

**Zero new LLM calls** — uses existing structured data. The report now describes how consensus formed, not just what it concluded.

### 3.4 Residue Violation Blocks DECIDE
New Gate 2 rule 13: if `residue.threshold_violation` is True → ESCALATE.
Starting threshold: 25% omissions. Collect data; relax only if false positives observed.

### 3.5 Wire Ungrounded Stat Detector
Activate after R1 and R2. Unverified numeric claims generate:
- Targeted search queries for verification
- BLK-UNG-{n} blockers

Unresolved after search → ESCALATE trigger.

### 3.6 Capped Semantic Contradiction Detection
For evidence pairs sharing ≥4 topic words with no numeric conflict, run a Sonnet call (max 5 per search phase). Output as SEMANTIC_CTR with same tracking as numeric CTR. In Gate 2: lower effective agreement_ratio threshold by 0.05 per unresolved semantic contradiction (soft signal, not hard block).

### 3.7 Paywall Detection
Before extraction, string-match fetched pages for paywall phrases ("subscribe," "premium," "member exclusive"). If >30% match → mark PAYWALLED, skip extraction, log in proof.json. Low-cost addition to `page_fetch.py`.

### 3.8 Evidence Quality Floor
Gate 2 rule 5 enhanced: check average evidence score. Minimum score threshold (e.g., 2.0) required for DECIDE.

### 3.9 Argument Auto-Promotion
An argument unaddressed (MENTIONED or IGNORED) for ≥2 consecutive rounds → automatically promoted to `critical`. Deterministic rule, no LLM call. Gated by CS Audit's `question_class` (applies to OPEN/AMBIGUOUS questions).

### 3.10 Cross-Domain Filter Enhancement
Adjust compatibility matrix to check non-empty intersection between brief and evidence domain sets, allowing hybrid domains (e.g., security+infrastructure) rather than binary allow/reject.

### 3.11 Gate 2 Rule 11 Clarification
Explicitly state: "If agreement_ratio ≥ 0.75 in R1 AND effort_tier ≠ SHORT_CIRCUIT AND evidence_count == 0 → ESCALATE."

### 3.12 Proof.json Extensions
New fields:
- `reasoning_contract`: effort tier, modality, compression status
- `premise_defect_log`: original and reformulated briefs
- `outcome_confidence`: weighted aggregate of agreement_ratio, evidence quality, argument resolution, frame resolution
- `escalate_remediation`: per-rule human-readable remediation steps
- `evicted_evidence`: content and contradiction linkage for evicted items
- `coverage_assessment`: COMPREHENSIVE / PARTIAL / GAPPED (ANALYSIS mode)

---

## 4. ANALYSIS Mode

### Design Principle
ANALYSIS reuses ~70-80% of the decision pipeline. The engine is the same; the **scoring function and terminal contract** differ. ANALYSIS seeks a comprehensive map of the problem space, not a verdict.

### 4.1 What to Keep (unchanged from DECIDE)
- Gate 1 (with modality tag + auto-reformulation)
- CS Audit (skip `stakes_class` for ANALYSIS; question_class and premise flags still apply)
- Fixed round topology 4→3→2→2
- Search phase (with expanded evidence caps: STANDARD=15, ELEVATED=20)
- EvidenceLedger (with DC-5 fix in place)
- Argument Tracker
- Divergent Framing Pass
- Invariant Validator
- proof.json
- Zero tolerance

### 4.2 What to Replace

**Position Tracker → Dimension Tracker:**
After each round, Sonnet extracts analytical dimensions bottom-up from model outputs. Tracks:
- Dimension names and definitions
- Coverage status per dimension (well-covered / thinly-covered / missing)
- Cross-dimension interactions (reinforcements, trade-offs, dependencies)

`dimension_coverage` < 0.80 at end of R4 → ESCALATE.

**Adversarial Role → Stakeholder Perspectives:**
Assign each R1 model a stakeholder role (engineering, users, budget, operations) based on CS Audit's `question_class`. Fallback to standard adversarial role if mapping fails.

### 4.3 What to Omit
- Gate 2 consensus rules 2, 3, 5, 11 (agreement-ratio-based rules are irrelevant for ANALYSIS)
- Blocker kind CONTESTED_POSITION (disagreement is a feature in ANALYSIS, not a blocker)

### 4.4 ANALYSIS-Specific Round Prompts

**R1-R2:** Aggressively expand the map. Different frames, stakeholder lenses, causal hypotheses, risk dimensions, rival interpretations. Standard exploration mechanisms apply.

**R3 — Landscape Consolidation:**
> "Do not optimize for choosing a winner. Collapse duplicate frames, preserve materially distinct dimensions, identify coverage gaps. For each retained dimension, output: dimension name, why it matters, arguments present, counterarguments present, uncertainty, dependent assumptions. Expose cross-dimension dependencies."

**R4 — Landscape Map + Stress Test:**
> "Produce a final analysis map detailing settled understanding and remaining tensions. Preserve materially distinct dimensions. For each dimension, state the settled understanding, remaining live tension, and whether sufficiently explored. Conclude by stress-testing: explicitly identify edge cases, boundary failures, brittle assumptions, hidden dependencies, and unaddressed vulnerabilities most likely to break or alter this landscape. End with a coverage assessment."

### 4.5 ANALYSIS Gate 2 Rules
Three rules only:
- **A1:** dimension_coverage < 0.80 → ESCALATE
- **A2:** residue.threshold_violation → ESCALATE
- **A3:** otherwise → ANALYSIS

### 4.6 ANALYSIS Synthesis Output Format
Structured document:
1. **Dimensions Explored** — normalized list with coverage status
2. **Evidence Map** — evidence clustered by dimension
3. **Tension Catalog** — trade-offs, competing frameworks, unresolved disagreements
4. **Frame Catalog** — surviving frames with lifecycle summary
5. **Information Boundary** — each claim classified as EVIDENCED (direct citation), EXTRAPOLATED (inferred from evidence), or INFERRED (no evidence). Classification is extractive (Sonnet), not self-tagged by models.
6. **Open Questions** — what remains unknown, what evidence would resolve it
7. **Action Implications** — if applicable, what decisions this analysis enables
8. **Coverage Assessment** — COMPREHENSIVE / PARTIAL / GAPPED (recorded in proof.json as `coverage_assessment`)

### 4.7 Information Boundary Classification
After each round, Sonnet classifies each claim extractively:
- **EVIDENCED** {E} — direct citation to evidence item
- **EXTRAPOLATED** {X} — inferred from evidence but not directly stated
- **INFERRED** {I} — no evidence backing

Applied by Sonnet, not self-tagged by models. Prevents models from inflating their evidence basis.

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Virtual pre-R1 frames may be irrelevant | Medium | Auto-demote if unaddressed by R2; lower initial materiality |
| Rotating adversarial adds ~8% token overhead | Medium | Activate only when agreement_ratio > 0.70; load-test first |
| SHORT_CIRCUIT compressed mode may miss nuance | Medium | Minimal protocol retains invariants; proof.json preserves full structure |
| Pin bloat under claim-aware pinning | Medium | 15% context cap; pin decay on resolution only; ESCALATE if cap reached |
| Semantic contradiction detection adds Sonnet calls | Low | Cap at 5 per search phase; feature-flag for testing |
| Dimension Tracker may miss collectively-overlooked aspects | Medium | Virtual pre-R1 frames provide implied dimensions as hybrid supplement |
| Auto-reformulation may silently change the question | Medium | Log original + reformulated in proof.json; surface in synthesis |
| Argument auto-promotion may over-escalate low-value arguments | Low | Gated by question_class; only OPEN/AMBIGUOUS questions |

---

## Consensus Summary

All four platforms converged on:
1. Common sense = controller policy (not model trait). Retroactive premise escalation + effort calibration + auto-reformulation.
2. Exploration = proactive injection (virtual frames + lenses + rotating adversary), not reactive extraction.
3. DC-5 = claim-aware pinning with budget discipline + forensic logging. Canonical cross-round entity IDs as foundational infrastructure.
4. ANALYSIS = same engine, different contract. Dimension Tracker replaces Position Tracker. R3 consolidates, R4 stress-tests. Gate 2 checks coverage, not convergence.

**No unresolved disputes remain.**
