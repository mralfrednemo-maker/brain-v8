# Brief: Create a Master Design & DOD Document for the Thinker Platform

## Platform Context

The Thinker is a multi-model deliberation platform. It takes a question or decision brief from a human requester and runs it through a structured pipeline of 4 rounds of debate between independent LLM models (DeepSeek-R1, DeepSeek-Reasoner, GLM-5, Kimi-K2). The platform exists because no single model can reliably handle complex, high-stakes questions alone — models hallucinate, exhibit groupthink, miss edge cases, and lack adversarial pressure. The Thinker solves this by:

1. **Forcing breadth** — multiple models explore the question from different angles before convergence is allowed
2. **Grounding in evidence** — a search phase fetches real-world evidence, and claims must bind to it
3. **Tracking disagreement honestly** — frames, arguments, blockers, and contradictions are tracked across rounds with auditable lineage
4. **Knowing when it can't decide** — a deterministic Gate 2 rule engine (no LLM) evaluates the proof state and emits DECIDE only when the evidence and convergence criteria are met

The output is a `proof.json` — a machine-readable, auditable artifact that records every stage's output, every argument's lifecycle, every piece of evidence, and the deterministic rule that produced the final outcome.

**Non-negotiable constraints:**
- Round topology is always 4→3→2→2
- Outcome taxonomy: DECIDE, ESCALATE, NO_CONSENSUS, ANALYSIS, NEED_MORE, ERROR
- ERROR is reserved for infrastructure failures only
- Zero tolerance for silent failures

## Question

Consider the two versions of Design and DOD documents, and after analyzing and deeply understanding the purpose of this platform, create one final document by merging the best features and optimal solutions in one Master document where the design and the DOD will be detailed. Since V3.0 and its current implementation are the baseline and our existing codebase, you will need to create your delta proposal based on that.

Specifically:

1. **Read all provided documents completely** — both design versions, both DOD versions, and the current implementation files. Understand what is already built before proposing anything.

2. **Treat V3.0 + the current code as the baseline.** Do not propose replacing what already works. Every recommendation must be a targeted addition or replacement on top of what exists.

3. **For each V3.0B feature that is stronger than its V3.0 equivalent**, describe precisely:
   - What it replaces or sits alongside in V3.0
   - What changes in the code (which files, which components)
   - What conflicts arise with the existing implementation
   - What the DOD acceptance criteria should be for the new/changed feature

4. **Produce a single Master document** containing:
   - **Part 1: DESIGN** — V3.0 as the foundation, with each selected V3.0B improvement clearly marked as a delta
   - **Part 2: DOD** — V3.0 DOD as the foundation, updated to cover every delta in Part 1, with acceptance criteria, failure modes, and Gate 2 rules

5. **Do not invent new features.** Only select from what exists in the two design versions.

## Epistemic Override

All documents and source files are provided below. You have everything you need.

---

## DESIGN-V3.md (baseline design)

# Brain V8 — Expanded Platform Design (v3.0)

**Date:** 2026-04-02
**Status:** CONFIRMED — Design Session complete
**Source:** Two-pass multi-platform deliberation (Brain V8 + ChatGPT + Gemini + Claude)
**Locked constraints:** Round topology 4->3->2->2 (unchanged). Outcome taxonomy: DECIDE/ESCALATE/NO_CONSENSUS + ANALYSIS + NEED_MORE/ERROR.

---

## 1. Common Sense Reasoning

Common sense is a pipeline property enforced through three mechanisms, not a model capability.

### 1.1 Prescriptive Preflight Assessment

Gate 1 and CS Audit merge into a single **PreflightAssessment** stage. One Sonnet call produces a typed schema:

```
PreflightAssessment:
  answerability: ANSWERABLE | NEED_MORE | INVALID_FORM
  question_class: TRIVIAL | WELL_ESTABLISHED | OPEN | AMBIGUOUS
  stakes_class: LOW | STANDARD | HIGH
  effort_tier: SHORT_CIRCUIT | STANDARD | ELEVATED
  modality: DECIDE | ANALYSIS
  premise_flags[]: type + severity + summary
  hidden_context_gaps[]: description + impact_if_unresolved
  search_scope: NONE | TARGETED | BROAD
  exploration_required: boolean
  short_circuit_allowed: boolean
```

Each detected defect gets explicit routing:
- **Requester-fixable** (missing context, ambiguous target) -> **NEED_MORE** with specific follow-up questions
- **Manageable unknowns** (genuine unknowns, contested assumptions) -> **inject as debate obligation + register as blocker**
- **Framing defect** (false dichotomy, wrong comparison) -> **inject reframed version into R1, force engagement**
- **Fundamentally broken premise** -> **NEED_MORE** with `fatal_premise: true` flag

Gate 1 also surfaces 3-5 critical unstated assumptions. If any are unverifiable or demonstrably false, return NEED_MORE with specific follow-up questions.

### 1.2 Taxonomy Fix

CS Audit INVALID -> ERROR is removed. ERROR is reserved exclusively for infrastructure failures (LLM/search unavailable). Invalid or malformed questions route through the defect taxonomy above.

### 1.3 SHORT_CIRCUIT Path

When `effort_tier=SHORT_CIRCUIT` + `question_class in {TRIVIAL, WELL_ESTABLISHED}` + `stakes_class=LOW` + no CRITICAL premise flags + no material hidden-context gaps:

- Run the full 4->3->2->2 topology (topology is fixed)
- Shrink search budget, prohibit speculative expansion
- Force every round to either confirm the trivial answer or surface a hidden defect
- Require high-authority evidence to proceed; otherwise fall back to full deliberation
- Logged as `SHORT_CIRCUIT_DECIDE` in proof.json

### 1.4 Dynamic Token Budgeting

CS Audit effort_tier influences token budgets per round:
- SHORT_CIRCUIT: tighter budgets per model
- STANDARD: current budgets
- ELEVATED: full allocation + broader search

Topology stays 4->3->2->2 regardless.

### 1.5 Ungrounded Stat Detector

Wire the existing (but inactive) Ungrounded Stat Detector into the proactive search phase after R1 and R2. Post-R3 unverified numeric claims become `UNVERIFIED_CLAIM` blockers, severity scaled by `stakes_class`.

---

## 2. Multi-Aspect Exploration

Breadth is structurally guaranteed before R1, not extracted after.

### 2.1 Dimension Seeder (pre-R1)

One Sonnet call generates 3-5 mandatory exploration dimensions from the brief. Injected into all R1 prompts. Models must address all dimensions or justify irrelevance. Zero-coverage dimensions -> `COVERAGE_GAP` blocker.

### 2.2 Perspective Cards (R1)

Each R1 model output must include structured fields:
- `primary_frame` — the model's primary way of looking at the question
- `hidden_assumption_attacked` — which assumption does this model challenge
- `stakeholder_lens` — whose perspective is this model representing
- `time_horizon` — short-term, medium-term, or long-term focus
- `failure_mode` — what could go wrong with the model's recommended approach

The contrarian slot (Kimi) remains. The other three models get distinct coverage obligations (mechanism analysis, operational risk, objective reframing) enforced through prompt structure.

### 2.3 Frame Survival Reform

- **R2:** Drop threshold raised from 2 votes to 3 (all three R2 models must object with traceable rebuttals)
- **R3/R4:** Frames cannot be dropped. They transition to **CONTESTED** if not rebutted. Gate 2 rule 10 catches unrebutted material frames -> ESCALATE
- **R2 frame enforcement:** Each model must adopt one frame, rebut one frame, and generate one new frame

### 2.4 Exploration Stress Trigger

If R1 `agreement_ratio > 0.75` on an OPEN or HIGH-stakes question:
- Inject 2-3 seed frames (INVERSION, STAKEHOLDER_PERSPECTIVE) into R2 prompts
- Flag in proof.json as `exploration_stress_triggered: true`

Fast consensus on hard questions is suspicious, not comforting.

---

## 3. Pipeline Gap Fixes

Six priority fixes, ordered by impact.

### 3.1 Two-Tier Evidence Ledger (fixes DC-5/V8-F3)

Replace the single capped store with two separate stores:

- **Active Working Set** — capped at 10 items, used for prompt injection. Score-based eviction continues here.
- **Immutable Evidence Archive** — uncapped, never deletes anything. All fetched and extracted evidence lives here permanently.

Evidence can be demoted from active to archive but never deleted from the system. Any evidence referenced by a contradiction, blocker, claim binding, or synthesis citation is always available for audit. Eviction events logged in `proof.json.eviction_log`.

### 3.2 Synthesis Blindness Fix

Synthesis currently sees only R4 outputs. Replace with a controller-curated synthesis packet:

- Final positions (from R4)
- Condensed argument lifecycle (max 20 arguments): ID -> dimension -> strongest round text -> status evolution
- Active/dropped frames with survival history
- Open/resolved blockers with lifecycle
- Decisive claim bindings (which claims carry the conclusion, and what evidence supports them)
- Contradiction summary
- Premise flags and their resolution status

Synthesis prompt requires a schema-shaped report with structured dispositions for every open finding.

### 3.3 Semantic Contradiction Detection

Add a Sonnet-based semantic contradiction pass on shortlisted evidence pairs:
- Same topic cluster
- Opposite polarity cues
- Same entity/timeframe
- Evidence linked to an open contradiction or blocker

Produces structured CTR records with justification. Complements the existing deterministic numeric detector. Output feeds Gate 2 rule 6.

### 3.4 Argument Resolution Status

Add resolution state to the Argument Tracker. Each argument tagged as:
- **ORIGINAL** — first appearance
- **REFINED** — updated version of a prior argument (linked via SUPERSEDED_BY)
- **SUPERSEDED_BY[ID]** — this argument has been replaced by a more developed version

This gives Gate 2 the ability to distinguish genuinely resolved arguments from ones that were restated or ignored. Can upgrade to full genealogy later if needed.

### 3.5 Search Auditability

Add `proof.json.search_log` recording:
- Every query submitted
- Provenance: `model_claim` | `premise_defect` | `frame_test` | `evidence_gap` | `ungrounded_stat`
- Pages fetched per query
- Evidence yield count (0 if nothing returned)

Critical for negative-result traceability — knowing whether a gap is real absence or search failure.

### 3.6 Residue Verification Depth

Replace string-match residue checking with structured narrative obligations. Synthesis must emit a disposition object for every:
- Open blocker: `{id, status, importance, narrative_explanation, evidence_refs[]}`
- Active frame: same structure
- Decisive claim: same structure
- Contradiction: same structure

Residue verification becomes schema validation + coverage validation. Deeper semantic scan (checking surrounding context for resolution tokens) triggers only when >20% omissions detected.

### 3.7 Gate 2 Enhancements

Add three stability tests to Gate 2:
- **Conclusion stability** — do the remaining models converge on the same recommendation?
- **Reason stability** — do they converge for the same reasons?
- **Assumption stability** — are they relying on the same unresolved assumptions?

Agreement on conclusion without agreement on reasoning = weaker confidence. Admissibility (claims bound to evidence, premises resolved, frames handled) is the standard; agreement is a symptom.

---

## 4. ANALYSIS Mode

Shared pipeline, forked controller contract. ~80% code reuse.

### 4.1 What Stays Unchanged

- PreflightAssessment (Gate 1 + CS Audit)
- R1-R4 topology (4->3->2->2)
- Search phase
- Evidence Ledger (two-tier)
- Argument Tracker (with resolution status)
- Divergent Framing Pass
- Invariant Validator
- proof.json base schema

### 4.2 What Is Omitted as Primary Logic

- Position Tracker's `agreement_ratio` driving outcomes (Position Tracker can still run diagnostically)
- Adversarial role (Kimi contrarian) — replaced with broader exploration obligations
- All Gate 2 consensus rules (rules 2, 3, 4, 5, 6, 9, 10, 11)

### 4.3 What Is Modified

**Round prompts:** Shift from "converge on a verdict" to "deepen exploration by dimension — identify knowns (evidence-backed), inferred (model-supported), unknowns (gaps). Do not seek agreement."

**Frame survival:** Dropping disabled entirely in ANALYSIS. Frame statuses become:
- **EXPLORED** — the frame was substantively investigated
- **NOTED** — the frame was acknowledged but not deeply explored
- **UNEXPLORED** — the frame was identified but not investigated

**Synthesis contract:** Produces a structured analysis map per dimension. Header: "EXPLORATORY MAP — NOT A DECISION." Output structure:
- Framing of the question
- Aspect map (by dimension)
- Competing hypotheses or lenses
- Evidence for and against each
- Unresolved uncertainties
- What information would most change the map

### 4.4 ANALYSIS Gate 2 Rules

Replacing consensus rules with coverage accounting:

- **A1:** Missing PreflightAssessment -> ERROR
- **A2:** Evidence ledger empty AND search was recommended -> ESCALATE
- **A3:** Any mandatory dimension (from Dimension Seeder) has zero arguments -> ESCALATE
- **A4:** Total arguments < 8 -> ESCALATE
- **A5:** Otherwise -> ANALYSIS

### 4.5 proof.json Additions

- Replace `positions` section with `analysis_map` (keyed by dimension)
- Add `dimension_coverage_score` = (dimensions with >= 2 arguments) / (total dimensions)
- Add `hypothesis_ledger` tracking competing explanatory models with evidence bindings

### 4.6 Implementation Staging

Define the ANALYSIS Gate 2 rules (A1-A5) upfront. Deploy with a `debug_mode: true` flag in proof.json for the first N runs:
- Rules log what they would do without enforcing
- Pipeline outputs ANALYSIS based on synthesis contract alone
- proof.json records both the debug gate result and the actual output

Harden rules (remove debug flag) after observing real runs and confirming the rules produce correct outcomes. This gets architectural correctness (Gate 2 is the real modality switch) with deployment safety (don't break DECIDE while learning).

---

## Design Decisions Record

| # | Decision | Chosen | Alternatives considered |
|---|---|---|---|
| 1 | Evidence eviction fix | Two-tier ledger (active + archive) | Cascade eviction (Brain V8), Eviction immunity (Gemini) |
| 2 | R1 breadth mechanism | Dimension Seeder + Perspective Cards | Seeder only (ChatGPT), Functional Hats (Gemini) |
| 3 | Frame survival R3/R4 | CONTESTED status (not dropped, not frozen) | 2-vote drop (current), Frozen ACTIVE (Claude) |
| 4 | Argument tracking | Resolution status tags (ORIGINAL/REFINED/SUPERSEDED) | Full genealogy (ChatGPT), Keep current (Brain V8) |
| 5 | ANALYSIS staging | Gate 2 rules + DEBUG flag | Synthesis variant first (Claude), Gate 2 immediate (Gemini) |
| 6 | Gate 1 + CS Audit | Merge into PreflightAssessment | Keep separate + dual audit (Brain V8) |
| 7 | Gate 2 enhancements | Add reason + assumption stability tests | Current rules sufficient (Brain V8) |

---

## Requirements Traceability

| Requirement | Design section |
|---|---|
| R0: Enough context to reason about | 1.1 PreflightAssessment, 1.1 hidden_context_gaps |
| R1: Multiple independent opinions | 2.1 Dimension Seeder, 2.2 Perspective Cards |
| R2: Grounded in evidence | 3.1 Two-tier ledger, 3.3 Semantic contradiction, 1.5 Ungrounded Stat Detector |
| R3: Honest about disagreement | 2.3 Frame survival, 3.4 Argument resolution status, 3.7 Stability tests |
| R4: Knows when it can't decide | 4.4 ANALYSIS Gate 2, 1.2 Taxonomy fix |

---

## DESIGN-V3.0B.md (candidate improvements)

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

---

## DOD-V3.md (baseline DOD)

# Brain V8 — Definition of Done v3.0

**Date:** 2026-04-02
**Status:** Draft — pending multi-platform synthesis confirmation
**Scope:** Full rewrite. Self-contained. Covers the entire expanded platform.
**Source:** DESIGN-V3.md + two-pass multi-platform deliberation (Brain V8 + ChatGPT + Gemini + Claude)
**proof_version:** "3.0"

---

## 1. Authoritative Outcome Contract

### 1.1 Allowed Outcomes

Brain V8 SHALL emit only these outcomes:

| Outcome | Modality | Meaning |
|---|---|---|
| DECIDE | DECIDE | Models converged, evidence supports it, stability verified |
| ESCALATE | DECIDE / ANALYSIS | Partial consensus, unresolved material issues, or insufficient coverage |
| NO_CONSENSUS | DECIDE | Fundamental disagreement — irreducible split |
| ANALYSIS | ANALYSIS | Exploratory map complete with sufficient coverage |
| NEED_MORE | Universal (pre-run) | Brief lacks context — returned by PreflightAssessment only |
| ERROR | Universal | Infrastructure failure or fatal integrity violation |

### 1.2 Modality Contract

- DECIDE modality may emit: DECIDE, ESCALATE, NO_CONSENSUS, ERROR
- ANALYSIS modality may emit: ANALYSIS, ESCALATE, ERROR
- NEED_MORE is emitted only by PreflightAssessment, never by Gate 2
- ERROR is reserved exclusively for: (a) infrastructure failures (LLM/search unavailable), (b) fatal integrity violations (missing mandatory stages, unparseable outputs, schema corruption)
- ERROR SHALL NOT be used for bad user questions, invalid briefs, or malformed requests

### 1.3 SHORT_CIRCUIT Contract

SHORT_CIRCUIT is not a top-level outcome. It is an effort tier and execution policy within DECIDE modality. A successful short-circuit run emits DECIDE with `short_circuit_taken: true` in proof.json.

### 1.4 Fixed Topology

All admitted runs SHALL preserve the round topology 4→3→2→2 regardless of effort tier or modality.

### 1.5 Acceptance Criteria

- proof.outcome is one of the six allowed values
- proof.preflight.modality is DECIDE or ANALYSIS
- proof.topology.round_model_counts = [4, 3, 2, 2] on every admitted run
- NEED_MORE implies no R1 model was invoked
- ERROR implies proof.error_class in {INFRASTRUCTURE, FATAL_INTEGRITY}

### 1.6 Failure Modes

| Failure | Outcome |
|---|---|
| Outcome outside allowed taxonomy | ERROR |
| Admitted run violates 4→3→2→2 | ERROR |
| NEED_MORE emitted after R1 begins | ERROR |
| SHORT_CIRCUIT treated as top-level outcome | ERROR |
| Modality mismatch (DECIDE rules applied to ANALYSIS run or vice versa) | ERROR |

**Traceability:** R4

---

## 2. Base Requirements

| Req | Meaning | Enforced by |
|---|---|---|
| R0 | Enough context to reason about | PreflightAssessment, hidden_context_gaps, critical_assumptions, fatal_premise routing |
| R1 | Multiple independent opinions | 4→3→2→2 topology, Dimension Seeder, Perspective Cards, R2 frame enforcement |
| R2 | Grounded in evidence | Search, evidence ledger, claim bindings, contradiction detection, ungrounded stat detection |
| R3 | Honest about disagreement | Frame survival, blocker lifecycle, contradiction ledger, argument resolution status, stability tests |
| R4 | Knows when it can't decide | NEED_MORE routing, ESCALATE/NO_CONSENSUS rules, ANALYSIS branch |

Every section in this DoD traces to at least one of R0–R4.

---

## 3. Determinism and Stage Integrity

### 3.1 Determinism Rule

Given identical proof.json state, Gate 2 MUST emit the same outcome. Gate 2 SHALL NOT invoke an LLM.

### 3.2 Mandatory Stages (admitted runs)

PreflightAssessment → DimensionSeeder → R1 → R2 → R3 → R4 → Synthesis → Gate2

Additional mandatory stages when applicable:
- DivergentFramingPass: when proof.divergence.required = true
- SemanticContradictionPass: when shortlist criteria are met
- UngroundedStatDetector: after R1 and after R2 on DECIDE runs

### 3.3 Fatal Integrity Definition

A fatal integrity failure exists if any of:
- Required stage missing or executed out of order
- Required stage output absent or unparseable
- Round count mismatch against 4→3→2→2
- Branch-required proof object missing
- Synthesis disposition objects missing for tracked open findings
- Proof schema invalid for any field used by Gate 2

### 3.4 Acceptance Criteria

- proof.stage_integrity.all_required_present = true
- proof.stage_integrity.order_valid = true
- proof.stage_integrity.fatal = false on all non-ERROR runs

### 3.5 Failure Modes

| Failure | Outcome |
|---|---|
| Missing required stage | ERROR |
| Invalid stage order | ERROR |
| Missing branch-required proof object | ERROR |
| Round count mismatch | ERROR |
| Unparseable required stage output | ERROR |

**Traceability:** R1, R4

---

## 4. PreflightAssessment

### 4.1 Purpose

Single merged stage replacing Gate 1 + CS Audit. Handles admission, modality selection, effort calibration, defect typing, hidden-context discovery, assumption surfacing, and search scope selection.

### 4.2 Required Output Schema

proof.preflight SHALL contain:

| Field | Type | Required | Notes |
|---|---|---|---|
| executed | bool | always | true on all runs |
| parse_ok | bool | always | false → ERROR |
| answerability | enum | always | ANSWERABLE, NEED_MORE, INVALID_FORM |
| question_class | enum | always | TRIVIAL, WELL_ESTABLISHED, OPEN, AMBIGUOUS |
| stakes_class | enum | always | LOW, STANDARD, HIGH |
| effort_tier | enum | always | SHORT_CIRCUIT, STANDARD, ELEVATED |
| modality | enum | always | DECIDE, ANALYSIS |
| search_scope | enum | always | NONE, TARGETED, BROAD |
| exploration_required | bool | always | |
| short_circuit_allowed | bool | always | |
| fatal_premise | bool | always | |
| follow_up_questions | array[string] | when NEED_MORE | specific, user-addressable |
| premise_flags | array[object] | always | may be empty |
| hidden_context_gaps | array[object] | always | may be empty |
| critical_assumptions | array[object] | always | 3-5 items on admitted runs |

Each premise_flags[] item:

| Field | Type |
|---|---|
| flag_id | string (PFLAG-N) |
| flag_type | enum (INTERNAL_CONTRADICTION, UNSUPPORTED_ASSUMPTION, AMBIGUITY, IMPOSSIBLE_REQUEST, FRAMING_DEFECT) |
| severity | enum (INFO, WARNING, CRITICAL) |
| summary | string |
| routing | enum (REQUESTER_FIXABLE, MANAGEABLE_UNKNOWN, FRAMING_DEFECT, FATAL_PREMISE) |
| blocking | bool |
| resolved | bool |
| resolved_stage | string or null |

Each hidden_context_gaps[] item:

| Field | Type |
|---|---|
| gap_id | string |
| description | string |
| impact_if_unresolved | string |
| material | bool |
| resolved | bool |

Each critical_assumptions[] item:

| Field | Type |
|---|---|
| assumption_id | string |
| text | string |
| verifiability | enum (VERIFIABLE, UNVERIFIABLE, FALSE, UNKNOWN) |
| material | bool |
| resolved | bool |

### 4.3 Defect Routing

- REQUESTER_FIXABLE → NEED_MORE with specific follow_up_questions
- MANAGEABLE_UNKNOWN → inject as debate obligation + register as blocker
- FRAMING_DEFECT → inject reframed version into R1, force engagement
- FATAL_PREMISE → NEED_MORE with fatal_premise: true
- INVALID_FORM is a diagnostic label; its outcome is always NEED_MORE, never ERROR

### 4.4 Admission Guards

- short_circuit_allowed = true ONLY when: question_class in {TRIVIAL, WELL_ESTABLISHED} AND stakes_class = LOW AND no CRITICAL premise flags AND no material unresolved hidden_context_gaps
- effort_tier = ELEVATED when: stakes_class = HIGH OR question_class = AMBIGUOUS OR any CRITICAL premise flag exists
- Any critical_assumption with verifiability in {UNVERIFIABLE, FALSE} and material = true prevents admission → NEED_MORE

### 4.5 Failure Modes

| Failure | Outcome |
|---|---|
| Missing/unparseable preflight output | ERROR |
| Requester-fixable defect admitted to deliberation | ERROR |
| Fatal premise not returned as NEED_MORE | ERROR |
| Invalid brief mapped to ERROR without infrastructure failure | ERROR |
| Material false/unverifiable assumption admitted | NEED_MORE |

**Traceability:** R0, R4

---

## 5. Effort Policy and SHORT_CIRCUIT

### 5.1 Dynamic Token Budgeting

proof.budgeting SHALL contain:

| Field | Type | Required |
|---|---|---|
| effort_tier | enum | always |
| per_round_token_budgets | object | always |
| search_budget_policy | enum | always |
| speculative_expansion_allowed | bool | always |
| high_authority_evidence_required | bool | always |
| short_circuit_taken | bool | always |
| fallback_from_short_circuit | bool | always |

### 5.2 SHORT_CIRCUIT Requirements

When short_circuit_taken = true:
- Topology remains 4→3→2→2
- Search budget is reduced; speculative expansion is disabled
- Every round is instructed to either confirm the trivial answer or surface a hidden defect
- DECIDE is permitted ONLY if high_authority_evidence_required is satisfied (at least one high-authority evidence item in archive when search_scope != NONE)
- If search_scope = NONE AND question_class = TRIVIAL, zero evidence is acceptable
- If high-authority evidence is absent when required, run falls back to full deliberation

### 5.3 Failure Modes

| Failure | Outcome |
|---|---|
| SHORT_CIRCUIT changes topology | ERROR |
| SHORT_CIRCUIT taken with violated guardrails (wrong class/stakes/flags) | ERROR |
| SHORT_CIRCUIT DECIDE without required evidence | ESCALATE |

**Traceability:** R0, R2, R4

---

## 6. Dimension Seeder

### 6.1 Required Schema

proof.dimensions SHALL contain:

| Field | Type | Required |
|---|---|---|
| seeded | bool | always on admitted runs |
| parse_ok | bool | always |
| items | array[object] | always |
| dimension_count | int | always |
| dimension_coverage_score | float | always |

Each dimensions.items[] entry:

| Field | Type |
|---|---|
| dimension_id | string |
| name | string |
| mandatory | bool |
| coverage_status | enum (ZERO, PARTIAL, SATISFIED) |
| argument_count | int |
| justified_irrelevance | bool |

### 6.2 Requirements

- Seeder generates 3–5 mandatory dimensions. Fewer than 3 → ERROR.
- All dimensions injected into all R1 prompts.
- A dimension counts as covered if: argument_count > 0 OR justified_irrelevance = true with recorded explanation. Silent omission is a blocker.
- dimension_coverage_score = (dimensions with argument_count ≥ 2) / (total mandatory dimensions)

### 6.3 Failure Modes

| Failure | Outcome |
|---|---|
| Seeder missing on admitted run | ERROR |
| Fewer than 3 dimensions | ERROR |
| Mandatory dimension ZERO coverage without irrelevance justification | ESCALATE (via COVERAGE_GAP blocker) |

**Traceability:** R1, R4

---

## 7. Perspective Cards (R1)

### 7.1 Required Schema

proof.perspective_cards SHALL contain one entry per R1 model:

| Field | Type |
|---|---|
| model_id | string |
| primary_frame | string |
| hidden_assumption_attacked | string |
| stakeholder_lens | string |
| time_horizon | enum (SHORT, MEDIUM, LONG) |
| failure_mode | string |
| coverage_obligation | enum (CONTRARIAN, MECHANISM_ANALYSIS, OPERATIONAL_RISK, OBJECTIVE_REFRAMING) |
| dimensions_addressed | array[string] |

### 7.2 Requirements

- Exactly 4 R1 cards exist (one per R1 model)
- All 5 structured fields present on each card
- Distinct coverage_obligation assigned across the 4 models

### 7.3 Failure Modes

| Failure | Outcome |
|---|---|
| Missing card or field | ERROR |
| Coverage obligation not assigned | ERROR |

**Traceability:** R1, R3

---

## 8. Divergence, Frame Survival, and Exploration Stress

### 8.1 Required Schema

proof.divergence SHALL contain:

| Field | Type | Required |
|---|---|---|
| required | bool | always |
| adversarial_slot_assigned | bool | always |
| adversarial_model_id | string or null | always |
| adversarial_assignment_type | enum or null | always |
| framing_pass_executed | bool | always |
| exploration_stress_triggered | bool | always |
| stress_seed_frames | array[object] | always |
| material_unrebutted_frame_count | int | always |

Each alt_frames[] item:

| Field | Type |
|---|---|
| frame_id | string (FRAME-N) |
| text | string |
| origin_round | int |
| origin_model | string |
| frame_type | enum (INVERSION, OBJECTIVE_REWRITE, PREMISE_CHALLENGE, CROSS_DOMAIN_ANALOGY, OPPOSITE_STANCE, REMOVE_PROBLEM) |
| material_to_outcome | bool |
| survival_status | enum (ACTIVE, CONTESTED, DROPPED, ADOPTED, REBUTTED) |
| r2_drop_vote_count | int |
| r2_drop_vote_refs | array[string] |
| rebuttal_status | enum (NONE, PARTIAL, REBUTTED) |
| synthesis_disposition_status | enum (ADDRESSED, UNADDRESSED) |

**Material frame definition:** A frame is material if: (a) it is linked to a Dimension Seeder output, OR (b) it is adopted by ≥2 models in R2.

### 8.2 Frame Survival Rules

- R2: frame DROPPED only if all 3 R2 models cast traceable drop votes (each citing an argument_id or evidence_id). r2_drop_vote_count < 3 → frame stays non-dropped.
- R3/R4: frames CANNOT be dropped. Status moves to CONTESTED if not rebutted.
- R2 frame enforcement: each R2 model MUST adopt one frame, rebut one frame, and generate one new frame.
- Drop votes do NOT feed into agreement_ratio.

### 8.3 Exploration Stress Trigger

Condition: R1 agreement_ratio > 0.75 AND (question_class = OPEN OR stakes_class = HIGH) — this is a union, not intersection.

When triggered:
- 2-3 seed frames injected into R2 prompts
- exploration_stress_triggered = true in proof

### 8.4 Failure Modes

| Failure | Outcome |
|---|---|
| Divergence required but adversarial slot missing | ERROR |
| Divergence required but framing pass missing | ERROR |
| Frame dropped with < 3 traceable R2 votes | ERROR |
| Material frame disappears from lineage | ERROR |
| Material frame ACTIVE/CONTESTED without rebuttal at synthesis | ESCALATE |
| Stress trigger met but no seed frames injected | ERROR |
| R2 adopt/rebut/generate obligation missing | ERROR |

**Traceability:** R1, R3, R4

---

## 9. Search, Provenance, and Ungrounded Stat Detection

### 9.1 Search Log Schema

proof.search_log SHALL be an array:

| Field | Type |
|---|---|
| query_id | string |
| query_text | string |
| provenance | enum (model_claim, premise_defect, frame_test, evidence_gap, ungrounded_stat) |
| issued_after_stage | string |
| pages_fetched | int |
| evidence_yield_count | int |
| query_status | enum (SUCCESS, ZERO_RESULT, FAILED, SKIPPED) |

### 9.2 Ungrounded Stat Detector Schema

proof.ungrounded_stats SHALL contain:

| Field | Type | Required |
|---|---|---|
| post_r1_executed | bool | DECIDE admitted runs |
| post_r2_executed | bool | DECIDE admitted runs |
| flagged_claims | array[object] | always |

Each flagged_claims[] item:

| Field | Type |
|---|---|
| claim_id | string |
| text | string |
| numeric | bool |
| verified | bool |
| blocker_id | string or null |
| severity | enum |
| status | enum (CLEAR, UNVERIFIED_CLAIM) |

### 9.3 Requirements

- Every search query logged with provenance and query_status
- Zero-result queries still logged (query_status = ZERO_RESULT)
- Search subsystem failure → query_status = FAILED → ERROR if critical
- Ungrounded Stat Detector runs after R1 and R2 on DECIDE admitted runs
- Post-R3 unresolved material unverified numeric claim → UNVERIFIED_CLAIM blocker

### 9.4 Failure Modes

| Failure | Outcome |
|---|---|
| Query executed but not logged | ERROR |
| Missing provenance on query | ERROR |
| Ungrounded stat detector skipped on DECIDE run | ERROR |
| Search subsystem failure | ERROR |
| Material unverified claim unresolved at Gate 2 | ESCALATE |

**Traceability:** R2, R4

---

## 10. Two-Tier Evidence Ledger

### 10.1 Required Schema

proof.evidence SHALL contain:

| Field | Type | Required |
|---|---|---|
| active_working_set | array[object] | always |
| archive | array[object] | always |
| active_count | int | always |
| archive_count | int | always |
| eviction_log | array[object] | always |
| high_authority_evidence_present | bool | always |

Each evidence item (in both stores):

| Field | Type |
|---|---|
| evidence_id | string (E001, E002...) |
| source_url | string |
| topic_cluster | string |
| authority_tier | enum |
| is_active | bool |
| is_archived | bool |
| referenced_by | array[string] |

Each eviction_log[] item:

| Field | Type |
|---|---|
| event_id | string |
| evidence_id | string |
| from_active | bool |
| to_archive | bool |
| reason | string |

### 10.2 Requirements

- Active working set capped at 10
- Archive uncapped — never deletes anything
- Evidence moves from active to archive but never disappears from system
- Every cited evidence item exists in either active or archive
- Gate 2 reasons over archive-backed truth, not just active set

### 10.3 Failure Modes

| Failure | Outcome |
|---|---|
| Active exceeds 10 | ERROR |
| Evidence deleted rather than archived | ERROR |
| Cited evidence missing from both stores | ERROR |
| SHORT_CIRCUIT DECIDE without required high-authority evidence | ESCALATE |

**Traceability:** R2, R4

---

## 11. Argument Tracker and Resolution Status

### 11.1 Required Schema

proof.arguments SHALL be an object map keyed by argument_id:

| Field | Type |
|---|---|
| argument_id | string (R{round}-ARG-{n}) |
| round_origin | int |
| model_id | string |
| dimension_id | string |
| text | string |
| resolution_status | enum (ORIGINAL, REFINED, SUPERSEDED) |
| superseded_by | string or null |
| blocker_link_ids | array[string] |
| evidence_refs | array[string] |
| open | bool |

### 11.2 Requirements

- Every argument has a stable unique ID
- REFINED arguments link to the argument they refine
- SUPERSEDED arguments have superseded_by != null pointing to the replacing argument
- Restatement without explicit linkage is NOT resolution
- Open material arguments at synthesis require structured dispositions

### 11.3 Failure Modes

| Failure | Outcome |
|---|---|
| Argument disappears without resolution status | ERROR |
| Supersession link broken (superseded_by points to nonexistent ID) | ERROR |
| Open material argument omitted from synthesis disposition | ESCALATE |
| Restated argument treated as resolved without lineage | ESCALATE |

**Traceability:** R3, R4

---

## 12. Contradictions

### 12.1 Required Schema

proof.contradictions SHALL contain:

| Field | Type | Required |
|---|---|---|
| numeric_records | array[object] | always |
| semantic_records | array[object] | always |
| semantic_pass_executed | bool | always |

Each contradiction record:

| Field | Type |
|---|---|
| ctr_id | string (CTR-N) |
| detection_mode | enum (NUMERIC, SEMANTIC) |
| evidence_ref_a | string |
| evidence_ref_b | string |
| same_entity | bool |
| same_timeframe | bool |
| severity | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| status | enum (OPEN, RESOLVED, NON_MATERIAL) |
| justification | string |
| linked_claim_ids | array[string] |

### 12.2 Semantic Contradiction Shortlist Criteria

A pair is shortlisted when: same topic cluster AND (opposite polarity cues OR same entity + same timeframe) AND at least one member linked to a decisive claim, blocker, or open contradiction.

### 12.3 Failure Modes

| Failure | Outcome |
|---|---|
| Semantic pass required but skipped | ERROR |
| Unresolved HIGH/CRITICAL contradiction | ESCALATE |

**Traceability:** R2, R3

---

## 13. Blockers and Decisive Claims

### 13.1 Blocker Schema

proof.blockers[] items:

| Field | Type |
|---|---|
| blocker_id | string (BLK-N) |
| type | enum (EVIDENCE_GAP, CONTRADICTION, UNRESOLVED_DISAGREEMENT, CONTESTED_POSITION, COVERAGE_GAP, UNVERIFIED_CLAIM) |
| severity | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| status | enum (OPEN, RESOLVED, DEFERRED) |
| linked_ids | array[string] |
| resolution_summary | string or null |

### 13.2 Decisive Claims Schema (DECIDE only)

proof.decisive_claims[] items:

| Field | Type |
|---|---|
| claim_id | string |
| text | string |
| material_to_conclusion | bool |
| evidence_refs | array[string] |
| evidence_support_status | enum (SUPPORTED, PARTIAL, UNSUPPORTED) |
| analogy_refs | array[string] |

### 13.3 Cross-Domain Analogies

proof.cross_domain_analogies[] items:

| Field | Type |
|---|---|
| analogy_id | string |
| source_domain | string |
| target_claim_id | string |
| transfer_mechanism | string |
| test_status | enum (UNTESTED, SUPPORTED, REJECTED) |

An analogy with test_status = UNTESTED SHALL NOT carry decisive factual load.

### 13.4 Failure Modes

| Failure | Outcome |
|---|---|
| Decisive claim missing evidence_support_status | ERROR |
| Decisive claim SUPPORTED with zero evidence_refs | ERROR |
| Untested analogy used decisively | ESCALATE |
| Unresolved CRITICAL blocker at Gate 2 | ESCALATE |

**Traceability:** R2, R3, R4

---

## 14. Synthesis Packet and Residue Verification

### 14.1 Synthesis Packet Schema

proof.synthesis_packet SHALL contain:

| Field | Type | Required |
|---|---|---|
| final_positions | array[object] | DECIDE |
| argument_lifecycle | array[object] | always (max 20) |
| frame_summary | array[object] | always |
| blocker_summary | array[object] | always |
| decisive_claim_bindings | array[object] | DECIDE |
| contradiction_summary | array[object] | always |
| premise_flag_summary | array[object] | always |
| packet_complete | bool | always |

### 14.2 Structured Dispositions

proof.synthesis_output.dispositions SHALL contain arrays for: blockers, frames, claims, contradictions.

Each disposition object:

| Field | Type |
|---|---|
| target_type | enum (BLOCKER, FRAME, CLAIM, CONTRADICTION) |
| target_id | string |
| status | string |
| importance | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| narrative_explanation | string |
| evidence_refs | array[string] |

### 14.3 Orphaned Evidence Obligation

If archive contains evidence with authority_tier = HIGH that is NOT cited in any decisive claim, blocker, contradiction, or synthesis disposition, synthesis MUST explain why it was non-decisive.

### 14.4 Residue Verification Schema

proof.residue_verification SHALL contain:

| Field | Type |
|---|---|
| expected_disposition_count | int |
| emitted_disposition_count | int |
| omission_rate | float |
| deep_scan_triggered | bool |
| coverage_pass | bool |

### 14.5 Requirements

- Synthesis receives controller-curated state bundle (not just R4 outputs)
- Every tracked open finding gets a disposition object
- omission_rate > 0.20 triggers deep semantic scan
- coverage_pass = true required on all non-ERROR runs

### 14.6 Failure Modes

| Failure | Outcome |
|---|---|
| Synthesis packet missing controller-curated state | ERROR |
| Disposition missing for tracked open finding | ERROR |
| Deep scan threshold exceeded but scan not run | ERROR |
| Material omissions unresolved after deep scan | ESCALATE |

**Traceability:** R2, R3, R4

---

## 15. Stability Tests (DECIDE only)

### 15.1 Required Schema

proof.stability SHALL contain:

| Field | Type | Required |
|---|---|---|
| conclusion_stable | bool | DECIDE |
| reason_stable | bool | DECIDE |
| assumption_stable | bool | DECIDE |
| independent_evidence_present | bool | DECIDE |
| fast_consensus_observed | bool | DECIDE (true if R1 agreement_ratio ≥ 0.95) |
| groupthink_warning | bool | DECIDE |

### 15.2 Definitions

- **conclusion_stable:** Final surviving models converge on the same recommendation after supersession filtering
- **reason_stable:** Models converge for the same reasons (shared decisive claim set and evidence bindings)
- **assumption_stable:** Models rely on the same set of unresolved assumptions
- **groupthink_warning:** fast_consensus_observed = true AND (question_class = OPEN OR stakes_class = HIGH) AND independent_evidence_present = false

### 15.3 Requirements

- Stability fields are boolean Gate 2 inputs
- Computation method for each boolean is specified in the implementation spec, not the DoD
- All three stability booleans present on every DECIDE run

**Traceability:** R3, R4

---

## 16. Gate 2 — DECIDE Rules (D1–D14)

Evaluated in order. First match determines outcome.

| Rule | Condition | Outcome |
|---|---|---|
| D1 | Fatal integrity or infrastructure failure | ERROR |
| D2 | Modality mismatch (preflight.modality ≠ DECIDE) | ERROR |
| D3 | Illegal SHORT_CIRCUIT state (guardrails violated) | ERROR |
| D4 | agreement_ratio < 0.50 | NO_CONSENSUS |
| D5 | agreement_ratio ≥ 0.50 and < 0.75 | ESCALATE |
| D6 | Any unresolved CRITICAL blocker (includes COVERAGE_GAP, UNVERIFIED_CLAIM) | ESCALATE |
| D7 | Any decisive claim lacks valid evidence binding (evidence_support_status ≠ SUPPORTED) | ESCALATE |
| D8 | Any HIGH/CRITICAL contradiction unresolved | ESCALATE |
| D9 | Any unresolved CRITICAL premise flag | ESCALATE |
| D10 | Any material frame ACTIVE/CONTESTED without rebuttal and without synthesis disposition | ESCALATE |
| D11 | conclusion_stable = false | NO_CONSENSUS |
| D12 | reason_stable = false OR assumption_stable = false | ESCALATE |
| D13 | groupthink_warning = true AND independent_evidence_present = false | ESCALATE |
| D14 | Otherwise | DECIDE |

### Requirements

- Same proof state → same outcome (deterministic)
- Frame drop votes do NOT affect agreement_ratio
- Rule order is preserved exactly
- gate2.rule_trace[] records which rule fired

### Gate 2 Trace Schema

proof.gate2 SHALL contain:

| Field | Type |
|---|---|
| modality | enum (DECIDE, ANALYSIS) |
| rule_trace | array[{rule_id, evaluated, fired, outcome_if_fired}] |
| final_outcome | enum |

**Traceability:** R2, R3, R4

---

## 17. Gate 2 — ANALYSIS Rules (A1–A7)

Evaluated in order. First match determines outcome.

| Rule | Condition | Outcome |
|---|---|---|
| A1 | Missing or invalid PreflightAssessment | ERROR |
| A2 | Modality mismatch (preflight.modality ≠ ANALYSIS) | ERROR |
| A3 | Missing required shared pipeline artifacts (dimension seeder, evidence, analysis_map, synthesis) | ERROR |
| A4 | Evidence archive empty AND search_scope ≠ NONE | ESCALATE |
| A5 | Any mandatory dimension has zero arguments | ESCALATE |
| A6 | Total arguments < 8 | ESCALATE |
| A7 | Otherwise | ANALYSIS |

### ANALYSIS Coverage Threshold

dimension_coverage_score ≥ 0.8 is the recommended operational floor. If score < 0.8 but all mandatory dimensions have at least some arguments (rule A5 passes), ANALYSIS is still permitted — the score is recorded for diagnostic purposes.

**Traceability:** R1, R2, R4

---

## 18. ANALYSIS Mode Contract

### 18.1 Shared Pipeline

ANALYSIS reuses: PreflightAssessment, 4→3→2→2 topology, Search, Evidence Ledger, Argument Tracker, Divergent Framing Pass, Invariant Validator, proof.json base schema.

### 18.2 Modified Behavior

- Round prompts: "deepen exploration by dimension — identify knowns, inferred, unknowns. Do not seek agreement."
- Frame survival: dropping disabled entirely. Statuses: EXPLORED, NOTED, UNEXPLORED.
- Position Tracker runs diagnostically (proof.diagnostics.positions) — does NOT drive outcomes.
- Adversarial assignment not required (but frame tracking remains).

### 18.3 Analysis Map Schema

proof.analysis_map SHALL contain:

| Field | Type |
|---|---|
| header | string ("EXPLORATORY MAP — NOT A DECISION") |
| dimensions | object (keyed by dimension_id) |
| dimension_coverage_score | float |
| hypothesis_ledger | array[object] |
| total_argument_count | int |

Each dimension entry:

| Field | Type |
|---|---|
| knowns | array[string] |
| inferred | array[string] |
| unknowns | array[string] |
| evidence_for | array[string] |
| evidence_against | array[string] |
| competing_lenses | array[string] |
| argument_count | int |

Each hypothesis entry:

| Field | Type |
|---|---|
| hypothesis_id | string |
| dimension_id | string |
| text | string |
| evidence_refs | array[string] |
| status | enum (SUPPORTED, MIXED, WEAK, UNKNOWN) |

### 18.4 Implementation Staging

proof.analysis_debug SHALL contain (during staged rollout):

| Field | Type | Required |
|---|---|---|
| debug_mode | bool | always on staged runs |
| debug_gate2_result | enum or null | when debug_mode = true |
| actual_output | enum | when debug_mode = true |
| rules_enforced | bool | when debug_mode = true |
| remaining_debug_runs | int | when debug_mode = true |

**DEBUG sunset:** debug_mode automatically disables when remaining_debug_runs reaches 0. Leaving DEBUG on after counter expires → ERROR.

### 18.5 Failure Modes

| Failure | Outcome |
|---|---|
| ANALYSIS output contains verdict language instead of exploratory map | ERROR |
| Frame dropping occurs in ANALYSIS mode | ERROR |
| analysis_map missing on ANALYSIS run | ERROR |
| analysis_map.header ≠ "EXPLORATORY MAP — NOT A DECISION" | ERROR |
| Debug mode active after sunset | ERROR |

**Traceability:** R1, R4

---

## 19. proof.json Top-Level Schema

| Field | Type | Required |
|---|---|---|
| proof_version | string ("3.0") | always |
| run_id | string | always |
| timestamp_started | string | always |
| timestamp_completed | string | always |
| topology | object | always |
| outcome | object | always |
| error_class | enum or null | always |
| stage_integrity | object | always |
| config_snapshot | object | always |
| preflight | object | always |
| budgeting | object | always |
| dimensions | object | admitted runs |
| perspective_cards | array | admitted runs |
| rounds | object | admitted runs |
| divergence | object | admitted runs |
| search_log | array | admitted runs |
| ungrounded_stats | object | DECIDE admitted runs |
| evidence | object | admitted runs |
| arguments | object (map) | admitted runs |
| blockers | array | admitted runs |
| decisive_claims | array | DECIDE runs |
| cross_domain_analogies | array | admitted runs |
| contradictions | object | admitted runs |
| synthesis_packet | object | admitted runs |
| synthesis_output | object | admitted runs |
| residue_verification | object | admitted runs |
| positions | object | DECIDE runs |
| stability | object | DECIDE runs |
| analysis_map | object | ANALYSIS runs |
| analysis_debug | object | staged ANALYSIS runs |
| diagnostics | object | always (optional diagnostic data) |
| gate2 | object | admitted runs |

**Traceability:** R2, R4

---

## 20. Verification and Test Suite

| Test | Verifies |
|---|---|
| Preflight requester-fixable defect → NEED_MORE | Correct defect routing |
| Preflight fatal premise → NEED_MORE + fatal_premise=true | Fatal premise routing |
| Preflight INVALID_FORM → NEED_MORE, not ERROR | Taxonomy compliance |
| Missing preflight field → ERROR | Schema integrity |
| SHORT_CIRCUIT preserves 4→3→2→2 | Fixed topology |
| SHORT_CIRCUIT without high-authority evidence → ESCALATE | Evidence guardrail |
| SHORT_CIRCUIT with violated guardrails → ERROR | Integrity check |
| Seeder emits 3–5 dimensions; <3 → ERROR | Breadth seeding |
| Zero-covered mandatory dimension → blocker → ESCALATE | Coverage gap |
| Justified irrelevance counts as covered | Dimension coverage |
| All four R1 cards contain 5 structured fields | Perspective Card completeness |
| Divergence required but missing adversarial slot → ERROR | Mandatory divergence |
| Single or double R2 drop vote does not drop frame | 3-vote rule |
| Three R2 drop votes with traceable refs → DROPPED | Drop threshold |
| R3/R4 cannot drop frames (CONTESTED only) | Late-round reform |
| Exploration stress trigger (union: OPEN OR HIGH) injects 2–3 seed frames | Suspicious consensus |
| Query provenance + query_status logged for all queries including zero-result | Search auditability |
| Material unverified numeric claim unresolved → ESCALATE | Ungrounded stat enforcement |
| Active evidence capped at 10; evicted item in archive | Two-tier ledger |
| Cited evidence missing from both stores → ERROR | Audit integrity |
| Semantic contradiction pass required but absent → ERROR | Contradiction integrity |
| Untested analogy used decisively → ESCALATE | Analogy restriction |
| Restated argument without lineage not counted as resolution | Argument resolution |
| Orphaned high-relevance evidence requires synthesis explanation | Evidence accountability |
| Missing disposition for open material finding → ERROR | Residue verification |
| Omission rate >20% triggers deep scan | Residue depth |
| conclusion_stable=false → NO_CONSENSUS | Stability rule D11 |
| reason/assumption unstable → ESCALATE | Stability rule D12 |
| Groupthink warning + no independent evidence → ESCALATE | Stability rule D13 |
| ANALYSIS A5: zero-argument dimension → ESCALATE | Coverage rule |
| ANALYSIS A6: total arguments <8 → ESCALATE | Minimum floor |
| ANALYSIS frame dropping → ERROR | Mode contract |
| ANALYSIS debug mode records both debug and actual results | Staged rollout |
| Debug mode active after sunset → ERROR | Sunset enforcement |
| Same proof state twice → same Gate 2 result | Determinism |
| proof_version = "3.0" on all v3.0 runs | Schema versioning |
| Modality mismatch → ERROR | Controller contract |

**Traceability:** R0–R4

---

## 21. Consolidated Failure-Mode Matrix

| Mechanism | Failure | Outcome |
|---|---|---|
| PreflightAssessment | missing/unparseable | ERROR |
| Defect routing | requester-fixable or fatal premise admitted | ERROR / NEED_MORE |
| Assumptions | material false/unverifiable unresolved | NEED_MORE |
| SHORT_CIRCUIT | guardrails violated | ERROR |
| SHORT_CIRCUIT | no required evidence | ESCALATE |
| Token budgeting | policy missing | ERROR |
| Dimension Seeder | missing / <3 dimensions | ERROR |
| Perspective Cards | missing fields | ERROR |
| Divergent Framing | required but absent | ERROR |
| Frame survival | dropped with <3 R2 votes | ERROR |
| Material frame | ACTIVE/CONTESTED unaddressed | ESCALATE |
| Exploration stress | trigger met, no seed frames | ERROR |
| Search log | query not logged / missing provenance | ERROR |
| Search subsystem | infrastructure failure | ERROR |
| Ungrounded stats | material unverified claim unresolved | ESCALATE |
| Evidence ledger | evidence deleted / cited missing | ERROR |
| Synthesis packet | controller state absent | ERROR |
| Semantic contradiction | required but skipped | ERROR |
| Contradiction | HIGH/CRITICAL unresolved | ESCALATE |
| Argument tracking | restatement counted as resolution | ESCALATE |
| Argument tracking | supersession link broken | ERROR |
| Residue verification | material omissions | ESCALATE |
| Stability tests | conclusion unstable | NO_CONSENSUS |
| Stability tests | reason/assumption unstable | ESCALATE |
| ANALYSIS map | missing or wrong contract | ERROR |
| ANALYSIS coverage | empty evidence + search recommended / zero-arg dimension / <8 total | ESCALATE |
| Debug sunset | debug active after expiry | ERROR |

---

## 22. Definition of Done — Final Pass Condition

Brain V8 v3.0 is Done only if ALL of the following are true:

1. PreflightAssessment executes exactly once before R1 and routes all defects per typed routing rules
2. Every admitted run preserves topology 4→3→2→2
3. All mechanisms implemented and recorded in proof.json: PreflightAssessment, Dimension Seeder, Perspective Cards, frame survival reform, exploration stress trigger, two-tier evidence ledger, controller-curated synthesis, semantic contradiction detection, argument resolution status, search provenance, ungrounded stat detection, residue verification, stability tests, ANALYSIS mode, staged ANALYSIS Gate 2, dynamic token budgeting
4. Gate 2 is fully deterministic and evaluable from proof.json alone, with rule_trace recorded
5. ERROR is emitted only for infrastructure or fatal integrity failure
6. NEED_MORE is emitted only from PreflightAssessment
7. DECIDE runs cannot pass with unresolved material evidence, premise, frame, contradiction, or support defects
8. ANALYSIS runs cannot pass without minimum coverage under A1–A7
9. proof_version = "3.0" on all runs
10. The verification suite in Section 20 passes
11. The complete proof.json contract in Section 19 is satisfied

---

## DOD-V3.0B.md (candidate DOD improvements)

# Brain V8 — Definition of Done V3.0B

**Date:** 2026-04-02
**Status:** Complete — produced via multi-platform deliberation (Claude + Brain V8 + ChatGPT 5.4 + Gemini Pro)
**Scope:** Full rewrite based on DESIGN-V3.0B. Self-contained.
**Source:** DESIGN-V3.0B (multi-platform consensus, 2026-04-02)
**proof_version:** "3.0B"

---

## 1. Authoritative Outcome Contract

### 1.1 Allowed Outcomes

Brain V8 SHALL emit only these outcomes:

| Outcome | Modality | Meaning |
|---|---|---|
| DECIDE | DECIDE | Models converged, evidence supports it, stability verified |
| ESCALATE | DECIDE / ANALYSIS | Mechanism failures: pin cap reached, missing invariants, insufficient evidence, insufficient coverage |
| NO_CONSENSUS | DECIDE | Fundamental disagreement — irreducible split |
| ANALYSIS | ANALYSIS | Exploratory map complete with sufficient coverage |
| NEED_MORE | Universal (pre-run) | Brief lacks context — returned by Gate 1 only |
| ERROR | Universal | Infrastructure failure or fatal integrity violation |

### 1.2 Modality Contract

- DECIDE modality may emit: DECIDE, ESCALATE, NO_CONSENSUS, ERROR
- ANALYSIS modality may emit: ANALYSIS, ESCALATE, ERROR
- NEED_MORE is emitted only by Gate 1, never by Gate 2
- ERROR is reserved exclusively for: (a) infrastructure failures (LLM/search unavailable), (b) fatal integrity violations (missing mandatory stages, unparseable outputs, schema corruption)
- ERROR SHALL NOT be used for bad user questions, invalid briefs, or malformed requests

### 1.3 Three-Tier Failure Taxonomy

All failure conditions in Brain V8 are classified into exactly one of:

| Tier | Scope | Examples | Outcome |
|---|---|---|---|
| ERROR | Infrastructure and integrity ONLY | LLM unavailable, search down, missing mandatory stage, unparseable output, schema corruption, round count mismatch | ERROR |
| ESCALATE | Mechanism failures | Pin cap reached, missing invariants, insufficient evidence, unresolved CRITICAL blocker, coverage below threshold, residue violation | ESCALATE |
| WARNING | Suboptimal conditions (non-blocking) | Low diversity score (<2), pin budget >80% utilized, high eviction rate, argument auto-promotion triggered | Logged in proof.json; does NOT alter outcome |

"Zero tolerance" is scoped to infrastructure only. Mechanism failures produce ESCALATE. Suboptimal conditions produce WARNING.

### 1.4 SHORT_CIRCUIT Contract

SHORT_CIRCUIT is not a top-level outcome. It is an effort tier and execution policy within DECIDE modality. A successful short-circuit run emits DECIDE with `short_circuit_taken: true` in proof.json.

### 1.5 Fixed Topology

All admitted runs SHALL preserve the round topology 4→3→2→2 regardless of effort tier or modality.

### 1.6 Schema Versioning

- `proof.schema_version` MUST equal `"3.0B"` on all V3.0B runs
- New fields introduced in V3.0B are optional during the transition period (first 10 runs or until `transition_complete: true` set in config)
- Backward compatibility tests required: V3.0 proof files must parse without ERROR (unknown fields ignored, missing new fields tolerated)
- Schema version mismatch (proof generated under 3.0B rules but `schema_version` != `"3.0B"`) → ERROR

### 1.7 Acceptance Criteria

- proof.outcome is one of the six allowed values
- proof.schema_version == "3.0B"
- proof.gate1.modality is DECIDE or ANALYSIS
- proof.topology.round_model_counts = [4, 3, 2, 2] on every admitted run
- NEED_MORE implies no R1 model was invoked
- ERROR implies proof.error_class in {INFRASTRUCTURE, FATAL_INTEGRITY}
- Every failure condition maps to exactly one tier (ERROR / ESCALATE / WARNING)
- WARNING entries exist in proof.warnings[] and do NOT alter proof.outcome

### 1.8 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Outcome outside allowed taxonomy | ERROR | ERROR |
| Admitted run violates 4→3→2→2 | ERROR | ERROR |
| NEED_MORE emitted after R1 begins | ERROR | ERROR |
| SHORT_CIRCUIT treated as top-level outcome | ERROR | ERROR |
| Modality mismatch (DECIDE rules applied to ANALYSIS run or vice versa) | ERROR | ERROR |
| schema_version != "3.0B" on V3.0B run | ERROR | ERROR |
| Failure condition not classified into a tier | ERROR | ERROR |

**Traceability:** R0

---

## 2. Base Requirements

| Req | Meaning | Enforced by |
|---|---|---|
| R0 | Outcome contract, topology, integrity | Gate 1, CS Audit, schema validation, stage integrity checks |
| R1 | Admission, premise validation, effort calibration | Gate 1, CS Audit, perspective lenses, 4→3→2→2 topology |
| R2 | Exploration, search, evidence grounding | Search, evidence ledger, claim bindings, contradiction detection, ungrounded stat detection |
| R3 | Tracking, evidence management, contradiction handling, synthesis inputs | Argument Tracker, Position Tracker, Dimension Tracker, frame survival, blocker lifecycle, contradiction ledger |
| R4 | Terminal rules, synthesis output, modality reporting | Gate 2 rules, synthesis packet, residue verification, coverage assessment |

Every section in this DoD traces to at least one of R0-R4.

---

## 3. Determinism and Stage Integrity

### 3.1 Determinism Rule

Given identical proof.json state, Gate 2 MUST emit the same outcome. Gate 2 SHALL NOT invoke an LLM.

### 3.2 Mandatory Stages (admitted runs)

Gate 1 → CS Audit → Virtual Frame Seeder → R1 → DivergentFramingPass → R2 → R3 → R4 → Synthesis → Gate 2

Additional mandatory stages when applicable:
- RetroactivePremiseEscalation: after R1, when ≥2 models flag same flawed premise
- UngroundedStatDetector: after R1 and after R2 on DECIDE runs
- SemanticContradictionPass: when shortlist criteria are met
- CalibratedAntiGroupthinkSearch: when agreement_ratio > 0.80 AND question is OPEN/HIGH-stakes
- BreadthRecoveryPulse: when >40% of R1 arguments IGNORED in R2

### 3.3 Fatal Integrity Definition

A fatal integrity failure exists if any of:
- Required stage missing or executed out of order
- Required stage output absent or unparseable
- Round count mismatch against 4→3→2→2
- Branch-required proof object missing
- Synthesis disposition objects missing for tracked open findings
- Proof schema invalid for any field used by Gate 2
- Entity ID collision without resolution (see Section 8)

### 3.4 Required Schema

proof.stage_integrity SHALL contain:

| Field | Type | Required |
|---|---|---|
| all_required_present | bool | always |
| order_valid | bool | always |
| fatal | bool | always |
| stages_executed | array[string] | always |
| stages_expected | array[string] | always |

### 3.5 Acceptance Criteria

- proof.stage_integrity.all_required_present = true on all non-ERROR runs
- proof.stage_integrity.order_valid = true on all non-ERROR runs
- proof.stage_integrity.fatal = false on all non-ERROR runs
- Gate 1 and CS Audit appear as separate entries in stages_executed

### 3.6 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Missing required stage | ERROR | ERROR |
| Invalid stage order | ERROR | ERROR |
| Missing branch-required proof object | ERROR | ERROR |
| Round count mismatch | ERROR | ERROR |
| Unparseable required stage output | ERROR | ERROR |

**Traceability:** R0, R1

---

## 4. Gate 1 (Admission)

### 4.1 Purpose

Gate 1 is the first stage. It handles brief parsing, answerability assessment, and lightweight modality tagging. Gate 1 does NOT perform effort calibration or premise analysis — those are CS Audit responsibilities. Gate 1 and CS Audit are SEPARATE stages to limit failure blast radius.

### 4.2 Required Schema

proof.gate1 SHALL contain:

| Field | Type | Required | Notes |
|---|---|---|---|
| executed | bool | always | true on all runs |
| parse_ok | bool | always | false → ERROR |
| answerability | enum | always | ANSWERABLE, NEED_MORE, INVALID_FORM |
| modality | enum | always | DECIDE or ANALYSIS (lightweight tag) |
| follow_up_questions | array[string] | when NEED_MORE | specific, user-addressable |
| fatal_premise | bool | always | true → NEED_MORE |
| entity_ids_assigned | array[object] | always | initial claim/frame IDs assigned here |

### 4.3 Admission Guards

- ANSWERABLE → proceed to CS Audit
- NEED_MORE → return NEED_MORE with follow_up_questions; no further stages execute
- INVALID_FORM → return NEED_MORE (not ERROR); INVALID_FORM is a diagnostic label only
- fatal_premise = true → NEED_MORE regardless of other fields

### 4.4 Acceptance Criteria

- Gate 1 executes exactly once before CS Audit
- Gate 1 output is parseable and contains all required fields
- NEED_MORE runs have no R1 model invocations
- INVALID_FORM never produces ERROR
- Gate 1 assigns initial entity IDs to claims extracted from the brief

### 4.5 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Missing/unparseable gate1 output | ERROR | ERROR |
| Fatal premise not returned as NEED_MORE | ERROR | ERROR |
| Invalid brief mapped to ERROR without infrastructure failure | ERROR | ERROR |
| Gate 1 skipped or merged with CS Audit | ERROR | ERROR |

**Traceability:** R0, R1

---

## 5. CS Audit (Common Sense Calibration)

### 5.1 Purpose

CS Audit performs effort calibration, premise analysis, question classification, stakes assessment, search scope selection, defect typing, hidden-context discovery, and assumption surfacing. Runs after Gate 1, before R1.

### 5.2 Required Schema

proof.cs_audit SHALL contain:

| Field | Type | Required | Notes |
|---|---|---|---|
| executed | bool | always | true on all admitted runs |
| parse_ok | bool | always | false → ERROR |
| question_class | enum | always | TRIVIAL, WELL_ESTABLISHED, OPEN, AMBIGUOUS |
| stakes_class | enum | always | LOW, STANDARD, HIGH |
| effort_tier | enum | always | SHORT_CIRCUIT, STANDARD, ELEVATED |
| modality | enum | always | DECIDE or ANALYSIS (refined from Gate 1) |
| search_scope | enum | always | NONE, TARGETED, BROAD |
| exploration_required | bool | always | |
| short_circuit_allowed | bool | always | |
| premise_flags | array[object] | always | may be empty |
| hidden_context_gaps | array[object] | always | may be empty |
| critical_assumptions | array[object] | always | 3-5 items on admitted runs |
| reformulated_brief | string or null | always | non-null when auto-reformulation applied |
| original_brief | string | always | preserved even when reformulated |

Each premise_flags[] item:

| Field | Type |
|---|---|
| flag_id | string (PFLAG-N) |
| flag_type | enum (INTERNAL_CONTRADICTION, UNSUPPORTED_ASSUMPTION, AMBIGUITY, IMPOSSIBLE_REQUEST, FRAMING_DEFECT) |
| severity | enum (INFO, WARNING, CRITICAL) |
| summary | string |
| routing | enum (REQUESTER_FIXABLE, MANAGEABLE_UNKNOWN, FRAMING_DEFECT, FATAL_PREMISE) |
| blocking | bool |
| resolved | bool |
| resolved_stage | string or null |

Each hidden_context_gaps[] item:

| Field | Type |
|---|---|
| gap_id | string |
| description | string |
| impact_if_unresolved | string |
| material | bool |
| resolved | bool |

Each critical_assumptions[] item:

| Field | Type |
|---|---|
| assumption_id | string |
| text | string |
| verifiability | enum (VERIFIABLE, UNVERIFIABLE, FALSE, UNKNOWN) |
| material | bool |
| resolved | bool |

### 5.3 Effort-Tier Calibration (binding)

CS Audit's effort_tier output is binding on all downstream stages:

| Effort Tier | Prompt Depth | Search Scope | Evidence Cap | Synthesis |
|---|---|---|---|---|
| SHORT_CIRCUIT | Compressed (minimal protocol) | No search-request sections | Standard (10) | One-paragraph |
| STANDARD | Full | Full | Standard (10) | Full report |
| ELEVATED | Expanded + scrutiny sections | Expanded proactive queries | Raised (15) | Full report + extended |

### 5.4 Defect Routing

- REQUESTER_FIXABLE → NEED_MORE with specific follow_up_questions (returned via Gate 1)
- MANAGEABLE_UNKNOWN → inject as debate obligation + register as blocker
- FRAMING_DEFECT → inject reframed version into R1, force engagement
- FATAL_PREMISE → NEED_MORE with fatal_premise: true

### 5.5 Auto-Reformulation for Reparable Flaws

When CS Audit detects a fixable missing assumption (repairable premise defect):
- Append the assumption to the brief as explicit context
- Proceed to deliberation (do NOT return NEED_MORE)
- Log both original_brief and reformulated_brief in proof.json
- Surface reformulation in synthesis output

### 5.6 Admission Guards

- short_circuit_allowed = true ONLY when: question_class in {TRIVIAL, WELL_ESTABLISHED} AND stakes_class = LOW AND no CRITICAL premise flags AND no material unresolved hidden_context_gaps
- effort_tier = ELEVATED when: stakes_class = HIGH OR question_class = AMBIGUOUS OR any CRITICAL premise flag exists
- Any critical_assumption with verifiability in {UNVERIFIABLE, FALSE} and material = true prevents admission → NEED_MORE

### 5.7 Acceptance Criteria

- CS Audit executes exactly once, after Gate 1 and before R1
- CS Audit output contains all required fields
- effort_tier is binding: downstream stages respect the tier's prompt depth, search scope, and evidence cap
- Auto-reformulation preserves original_brief alongside reformulated_brief
- Reparable flaws do NOT produce NEED_MORE
- CS Audit modality tag may differ from Gate 1 modality tag (CS Audit refines)

### 5.8 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Missing/unparseable cs_audit output | ERROR | ERROR |
| Requester-fixable defect admitted to deliberation | ERROR | ERROR |
| Material false/unverifiable assumption admitted | ESCALATE | NEED_MORE |
| Effort tier not binding on downstream stages | ERROR | ERROR |
| Auto-reformulation without logging both briefs | ERROR | ERROR |

**Traceability:** R0, R1

---

## 6. Retroactive Premise Escalation

### 6.1 Purpose

After R1, the Argument Tracker scans for `premise_challenge` arguments. If >=2 models independently identify the same flawed premise, trigger a mid-pipeline re-run of the CS Audit. Catches premise defects that Gate 1 missed without adding latency to the happy path.

### 6.2 Required Schema

proof.retroactive_premise SHALL contain:

| Field | Type | Required |
|---|---|---|
| scan_executed | bool | always on admitted runs |
| premise_challenges_found | array[object] | always |
| escalation_triggered | bool | always |
| cs_audit_rerun | bool | always |

Each premise_challenges_found[] item:

| Field | Type |
|---|---|
| premise_text | string |
| flagging_model_ids | array[string] |
| independent_count | int |
| threshold_met | bool |

### 6.3 Acceptance Criteria

- Scan executes after R1 on all admitted runs
- Threshold: >=2 independent models flagging the same premise
- When threshold met: CS Audit re-runs with updated context
- When threshold not met: escalation_triggered = false, pipeline proceeds normally
- Re-run results logged separately from initial CS Audit (proof.cs_audit_rerun)

### 6.4 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Scan skipped on admitted run | ERROR | ERROR |
| Threshold met but CS Audit not re-run | ERROR | ERROR |
| Re-run results not logged | ERROR | ERROR |

**Traceability:** R1, R3

---

## 7. Effort Policy and SHORT_CIRCUIT

### 7.1 Dynamic Token Budgeting

proof.budgeting SHALL contain:

| Field | Type | Required |
|---|---|---|
| effort_tier | enum | always |
| per_round_token_budgets | object | always |
| search_budget_policy | enum | always |
| speculative_expansion_allowed | bool | always |
| high_authority_evidence_required | bool | always |
| short_circuit_taken | bool | always |
| fallback_from_short_circuit | bool | always |

### 7.2 SHORT_CIRCUIT Requirements

When short_circuit_taken = true:
- Topology remains 4→3→2→2
- Search budget is reduced; speculative expansion is disabled
- Every round is instructed to either confirm the trivial answer or surface a hidden defect
- DECIDE is permitted ONLY if high_authority_evidence_required is satisfied (at least one high-authority evidence item when search_scope != NONE)
- If search_scope = NONE AND question_class = TRIVIAL, zero evidence is acceptable
- If high-authority evidence is absent when required, run falls back to full deliberation (fallback_from_short_circuit = true)

### 7.3 Compressed-Mode Invariants

SHORT_CIRCUIT runs use a compressed system prompt. The following 5 invariants MUST be present in every compressed-mode model response:

1. **Premise check** — did the model validate the premise?
2. **Confidence basis** — what supports this answer?
3. **Known unknowns** — what could change this?
4. **One counter-consideration** — what argues against?
5. **Machine-readable compression reason** — why is this SHORT_CIRCUIT?

### 7.4 Acceptance Criteria

- short_circuit_taken = true ONLY when cs_audit.short_circuit_allowed = true
- Topology 4→3→2→2 preserved under SHORT_CIRCUIT
- All 5 compressed-mode invariants present in each model response when short_circuit_taken = true
- Fallback to full deliberation logged with fallback_from_short_circuit = true
- Missing any invariant in compressed mode → ERROR

### 7.5 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| SHORT_CIRCUIT changes topology | ERROR | ERROR |
| SHORT_CIRCUIT taken with violated guardrails (wrong class/stakes/flags) | ERROR | ERROR |
| SHORT_CIRCUIT DECIDE without required evidence | ESCALATE | ESCALATE |
| Compressed-mode response missing any of the 5 invariants | ERROR | ERROR |
| Fallback not logged | ERROR | ERROR |

**Traceability:** R0, R1, R4

---

## 8. Canonical Cross-Round Entity IDs

### 8.1 Purpose

Assign deterministic IDs at Gate 1/R1 to transform Position Tracker from fuzzy semantic matching to a deterministic lineage graph. Foundational infrastructure for forensic logging, claim-aware pinning, and cross-round traceability.

### 8.2 ID Format

| Entity Type | Format | Assigned At |
|---|---|---|
| Claims | `claim_{topic}_{nn}` | Gate 1 (initial), R1+ (new claims) |
| Arguments | `arg_{round}_{nn}` | Each round (existing format) |
| Frames | `frame_{nn}` | Divergent Framing Pass (existing format) |
| Blockers | `blk_{nn}` | As created (existing format) |
| Evidence bindings | `evidence_binding_{nn}` | Search phase |

### 8.3 Required Schema

proof.entity_registry SHALL contain:

| Field | Type | Required |
|---|---|---|
| claims | object (map: claim_id → claim_object) | always on admitted runs |
| arguments | object (map: arg_id → arg_object) | always on admitted runs |
| frames | object (map: frame_id → frame_object) | always on admitted runs |
| blockers | object (map: blk_id → blocker_object) | always on admitted runs |
| evidence_bindings | object (map: binding_id → binding_object) | always on admitted runs |
| collision_log | array[object] | always |

### 8.4 Collision Handling

- Dangling references (ID cited but not in registry) → WARNING logged in proof.warnings[]
- Topic extraction variance (same claim, different topic slug) → content hash fallback for deduplication
- ID collisions (two entities assigned same ID) → append `_{model_id}_{round}` to disambiguate; log in collision_log[]
- Regex patterns for entity ID matching MUST accept appended lineage tags (e.g., `claim_security_01_kimi_r2`)

### 8.5 Lineage Requirements

- Subsequent rounds MUST explicitly cite entity IDs when supporting, mutating, or rebutting
- Every mutation creates a new entity with `lineage_parent` pointing to the original ID
- Superseded entities retain their ID but gain `superseded_by` field

### 8.6 Acceptance Criteria

- All entities in proof.json have valid canonical IDs
- Every cross-round reference uses canonical IDs (no free-text references without ID)
- Collision log is empty OR contains only resolved collisions
- Dangling references produce WARNING (not ERROR)
- Entity ID regex accepts lineage-tagged variants
- Content hash fallback activates when topic extraction produces different slugs for semantically identical claims

### 8.7 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Entity without canonical ID in proof | ERROR | ERROR |
| Unresolved ID collision | ERROR | ERROR |
| Dangling reference (ID not in registry) | WARNING | Logged; no outcome change |
| Topic extraction variance without hash fallback | WARNING | Logged; no outcome change |
| Cross-round reference without canonical ID | ERROR | ERROR |

**Traceability:** R0, R3

---

## 9. Pre-R1 Virtual Frames

### 9.1 Purpose

Before R1, a single Sonnet call generates 3-5 alternative frames. These are NOT injected into real model prompts (independence preserved). They feed the Divergent Framing Pass as virtual outputs, guaranteeing frame diversity even if R1 converges naturally.

### 9.2 Required Schema

proof.virtual_frames SHALL contain:

| Field | Type | Required |
|---|---|---|
| executed | bool | always on admitted runs |
| parse_ok | bool | always |
| frames | array[object] | always |
| frame_count | int | always |

Each frame:

| Field | Type |
|---|---|
| frame_id | string (VFRAME-N) |
| text | string |
| frame_type | enum (INVERSION, STAKEHOLDER, PREMISE_CHALLENGE, CROSS_DOMAIN_ANALOGY, OPPOSITE_STANCE, REMOVE_PROBLEM) |
| origin | "virtual_seeder" |
| demoted | bool |
| demoted_reason | string or null |

### 9.3 Acceptance Criteria

- Virtual frame seeder executes after CS Audit, before R1
- Generates 3-5 frames; fewer than 3 → ERROR
- Frames NOT injected into R1 model prompts (independence preserved)
- Frames ARE available to the Divergent Framing Pass
- Auto-demote if unaddressed by R2 (demoted = true with reason)

### 9.4 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Virtual frame seeder missing on admitted run | ERROR | ERROR |
| Fewer than 3 frames generated | ERROR | ERROR |
| Virtual frames injected into R1 model prompts | ERROR | ERROR |

**Traceability:** R1, R3

---

## 10. R1 Perspective Lenses

### 10.1 Purpose

Assign differentiated exploration mandates to R1 models via system prompts. Prevents premature convergence by structurally diversifying the exploration space.

### 10.2 Required Schema

proof.perspective_lenses SHALL contain one entry per R1 model:

| Field | Type |
|---|---|
| model_id | string |
| lens | enum (UTILITY_EFFICIENCY, RISK_SECURITY, SYSTEMS_ARCHITECTURE, CONTRARIAN_INVERSION) |
| adapted_from_question_class | bool |
| fallback_to_standard | bool |

### 10.3 R1 Space-Mapping Format

Every R1 model response MUST include:
- Viable options enumerated
- A declared lean (preferred option)
- Evidence needed to switch from that lean

### 10.4 Diversity Score

Position Tracker computes a diversity score from R1 outputs. Score < 2 → WARNING logged in proof.warnings[].

### 10.5 Acceptance Criteria

- Exactly 4 R1 models, each assigned a distinct lens
- Lenses adapted based on CS Audit's question_class; fallback to standard if mapping fails
- Contrarian/Inversion lens assigned to Kimi (adversarial role retained)
- All 3 space-mapping fields present in each R1 response
- Diversity score computed and recorded

### 10.6 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| R1 model missing lens assignment | ERROR | ERROR |
| Space-mapping fields missing from R1 response | ERROR | ERROR |
| Diversity score < 2 | WARNING | Logged; no outcome change |

**Traceability:** R1, R3

---

## 11. Divergent Framing Pass and Frame Survival

### 11.1 Required Schema

proof.divergence SHALL contain:

| Field | Type | Required |
|---|---|---|
| required | bool | always |
| framing_pass_executed | bool | always |
| adversarial_slot_assigned | bool | always |
| adversarial_model_id | string or null | always |
| adversarial_assignment_type | enum or null | always |
| exploration_stress_triggered | bool | always |
| stress_seed_frames | array[object] | always |
| material_unrebutted_frame_count | int | always |

Each alt_frames[] item:

| Field | Type |
|---|---|
| frame_id | string (FRAME-N) |
| text | string |
| origin_round | int |
| origin_model | string |
| frame_type | enum (INVERSION, OBJECTIVE_REWRITE, PREMISE_CHALLENGE, CROSS_DOMAIN_ANALOGY, OPPOSITE_STANCE, REMOVE_PROBLEM) |
| material_to_outcome | bool |
| survival_status | enum (ACTIVE, CONTESTED, DROPPED, ADOPTED, REBUTTED) |
| r2_drop_vote_count | int |
| r2_drop_vote_refs | array[string] |
| rebuttal_status | enum (NONE, PARTIAL, REBUTTED) |
| synthesis_disposition_status | enum (ADDRESSED, UNADDRESSED) |
| coupled_arguments | array[string] |

**Material frame definition:** A frame is material if: (a) it is linked to a virtual frame or dimension, OR (b) it is adopted by >=2 models in R2.

### 11.2 Frame Survival Rules

- R2: frame DROPPED only if all 3 R2 models cast traceable drop votes (each citing an argument_id or evidence_id). r2_drop_vote_count < 3 → frame stays non-dropped.
- R3/R4: frames CANNOT be dropped. Status moves to CONTESTED if not rebutted.
- R2 frame enforcement: each R2 model MUST adopt one frame, rebut one frame, and generate one new frame.
- Drop votes do NOT feed into agreement_ratio.

### 11.3 Frame-Argument Coupling

If arguments belonging to a frame are systematically ignored for >=2 rounds:
- Re-activate that frame (bump from CONTESTED back to ACTIVE)
- Record coupling activation in proof.divergence.coupling_activations[]

### 11.4 Moderated Frame Rebuttal (R2)

In R2, at least one surviving model MUST explicitly test the leading frame with a rebuttal before supporting the majority position. One explicit challenge per leading frame is sufficient.

### 11.5 Exploration Stress Trigger

Condition: R1 agreement_ratio > 0.75 AND (question_class = OPEN OR stakes_class = HIGH) — union, not intersection.

When triggered:
- 2-3 seed frames injected into R2 prompts
- exploration_stress_triggered = true in proof

### 11.6 Acceptance Criteria

- Framing pass executes on all admitted runs where divergence.required = true
- Virtual frames feed into the framing pass alongside organic R1 frames
- Frame dropping requires exactly 3 traceable R2 votes
- R3/R4 never drop frames
- Each R2 model adopts 1, rebuts 1, generates 1 frame
- Frame-argument coupling re-activates frames when arguments are ignored >=2 rounds
- At least one R2 model rebuts the leading frame before supporting it
- Stress trigger uses union condition (OPEN OR HIGH)

### 11.7 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Divergence required but framing pass missing | ERROR | ERROR |
| Frame dropped with < 3 traceable R2 votes | ERROR | ERROR |
| Material frame disappears from lineage | ERROR | ERROR |
| Material frame ACTIVE/CONTESTED without rebuttal at synthesis | ESCALATE | ESCALATE |
| Stress trigger met but no seed frames injected | ERROR | ERROR |
| R2 adopt/rebut/generate obligation missing | ERROR | ERROR |
| Leading frame not rebutted in R2 | ESCALATE | ESCALATE |

**Traceability:** R1, R3, R4

---

## 12. Rotating Adversarial Role (R2-R4)

### 12.1 Purpose

After each round, assign the contrarian role to the model farthest from the position centroid. Maintains diversity pressure throughout deliberation.

### 12.2 Required Schema

proof.adversarial_rotation SHALL contain:

| Field | Type | Required |
|---|---|---|
| activations | array[object] | always on admitted runs |

Each activation:

| Field | Type |
|---|---|
| round | int |
| activated | bool |
| agreement_ratio_at_trigger | float |
| assigned_model_id | string or null |
| distance_from_centroid | float or null |

### 12.3 Activation Threshold

Only activate when agreement_ratio > 0.70. Below 0.70, organic disagreement is sufficient.

### 12.4 Acceptance Criteria

- Rotation evaluated after each round (R1, R2, R3)
- Activated only when agreement_ratio > 0.70
- Assigned model is the one farthest from position centroid
- Token overhead approximately 8% when active (subject to load-testing validation)

### 12.5 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Rotation evaluation skipped on admitted run | ERROR | ERROR |
| Rotation activated below threshold | WARNING | Logged |

**Traceability:** R1, R3

---

## 13. Breadth-Recovery Pulse

### 13.1 Purpose

Prevents premature narrowing of deliberation. If Argument Tracker shows >40% of R1 arguments IGNORED in R2, inject recovery prompt into R3.

### 13.2 Required Schema

proof.breadth_recovery SHALL contain:

| Field | Type | Required |
|---|---|---|
| evaluated | bool | always on admitted runs |
| r1_argument_count | int | always |
| ignored_in_r2_count | int | always |
| ignored_ratio | float | always |
| triggered | bool | always |
| injected_arguments | array[string] | when triggered |

### 13.3 Acceptance Criteria

- Evaluated after R2 on all admitted runs
- Threshold: >40% of R1 arguments have status IGNORED in R2
- When triggered: R3 prompt includes "Address at least 2 of the following ignored arguments before proceeding" with the specific argument IDs
- When not triggered: triggered = false, pipeline proceeds

### 13.4 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Evaluation skipped on admitted run | ERROR | ERROR |
| Trigger met but no injection into R3 | ERROR | ERROR |

**Traceability:** R1, R3

---

## 14. Calibrated Anti-Groupthink Search

### 14.1 Purpose

When non-trivial questions produce agreement_ratio > 0.80 in R1, trigger one adversarial search query looking for evidence that disproves or weakens the consensus.

### 14.2 Required Schema

proof.anti_groupthink_search SHALL contain:

| Field | Type | Required |
|---|---|---|
| evaluated | bool | always on admitted runs |
| r1_agreement_ratio | float | always |
| question_class | enum | always |
| stakes_class | enum | always |
| triggered | bool | always |
| query_id | string or null | when triggered |
| query_text | string or null | when triggered |
| evidence_found | bool or null | when triggered |

### 14.3 Activation Conditions

- agreement_ratio > 0.80 in R1
- AND question_class in {OPEN, AMBIGUOUS} OR stakes_class = HIGH
- NOT triggered for TRIVIAL or WELL_ESTABLISHED with LOW stakes

### 14.4 Acceptance Criteria

- Evaluated after R1 on all admitted runs
- When triggered: exactly one adversarial search query issued
- Query specifically targets evidence that disproves/weakens the consensus
- Results fed into R2 evidence pool
- Query logged in proof.search_log with provenance = "anti_groupthink"

### 14.5 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Evaluation skipped | ERROR | ERROR |
| Trigger met but no query issued | ERROR | ERROR |
| Query issued but not logged in search_log | ERROR | ERROR |

**Traceability:** R2, R3

---

## 15. Distant-Domain Analogical Queries

### 15.1 Purpose

For OPEN questions where R1 exploration is narrow, Sonnet generates 1-2 cross-domain search queries. Optional mechanism, never mandatory.

### 15.2 Required Schema

proof.analogical_queries SHALL contain:

| Field | Type | Required |
|---|---|---|
| evaluated | bool | always on admitted runs |
| triggered | bool | always |
| queries | array[object] | when triggered |

Each query:

| Field | Type |
|---|---|
| query_id | string |
| query_text | string |
| source_domain | string |
| target_claim_id | string |

### 15.3 Acceptance Criteria

- Optional: not triggering is never a failure
- When triggered: 1-2 queries max
- Queries logged in proof.search_log with provenance = "analogical"

### 15.4 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Analogical query issued but not logged | ERROR | ERROR |

**Traceability:** R2

---

## 16. Concurrent Mechanism Budget

### 16.1 Purpose

Multiple exploration mechanisms may compete for token budget. A priority hierarchy prevents budget exhaustion and ensures the highest-value mechanisms always execute.

### 16.2 Priority Hierarchy

1. **Pinning** (highest) — claim-aware pinning for DC-5 fix
2. **Anti-groupthink** — adversarial search when consensus is suspicious
3. **Breadth-recovery** — recovery pulse for ignored arguments
4. **Analogical** (lowest) — distant-domain queries

### 16.3 Global Token Reserve

25% of the total token budget is reserved as a global reserve. No single mechanism may consume more than its allocated share such that the reserve drops below 25%.

### 16.4 Required Schema

proof.mechanism_budget SHALL contain:

| Field | Type | Required |
|---|---|---|
| total_token_budget | int | always |
| reserve_percentage | float | always (0.25) |
| reserve_available | int | always |
| mechanism_allocations | object | always |
| reserve_breach | bool | always |

### 16.5 Acceptance Criteria

- Reserve percentage = 25% (configurable via config.yaml)
- Higher-priority mechanisms pre-empt lower-priority ones when budget is constrained
- reserve_breach = false on all non-ERROR runs
- If reserve would be breached: lower-priority mechanisms are skipped, not the reserve

### 16.6 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Reserve breached (below 25%) | ESCALATE | ESCALATE |
| Mechanism allocation not recorded | ERROR | ERROR |

**Traceability:** R0, R3

---

## 17. Search, Provenance, and Ungrounded Stat Detection

### 17.1 Search Log Schema

proof.search_log SHALL be an array:

| Field | Type |
|---|---|
| query_id | string |
| query_text | string |
| provenance | enum (model_claim, premise_defect, frame_test, evidence_gap, ungrounded_stat, anti_groupthink, analogical) |
| issued_after_stage | string |
| pages_fetched | int |
| evidence_yield_count | int |
| query_status | enum (SUCCESS, ZERO_RESULT, FAILED, SKIPPED) |

### 17.2 Paywall Detection

Before extraction, string-match fetched pages for paywall phrases ("subscribe," "premium," "member exclusive"). If >30% of page content matches paywall indicators:
- Mark page as PAYWALLED
- Skip extraction
- Log in proof.search_log entry with paywall_detected = true

### 17.3 Ungrounded Stat Detector Schema

proof.ungrounded_stats SHALL contain:

| Field | Type | Required |
|---|---|---|
| post_r1_executed | bool | DECIDE admitted runs |
| post_r2_executed | bool | DECIDE admitted runs |
| flagged_claims | array[object] | always |

Each flagged_claims[] item:

| Field | Type |
|---|---|
| claim_id | string |
| text | string |
| numeric | bool |
| verified | bool |
| blocker_id | string or null (BLK-UNG-{n}) |
| severity | enum |
| status | enum (CLEAR, UNVERIFIED_CLAIM) |
| search_query_ids | array[string] |

### 17.4 Acceptance Criteria

- Every search query logged with provenance and query_status
- Zero-result queries still logged (query_status = ZERO_RESULT)
- Search subsystem failure → query_status = FAILED → ERROR if critical
- Ungrounded Stat Detector runs after R1 and R2 on DECIDE admitted runs
- Unverified numeric claims generate targeted search queries for verification
- Unverified numeric claims generate BLK-UNG-{n} blockers
- Post-R3 unresolved material unverified numeric claim → ESCALATE trigger
- Paywall detection runs before extraction; paywalled pages skipped

### 17.5 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Query executed but not logged | ERROR | ERROR |
| Missing provenance on query | ERROR | ERROR |
| Ungrounded stat detector skipped on DECIDE run | ERROR | ERROR |
| Search subsystem failure | ERROR | ERROR |
| Material unverified claim unresolved at Gate 2 | ESCALATE | ESCALATE |

**Traceability:** R2, R4

---

## 18. DC-5 Fix: Claim-Aware Pinning + Budget Discipline + Forensic Logging

### 18.1 Purpose

Three-pillar approach to prevent evidence orphaning, context bloat, and silent contradiction dropping. This replaces the two-tier active/archive evidence ledger approach from DOD-V3.md.

### 18.2 Pillar 1: Claim-Aware Pinning

Pin at the **claim-contradiction unit** level, not raw evidence items. Any evidence involved in an OPEN contradiction or active blocker cannot be evicted until that contradiction is resolved or the run ends.

### 18.3 Pillar 2: Budget Discipline

- Hard cap: max 15% of context window reserved for pinned items
- max_pinned_claims = 5
- Pin decay: a pinned item loses protection ONLY when the claim-level contradiction has been superseded, resolved, or explicitly archived — NOT based on naive model consensus about obsolescence
- If pin cap (5 claims) reached: new pins trigger forced archival of lowest-severity pin, with WARNING logged
- If 15% context budget reached: Gate 2 triggers ESCALATE

### 18.4 Pillar 3: Forensic Logging

Evicted evidence recorded in proof.json under `evicted_evidence`:

| Field | Type |
|---|---|
| event_id | string |
| evidence_id | string |
| linked_contradiction_id | string |
| contradiction_severity | enum |
| contradiction_type | enum (DIRECT_CONTRADICTION, SCOPE_NARROWING, DEFINITIONAL_CONFLICT, CONDITIONAL_OVERRIDE) |
| eviction_reason | string |
| high_severity_eviction | bool |

HIGH-severity evicted contradictions count as unresolved for Gate 2 rule D8.

### 18.5 Pin Cap Attack Surface

proof.pin_cap SHALL contain:

| Field | Type | Required |
|---|---|---|
| max_pinned_claims | int | always (5) |
| current_pinned_count | int | always |
| forced_archival_events | array[object] | always |
| budget_percentage_used | float | always |
| budget_cap_percentage | float | always (0.15) |
| cap_reached | bool | always |

Each forced_archival_events[] item:

| Field | Type |
|---|---|
| event_id | string |
| archived_claim_id | string |
| archived_severity | enum |
| new_pin_claim_id | string |
| new_pin_severity | enum |
| timestamp | string |

### 18.6 Token Measurement

- 15% pin cap is measured **proactively** (before prompt assembly), not reactively after context overflow
- A designated tokenizer is used for measurement (configurable in config.yaml)
- 10% safety margin applied: effective cap = 15% minus 10% safety = 13.5% trigger point for pre-emptive action
- If safety margin breached (>13.5%): context discipline fallbacks activate (evict lowest-severity pinned evidence first)
- If hard cap breached (>15%): ESCALATE

### 18.7 Required Schema

proof.evidence_pinning SHALL contain:

| Field | Type | Required |
|---|---|---|
| pinned_items | array[object] | always |
| evicted_evidence | array[object] | always |
| pin_budget_percentage | float | always |
| pin_budget_cap | float | always (0.15) |
| safety_margin | float | always (0.10) |
| safety_margin_breached | bool | always |
| hard_cap_breached | bool | always |
| tokenizer_id | string | always |

Each pinned_items[] item:

| Field | Type |
|---|---|
| evidence_id | string |
| linked_claim_id | string |
| linked_contradiction_id | string or null |
| linked_blocker_id | string or null |
| pin_reason | string |
| decay_condition | string |
| protected | bool |

### 18.8 Acceptance Criteria

- Evidence involved in OPEN contradictions or active blockers is pinned (cannot be evicted)
- Pinning operates at claim-contradiction unit level, not raw evidence level
- max_pinned_claims = 5 enforced
- Pin cap overflow triggers forced archival of lowest-severity pin + WARNING
- 15% context budget enforced proactively (before prompt assembly)
- 10% safety margin enforced
- Pin decay only on resolution/supersession/explicit archival (never on model consensus)
- Every eviction logged with contradiction linkage and severity
- HIGH-severity evictions count as unresolved for Gate 2
- Designated tokenizer recorded in proof

### 18.9 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Pinned evidence evicted while contradiction is OPEN | ERROR | ERROR |
| Pin budget >15% at prompt assembly | ESCALATE | ESCALATE |
| Safety margin breached without fallback activation | ERROR | ERROR |
| Pin decay triggered by model consensus (not resolution) | ERROR | ERROR |
| Eviction not logged | ERROR | ERROR |
| HIGH-severity eviction not counted as unresolved | ERROR | ERROR |
| Pin cap (5) reached, new pin without forced archival | WARNING | Logged + forced archival |
| Tokenizer not designated | ERROR | ERROR |

**Traceability:** R2, R3, R4

---

## 19. Evidence Ledger

### 19.1 Required Schema

proof.evidence SHALL contain:

| Field | Type | Required |
|---|---|---|
| items | array[object] | always |
| evidence_count | int | always |
| high_authority_evidence_present | bool | always |
| evidence_quality_floor | float | always |
| average_evidence_score | float | always |

Each evidence item:

| Field | Type |
|---|---|
| evidence_id | string (E001, E002...) |
| source_url | string |
| topic_cluster | string |
| authority_tier | enum |
| score | float |
| referenced_by | array[string] |
| pinned | bool |
| pin_reason | string or null |
| paywall_detected | bool |

### 19.2 Evidence Quality Floor

Gate 2 rule D7 enhanced: average_evidence_score must meet minimum threshold (2.0). Below threshold → ESCALATE.

### 19.3 Evidence Caps by Effort Tier

| Effort Tier | DECIDE Cap | ANALYSIS Cap |
|---|---|---|
| SHORT_CIRCUIT | 10 | N/A |
| STANDARD | 10 | 15 |
| ELEVATED | 15 | 20 |

### 19.4 Cross-Domain Filter

Compatibility check uses non-empty intersection between brief domain set and evidence domain set, allowing hybrid domains (e.g., security+infrastructure) rather than binary allow/reject.

### 19.5 Acceptance Criteria

- Every cited evidence item exists in proof.evidence.items
- Evidence caps respected per effort tier
- Average evidence score computed and recorded
- Cross-domain filter uses intersection-based compatibility
- Paywalled evidence items marked but not extracted

### 19.6 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Cited evidence missing from items | ERROR | ERROR |
| Evidence cap exceeded | ERROR | ERROR |
| Average evidence score below 2.0 on DECIDE run | ESCALATE | ESCALATE |

**Traceability:** R2, R4

---

## 20. Argument Tracker and Resolution Status

### 20.1 Required Schema

proof.arguments SHALL be an object map keyed by argument_id:

| Field | Type |
|---|---|
| argument_id | string (arg_{round}_{nn}) |
| round_origin | int |
| model_id | string |
| text | string |
| resolution_status | enum (ORIGINAL, REFINED, SUPERSEDED, IGNORED, MENTIONED) |
| superseded_by | string or null |
| blocker_link_ids | array[string] |
| evidence_refs | array[string] |
| open | bool |
| auto_promoted | bool |
| auto_promoted_from_status | string or null |
| critical | bool |

### 20.2 Argument Auto-Promotion

An argument unaddressed (MENTIONED or IGNORED) for >=2 consecutive rounds → automatically promoted to `critical: true`. Deterministic rule, no LLM call. Gated by CS Audit's question_class (applies only to OPEN/AMBIGUOUS questions).

### 20.3 Acceptance Criteria

- Every argument has a stable unique canonical ID
- REFINED arguments link to the argument they refine
- SUPERSEDED arguments have superseded_by != null pointing to the replacing argument
- Restatement without explicit linkage is NOT resolution
- Open material arguments at synthesis require structured dispositions
- Auto-promotion activates after 2 consecutive rounds of IGNORED/MENTIONED status
- Auto-promotion gated by question_class in {OPEN, AMBIGUOUS}

### 20.4 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Argument disappears without resolution status | ERROR | ERROR |
| Supersession link broken (superseded_by points to nonexistent ID) | ERROR | ERROR |
| Open material argument omitted from synthesis disposition | ESCALATE | ESCALATE |
| Restated argument treated as resolved without lineage | ESCALATE | ESCALATE |
| Auto-promotion not applied when conditions met | ERROR | ERROR |

**Traceability:** R3, R4

---

## 21. Contradictions

### 21.1 Required Schema

proof.contradictions SHALL contain:

| Field | Type | Required |
|---|---|---|
| numeric_records | array[object] | always |
| semantic_records | array[object] | always |
| semantic_pass_executed | bool | always |
| semantic_calls_used | int | always |

Each contradiction record:

| Field | Type |
|---|---|
| ctr_id | string (CTR-N) |
| detection_mode | enum (NUMERIC, SEMANTIC) |
| evidence_ref_a | string |
| evidence_ref_b | string |
| same_entity | bool |
| same_timeframe | bool |
| severity | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| status | enum (OPEN, RESOLVED, NON_MATERIAL) |
| justification | string |
| linked_claim_ids | array[string] |
| contradiction_type | enum (DIRECT_CONTRADICTION, SCOPE_NARROWING, DEFINITIONAL_CONFLICT, CONDITIONAL_OVERRIDE) |

### 21.2 Semantic Contradiction Detection (Capped)

- For evidence pairs sharing >=4 topic words with no numeric conflict: run a Sonnet call
- Max 5 Sonnet calls per search phase (feature-flaggable)
- Output as SEMANTIC_CTR with same tracking as numeric CTR
- Gate 2: lower effective agreement_ratio threshold by 0.05 per unresolved semantic contradiction (soft signal, not hard block)

### 21.3 Semantic Contradiction Shortlist Criteria

A pair is shortlisted when: same topic cluster AND (opposite polarity cues OR same entity + same timeframe) AND at least one member linked to a decisive claim, blocker, or open contradiction.

### 21.4 Acceptance Criteria

- Numeric contradictions detected automatically
- Semantic contradictions capped at 5 Sonnet calls per search phase
- All contradictions linked to claim IDs (canonical entity IDs)
- Contradiction type recorded for forensic logging
- Unresolved semantic contradictions lower agreement_ratio threshold by 0.05 each

### 21.5 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Semantic pass required but skipped | ERROR | ERROR |
| Semantic calls exceed cap (5) | ERROR | ERROR |
| Unresolved HIGH/CRITICAL contradiction | ESCALATE | ESCALATE |

**Traceability:** R2, R3

---

## 22. Blockers and Decisive Claims

### 22.1 Blocker Schema

proof.blockers[] items:

| Field | Type |
|---|---|
| blocker_id | string (blk_{nn}) |
| type | enum (EVIDENCE_GAP, CONTRADICTION, UNRESOLVED_DISAGREEMENT, CONTESTED_POSITION, COVERAGE_GAP, UNVERIFIED_CLAIM) |
| severity | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| status | enum (OPEN, RESOLVED, DEFERRED) |
| linked_ids | array[string] |
| resolution_summary | string or null |

### 22.2 Decisive Claims Schema (DECIDE only)

proof.decisive_claims[] items:

| Field | Type |
|---|---|
| claim_id | string (canonical entity ID) |
| text | string |
| material_to_conclusion | bool |
| evidence_refs | array[string] |
| evidence_support_status | enum (SUPPORTED, PARTIAL, UNSUPPORTED) |
| analogy_refs | array[string] |

### 22.3 Cross-Domain Analogies

proof.cross_domain_analogies[] items:

| Field | Type |
|---|---|
| analogy_id | string |
| source_domain | string |
| target_claim_id | string |
| transfer_mechanism | string |
| test_status | enum (UNTESTED, SUPPORTED, REJECTED) |

An analogy with test_status = UNTESTED SHALL NOT carry decisive factual load.

### 22.4 Acceptance Criteria

- All blockers use canonical entity IDs for linked_ids
- Decisive claims reference canonical claim IDs
- Every decisive claim has evidence_support_status
- SUPPORTED requires at least one evidence_ref
- Untested analogies excluded from decisive reasoning

### 22.5 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Decisive claim missing evidence_support_status | ERROR | ERROR |
| Decisive claim SUPPORTED with zero evidence_refs | ERROR | ERROR |
| Untested analogy used decisively | ESCALATE | ESCALATE |
| Unresolved CRITICAL blocker at Gate 2 | ESCALATE | ESCALATE |

**Traceability:** R2, R3, R4

---

## 23. Position Tracker (DECIDE mode)

### 23.1 Required Schema

proof.positions SHALL contain:

| Field | Type | Required |
|---|---|---|
| round_positions | object (keyed by round) | DECIDE runs |
| agreement_ratio | float | DECIDE runs |
| position_centroid | object | DECIDE runs |
| diversity_score | float | DECIDE runs |

Each round entry contains per-model positions with:

| Field | Type |
|---|---|
| model_id | string |
| position_summary | string |
| lean | string |
| distance_from_centroid | float |

### 23.2 Acceptance Criteria

- Position Tracker uses canonical entity IDs for deterministic lineage (not fuzzy semantic matching)
- agreement_ratio computed from positions after each round
- diversity_score computed from R1 outputs
- Position centroid computed for adversarial rotation assignment

### 23.3 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Position Tracker missing on DECIDE run | ERROR | ERROR |
| agreement_ratio not computed | ERROR | ERROR |

**Traceability:** R3, R4

---

## 24. Synthesis Packet and Residue Verification

### 24.1 Synthesis with Full Deliberation Arc

Synthesis prompt receives controller-curated state bundle including:
- One-line R1 position per model (from Position Tracker)
- Argument evolution summary (from Argument Tracker)
- Frame lifecycle (from Divergent Framing Pass)

**Zero new LLM calls** for state curation — uses existing structured data. The report describes how consensus formed, not just what it concluded.

### 24.2 Synthesis Packet Schema

proof.synthesis_packet SHALL contain:

| Field | Type | Required |
|---|---|---|
| final_positions | array[object] | DECIDE |
| argument_lifecycle | array[object] | always (max 20) |
| frame_summary | array[object] | always |
| blocker_summary | array[object] | always |
| decisive_claim_bindings | array[object] | DECIDE |
| contradiction_summary | array[object] | always |
| premise_flag_summary | array[object] | always |
| r1_position_summaries | array[object] | always |
| argument_evolution | array[object] | always |
| frame_lifecycle | array[object] | always |
| packet_complete | bool | always |

### 24.3 Structured Dispositions

proof.synthesis_output.dispositions SHALL contain arrays for: blockers, frames, claims, contradictions.

Each disposition object:

| Field | Type |
|---|---|
| target_type | enum (BLOCKER, FRAME, CLAIM, CONTRADICTION) |
| target_id | string (canonical entity ID) |
| status | string |
| importance | enum (LOW, MEDIUM, HIGH, CRITICAL) |
| narrative_explanation | string |
| evidence_refs | array[string] |

### 24.4 Orphaned Evidence Obligation

If evidence archive contains evidence with authority_tier = HIGH that is NOT cited in any decisive claim, blocker, contradiction, or synthesis disposition, synthesis MUST explain why it was non-decisive.

### 24.5 Residue Verification Schema

proof.residue_verification SHALL contain:

| Field | Type |
|---|---|
| expected_disposition_count | int |
| emitted_disposition_count | int |
| omission_rate | float |
| threshold_violation | bool |
| deep_scan_triggered | bool |
| coverage_pass | bool |

### 24.6 Residue Threshold

- Starting threshold: 25% omissions → threshold_violation = true
- omission_rate > 0.20 triggers deep semantic scan
- coverage_pass = true required on all non-ERROR runs
- threshold_violation = true → ESCALATE (Gate 2 rule D13)
- Threshold is configurable via config.yaml; collect data, relax only if false positives observed

### 24.7 Acceptance Criteria

- Synthesis receives controller-curated state bundle including deliberation arc
- Synthesis includes R1 position summaries, argument evolution, and frame lifecycle
- Every tracked open finding gets a disposition object
- All dispositions use canonical entity IDs
- omission_rate > 0.20 triggers deep semantic scan
- coverage_pass = true on all non-ERROR runs
- High-authority orphaned evidence gets explicit non-decisive explanation

### 24.8 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Synthesis packet missing controller-curated state | ERROR | ERROR |
| Synthesis missing deliberation arc (R1 positions, argument evolution, frame lifecycle) | ERROR | ERROR |
| Disposition missing for tracked open finding | ERROR | ERROR |
| Deep scan threshold exceeded but scan not run | ERROR | ERROR |
| Material omissions unresolved after deep scan | ESCALATE | ESCALATE |
| Orphaned high-authority evidence without explanation | ESCALATE | ESCALATE |
| threshold_violation = true | ESCALATE | ESCALATE |

**Traceability:** R3, R4

---

## 25. Stability Tests (DECIDE only)

### 25.1 Required Schema

proof.stability SHALL contain:

| Field | Type | Required |
|---|---|---|
| conclusion_stable | bool | DECIDE |
| reason_stable | bool | DECIDE |
| assumption_stable | bool | DECIDE |
| independent_evidence_present | bool | DECIDE |
| fast_consensus_observed | bool | DECIDE (true if R1 agreement_ratio >= 0.95) |
| groupthink_warning | bool | DECIDE |

### 25.2 Definitions

- **conclusion_stable:** Final surviving models converge on the same recommendation after supersession filtering
- **reason_stable:** Models converge for the same reasons (shared decisive claim set and evidence bindings)
- **assumption_stable:** Models rely on the same set of unresolved assumptions
- **groupthink_warning:** fast_consensus_observed = true AND (question_class = OPEN OR stakes_class = HIGH) AND independent_evidence_present = false

### 25.3 Acceptance Criteria

- All stability fields present on every DECIDE run
- Stability booleans are Gate 2 inputs
- groupthink_warning triggers ESCALATE when combined with no independent evidence

### 25.4 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Stability fields missing on DECIDE run | ERROR | ERROR |
| conclusion_stable = false | — | NO_CONSENSUS (via D11) |
| reason_stable = false OR assumption_stable = false | ESCALATE | ESCALATE (via D12) |
| groupthink_warning = true AND independent_evidence_present = false | ESCALATE | ESCALATE (via D13) |

**Traceability:** R3, R4

---

## 26. Gate 2 -- DECIDE Rules (D1-D14)

Evaluated in order. First match determines outcome.

| Rule | Condition | Outcome |
|---|---|---|
| D1 | Fatal integrity or infrastructure failure | ERROR |
| D2 | Modality mismatch (gate1.modality != DECIDE after CS Audit refinement) | ERROR |
| D3 | Illegal SHORT_CIRCUIT state (guardrails violated) | ERROR |
| D4 | agreement_ratio < 0.50 | NO_CONSENSUS |
| D5 | agreement_ratio >= 0.50 and < 0.75 | ESCALATE |
| D6 | Any unresolved CRITICAL blocker (includes COVERAGE_GAP, UNVERIFIED_CLAIM) | ESCALATE |
| D7 | Any decisive claim lacks valid evidence binding (evidence_support_status != SUPPORTED) OR average_evidence_score < 2.0 | ESCALATE |
| D8 | Any HIGH/CRITICAL contradiction unresolved (includes HIGH-severity evicted contradictions) | ESCALATE |
| D9 | Any unresolved CRITICAL premise flag | ESCALATE |
| D10 | Any material frame ACTIVE/CONTESTED without rebuttal and without synthesis disposition | ESCALATE |
| D11 | conclusion_stable = false | NO_CONSENSUS |
| D12 | reason_stable = false OR assumption_stable = false | ESCALATE |
| D13 | residue.threshold_violation = true (omissions > 25%) | ESCALATE |
| D14 | groupthink_warning = true AND independent_evidence_present = false | ESCALATE |
| D15 | pin_cap.hard_cap_breached = true (15% context budget exceeded) | ESCALATE |
| D16 | agreement_ratio >= 0.75 AND effort_tier != SHORT_CIRCUIT AND evidence_count == 0 | ESCALATE |
| D17 | Otherwise | DECIDE |

### 26.1 Pin Cap Rule (D15)

If pin budget exceeds 15% of context window at Gate 2 evaluation → ESCALATE. This prevents silent contradiction dropping when context is exhausted.

### 26.2 Residue Override (D13)

residue.threshold_violation overrides what would otherwise be DECIDE. Starting threshold: 25% omissions. Configurable via config.yaml.

### 26.3 Rule 16 Clarification (D16)

Explicitly: "If agreement_ratio >= 0.75 in R1 AND effort_tier != SHORT_CIRCUIT AND evidence_count == 0 → ESCALATE." High agreement without evidence on non-trivial questions is suspicious.

### 26.4 Semantic Contradiction Soft Signal

Unresolved semantic contradictions lower the effective agreement_ratio threshold by 0.05 each for rules D4 and D5. Example: 2 unresolved semantic contradictions → D5 threshold becomes 0.65 instead of 0.75.

### 26.5 Requirements

- Same proof state → same outcome (deterministic)
- Frame drop votes do NOT affect agreement_ratio
- Rule order is preserved exactly as D1-D17
- gate2.rule_trace[] records which rule fired

### 26.6 Gate 2 Trace Schema

proof.gate2 SHALL contain:

| Field | Type |
|---|---|
| modality | enum (DECIDE, ANALYSIS) |
| rule_trace | array[{rule_id, evaluated, fired, outcome_if_fired}] |
| final_outcome | enum |
| semantic_ctr_adjustment | float |
| effective_agreement_threshold | float |

### 26.7 Escalate Remediation

proof.escalate_remediation SHALL contain (when outcome = ESCALATE):

| Field | Type |
|---|---|
| triggered_rule | string (D1-D17) |
| human_readable_remediation | string |
| suggested_action | string |

### 26.8 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| Gate 2 invokes an LLM | ERROR | ERROR |
| Rule order not preserved | ERROR | ERROR |
| Rule trace missing | ERROR | ERROR |
| Same proof state produces different outcomes | ERROR | ERROR |

**Traceability:** R4

---

## 27. Gate 2 -- ANALYSIS Rules (A1-A3)

Evaluated in order. First match determines outcome.

| Rule | Condition | Outcome |
|---|---|---|
| A1 | dimension_coverage < 0.80 | ESCALATE |
| A2 | residue.threshold_violation = true | ESCALATE |
| A3 | Otherwise | ANALYSIS |

### 27.1 Omitted DECIDE Rules

The following DECIDE Gate 2 concepts are explicitly omitted for ANALYSIS:
- agreement_ratio-based rules (D4, D5, D16) — irrelevant for ANALYSIS
- Blocker type CONTESTED_POSITION — disagreement is a feature in ANALYSIS, not a blocker
- Stability tests (D11, D12) — ANALYSIS does not seek convergence
- Groupthink warning (D14) — not applicable

### 27.2 ANALYSIS Coverage Threshold

dimension_coverage_score >= 0.80 required. This threshold is configurable via config.yaml. Assert exact value (0.80) in tests. Require telemetry_hooks in schema for this gate.

### 27.3 Acceptance Criteria

- Only 3 rules evaluated for ANALYSIS (A1-A3)
- CONTESTED_POSITION blockers do not exist in ANALYSIS mode
- dimension_coverage is the primary quality gate

### 27.4 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| DECIDE rules applied to ANALYSIS run | ERROR | ERROR |
| dimension_coverage < 0.80 | ESCALATE | ESCALATE |
| residue.threshold_violation = true | ESCALATE | ESCALATE |

**Traceability:** R4

---

## 28. ANALYSIS Mode Contract

### 28.1 Shared Pipeline

ANALYSIS reuses: Gate 1, CS Audit (skip stakes_class), 4→3→2→2 topology, Search (with expanded evidence caps: STANDARD=15, ELEVATED=20), Evidence Ledger (with DC-5 fix), Argument Tracker, Divergent Framing Pass, Invariant Validator, proof.json, zero tolerance (infrastructure only).

### 28.2 Dimension Tracker (replaces Position Tracker)

After each round, Sonnet extracts analytical dimensions bottom-up from model outputs:

proof.dimension_tracker SHALL contain:

| Field | Type | Required |
|---|---|---|
| dimensions | array[object] | ANALYSIS runs |
| dimension_coverage_score | float | ANALYSIS runs |
| cross_dimension_interactions | array[object] | ANALYSIS runs |

Each dimension:

| Field | Type |
|---|---|
| dimension_id | string |
| name | string |
| definition | string |
| coverage_status | enum (WELL_COVERED, THINLY_COVERED, MISSING) |
| argument_count | int |
| evidence_count | int |
| round_first_seen | int |

Each cross_dimension_interaction:

| Field | Type |
|---|---|
| dimension_a | string |
| dimension_b | string |
| interaction_type | enum (REINFORCEMENT, TRADE_OFF, DEPENDENCY) |
| description | string |

### 28.3 Stakeholder Perspectives (replaces Adversarial Role)

Assign each R1 model a stakeholder role (engineering, users, budget, operations) based on CS Audit's question_class. Fallback to standard adversarial role if mapping fails.

### 28.4 ANALYSIS-Specific Round Prompts

**R1-R2:** Aggressively expand the map. Different frames, stakeholder lenses, causal hypotheses, risk dimensions, rival interpretations.

**R3 -- Landscape Consolidation:**
> "Do not optimize for choosing a winner. Collapse duplicate frames, preserve materially distinct dimensions, identify coverage gaps. For each retained dimension, output: dimension name, why it matters, arguments present, counterarguments present, uncertainty, dependent assumptions. Expose cross-dimension dependencies."

**R4 -- Landscape Map + Stress Test:**
> "Produce a final analysis map detailing settled understanding and remaining tensions. Preserve materially distinct dimensions. For each dimension, state the settled understanding, remaining live tension, and whether sufficiently explored. Conclude by stress-testing: explicitly identify edge cases, boundary failures, brittle assumptions, hidden dependencies, and unaddressed vulnerabilities most likely to break or alter this landscape. End with a coverage assessment."

### 28.5 ANALYSIS Synthesis Output Format

Structured document with 8 sections:

1. **Dimensions Explored** — normalized list with coverage status
2. **Evidence Map** — evidence clustered by dimension
3. **Tension Catalog** — trade-offs, competing frameworks, unresolved disagreements
4. **Frame Catalog** — surviving frames with lifecycle summary
5. **Information Boundary** — each claim classified as EVIDENCED/EXTRAPOLATED/INFERRED (extractive, not self-tagged)
6. **Open Questions** — what remains unknown, what evidence would resolve it
7. **Action Implications** — if applicable, what decisions this analysis enables
8. **Coverage Assessment** — COMPREHENSIVE / PARTIAL / GAPPED

### 28.6 ANALYSIS Mode: Semantic Contradiction for ANALYSIS

In ANALYSIS mode, mark semantic contradictions as `track_only: true`. These bypass Gate 2 blocker logic entirely. They are recorded for completeness but do NOT trigger ESCALATE.

### 28.7 Information Boundary Classification

After each round, Sonnet classifies each claim extractively:
- **EVIDENCED** {E} — direct citation to evidence item
- **EXTRAPOLATED** {X} — inferred from evidence but not directly stated
- **INFERRED** {I} — no evidence backing

Applied by Sonnet extractively, NOT self-tagged by models. Prevents models from inflating their evidence basis.

proof.information_boundary SHALL contain:

| Field | Type | Required |
|---|---|---|
| classifications | array[object] | ANALYSIS runs |

Each classification:

| Field | Type |
|---|---|
| claim_id | string (canonical entity ID) |
| classification | enum (EVIDENCED, EXTRAPOLATED, INFERRED) |
| evidence_ref | string or null |
| round_classified | int |
| classifier | "sonnet_extractive" |

### 28.8 Coverage Assessment

proof.coverage_assessment SHALL contain:

| Field | Type | Required |
|---|---|---|
| status | enum (COMPREHENSIVE, PARTIAL, GAPPED) | ANALYSIS runs |
| dimension_coverage_score | float | ANALYSIS runs |
| missing_dimensions | array[string] | ANALYSIS runs |
| thinly_covered_dimensions | array[string] | ANALYSIS runs |

### 28.9 Analysis Map Schema

proof.analysis_map SHALL contain:

| Field | Type |
|---|---|
| header | string ("EXPLORATORY MAP -- NOT A DECISION") |
| dimensions | object (keyed by dimension_id) |
| dimension_coverage_score | float |
| hypothesis_ledger | array[object] |
| total_argument_count | int |
| coverage_assessment | object |
| information_boundary | array[object] |

Each dimension entry:

| Field | Type |
|---|---|
| knowns | array[string] |
| inferred | array[string] |
| unknowns | array[string] |
| evidence_for | array[string] |
| evidence_against | array[string] |
| competing_lenses | array[string] |
| argument_count | int |
| cross_dimension_dependencies | array[string] |

### 28.10 Acceptance Criteria

- ANALYSIS uses Dimension Tracker, not Position Tracker, for driving outcomes
- Position Tracker runs diagnostically only (proof.diagnostics.positions), does NOT drive outcomes
- Stakeholder perspectives assigned to R1 models
- R3 prompt is consolidation-focused (not convergence-seeking)
- R4 prompt includes stress-testing
- All 8 synthesis sections present in ANALYSIS output
- Information boundary classification is extractive (Sonnet), not self-tagged
- Semantic contradictions marked track_only: true, bypass Gate 2
- Coverage assessment recorded in proof.json
- analysis_map.header = "EXPLORATORY MAP -- NOT A DECISION"
- dimension_coverage < 0.80 at end of R4 → ESCALATE

### 28.11 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| ANALYSIS output contains verdict language instead of exploratory map | ERROR | ERROR |
| Frame dropping occurs in ANALYSIS mode | ERROR | ERROR |
| analysis_map missing on ANALYSIS run | ERROR | ERROR |
| analysis_map.header != "EXPLORATORY MAP -- NOT A DECISION" | ERROR | ERROR |
| Dimension Tracker missing on ANALYSIS run | ERROR | ERROR |
| Information boundary self-tagged by model (not extractive) | ERROR | ERROR |
| Coverage assessment missing | ERROR | ERROR |
| dimension_coverage < 0.80 | ESCALATE | ESCALATE |
| Any ANALYSIS synthesis section missing | ESCALATE | ESCALATE |

**Traceability:** R1, R3, R4

---

## 29. proof.json Extensions (V3.0B-specific)

### 29.1 New Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| reasoning_contract | object | always | effort tier, modality, compression status |
| premise_defect_log | object | always | original and reformulated briefs |
| outcome_confidence | object | always | weighted aggregate |
| escalate_remediation | object | when ESCALATE | per-rule human-readable steps |
| evicted_evidence | array | always | content and contradiction linkage |
| coverage_assessment | object | ANALYSIS runs | COMPREHENSIVE/PARTIAL/GAPPED |
| warnings | array | always | all WARNING-tier events |
| entity_registry | object | admitted runs | canonical entity IDs |
| pin_cap | object | always | pin budget tracking |
| mechanism_budget | object | always | concurrent mechanism allocation |

### 29.2 Reasoning Contract

proof.reasoning_contract SHALL contain:

| Field | Type |
|---|---|
| effort_tier | enum |
| modality | enum |
| compression_active | bool |
| short_circuit_taken | bool |

### 29.3 Outcome Confidence

proof.outcome_confidence SHALL contain:

| Field | Type |
|---|---|
| agreement_ratio_weight | float |
| evidence_quality_weight | float |
| argument_resolution_weight | float |
| frame_resolution_weight | float |
| weighted_score | float |

### 29.4 Telemetry Hooks

proof.telemetry_hooks SHALL contain:

| Field | Type | Required |
|---|---|---|
| gate_thresholds | object | always |
| configurable_values | object | always |

gate_thresholds entries:

| Threshold | Default | Configurable |
|---|---|---|
| agreement_ratio_decide | 0.75 | config.yaml |
| agreement_ratio_no_consensus | 0.50 | config.yaml |
| dimension_coverage_analysis | 0.80 | config.yaml |
| diversity_score_warning | 2.0 | config.yaml |
| residue_omission_threshold | 0.25 | config.yaml |
| evidence_quality_floor | 2.0 | config.yaml |
| pin_budget_cap | 0.15 | config.yaml |
| pin_safety_margin | 0.10 | config.yaml |
| semantic_ctr_agreement_adjustment | 0.05 | config.yaml |
| groupthink_agreement_ratio | 0.80 | config.yaml |
| adversarial_activation_ratio | 0.70 | config.yaml |
| breadth_recovery_ignored_ratio | 0.40 | config.yaml |
| exploration_stress_ratio | 0.75 | config.yaml |
| max_pinned_claims | 5 | config.yaml |

### 29.5 Acceptance Criteria

- All new fields present in proof.json per their "Required" conditions
- All threshold values configurable via config.yaml
- Test suite asserts exact default values (0.80, 0.70, 0.15, etc.)
- Telemetry hooks schema validated on every run
- Warnings array captures all WARNING-tier events

**Traceability:** R0, R4

---

## 30. proof.json Top-Level Schema

| Field | Type | Required |
|---|---|---|
| schema_version | string ("3.0B") | always |
| proof_version | string ("3.0B") | always |
| run_id | string | always |
| timestamp_started | string | always |
| timestamp_completed | string | always |
| topology | object | always |
| outcome | object | always |
| error_class | enum or null | always |
| stage_integrity | object | always |
| config_snapshot | object | always |
| gate1 | object | always |
| cs_audit | object | admitted runs |
| retroactive_premise | object | admitted runs |
| budgeting | object | always |
| virtual_frames | object | admitted runs |
| perspective_lenses | array | admitted runs |
| rounds | object | admitted runs |
| divergence | object | admitted runs |
| adversarial_rotation | object | admitted runs |
| breadth_recovery | object | admitted runs |
| anti_groupthink_search | object | admitted runs |
| analogical_queries | object | admitted runs |
| mechanism_budget | object | always |
| search_log | array | admitted runs |
| ungrounded_stats | object | DECIDE admitted runs |
| evidence | object | admitted runs |
| evidence_pinning | object | admitted runs |
| pin_cap | object | always |
| entity_registry | object | admitted runs |
| arguments | object (map) | admitted runs |
| blockers | array | admitted runs |
| decisive_claims | array | DECIDE runs |
| cross_domain_analogies | array | admitted runs |
| contradictions | object | admitted runs |
| positions | object | DECIDE runs |
| dimension_tracker | object | ANALYSIS runs |
| information_boundary | object | ANALYSIS runs |
| synthesis_packet | object | admitted runs |
| synthesis_output | object | admitted runs |
| residue_verification | object | admitted runs |
| stability | object | DECIDE runs |
| analysis_map | object | ANALYSIS runs |
| coverage_assessment | object | ANALYSIS runs |
| reasoning_contract | object | always |
| premise_defect_log | object | always |
| outcome_confidence | object | always |
| escalate_remediation | object | when ESCALATE |
| evicted_evidence | array | always |
| warnings | array | always |
| telemetry_hooks | object | always |
| gate2 | object | admitted runs |
| diagnostics | object | always (optional diagnostic data) |

**Traceability:** R0, R4

---

## 31. All Thresholds: Provisional but Testable

Every numerical threshold in this DoD is provisional (subject to tuning based on operational data) but MUST be:

1. **Asserted at exact values in tests** — tests fail if the value changes without updating the test
2. **Configurable via config.yaml** — no hardcoded magic numbers in implementation
3. **Tracked via telemetry_hooks** — every gate that uses a threshold records the threshold value used in proof.json

| Threshold | Default Value | Used By | Section |
|---|---|---|---|
| agreement_ratio for DECIDE | 0.75 | D5, D16 | 26 |
| agreement_ratio for NO_CONSENSUS | 0.50 | D4 | 26 |
| dimension_coverage for ANALYSIS | 0.80 | A1 | 27, 28 |
| diversity_score WARNING | 2.0 | R1 diversity | 10 |
| residue omission threshold | 0.25 | D13 | 24 |
| deep scan trigger | 0.20 | Residue verification | 24 |
| evidence_quality_floor | 2.0 | D7 | 19 |
| pin_budget_cap | 0.15 (15%) | D15, pinning | 18 |
| pin_safety_margin | 0.10 (10%) | Proactive pin measurement | 18 |
| max_pinned_claims | 5 | Pin cap | 18 |
| semantic_ctr_agreement_adjustment | 0.05 | D4/D5 soft signal | 21, 26 |
| groupthink_agreement_ratio | 0.80 | Anti-groupthink search | 14 |
| adversarial_activation_ratio | 0.70 | Rotating adversarial | 12 |
| breadth_recovery_ignored_ratio | 0.40 | Breadth-recovery pulse | 13 |
| exploration_stress_ratio | 0.75 | Exploration stress trigger | 11 |
| semantic_ctr_call_cap | 5 | Semantic contradiction | 21 |
| paywall_match_threshold | 0.30 | Paywall detection | 17 |
| evidence_cap_standard | 10 | Evidence ledger | 19 |
| evidence_cap_elevated | 15 | Evidence ledger | 19 |
| analysis_evidence_cap_standard | 15 | ANALYSIS evidence | 19, 28 |
| analysis_evidence_cap_elevated | 20 | ANALYSIS evidence | 19, 28 |
| compressed_mode_invariant_count | 5 | SHORT_CIRCUIT | 7 |

### 31.1 Acceptance Criteria

- Every threshold above has a corresponding test that asserts its exact default value
- Every threshold is loaded from config.yaml at runtime
- Every threshold used by Gate 2 is recorded in proof.telemetry_hooks.gate_thresholds
- Changing a threshold value without updating its test causes test failure

**Traceability:** R0, R4

---

## 32. Verification and Test Suite

| Test | Verifies | Section |
|---|---|---|
| Gate 1 missing/unparseable → ERROR | Gate 1 integrity | 4 |
| Gate 1 fatal premise → NEED_MORE + fatal_premise=true | Fatal premise routing | 4 |
| Gate 1 INVALID_FORM → NEED_MORE, not ERROR | Taxonomy compliance | 4 |
| CS Audit missing/unparseable → ERROR | CS Audit integrity | 5 |
| CS Audit requester-fixable defect → NEED_MORE | Defect routing | 5 |
| CS Audit auto-reformulation logs both briefs | Reformulation audit trail | 5 |
| Gate 1 and CS Audit are separate stages in stage_integrity | Separation of concerns | 3, 4, 5 |
| Retroactive premise escalation scans after R1 | Premise safety net | 6 |
| Retroactive premise with >=2 flags triggers CS Audit re-run | Threshold enforcement | 6 |
| SHORT_CIRCUIT preserves 4→3→2→2 | Fixed topology | 7 |
| SHORT_CIRCUIT without high-authority evidence → ESCALATE | Evidence guardrail | 7 |
| SHORT_CIRCUIT with violated guardrails → ERROR | Integrity check | 7 |
| All 5 compressed-mode invariants present in SHORT_CIRCUIT | Compressed protocol | 7 |
| Entity IDs canonical and collision-free | Entity registry integrity | 8 |
| Dangling entity reference → WARNING (not ERROR) | Collision handling | 8 |
| Content hash fallback for topic extraction variance | Deduplication resilience | 8 |
| Virtual frame seeder generates 3-5 frames | Frame diversity | 9 |
| Virtual frames NOT injected into R1 prompts | Independence preservation | 9 |
| 4 R1 models with distinct perspective lenses | Lens assignment | 10 |
| R1 space-mapping fields present (options, lean, switch evidence) | Space mapping | 10 |
| Diversity score < 2 → WARNING | Diversity monitoring | 10 |
| Single or double R2 drop vote does not drop frame | 3-vote rule | 11 |
| Three R2 drop votes with traceable refs → DROPPED | Drop threshold | 11 |
| R3/R4 cannot drop frames (CONTESTED only) | Late-round reform | 11 |
| Frame-argument coupling re-activates ignored frames | Coupling mechanism | 11 |
| R2 moderated rebuttal of leading frame | Frame rebuttal | 11 |
| Exploration stress trigger (union: OPEN OR HIGH) injects 2-3 seed frames | Suspicious consensus | 11 |
| Rotating adversarial activates only when agreement > 0.70 | Activation threshold | 12 |
| Breadth-recovery pulse triggers when >40% R1 args IGNORED in R2 | Breadth protection | 13 |
| Anti-groupthink search triggers when agreement > 0.80 on OPEN/HIGH | Groupthink detection | 14 |
| Anti-groupthink query logged with provenance "anti_groupthink" | Search auditability | 14 |
| Concurrent mechanism budget respects priority hierarchy | Budget discipline | 16 |
| 25% global token reserve maintained | Reserve protection | 16 |
| Query provenance + query_status logged for all queries including zero-result | Search auditability | 17 |
| Paywall detection skips extraction for paywalled pages | Paywall handling | 17 |
| Material unverified numeric claim unresolved → ESCALATE | Ungrounded stat enforcement | 17 |
| Claim-aware pinning at claim-contradiction unit level | DC-5 pillar 1 | 18 |
| max_pinned_claims = 5 enforced | Pin cap | 18 |
| Pin cap overflow → forced archival of lowest-severity + WARNING | Pin cap attack surface | 18 |
| 15% context budget measured proactively (before prompt assembly) | Token measurement | 18 |
| 10% safety margin triggers context discipline fallbacks | Safety margin | 18 |
| Every eviction logged with contradiction linkage | Forensic logging | 18 |
| HIGH-severity eviction counts as unresolved for Gate 2 | Eviction severity | 18 |
| Pin decay only on resolution (never model consensus) | Pin decay rule | 18 |
| Evidence quality floor (average score >= 2.0) for DECIDE | Evidence quality | 19 |
| Cross-domain filter uses intersection-based compatibility | Domain filtering | 19 |
| Argument auto-promotion after 2 rounds IGNORED/MENTIONED | Auto-promotion | 20 |
| Auto-promotion gated by question_class OPEN/AMBIGUOUS | Promotion guard | 20 |
| Semantic contradiction capped at 5 Sonnet calls per search phase | CTR budget | 21 |
| Unresolved semantic CTR lowers agreement threshold by 0.05 each | Soft signal | 21 |
| Contradiction type recorded (DIRECT/SCOPE/DEFINITIONAL/CONDITIONAL) | Forensic typing | 21 |
| Decisive claim SUPPORTED with zero evidence_refs → ERROR | Evidence integrity | 22 |
| Untested analogy used decisively → ESCALATE | Analogy restriction | 22 |
| Position Tracker uses canonical entity IDs | Lineage graph | 23 |
| Synthesis includes deliberation arc (R1 positions, argument evolution, frame lifecycle) | Full arc | 24 |
| Orphaned high-authority evidence requires explanation | Evidence accountability | 24 |
| Residue omission >25% → threshold_violation = true → ESCALATE (D13) | Residue enforcement | 24 |
| omission_rate > 0.20 triggers deep scan | Residue depth | 24 |
| Stability fields present on all DECIDE runs | Stability completeness | 25 |
| conclusion_stable=false → NO_CONSENSUS (D11) | Stability rule | 25, 26 |
| reason/assumption unstable → ESCALATE (D12) | Stability rule | 25, 26 |
| Groupthink warning + no independent evidence → ESCALATE (D14) | Stability rule | 25, 26 |
| Gate 2 DECIDE: rules evaluated D1-D17 in exact order | Rule ordering | 26 |
| Pin cap budget breach → ESCALATE (D15) | Pin cap rule | 26 |
| High agreement + no evidence + non-trivial → ESCALATE (D16) | Suspicious agreement | 26 |
| Semantic CTR adjustment applied to effective threshold | Soft signal integration | 26 |
| ESCALATE includes remediation steps | Remediation | 26 |
| Gate 2 ANALYSIS: only A1-A3 evaluated | ANALYSIS simplification | 27 |
| dimension_coverage < 0.80 → ESCALATE (A1) | Coverage rule | 27 |
| ANALYSIS dimension tracker replaces position tracker | Mode contract | 28 |
| ANALYSIS R3 consolidation prompt used | Round specialization | 28 |
| ANALYSIS R4 stress-test prompt used | Round specialization | 28 |
| ANALYSIS synthesis has all 8 sections | Output completeness | 28 |
| Information boundary extractive (Sonnet), not self-tagged | Classification integrity | 28 |
| ANALYSIS semantic contradictions marked track_only: true | ANALYSIS bypass | 28 |
| Coverage assessment in proof.json (COMPREHENSIVE/PARTIAL/GAPPED) | Coverage metadata | 28 |
| ANALYSIS frame dropping → ERROR | Mode contract | 28 |
| analysis_map.header = "EXPLORATORY MAP -- NOT A DECISION" | Contract enforcement | 28 |
| schema_version = "3.0B" on all V3.0B runs | Schema versioning | 1, 30 |
| V3.0 proof files parse without ERROR (backward compat) | Schema compatibility | 1 |
| All thresholds loaded from config.yaml | Configurability | 31 |
| All thresholds have exact-value tests | Test coverage | 31 |
| All gate thresholds in telemetry_hooks | Observability | 29, 31 |
| Three-tier failure taxonomy applied (ERROR/ESCALATE/WARNING) | Taxonomy compliance | 1 |
| WARNING events in proof.warnings[] do not alter outcome | WARNING non-blocking | 1 |
| Same proof state twice → same Gate 2 result | Determinism | 3, 26 |
| Modality mismatch → ERROR | Controller contract | 26, 27 |

**Traceability:** R0-R4

---

## 33. Consolidated Failure-Mode Matrix

| Mechanism | Failure | Tier | Outcome |
|---|---|---|---|
| Gate 1 | missing/unparseable | ERROR | ERROR |
| Gate 1 | fatal premise admitted | ERROR | ERROR |
| CS Audit | missing/unparseable | ERROR | ERROR |
| CS Audit | requester-fixable admitted | ERROR | ERROR |
| CS Audit | auto-reformulation not logged | ERROR | ERROR |
| Assumptions | material false/unverifiable unresolved | ESCALATE | NEED_MORE |
| Retroactive Premise | scan skipped | ERROR | ERROR |
| Retroactive Premise | threshold met, no re-run | ERROR | ERROR |
| SHORT_CIRCUIT | guardrails violated | ERROR | ERROR |
| SHORT_CIRCUIT | no required evidence | ESCALATE | ESCALATE |
| SHORT_CIRCUIT | compressed invariant missing | ERROR | ERROR |
| Entity IDs | unresolved collision | ERROR | ERROR |
| Entity IDs | dangling reference | WARNING | Logged |
| Virtual Frames | missing / <3 frames | ERROR | ERROR |
| Virtual Frames | injected into R1 prompts | ERROR | ERROR |
| Perspective Lenses | missing lens assignment | ERROR | ERROR |
| Perspective Lenses | space-mapping fields missing | ERROR | ERROR |
| Divergent Framing | required but absent | ERROR | ERROR |
| Frame survival | dropped with <3 R2 votes | ERROR | ERROR |
| Material frame | ACTIVE/CONTESTED unaddressed | ESCALATE | ESCALATE |
| Frame rebuttal | leading frame not rebutted in R2 | ESCALATE | ESCALATE |
| Exploration stress | trigger met, no seed frames | ERROR | ERROR |
| Rotating adversarial | evaluation skipped | ERROR | ERROR |
| Breadth recovery | trigger met, no injection | ERROR | ERROR |
| Anti-groupthink | trigger met, no query | ERROR | ERROR |
| Mechanism budget | reserve breached | ESCALATE | ESCALATE |
| Search log | query not logged / missing provenance | ERROR | ERROR |
| Search subsystem | infrastructure failure | ERROR | ERROR |
| Ungrounded stats | detector skipped on DECIDE | ERROR | ERROR |
| Ungrounded stats | material unverified claim unresolved | ESCALATE | ESCALATE |
| Evidence pinning | pinned evidence evicted while OPEN | ERROR | ERROR |
| Evidence pinning | budget >15% at prompt assembly | ESCALATE | ESCALATE |
| Evidence pinning | safety margin breached without fallback | ERROR | ERROR |
| Evidence pinning | decay by model consensus | ERROR | ERROR |
| Evidence pinning | eviction not logged | ERROR | ERROR |
| Pin cap | cap reached, no forced archival | WARNING | Logged |
| Evidence ledger | cited evidence missing | ERROR | ERROR |
| Evidence quality | average score < 2.0 on DECIDE | ESCALATE | ESCALATE |
| Semantic contradiction | required but skipped | ERROR | ERROR |
| Semantic contradiction | calls exceed cap (5) | ERROR | ERROR |
| Contradiction | HIGH/CRITICAL unresolved | ESCALATE | ESCALATE |
| Argument tracking | restatement counted as resolution | ESCALATE | ESCALATE |
| Argument tracking | supersession link broken | ERROR | ERROR |
| Argument tracking | auto-promotion not applied | ERROR | ERROR |
| Decisive claims | missing evidence_support_status | ERROR | ERROR |
| Decisive claims | SUPPORTED with zero evidence | ERROR | ERROR |
| Analogies | untested used decisively | ESCALATE | ESCALATE |
| Synthesis packet | controller state absent | ERROR | ERROR |
| Synthesis packet | deliberation arc missing | ERROR | ERROR |
| Residue verification | material omissions | ESCALATE | ESCALATE |
| Residue verification | threshold_violation = true | ESCALATE | ESCALATE |
| Stability tests | conclusion unstable | — | NO_CONSENSUS |
| Stability tests | reason/assumption unstable | ESCALATE | ESCALATE |
| Stability tests | groupthink + no evidence | ESCALATE | ESCALATE |
| ANALYSIS map | missing or wrong header | ERROR | ERROR |
| ANALYSIS coverage | dimension_coverage < 0.80 | ESCALATE | ESCALATE |
| ANALYSIS | frame dropping | ERROR | ERROR |
| ANALYSIS | information boundary self-tagged | ERROR | ERROR |
| ANALYSIS | semantic CTR not track_only | ERROR | ERROR |
| Schema | version mismatch | ERROR | ERROR |

---

## 34. Schema Versioning and Backward Compatibility

### 34.1 Version Rule

- proof.schema_version MUST equal "3.0B"
- All V3.0B fields listed in Section 30 are the canonical schema
- New fields introduced in V3.0B (entity_registry, pin_cap, mechanism_budget, evidence_pinning, virtual_frames, perspective_lenses, adversarial_rotation, breadth_recovery, anti_groupthink_search, analogical_queries, dimension_tracker, information_boundary, coverage_assessment, reasoning_contract, outcome_confidence, warnings, telemetry_hooks) are optional during the transition period

### 34.2 Transition Period

- First 10 V3.0B runs OR until config.yaml sets `transition_complete: true`
- During transition: missing new fields are tolerated (WARNING, not ERROR)
- After transition: all fields per Section 30 are mandatory per their "Required" conditions

### 34.3 Backward Compatibility

- V3.0 proof files MUST parse without ERROR under V3.0B code
- Unknown fields in V3.0 proofs are ignored
- Missing V3.0B-specific fields in V3.0 proofs are tolerated
- schema_version check: "3.0" proofs processed under V3.0 rules; "3.0B" proofs processed under V3.0B rules

### 34.4 Acceptance Criteria

- schema_version present on all proofs
- V3.0 proofs parse without error under V3.0B code
- New V3.0B fields optional during transition, mandatory after
- Transition period has defined exit criteria

### 34.5 Failure Modes

| Failure | Tier | Outcome |
|---|---|---|
| schema_version missing | ERROR | ERROR |
| V3.0B run with schema_version != "3.0B" | ERROR | ERROR |
| V3.0 proof causes ERROR under V3.0B parser | ERROR | ERROR (parser bug) |
| Mandatory field missing after transition period | ERROR | ERROR |

**Traceability:** R0

---

## 35. Definition of Done -- Final Pass Condition

Brain V8 V3.0B is Done only if ALL of the following are true:

1. Gate 1 executes exactly once as a separate stage, before CS Audit, routing NEED_MORE and fatal premises
2. CS Audit executes exactly once as a separate stage, after Gate 1, providing binding effort calibration, defect routing, and auto-reformulation
3. Every admitted run preserves topology 4→3→2→2
4. All mechanisms implemented and recorded in proof.json: Gate 1, CS Audit, Retroactive Premise Escalation, Virtual Frame Seeder, Perspective Lenses, Rotating Adversarial, Breadth-Recovery Pulse, Calibrated Anti-Groupthink Search, Frame-Argument Coupling, Moderated Frame Rebuttal, Distant-Domain Analogical Queries, Concurrent Mechanism Budget, Claim-Aware Pinning (DC-5 fix), Canonical Cross-Round Entity IDs, Evidence Ledger, Ungrounded Stat Detection, Semantic Contradiction Detection (capped), Paywall Detection, Cross-Domain Filter, Argument Auto-Promotion, Synthesis with Full Deliberation Arc, Residue Verification, Stability Tests, Dimension Tracker (ANALYSIS), Information Boundary Classification (ANALYSIS), Coverage Assessment (ANALYSIS), ANALYSIS Gate 2
5. Gate 2 is fully deterministic and evaluable from proof.json alone, with rule_trace recorded
6. Three-tier failure taxonomy applied: ERROR (infrastructure/integrity), ESCALATE (mechanism failures), WARNING (suboptimal conditions)
7. ERROR is emitted only for infrastructure or fatal integrity failure
8. NEED_MORE is emitted only from Gate 1 (not from CS Audit or later stages)
9. DECIDE runs cannot pass with unresolved material evidence, premise, frame, contradiction, support, pin-cap, or residue defects
10. ANALYSIS runs cannot pass without dimension_coverage >= 0.80 and residue compliance
11. ANALYSIS semantic contradictions marked track_only: true and bypass Gate 2 blocker logic
12. DC-5 fix implemented as three pillars: claim-aware pinning + 15% budget cap + forensic logging
13. Canonical cross-round entity IDs assigned to all entities with collision handling
14. Pin cap (max_pinned_claims = 5) enforced with forced archival on overflow
15. 15% pin budget measured proactively with designated tokenizer + 10% safety margin
16. Concurrent mechanism budget respects priority hierarchy with 25% global token reserve
17. All thresholds configurable via config.yaml, asserted at exact values in tests, tracked via telemetry_hooks
18. schema_version = "3.0B" on all V3.0B runs
19. Backward compatibility: V3.0 proofs parse without error under V3.0B code
20. The verification suite in Section 32 passes
21. The complete proof.json contract in Section 30 is satisfied

---

## Current Implementation: thinker/types.py

"""Core types for the Thinker V8 Brain engine."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


def extract_json(text: str) -> dict:
    """Extract JSON object from LLM response text.

    Handles: raw JSON, code-fenced JSON, JSON with trailing commentary.
    Raises json.JSONDecodeError if no valid JSON object found.
    """
    # Strip code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])
    cleaned = cleaned.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find first { and match to closing }
    start = cleaned.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", cleaned, 0)

    depth = 0
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start:i + 1])

    raise json.JSONDecodeError("Unterminated JSON object", cleaned, start)


class BrainError(Exception):
    """Fatal pipeline error — zero tolerance for silent failures.

    Raised when a critical component fails: LLM call, position extraction,
    argument tracking, synthesis. The pipeline must stop immediately.
    """
    def __init__(
        self,
        stage: str,
        message: str,
        detail: str = "",
        error_class: str = "FATAL_INTEGRITY",
    ):
        self.stage = stage
        self.message = message
        self.detail = detail
        self.error_class = error_class
        super().__init__(f"[{stage}] {message}")


class Outcome(Enum):
    """Top-level outcomes of a Brain deliberation (DoD v3.0 Section 1)."""
    DECIDE = "DECIDE"
    ESCALATE = "ESCALATE"
    NO_CONSENSUS = "NO_CONSENSUS"
    ANALYSIS = "ANALYSIS"
    ERROR = "ERROR"
    NEED_MORE = "NEED_MORE"  # PreflightAssessment only


class Confidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BlockerKind(Enum):
    EVIDENCE_GAP = "EVIDENCE_GAP"
    CONTRADICTION = "CONTRADICTION"
    UNRESOLVED_DISAGREEMENT = "UNRESOLVED_DISAGREEMENT"
    CONTESTED_POSITION = "CONTESTED_POSITION"
    COVERAGE_GAP = "COVERAGE_GAP"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"


class BlockerStatus(Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"
    DROPPED = "DROPPED"


class ArgumentStatus(Enum):
    ADDRESSED = "ADDRESSED"
    MENTIONED = "MENTIONED"
    IGNORED = "IGNORED"


class AcceptanceStatus(Enum):
    ACCEPTED = "ACCEPTED"


class Modality(Enum):
    DECIDE = "DECIDE"
    ANALYSIS = "ANALYSIS"


class Answerability(Enum):
    ANSWERABLE = "ANSWERABLE"
    NEED_MORE = "NEED_MORE"
    INVALID_FORM = "INVALID_FORM"


class SearchScope(Enum):
    NONE = "NONE"
    TARGETED = "TARGETED"
    BROAD = "BROAD"


class PremiseFlagRouting(Enum):
    REQUESTER_FIXABLE = "REQUESTER_FIXABLE"
    MANAGEABLE_UNKNOWN = "MANAGEABLE_UNKNOWN"
    FRAMING_DEFECT = "FRAMING_DEFECT"
    FATAL_PREMISE = "FATAL_PREMISE"


class StakesClass(Enum):
    LOW = "LOW"
    STANDARD = "STANDARD"
    HIGH = "HIGH"


class QuestionClass(Enum):
    TRIVIAL = "TRIVIAL"
    WELL_ESTABLISHED = "WELL_ESTABLISHED"
    OPEN = "OPEN"
    AMBIGUOUS = "AMBIGUOUS"


class EffortTier(Enum):
    SHORT_CIRCUIT = "SHORT_CIRCUIT"
    STANDARD = "STANDARD"
    ELEVATED = "ELEVATED"


class PremiseFlagSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class PremiseFlagType(Enum):
    INTERNAL_CONTRADICTION = "INTERNAL_CONTRADICTION"
    UNSUPPORTED_ASSUMPTION = "UNSUPPORTED_ASSUMPTION"
    AMBIGUITY = "AMBIGUITY"
    IMPOSSIBLE_REQUEST = "IMPOSSIBLE_REQUEST"
    FRAMING_DEFECT = "FRAMING_DEFECT"


class CoverageObligation(Enum):
    CONTRARIAN = "CONTRARIAN"
    MECHANISM_ANALYSIS = "MECHANISM_ANALYSIS"
    OPERATIONAL_RISK = "OPERATIONAL_RISK"
    OBJECTIVE_REFRAMING = "OBJECTIVE_REFRAMING"


class TimeHorizon(Enum):
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"


class FrameType(Enum):
    INVERSION = "INVERSION"
    OBJECTIVE_REWRITE = "OBJECTIVE_REWRITE"
    PREMISE_CHALLENGE = "PREMISE_CHALLENGE"
    CROSS_DOMAIN_ANALOGY = "CROSS_DOMAIN_ANALOGY"
    OPPOSITE_STANCE = "OPPOSITE_STANCE"
    REMOVE_PROBLEM = "REMOVE_PROBLEM"


class FrameSurvivalStatus(Enum):
    ACTIVE = "ACTIVE"
    CONTESTED = "CONTESTED"
    DROPPED = "DROPPED"
    ADOPTED = "ADOPTED"
    REBUTTED = "REBUTTED"
    # ANALYSIS mode statuses
    EXPLORED = "EXPLORED"
    NOTED = "NOTED"
    UNEXPLORED = "UNEXPLORED"


class ResolutionStatus(Enum):
    ORIGINAL = "ORIGINAL"
    REFINED = "REFINED"
    SUPERSEDED = "SUPERSEDED"


class DetectionMode(Enum):
    NUMERIC = "NUMERIC"
    SEMANTIC = "SEMANTIC"


class ContradictionSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ContradictionStatus(Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    NON_MATERIAL = "NON_MATERIAL"


class EvidenceSupportStatus(Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"


class AnalogyTestStatus(Enum):
    UNTESTED = "UNTESTED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"


class QueryProvenance(Enum):
    MODEL_CLAIM = "model_claim"
    PREMISE_DEFECT = "premise_defect"
    FRAME_TEST = "frame_test"
    EVIDENCE_GAP = "evidence_gap"
    UNGROUNDED_STAT = "ungrounded_stat"


class QueryStatus(Enum):
    SUCCESS = "SUCCESS"
    ZERO_RESULT = "ZERO_RESULT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class DispositionTargetType(Enum):
    BLOCKER = "BLOCKER"
    FRAME = "FRAME"
    CLAIM = "CLAIM"
    CONTRADICTION = "CONTRADICTION"
    ARGUMENT = "ARGUMENT"  # DOD §11.3: open material arguments need dispositions


class ErrorClass(Enum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    FATAL_INTEGRITY = "FATAL_INTEGRITY"


class AssumptionVerifiability(Enum):
    # DOD §4.2: VERIFIABLE | UNVERIFIABLE | FALSE | UNKNOWN
    VERIFIABLE = "VERIFIABLE"
    UNVERIFIABLE = "UNVERIFIABLE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass
class ModelResponse:
    """Raw response from a single LLM call."""
    model: str
    ok: bool
    text: str
    elapsed_s: float
    error: Optional[str] = None


@dataclass
class EvidenceItem:
    """A single piece of verified evidence."""
    evidence_id: str
    topic: str
    fact: str
    url: str
    confidence: Confidence
    content_hash: str = ""
    score: float = 0.0
    topic_cluster: str = ""
    authority_tier: str = "STANDARD"  # STANDARD, HIGH, AUTHORITATIVE
    is_active: bool = True
    is_archived: bool = False
    referenced_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "topic": self.topic,
            "fact": self.fact,
            "source_url": self.url,
            "confidence": self.confidence.value,
            "content_hash": self.content_hash,
            "score": self.score,
            "topic_cluster": self.topic_cluster,
            "authority_tier": self.authority_tier,
            "is_active": self.is_active,
            "is_archived": self.is_archived,
            "referenced_by": self.referenced_by,
        }


@dataclass
class Argument:
    """A distinct argument extracted from model output."""
    argument_id: str
    round_num: int
    model: str
    text: str
    status: ArgumentStatus = ArgumentStatus.IGNORED
    addressed_in_round: Optional[int] = None
    resolution_status: ResolutionStatus = ResolutionStatus.ORIGINAL
    refines: Optional[str] = None
    superseded_by: Optional[str] = None
    dimension_id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    open: bool = True
    blocker_link_ids: list[str] = field(default_factory=list)  # DOD §11.1

    def to_dict(self) -> dict:
        return {
            "argument_id": self.argument_id,
            "round_origin": self.round_num,
            "model_id": self.model,
            "text": self.text,
            "status": self.status.value,
            "addressed_in_round": self.addressed_in_round,
            "resolution_status": self.resolution_status.value,
            "refines": self.refines,
            "superseded_by": self.superseded_by,
            "dimension_id": self.dimension_id,
            "blocker_link_ids": self.blocker_link_ids,
            "evidence_refs": self.evidence_refs,
            "open": self.open,
        }


@dataclass
class Position:
    """A model's position in a given round."""
    model: str
    round_num: int
    primary_option: str
    components: list[str] = field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    qualifier: str = ""
    kind: str = "single"  # "single" or "sequence"


@dataclass
class Blocker:
    """A tracked blocker (evidence gap, contradiction, disagreement)."""
    blocker_id: str
    kind: BlockerKind
    source: str
    detected_round: int
    status: BlockerStatus = BlockerStatus.OPEN
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    status_history: list[dict] = field(default_factory=list)
    models_involved: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    detail: str = ""
    resolution_note: str = ""

    def to_dict(self) -> dict:
        serialized_history = []
        for entry in self.status_history:
            status = entry.get("status")
            serialized_history.append({
                **entry,
                "status": "DEFERRED" if status == "DROPPED" else status,
            })
        return {
            "blocker_id": self.blocker_id,
            "type": self.kind.value,
            "source_dimension": self.source,
            "detected_round": self.detected_round,
            "status": "DEFERRED" if self.status.value == "DROPPED" else self.status.value,
            "severity": self.severity,
            "status_history": serialized_history,
            "models_involved": self.models_involved,
            "linked_ids": self.evidence_ids,
            "detail": self.detail,
            "resolution_summary": self.resolution_note,
        }


@dataclass
class Contradiction:
    """A detected contradiction between evidence items."""
    ctr_id: str
    evidence_ids: list[str]
    topic: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    status: str = "OPEN"  # OPEN, RESOLVED, NON_MATERIAL
    detection_mode: str = "NUMERIC"  # NUMERIC, SEMANTIC
    justification: str = ""
    linked_claim_ids: list[str] = field(default_factory=list)
    # DOD §12.1 unified schema fields
    evidence_ref_a: str = ""
    evidence_ref_b: str = ""
    same_entity: bool = False
    same_timeframe: bool = False

    @property
    def contradiction_id(self) -> str:
        """Backward-compatible alias for older callers."""
        return self.ctr_id

    @contradiction_id.setter
    def contradiction_id(self, value: str) -> None:
        self.ctr_id = value

    def to_dict(self) -> dict:
        return {
            "ctr_id": self.ctr_id,
            "detection_mode": self.detection_mode,
            "evidence_ref_a": self.evidence_ref_a,
            "evidence_ref_b": self.evidence_ref_b,
            "same_entity": self.same_entity,
            "same_timeframe": self.same_timeframe,
            "topic": self.topic,
            "severity": self.severity,
            "status": self.status,
            "justification": self.justification,
            "linked_claim_ids": self.linked_claim_ids,
        }


@dataclass
class SearchResult:
    """A single search result (URL + content)."""
    url: str
    title: str
    snippet: str
    full_content: Optional[str] = None


@dataclass
class Gate1Result:
    """Result of Gate 1 assessment."""
    passed: bool
    outcome: Outcome
    questions: list[str] = field(default_factory=list)
    reasoning: str = ""
    search_recommended: bool = True  # Default to YES (conservative)
    search_reasoning: str = ""


@dataclass
class Gate2Assessment:
    """Result of Gate 2 trust assessment."""
    outcome: Outcome
    convergence_ok: bool
    evidence_credible: bool
    dissent_addressed: bool
    enough_data: bool
    report_honest: bool
    reasoning: str = ""
    modality: Optional[str] = None  # DECIDE or ANALYSIS
    rule_trace: list[dict] = field(default_factory=list)


@dataclass
class RoundResult:
    """Result of a single deliberation round."""
    round_num: int
    responses: dict[str, ModelResponse] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)

    @property
    def responded(self) -> list[str]:
        return [m for m, r in self.responses.items() if r.ok]

    @property
    def texts(self) -> dict[str, str]:
        return {m: r.text for m, r in self.responses.items() if r.ok}


@dataclass
class BrainResult:
    """Final result of a complete Brain deliberation."""
    outcome: Outcome
    proof: dict
    report: str
    gate1: Optional[Gate1Result] = None
    preflight: Optional["PreflightResult"] = None
    gate2: Optional[Gate2Assessment] = None
    dimensions: Optional["DimensionSeedResult"] = None
    perspective_cards: Optional[list["PerspectiveCard"]] = None
    divergence: Optional["DivergenceResult"] = None
    stability: Optional["StabilityResult"] = None
    error_class: Optional[ErrorClass] = None


# --- V9 New Dataclasses ---


@dataclass
class PremiseFlag:
    """A premise defect detected by PreflightAssessment."""
    flag_id: str
    flag_type: PremiseFlagType
    severity: PremiseFlagSeverity
    summary: str
    routing: PremiseFlagRouting = PremiseFlagRouting.MANAGEABLE_UNKNOWN
    blocking: bool = False
    resolved: bool = False
    resolved_stage: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "flag_id": self.flag_id,
            "flag_type": self.flag_type.value,
            "severity": self.severity.value,
            "summary": self.summary,
            "routing": self.routing.value,
            "blocking": self.blocking,
            "resolved": self.resolved,
            "resolved_stage": self.resolved_stage,
        }


@dataclass
class HiddenContextGap:
    """A hidden context gap detected by PreflightAssessment."""
    gap_id: str
    description: str
    impact_if_unresolved: str
    material: bool = False
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "gap_id": self.gap_id,
            "description": self.description,
            "impact_if_unresolved": self.impact_if_unresolved,
            "material": self.material,
            "resolved": self.resolved,
        }


@dataclass
class CriticalAssumption:
    """A critical assumption surfaced by PreflightAssessment."""
    assumption_id: str
    text: str
    verifiability: AssumptionVerifiability = AssumptionVerifiability.UNKNOWN
    material: bool = True
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "assumption_id": self.assumption_id,
            "text": self.text,
            "verifiability": self.verifiability.value,
            "material": self.material,
            "resolved": self.resolved,
        }


@dataclass
class PreflightResult:
    """Result of PreflightAssessment (DoD v3.0 Section 4)."""
    executed: bool = True
    parse_ok: bool = True
    answerability: Answerability = Answerability.ANSWERABLE
    question_class: QuestionClass = QuestionClass.OPEN
    stakes_class: StakesClass = StakesClass.STANDARD
    effort_tier: EffortTier = EffortTier.STANDARD
    modality: Modality = Modality.DECIDE
    search_scope: SearchScope = SearchScope.TARGETED
    exploration_required: bool = False
    short_circuit_allowed: bool = False
    fatal_premise: bool = False
    follow_up_questions: list[str] = field(default_factory=list)
    premise_flags: list[PremiseFlag] = field(default_factory=list)
    hidden_context_gaps: list[HiddenContextGap] = field(default_factory=list)
    critical_assumptions: list[CriticalAssumption] = field(default_factory=list)
    reasoning: str = ""

    @property
    def has_critical_flags(self) -> bool:
        return any(f.severity == PremiseFlagSeverity.CRITICAL and not f.resolved
                   for f in self.premise_flags)

    @property
    def unresolved_critical_flags(self) -> list[PremiseFlag]:
        return [f for f in self.premise_flags
                if f.severity == PremiseFlagSeverity.CRITICAL and not f.resolved]

    @property
    def has_material_unresolved_gaps(self) -> bool:
        return any(g.material and not g.resolved for g in self.hidden_context_gaps)

    @property
    def has_fatal_assumptions(self) -> bool:
        return any(a.verifiability in (AssumptionVerifiability.UNVERIFIABLE,
                                        AssumptionVerifiability.FALSE)
                   and a.material and not a.resolved
                   for a in self.critical_assumptions)

    def to_dict(self) -> dict:
        return {
            "executed": self.executed,
            "parse_ok": self.parse_ok,
            "answerability": self.answerability.value,
            "question_class": self.question_class.value,
            "stakes_class": self.stakes_class.value,
            "effort_tier": self.effort_tier.value,
            "modality": self.modality.value,
            "search_scope": self.search_scope.value,
            "exploration_required": self.exploration_required,
            "short_circuit_allowed": self.short_circuit_allowed,
            "fatal_premise": self.fatal_premise,
            "follow_up_questions": self.follow_up_questions,
            "premise_flags": [f.to_dict() for f in self.premise_flags],
            "hidden_context_gaps": [g.to_dict() for g in self.hidden_context_gaps],
            "critical_assumptions": [a.to_dict() for a in self.critical_assumptions],
            "reasoning": self.reasoning,
        }


@dataclass
class DimensionItem:
    """A single exploration dimension from the Dimension Seeder."""
    dimension_id: str
    name: str
    mandatory: bool = True
    coverage_status: str = "ZERO"  # ZERO, PARTIAL, SATISFIED
    argument_count: int = 0
    justified_irrelevance: bool = False
    irrelevance_explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "dimension_id": self.dimension_id,
            "name": self.name,
            "mandatory": self.mandatory,
            "coverage_status": self.coverage_status,
            "argument_count": self.argument_count,
            "justified_irrelevance": self.justified_irrelevance,
            "irrelevance_explanation": self.irrelevance_explanation,  # DOD §6.1
        }


@dataclass
class DimensionSeedResult:
    """Result of the Dimension Seeder (DoD v3.0 Section 6)."""
    seeded: bool = True
    parse_ok: bool = True
    items: list[DimensionItem] = field(default_factory=list)
    dimension_count: int = 0
    dimension_coverage_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "seeded": self.seeded,
            "parse_ok": self.parse_ok,
            "items": [d.to_dict() for d in self.items],
            "dimension_count": self.dimension_count,
            "dimension_coverage_score": self.dimension_coverage_score,
        }


@dataclass
class PerspectiveCard:
    """Structured R1 output for a single model (DoD v3.0 Section 7).

    field_provenance tracks per-field extraction method:
    - "native": field extracted directly from model's R1 output via regex
    - "inferred:haiku": field inferred by Haiku from model's R1 output
    - "inferred:sonnet": field inferred by Sonnet (fallback) from model's R1 output
    """
    model_id: str
    primary_frame: str = ""
    hidden_assumption_attacked: str = ""
    stakeholder_lens: str = ""
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM
    failure_mode: str = ""
    coverage_obligation: CoverageObligation = CoverageObligation.MECHANISM_ANALYSIS
    dimensions_addressed: list[str] = field(default_factory=list)
    field_provenance: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "primary_frame": self.primary_frame,
            "hidden_assumption_attacked": self.hidden_assumption_attacked,
            "stakeholder_lens": self.stakeholder_lens,
            "time_horizon": self.time_horizon.value,
            "failure_mode": self.failure_mode,
            "coverage_obligation": self.coverage_obligation.value,
            "dimensions_addressed": self.dimensions_addressed,
            "field_provenance": self.field_provenance,
        }


@dataclass
class FrameInfo:
    """A material alternative frame tracked by the Divergent Framing system."""
    frame_id: str
    text: str
    origin_round: int = 1
    origin_model: str = ""
    frame_type: FrameType = FrameType.INVERSION
    material_to_outcome: bool = True
    survival_status: FrameSurvivalStatus = FrameSurvivalStatus.ACTIVE
    r2_drop_vote_count: int = 0
    r2_drop_vote_refs: list[str] = field(default_factory=list)
    rebuttal_status: str = "NONE"  # NONE, PARTIAL, REBUTTED
    synthesis_disposition_status: str = "UNADDRESSED"  # ADDRESSED, UNADDRESSED

    def to_dict(self) -> dict:
        return {
            "frame_id": self.frame_id,
            "text": self.text,
            "origin_round": self.origin_round,
            "origin_model": self.origin_model,
            "frame_type": self.frame_type.value,
            "material_to_outcome": self.material_to_outcome,
            "survival_status": self.survival_status.value,
            "r2_drop_vote_count": self.r2_drop_vote_count,
            "r2_drop_vote_refs": self.r2_drop_vote_refs,
            "rebuttal_status": self.rebuttal_status,
            "synthesis_disposition_status": self.synthesis_disposition_status,
        }


@dataclass
class CrossDomainAnalogy:
    """A cross-domain analogy extracted from deliberation."""
    analogy_id: str
    source_domain: str
    target_claim_id: str
    transfer_mechanism: str
    test_status: AnalogyTestStatus = AnalogyTestStatus.UNTESTED

    def to_dict(self) -> dict:
        return {
            "analogy_id": self.analogy_id,
            "source_domain": self.source_domain,
            "target_claim_id": self.target_claim_id,
            "transfer_mechanism": self.transfer_mechanism,
            "test_status": self.test_status.value,
        }


@dataclass
class DivergenceResult:
    """Result of the Divergent Framing system (DoD v3.0 Section 8)."""
    required: bool = True
    adversarial_slot_assigned: bool = False
    adversarial_model_id: Optional[str] = None
    adversarial_assignment_type: Optional[str] = None
    framing_pass_executed: bool = False
    exploration_stress_triggered: bool = False
    stress_seed_frames: list[dict] = field(default_factory=list)
    alt_frames: list[FrameInfo] = field(default_factory=list)
    cross_domain_analogies: list[CrossDomainAnalogy] = field(default_factory=list)

    @property
    def material_unrebutted_frame_count(self) -> int:
        return sum(1 for f in self.alt_frames
                   if f.material_to_outcome
                   and f.survival_status in (FrameSurvivalStatus.ACTIVE,
                                              FrameSurvivalStatus.CONTESTED))

    def to_dict(self) -> dict:
        return {
            "required": self.required,
            "adversarial_slot_assigned": self.adversarial_slot_assigned,
            "adversarial_model_id": self.adversarial_model_id,
            "adversarial_assignment_type": self.adversarial_assignment_type,
            "framing_pass_executed": self.framing_pass_executed,
            "exploration_stress_triggered": self.exploration_stress_triggered,
            "stress_seed_frames": self.stress_seed_frames,
            "material_unrebutted_frame_count": self.material_unrebutted_frame_count,
            "alt_frames": [f.to_dict() for f in self.alt_frames],
            "cross_domain_analogies": [a.to_dict() for a in self.cross_domain_analogies],
        }


@dataclass
class SearchLogEntry:
    """A single search query log entry (DoD v3.0 Section 9)."""
    query_id: str
    query_text: str
    provenance: QueryProvenance
    issued_after_stage: str
    pages_fetched: int = 0
    evidence_yield_count: int = 0
    query_status: QueryStatus = QueryStatus.SUCCESS

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "provenance": self.provenance.value,
            "issued_after_stage": self.issued_after_stage,
            "pages_fetched": self.pages_fetched,
            "evidence_yield_count": self.evidence_yield_count,
            "query_status": self.query_status.value,
        }


@dataclass
class EvictionEvent:
    """An evidence eviction event for the two-tier ledger."""
    event_id: str
    evidence_id: str
    from_active: bool = True
    to_archive: bool = True
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "evidence_id": self.evidence_id,
            "from_active": self.from_active,
            "to_archive": self.to_archive,
            "reason": self.reason,
        }


@dataclass
class DecisiveClaim:
    """A decisive claim with evidence bindings (DoD v3.0 Section 13)."""
    claim_id: str
    text: str
    material_to_conclusion: bool = True
    evidence_refs: list[str] = field(default_factory=list)
    evidence_support_status: EvidenceSupportStatus = EvidenceSupportStatus.UNSUPPORTED
    analogy_refs: list[str] = field(default_factory=list)
    supporting_model_ids: list[str] = field(default_factory=list)  # DOD §15.2: which models share this claim

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "material_to_conclusion": self.material_to_conclusion,
            "evidence_refs": self.evidence_refs,
            "evidence_support_status": self.evidence_support_status.value,
            "analogy_refs": self.analogy_refs,
            "supporting_model_ids": self.supporting_model_ids,
        }


@dataclass
class StabilityResult:
    """Stability test results (DoD v3.0 Section 15)."""
    conclusion_stable: bool = True
    reason_stable: bool = True
    assumption_stable: bool = True
    independent_evidence_present: bool = False
    fast_consensus_observed: bool = False
    groupthink_warning: bool = False

    def to_dict(self) -> dict:
        return {
            "conclusion_stable": self.conclusion_stable,
            "reason_stable": self.reason_stable,
            "assumption_stable": self.assumption_stable,
            "independent_evidence_present": self.independent_evidence_present,
            "fast_consensus_observed": self.fast_consensus_observed,
            "groupthink_warning": self.groupthink_warning,
        }


@dataclass
class DispositionObject:
    """A structured disposition for synthesis residue (DoD v3.0 Section 14)."""
    target_type: DispositionTargetType
    target_id: str
    status: str
    importance: str  # LOW, MEDIUM, HIGH, CRITICAL
    narrative_explanation: str
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_type": self.target_type.value,
            "target_id": self.target_id,
            "status": self.status,
            "importance": self.importance,
            "narrative_explanation": self.narrative_explanation,
            "evidence_refs": self.evidence_refs,
        }


@dataclass
class UngroundedStatItem:
    """DOD §9.2 schema for a flagged ungrounded statistical claim."""
    claim_id: str
    text: str
    numeric: bool = True
    verified: bool = False
    blocker_id: Optional[str] = None
    severity: str = "MEDIUM"
    status: str = "UNVERIFIED_CLAIM"

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "numeric": self.numeric,
            "verified": self.verified,
            "blocker_id": self.blocker_id,
            "severity": self.severity,
            "status": self.status,
        }


@dataclass(init=False)
class UngroundedStatResult:
    """DOD Â§9.2 container for detector findings and execution state."""
    flagged_claims: list[UngroundedStatItem]
    post_r1_executed: bool
    post_r2_executed: bool

    def __init__(
        self,
        flagged_claims: Optional[list[UngroundedStatItem]] = None,
        *,
        items: Optional[list[UngroundedStatItem]] = None,
        post_r1_executed: bool = False,
        post_r2_executed: bool = False,
    ):
        claims = flagged_claims if flagged_claims is not None else items
        self.flagged_claims = list(claims or [])
        self.post_r1_executed = post_r1_executed
        self.post_r2_executed = post_r2_executed

    @property
    def items(self) -> list[UngroundedStatItem]:
        return self.flagged_claims

    @items.setter
    def items(self, value: list[UngroundedStatItem]) -> None:
        self.flagged_claims = list(value)

    def to_dict(self) -> dict:
        return {
            "flagged_claims": [item.to_dict() if hasattr(item, "to_dict") else item for item in self.flagged_claims],
            "post_r1_executed": self.post_r1_executed,
            "post_r2_executed": self.post_r2_executed,
        }


@dataclass
class SynthesisPacket:
    """DOD §14.1 controller-curated synthesis packet."""
    packet_complete: bool = False
    brief_excerpt: str = ""
    final_positions: list[dict] = field(default_factory=list)
    argument_lifecycle: list[dict] = field(default_factory=list)
    argument_count_total: int = 0
    argument_count_open: int = 0
    frame_summary: list[dict] = field(default_factory=list)
    material_unrebutted_frames: int = 0
    blocker_summary: list[dict] = field(default_factory=list)
    open_blocker_count: int = 0
    decisive_claims: list[dict] = field(default_factory=list)
    contradiction_summary: list[dict] = field(default_factory=list)
    premise_flag_summary: list[dict] = field(default_factory=list)
    evidence_count: int = 0

    def to_dict(self) -> dict:
        return {
            "packet_complete": self.packet_complete,
            "brief_excerpt": self.brief_excerpt,
            "final_positions": self.final_positions,
            "argument_lifecycle": self.argument_lifecycle,
            "argument_count_total": self.argument_count_total,
            "argument_count_open": self.argument_count_open,
            "frame_summary": self.frame_summary,
            "material_unrebutted_frames": self.material_unrebutted_frames,
            "blocker_summary": self.blocker_summary,
            "open_blocker_count": self.open_blocker_count,
            "decisive_claims": self.decisive_claims,
            "contradiction_summary": self.contradiction_summary,
            "premise_flag_summary": self.premise_flag_summary,
            "evidence_count": self.evidence_count,
        }


@dataclass
class ResidueVerification:
    """DOD §14.4 residue verification / disposition coverage result."""
    coverage_pass: bool = True
    omission_rate: float = 0.0
    omissions: list[dict] = field(default_factory=list)
    deep_scan_triggered: bool = False
    expected_disposition_count: int = 0
    emitted_disposition_count: int = 0
    total_required: int = 0
    total_disposed: int = 0
    deep_scan: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "coverage_pass": self.coverage_pass,
            "omission_rate": self.omission_rate,
            "omissions": self.omissions,
            "deep_scan_triggered": self.deep_scan_triggered,
            "expected_disposition_count": self.expected_disposition_count,
            "emitted_disposition_count": self.emitted_disposition_count,
            "total_required": self.total_required,
            "total_disposed": self.total_disposed,
            "deep_scan": self.deep_scan,
        }


@dataclass
class AnalysisMap:
    """DOD §18.3 analysis-mode exploratory map."""
    header: str = "EXPLORATORY MAP — NOT A DECISION"
    dimensions: dict = field(default_factory=dict)
    hypothesis_ledger: list[dict] = field(default_factory=list)
    total_argument_count: int = 0
    dimension_coverage_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "header": self.header,
            "dimensions": self.dimensions,
            "hypothesis_ledger": self.hypothesis_ledger,
            "total_argument_count": self.total_argument_count,
            "dimension_coverage_score": self.dimension_coverage_score,
        }


@dataclass
class AnalysisDebug:
    """DOD §18.4 analysis-mode debug audit record."""
    debug_mode: bool = False
    debug_gate2_result: Optional[str] = None
    actual_output: Optional[str] = None
    rules_enforced: bool = True
    remaining_debug_runs: int = 0
    analysis_mode_active: bool = True
    dimension_coverage_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "debug_mode": self.debug_mode,
            "debug_gate2_result": self.debug_gate2_result,
            "actual_output": self.actual_output,
            "rules_enforced": self.rules_enforced,
            "remaining_debug_runs": self.remaining_debug_runs,
            "analysis_mode_active": self.analysis_mode_active,
            "dimension_coverage_score": self.dimension_coverage_score,
        }


@dataclass
class SemanticContradiction:
    """A semantic contradiction detected by LLM analysis."""
    ctr_id: str
    detection_mode: DetectionMode = DetectionMode.SEMANTIC
    evidence_ref_a: str = ""
    evidence_ref_b: str = ""
    same_entity: bool = False
    same_timeframe: bool = False
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    status: ContradictionStatus = ContradictionStatus.OPEN
    justification: str = ""
    linked_claim_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ctr_id": self.ctr_id,
            "detection_mode": self.detection_mode.value,
            "evidence_ref_a": self.evidence_ref_a,
            "evidence_ref_b": self.evidence_ref_b,
            "same_entity": self.same_entity,
            "same_timeframe": self.same_timeframe,
            "severity": self.severity.value,
            "status": self.status.value,
            "justification": self.justification,
            "linked_claim_ids": self.linked_claim_ids,
        }

---

## Current Implementation: thinker/brain.py

"""Brain Orchestrator — wires the full V9 deliberation pipeline.

Flow:
  Preflight -> Dimensions -> R1(+adversarial) -> PerspectiveCards -> FramingPass
  -> UngroundedR1 -> Search(R1) -> R2 -> FrameSurvivalR2 -> UngroundedR2 -> Search(R2)
  -> R3 -> FrameSurvivalR3 -> R4 -> SemanticContradiction -> SynthesisPacket
  -> Synthesis -> Stability -> Gate 2

Debug modes:
  --verbose          : Full logging at each stage
  --stop-after STAGE : Run up to STAGE, save checkpoint, exit
  --resume FILE      : Resume from a checkpoint file

Stage IDs: preflight, dimensions, r1, track1, perspective_cards, framing_pass,
           ungrounded_r1, search1, r2, track2, frame_survival_r2, ungrounded_r2, search2,
           r3, track3, frame_survival_r3, r4, track4,
           semantic_contradiction, synthesis_packet, synthesis, stability, gate2
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Awaitable, Optional

from thinker.argument_tracker import ArgumentTracker
from thinker.config import BrainConfig, ROUND_TOPOLOGY
from thinker.debug import RunLog
from thinker.evidence import EvidenceLedger
from thinker.evidence_extractor import extract_evidence_from_page
from thinker.gate2 import run_gate2_deterministic, classify_outcome
from thinker.invariant import validate_invariants
from thinker.page_fetch import fetch_pages_for_results
from thinker.proof import ProofBuilder
from thinker.residue import check_synthesis_residue, run_deep_semantic_scan
from thinker.rounds import execute_round
from thinker.search import SearchOrchestrator, SearchPhase
from thinker.synthesis import run_synthesis
from thinker.tools.blocker import BlockerLedger
from thinker.tools.position import PositionTracker
from thinker.checkpoint import PipelineState, should_stop
from thinker.types import (
    ArgumentStatus, BlockerKind, BrainError, BrainResult, Confidence,
    EvidenceItem, Outcome, Position, SearchResult, UngroundedStatItem,
    UngroundedStatResult,
)
from thinker.preflight import run_preflight
from thinker.dimension_seeder import run_dimension_seeder, format_dimensions_for_prompt
from thinker.perspective_cards import extract_perspective_cards, format_perspective_card_instructions
from thinker.divergent_framing import (
    run_framing_extract, run_frame_survival_check,
    check_exploration_stress, format_frames_for_prompt, format_r2_frame_enforcement,
    validate_r2_frame_obligations,
)
from thinker.semantic_contradiction import run_semantic_contradiction_pass
from thinker.tools.ungrounded import find_ungrounded_stats, generate_verification_queries
from thinker.stability import run_stability_tests
from thinker.decisive_claims import extract_decisive_claims
from thinker.analysis_mode import get_analysis_round_preamble, get_analysis_synthesis_contract
from thinker.synthesis_packet import build_synthesis_packet, format_synthesis_packet_for_prompt
from thinker.residue import check_disposition_coverage
from thinker.types import (
    DimensionSeedResult, DivergenceResult, FrameSurvivalStatus, Modality, PreflightResult, StabilityResult,
)


class Brain:
    """The V9 Brain deliberation engine."""

    def __init__(
        self,
        config: BrainConfig,
        llm_client,
        search_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        sonar_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        verbose: bool = False,
        stop_after: Optional[str] = None,
        outdir: str = "./output",
        resume_state: Optional[PipelineState] = None,
        debug_step: bool = False,
        search_override: Optional[bool] = None,
    ):
        self._config = config
        self._llm = llm_client
        self._search_fn = search_fn
        self._sonar_fn = sonar_fn
        self._stop_after = stop_after
        self._outdir = outdir
        self._debug_step = debug_step
        self._search_override = search_override  # None=preflight decides, True=force on, False=force off
        self.log = RunLog(verbose=verbose)
        self.state = resume_state if resume_state else PipelineState()

    def _checkpoint(self, stage_id: str):
        """Save checkpoint and check if we should stop."""
        import os
        self.state.current_stage = stage_id
        self.state.completed_stages.append(stage_id)
        os.makedirs(self._outdir, exist_ok=True)
        self.state.save(Path(self._outdir) / "checkpoint.json")
        if should_stop(stage_id, self._stop_after):
            self.log._print(f"\n  [CHECKPOINT] Stopped after {stage_id}. Resume with --resume {self._outdir}/checkpoint.json")
            return True
        if self._debug_step:
            self._debug_pause(stage_id)
        return False

    def _debug_pause(self, stage_id: str):
        """Print stage analysis and wait for user confirmation."""
        st = self.state
        self.log._print(f"\n{'='*60}")
        self.log._print(f"  [DEBUG-STEP] Completed: {stage_id}")
        self.log._print(f"  Pipeline so far: {' → '.join(st.completed_stages)}")

        # Stage-specific analysis
        if stage_id == "preflight":
            pf = st.preflight or {}
            self.log._print(f"  Preflight: {pf.get('answerability', 'N/A')} | {pf.get('modality', 'N/A')} | {pf.get('effort_tier', 'N/A')}")

        elif stage_id.startswith("r"):
            rnd = stage_id[1:]
            texts = st.round_texts.get(rnd, {})
            responded = st.round_responded.get(rnd, [])
            failed = st.round_failed.get(rnd, [])
            self.log._print(f"  Round {rnd}: {len(responded)} responded, {len(failed)} failed")
            for m in responded:
                chars = len(texts.get(m, ""))
                self.log._print(f"    {m}: {chars} chars")
            if failed:
                self.log._print(f"    FAILED: {', '.join(failed)}")

        elif stage_id.startswith("track"):
            rnd = stage_id[5:]
            positions = st.positions_by_round.get(rnd, {})
            args = st.arguments_by_round.get(rnd, [])
            self.log._print(f"  Track R{rnd}: {len(positions)} positions, {len(args)} arguments")
            for m, p in positions.items():
                self.log._print(f"    {m}: {p.get('option','')} [{p.get('confidence','')}]")

        elif stage_id.startswith("search"):
            rnd = stage_id[6:]
            phase = "R1_R2" if rnd == "1" else f"R{rnd}_R{int(rnd)+1}"
            results = st.search_results.get(phase, 0)
            queries = st.search_queries.get(phase, [])
            self.log._print(f"  Search R{rnd}: {len(queries)} queries → {results} evidence items")
            self.log._print(f"  Total evidence: {st.evidence_count}")

        elif stage_id == "synthesis":
            self.log._print(f"  Synthesis complete")

        elif stage_id == "gate2":
            self.log._print(f"  Outcome: {st.outcome}")
            self.log._print(f"  Class: {st.outcome_class}")
            self.log._print(f"  Agreement: {st.agreement_ratio:.2f}")

        self.log._print(f"  Checkpoint: {self._outdir}/checkpoint.json")
        self.log._print(f"{'='*60}")
        import sys
        if not sys.stdin.isatty():
            self.log._print("  [DEBUG-STEP] Non-interactive mode (no TTY) — skipping pause. Use --full-run for cron/CI.")
            return
        try:
            resp = input("  Press Enter to continue, 'q' to stop → ").strip().lower()
        except EOFError:
            resp = ""
        if resp == "q":
            self.log._print("  [DEBUG-STEP] Stopped by user.")
            raise SystemExit(0)

    def _stage_done(self, stage_id: str) -> bool:
        """Check if a stage was already completed (for resume)."""
        return stage_id in self.state.completed_stages

    def _enforce_post_admission_outcome_contract(self, outcome, stage: str) -> None:
        """Reject top-level outcomes that are illegal once R1 has begun."""
        value = outcome.value if hasattr(outcome, "value") else str(outcome)
        if value == Outcome.NEED_MORE.value:
            raise BrainError(
                stage,
                "NEED_MORE emitted after R1 began",
                error_class="FATAL_INTEGRITY",
                detail="DOD §1.6/§5.3: NEED_MORE is pre-admission only and cannot be a post-admission outcome.",
            )
        if value == "SHORT_CIRCUIT":
            raise BrainError(
                stage,
                "SHORT_CIRCUIT treated as a top-level outcome",
                error_class="FATAL_INTEGRITY",
                detail="DOD §1.6/§5.3: SHORT_CIRCUIT is an effort tier within DECIDE, not a top-level outcome.",
            )

    def _restore_trackers(self, argument_tracker: ArgumentTracker,
                          position_tracker: PositionTracker,
                          evidence: EvidenceLedger) -> tuple[dict[str, str], str]:
        """Restore tracker state from checkpoint. Returns (prior_views, unaddressed_text)."""
        from thinker.types import Argument, Confidence, Position
        st = self.state

        # Restore arguments by round
        for rnd_str, args_data in st.arguments_by_round.items():
            rnd = int(rnd_str)
            argument_tracker.arguments_by_round[rnd] = [
                Argument(
                    argument_id=a["id"], round_num=rnd,
                    model=a["model"], text=a["text"],
                )
                for a in args_data
            ]

        # Restore positions by round
        for rnd_str, pos_data in st.positions_by_round.items():
            rnd = int(rnd_str)
            positions = {}
            for model, p in pos_data.items():
                conf = Confidence[p.get("confidence", "MEDIUM")]
                option = p.get("option", "")
                components = p.get("components", [option])
                kind = p.get("kind", "single")
                positions[model] = Position(
                    model=model, round_num=rnd,
                    primary_option=option,
                    components=components,
                    confidence=conf,
                    qualifier=p.get("qualifier", ""),
                    kind=kind,
                )
            position_tracker.positions_by_round[rnd] = positions

        # Restore evidence items
        for ev_data in st.evidence_items:
            item = EvidenceItem(
                evidence_id=ev_data.get("evidence_id", ""),
                topic=ev_data.get("topic", ""),
                fact=ev_data.get("fact", ""),
                url=ev_data.get("url", ""),
                confidence=Confidence[ev_data.get("confidence", "MEDIUM")],
            )
            evidence.add(item)

        # Find the last completed round to restore prior_views
        prior_views: dict[str, str] = {}
        last_round = 0
        for rnd_str in st.round_texts:
            rnd = int(rnd_str)
            if rnd > last_round:
                last_round = rnd
        if last_round > 0:
            prior_views = st.round_texts.get(str(last_round), {})

        unaddressed_text = st.unaddressed_text
        return prior_views, unaddressed_text

    async def run(self, brief: str) -> BrainResult:
        """Execute a full Brain deliberation."""
        st = self.state
        resuming = len(st.completed_stages) > 0
        run_id = st.run_id if resuming else f"brain-{int(time.time())}"
        st.brief = brief
        st.rounds = self._config.rounds
        st.run_id = run_id

        if resuming:
            self.log._print(f"\n  [RESUME] Resuming from stage: {st.current_stage}")
            self.log._print(f"  [RESUME] Completed stages: {' → '.join(st.completed_stages)}")

        proof = ProofBuilder(run_id, brief, self._config.rounds)
        try:
            return await self._run_pipeline(brief, run_id, proof)
        except BrainError as e:
            # DOD §19: proof.json required "always", including on ERROR.
            # Write partial proof with error_class before re-raising.
            proof.set_error_class(e.error_class)
            proof.set_final_status(f"ERROR:{e.stage}")
            proof.set_timestamp_completed()
            e.partial_proof = proof.build()
            raise

    async def _run_pipeline(self, brief: str, run_id: str,
                            proof: ProofBuilder) -> BrainResult:
        """Inner pipeline execution — separated so run() can catch BrainError and write partial proof."""
        log = self.log
        st = self.state
        resuming = len(st.completed_stages) > 0
        run_start_time = time.monotonic()
        # DOD §19: topology and config_snapshot
        proof.set_topology({
            str(r): models for r, models in ROUND_TOPOLOGY.items()
        } | {"round_model_counts": [len(m) for m in ROUND_TOPOLOGY.values()]})
        proof.set_config_snapshot({
            "rounds": self._config.rounds,
            "max_evidence_items": self._config.max_evidence_items,
            "max_search_queries_per_phase": self._config.max_search_queries_per_phase,
            "search_after_rounds": self._config.search_after_rounds,
        })
        # DOD §19: stage_integrity and budgeting required "always" — set defaults
        # so they're present even on early NEED_MORE returns
        proof.set_stage_integrity(required=[], order=[], fatal=[])
        proof.set_budgeting({
            "effort_tier": "STANDARD", "per_round_token_budgets": {},
            "search_budget_policy": "NONE", "speculative_expansion_allowed": False,
            "high_authority_evidence_required": False,
            "short_circuit_taken": False, "fallback_from_short_circuit": False,
        })

        # Truncated brief for Sonnet extraction stages (framing, synthesis, etc.)
        brief_for_sonnet = brief[:15000] if len(brief) > 15000 else brief
        brief_keywords = {w.lower() for w in brief.split() if len(w) >= 4}
        search_log_entries: list = []
        evidence = EvidenceLedger(
            max_items=self._config.max_evidence_items,
            brief_keywords=brief_keywords,
        )
        argument_tracker = ArgumentTracker(self._llm)
        position_tracker = PositionTracker(self._llm)
        blocker_ledger = BlockerLedger()
        # Search decision deferred until after Gate 1 (needs recommendation)
        search_enabled = False
        search_orch = None
        proof.set_blocker_ledger(blocker_ledger)

        # V9 state — initialized here so they're available even on resume
        preflight_result = PreflightResult()  # defaults
        dimension_result = DimensionSeedResult()
        dimension_text = ""
        alt_frames_text = ""
        divergence_result = DivergenceResult()
        semantic_ctrs: list = []
        decisive_claims: list = []
        dispositions: list = []
        synthesis_ran_this_session = False
        is_analysis_mode = False
        stability_result = StabilityResult()

        # Restore tracker state if resuming
        if resuming:
            prior_views, unaddressed_text = self._restore_trackers(
                argument_tracker, position_tracker, evidence,
            )
            # Restore V9 state from checkpoint
            from thinker.types import (
                Answerability, QuestionClass, StakesClass, EffortTier, SearchScope,
                DimensionItem, FrameInfo, FrameType,
            )
            if st.preflight:
                pf = st.preflight
                preflight_result = PreflightResult(
                    answerability=Answerability(pf.get("answerability", "ANSWERABLE")),
                    question_class=QuestionClass(pf.get("question_class", "OPEN")),
                    stakes_class=StakesClass(pf.get("stakes_class", "STANDARD")),
                    effort_tier=EffortTier(pf.get("effort_tier", "STANDARD")),
                    modality=Modality(pf.get("modality", "DECIDE")),
                    search_scope=SearchScope(pf.get("search_scope", "TARGETED")),
                    exploration_required=pf.get("exploration_required", False),
                    short_circuit_allowed=pf.get("short_circuit_allowed", False),
                    fatal_premise=pf.get("fatal_premise", False),
                    reasoning=pf.get("reasoning", ""),
                )
            if st.dimensions:
                dim = st.dimensions
                items = [DimensionItem(
                    dimension_id=d.get("dimension_id", ""),
                    name=d.get("name", ""),
                ) for d in dim.get("items", [])]
                dimension_result = DimensionSeedResult(
                    items=items, dimension_count=dim.get("dimension_count", 0),
                )
                dimension_text = format_dimensions_for_prompt(dimension_result.items)
            if st.divergence:
                div = st.divergence
                divergence_result = DivergenceResult(
                    framing_pass_executed=div.get("framing_pass_executed", False),
                    exploration_stress_triggered=div.get("exploration_stress_triggered", False),
                )
                for f_data in div.get("alt_frames", []):
                    try:
                        divergence_result.alt_frames.append(FrameInfo(
                            frame_id=f_data.get("frame_id", ""),
                            text=f_data.get("text", ""),
                            frame_type=FrameType(f_data.get("frame_type", "INVERSION")),
                            survival_status=FrameSurvivalStatus(f_data.get("survival_status", "ACTIVE")),
                            material_to_outcome=f_data.get("material_to_outcome", True),
                        ))
                    except (ValueError, KeyError):
                        pass
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
        else:
            prior_views = {}
            unaddressed_text = ""

        # --- PreflightAssessment (V9 — replaces Gate 1) ---
        if not self._stage_done("preflight"):
            log._print("  [PREFLIGHT] Running PreflightAssessment...")
            t0 = time.monotonic()
            preflight_result = await run_preflight(self._llm, brief)
            log._print(f"  [PREFLIGHT] {preflight_result.answerability.value} | "
                       f"{preflight_result.modality.value} | {preflight_result.effort_tier.value} "
                       f"({time.monotonic() - t0:.1f}s)")

            if preflight_result.answerability.value in ("NEED_MORE", "INVALID_FORM"):
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                proof.set_outcome(Outcome.NEED_MORE, 0.0, "NEED_MORE")
                proof.set_timestamp_completed()
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            # DOD 4.5: FATAL_PREMISE cross-check — override answerability if LLM missed it
            if preflight_result.fatal_premise and preflight_result.answerability.value == "ANSWERABLE":
                log._print("  [PREFLIGHT] FATAL_PREMISE detected but answerability=ANSWERABLE — overriding to NEED_MORE")
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                proof.set_outcome(Outcome.NEED_MORE, 0.0, "NEED_MORE")
                proof.set_timestamp_completed()
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            # DOD 4.4: Material false/unverifiable assumptions block admission
            if preflight_result.has_fatal_assumptions:
                log._print("  [PREFLIGHT] Material UNVERIFIABLE/FALSE assumption detected — overriding to NEED_MORE")
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                proof.set_outcome(Outcome.NEED_MORE, 0.0, "NEED_MORE")
                proof.set_timestamp_completed()
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            st.preflight = preflight_result.to_dict()
            st.modality = preflight_result.modality.value
            is_analysis_mode = preflight_result.modality == Modality.ANALYSIS
            proof.set_preflight(preflight_result)

            # DOD §5.1: populate budgeting from preflight + config
            proof.set_budgeting({
                "effort_tier": preflight_result.effort_tier.value,
                "per_round_token_budgets": {
                    str(r): {"models": models, "max_tokens": 30000 if any(
                        m in ("r1", "reasoner") for m in models
                    ) else 16000} for r, models in ROUND_TOPOLOGY.items()
                },
                "search_budget_policy": preflight_result.search_scope.value,
                "speculative_expansion_allowed": preflight_result.effort_tier.value == "ELEVATED",
                "high_authority_evidence_required": preflight_result.search_scope.value != "NONE",
                "short_circuit_taken": False,
                "fallback_from_short_circuit": False,
            })

            # --- Defect Routing (V9, DESIGN-V3.md Section 1.1) ---
            from thinker.types import PremiseFlagRouting
            for flag in preflight_result.premise_flags:
                if flag.resolved:
                    continue
                if flag.routing == PremiseFlagRouting.REQUESTER_FIXABLE:
                    # DOD 4.3: REQUESTER_FIXABLE → NEED_MORE (must not be admitted)
                    log._print(f"  [DEFECT] {flag.flag_id}: REQUESTER_FIXABLE → rejecting brief")
                    proof.set_preflight(preflight_result)
                    proof.set_final_status("PREFLIGHT_REJECTED")
                    proof.set_outcome(Outcome.NEED_MORE, 0.0, "NEED_MORE")
                    proof.set_timestamp_completed()
                    return BrainResult(
                        outcome=Outcome.NEED_MORE, proof=proof.build(),
                        report="", preflight=preflight_result,
                    )
                elif flag.routing in (PremiseFlagRouting.MANAGEABLE_UNKNOWN, PremiseFlagRouting.REQUESTER_FIXABLE):
                    blocker_ledger.add(
                        kind=BlockerKind.COVERAGE_GAP,
                        source=f"preflight:{flag.flag_id}",
                        detected_round=0,
                        detail=f"Manageable unknown: {flag.summary}",
                        models=[],
                        severity="HIGH" if flag.severity.value == "CRITICAL" else "MEDIUM",
                    )
                    log._print(f"  [DEFECT] {flag.flag_id}: MANAGEABLE_UNKNOWN → blocker registered")
                elif flag.routing == PremiseFlagRouting.FRAMING_DEFECT:
                    dimension_text += f"\n\n## Reframing Required (Premise Defect)\n{flag.summary}\nYou MUST engage with this reframing in your analysis.\n"
                    log._print(f"  [DEFECT] {flag.flag_id}: FRAMING_DEFECT → reframe injected into R1")

            if self._checkpoint("preflight"):
                return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report="[STOPPED AT PREFLIGHT]", preflight=preflight_result)
        else:
            if st.preflight:
                preflight_result = PreflightResult(
                    modality=Modality(st.preflight.get("modality", "DECIDE")),
                )
            is_analysis_mode = preflight_result.modality == Modality.ANALYSIS

        # --- Dimension Seeder (V9) ---
        if not self._stage_done("dimensions"):
            log._print("  [DIMENSIONS] Running Dimension Seeder...")
            t0 = time.monotonic()
            dimension_result = await run_dimension_seeder(self._llm, brief)
            dimension_text = format_dimensions_for_prompt(dimension_result.items)
            log._print(f"  [DIMENSIONS] {dimension_result.dimension_count} dimensions ({time.monotonic() - t0:.1f}s)")
            # DOD §6.2: fewer than 3 dimensions → ERROR
            if dimension_result.dimension_count < 3:
                raise BrainError(
                    "dimensions",
                    f"Only {dimension_result.dimension_count} dimensions seeded (minimum 3 required)",
                    error_class="FATAL_INTEGRITY",
                    detail="DOD §6.2: dimension_count < 3 → ERROR.",
                )
            st.dimensions = dimension_result.to_dict()
            proof.set_dimensions(dimension_result)
            if self._checkpoint("dimensions"):
                return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report="[STOPPED AT DIMENSIONS]", preflight=preflight_result, dimensions=dimension_result)

        # --- Search Decision (V9: uses preflight.search_scope) ---
        from thinker.types import SearchScope
        has_search_provider = self._search_fn is not None
        if self._search_override is not None:
            search_enabled = self._search_override and has_search_provider
            source = "cli_override"
            reasoning = "Forced on via --search" if self._search_override else "Forced off via --no-search"
            proof.set_search_decision(source=source, value=search_enabled, reasoning=reasoning)
            log._print(f"  [SEARCH DECISION] {source}: {'ON' if search_enabled else 'OFF'} "
                        f"(Preflight scope: {preflight_result.search_scope.value})")
        else:
            search_enabled = (preflight_result.search_scope != SearchScope.NONE) and has_search_provider
            proof.set_search_decision(
                source="preflight",
                value=search_enabled,
                reasoning=f"Preflight search_scope={preflight_result.search_scope.value}",
            )
            log._print(f"  [SEARCH DECISION] preflight: {'ON' if search_enabled else 'OFF'} — scope={preflight_result.search_scope.value}")

        if search_enabled:
            search_orch = SearchOrchestrator(
                self._llm, search_fn=self._search_fn,
                sonar_fn=self._sonar_fn,
            )

        # --- Deliberation Rounds ---
        if not resuming:
            prior_views = {}
            unaddressed_text = ""

        for round_num in range(1, self._config.rounds + 1):
            is_last_round = round_num == self._config.rounds
            models = ROUND_TOPOLOGY[round_num]

            # --- Skip completed round stages on resume ---
            round_stage = f"r{round_num}"
            track_stage = f"track{round_num}"
            search_stage = f"search{round_num}"

            # Determine if this round's search phase exists (search runs after R1 and R2, not last round)
            has_search_phase = (round_num <= self._config.search_after_rounds
                                and not is_last_round and search_orch)

            if self._stage_done(search_stage):
                # Round + tracking + search all done — fully skip
                log._print(f"  [RESUME] Skipping round {round_num} (already completed)")
                # Repopulate proof from checkpoint so skipped rounds appear in proof.json
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                proof.record_round(round_num, saved_responded, saved_failed)
                if str(round_num) in st.positions_by_round:
                    _pos = {}
                    for _m, _p in st.positions_by_round[str(round_num)].items():
                        _pos[_m] = Position(
                            model=_m, round_num=round_num,
                            primary_option=_p.get("option", ""),
                            components=_p.get("components", [_p.get("option", "")]),
                            confidence=Confidence[_p.get("confidence", "MEDIUM")],
                            qualifier=_p.get("qualifier", ""),
                            kind=_p.get("kind", "single"),
                        )
                    proof.record_positions(round_num, _pos)
                continue

            if self._stage_done(track_stage) and not has_search_phase:
                # Track done, no search phase for this round — fully skip
                log._print(f"  [RESUME] Skipping round {round_num} (already completed)")
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                proof.record_round(round_num, saved_responded, saved_failed)
                if str(round_num) in st.positions_by_round:
                    _pos = {}
                    for _m, _p in st.positions_by_round[str(round_num)].items():
                        _pos[_m] = Position(
                            model=_m, round_num=round_num,
                            primary_option=_p.get("option", ""),
                            components=_p.get("components", [_p.get("option", "")]),
                            confidence=Confidence[_p.get("confidence", "MEDIUM")],
                            qualifier=_p.get("qualifier", ""),
                            kind=_p.get("kind", "single"),
                        )
                    proof.record_positions(round_num, _pos)
                continue

            # Need to reconstruct RoundResult if round execution is done
            round_result = None
            if self._stage_done(round_stage) or self._stage_done(track_stage):
                # Round executed — reconstruct from checkpoint for search/compare
                skip_msg = "resuming at search" if self._stage_done(track_stage) else "resuming at tracking"
                log._print(f"  [RESUME] Skipping round {round_num} execution ({skip_msg})")
                from thinker.types import ModelResponse, RoundResult
                saved_texts = st.round_texts.get(str(round_num), {})
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                responses = {}
                for m in saved_responded:
                    responses[m] = ModelResponse(model=m, ok=True, text=saved_texts.get(m, ""), elapsed_s=0.0)
                for m in saved_failed:
                    responses[m] = ModelResponse(model=m, ok=False, text="", elapsed_s=0.0, error="failed in prior run")
                round_result = RoundResult(round_num=round_num, responses=responses, failed=saved_failed)
            else:
                # Execute round normally
                log.round_start(round_num, models, is_last_round)

                t0 = time.monotonic()
                # ANALYSIS mode: prepend exploration preamble to brief
                effective_brief = (get_analysis_round_preamble() + brief) if is_analysis_mode else brief
                # R1: cap brief for perspective card compliance on very large briefs
                # Models need output budget for the 5 structured fields
                if round_num == 1 and len(effective_brief) > 100000:
                    effective_brief = effective_brief[:100000] + "\n\n[Brief truncated for R1 — full content available in subsequent rounds]\n"
                round_result = await execute_round(
                    self._llm, round_num=round_num, brief=effective_brief,
                    prior_views=prior_views if round_num > 1 else None,
                    evidence_text=evidence.format_for_prompt() if round_num > 1 else "",
                    unaddressed_arguments=unaddressed_text if round_num > 1 else "",
                    is_last_round=is_last_round,
                    adversarial_model="kimi" if round_num == 1 else "",
                    dimension_text=dimension_text if round_num == 1 else "",
                    perspective_card_instructions=format_perspective_card_instructions() if round_num == 1 else "",
                    alt_frames_text=alt_frames_text if round_num >= 2 else "",
                    frame_enforcement_text=format_r2_frame_enforcement() if round_num == 2 else "",
                )
                log.round_result(round_num, round_result.responded, round_result.failed,
                                 round_result.texts, time.monotonic() - t0)
                proof.record_round(round_num, round_result.responded, round_result.failed)
                # Store full text for resume — truncation loses SEARCH_REQUESTS appendix
                st.round_texts[str(round_num)] = round_result.texts
                st.round_responded[str(round_num)] = round_result.responded
                st.round_failed[str(round_num)] = round_result.failed

                if round_result.failed:
                    failed_details = "; ".join(
                        f"{m}: {round_result.responses[m].error}"
                        for m in round_result.failed
                        if m in round_result.responses
                    )
                    raise BrainError(
                        f"round{round_num}",
                        f"Model(s) failed in round {round_num}: {', '.join(round_result.failed)}",
                        error_class="INFRASTRUCTURE",
                        detail=failed_details,
                    )

                if self._checkpoint(f"r{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT R{round_num}]", preflight=preflight_result)

            # --- Tracking phase (skip if already done on resume) ---
            if not self._stage_done(track_stage):
                # Extract arguments
                t0 = time.monotonic()
                args = await argument_tracker.extract_arguments(round_num, round_result.texts)
                # Assign dimension_id by keyword matching
                if dimension_result and dimension_result.items:
                    dim_names = {d.dimension_id: d.name for d in dimension_result.items}
                    argument_tracker.assign_dimensions(args, dim_names)
                log.arg_extract(round_num, args, time.monotonic() - t0, argument_tracker.last_raw_response)
                st.arguments_by_round[str(round_num)] = [
                    {"id": a.argument_id, "model": a.model, "text": a.text} for a in args
                ]

                # Extract positions
                t0 = time.monotonic()
                positions = await position_tracker.extract_positions(round_num, round_result.texts)
                log.pos_extract(round_num, positions, time.monotonic() - t0, position_tracker.last_raw_response)
                proof.record_positions(round_num, positions)
                st.positions_by_round[str(round_num)] = {
                    m: {
                        "option": p.primary_option,
                        "confidence": p.confidence.value,
                        "qualifier": p.qualifier,
                        "components": p.components,
                        "kind": p.kind,
                    }
                    for m, p in positions.items()
                }

                # Track position changes
                if round_num > 1:
                    changes = position_tracker.get_position_changes(round_num - 1, round_num)
                    log.pos_changes(round_num - 1, round_num, changes)
                    proof.record_position_changes(changes)
                    st.position_changes.extend(changes)

                if self._checkpoint(f"track{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT TRACK{round_num}]", preflight=preflight_result)
            else:
                log._print(f"  [RESUME] Skipping track{round_num} (already completed)")

            # --- V9: Mark adversarial slot assigned (DOD §10) ---
            if round_num == 1:
                divergence_required = not is_analysis_mode and not preflight_result.short_circuit_allowed
                divergence_result.required = divergence_required
                divergence_result.adversarial_slot_assigned = divergence_required
                divergence_result.adversarial_model_id = "kimi" if divergence_required else None

            # --- V9: Post-R1 perspective cards + framing pass ---
            if round_num == 1 and not self._stage_done("perspective_cards"):
                log._print("  [CARDS] Extracting perspective cards...")
                t0 = time.monotonic()
                perspective_cards = await extract_perspective_cards(round_result.texts, llm_client=self._llm)
                inferred_count = sum(1 for c in perspective_cards if any(v.startswith("inferred:") for v in c.field_provenance.values()))
                log._print(f"  [CARDS] {len(perspective_cards)} cards ({inferred_count} with inferred fields) ({time.monotonic() - t0:.1f}s)")
                st.perspective_cards = [c.to_dict() for c in perspective_cards]
                proof.set_perspective_cards(perspective_cards)
                self._checkpoint("perspective_cards")

            if round_num == 1 and not self._stage_done("framing_pass"):
                if divergence_result.required:
                    log._print("  [FRAMING] Running framing extract...")
                    t0 = time.monotonic()
                    divergence_result = await run_framing_extract(self._llm, brief_for_sonnet, round_result.texts)
                    divergence_result.required = True
                    divergence_result.adversarial_slot_assigned = True
                    divergence_result.adversarial_model_id = "kimi"
                    r1_agreement = position_tracker.agreement_ratio(1)
                    if check_exploration_stress(r1_agreement, preflight_result.question_class, preflight_result.stakes_class):
                        divergence_result.exploration_stress_triggered = True
                        from thinker.types import FrameInfo, FrameType
                        seed_frames = [
                            FrameInfo(
                                frame_id="SEED-INV", text="What if the opposite of the emerging consensus is true? Argue against the majority position.",
                                origin_round=1, origin_model="controller", frame_type=FrameType.INVERSION,
                            ),
                            FrameInfo(
                                frame_id="SEED-STAKE", text="Consider the perspective of the stakeholder most harmed by the emerging consensus.",
                                origin_round=1, origin_model="controller", frame_type=FrameType.OPPOSITE_STANCE,
                            ),
                        ]
                        divergence_result.alt_frames.extend(seed_frames)
                        divergence_result.stress_seed_frames = [f.to_dict() for f in seed_frames]
                        log._print(f"  [STRESS] Exploration stress triggered - {len(seed_frames)} seed frames injected")
                    log._print(f"  [FRAMING] {len(divergence_result.alt_frames)} frames extracted ({time.monotonic() - t0:.1f}s)")
                else:
                    divergence_result.framing_pass_executed = False
                    log._print("  [FRAMING] Skipped - divergence not required for this run")
                st.divergence = divergence_result.to_dict()
                proof.set_divergence(divergence_result)
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                self._checkpoint("framing_pass")

            # --- V9: Post-R2 frame survival ---
            if round_num == 2 and not self._stage_done("frame_survival_r2"):
                missing_frame_obligations = validate_r2_frame_obligations(round_result.texts)
                if missing_frame_obligations:
                    # DOD §8.2: log as proof violation but do not halt —
                    # models on large briefs rarely emit explicit markers even
                    # when instructed; frame survival check below still runs.
                    proof.add_violation(
                        "R2-FRAME-OBLIGATIONS-MISSING",
                        "LOW",
                        f"R2 models missing explicit adopt/rebut/new_frame markers: "
                        f"{list(missing_frame_obligations.keys())}",
                    )
                log._print("  [FRAMING] Running frame survival check (R2)...")
                t0 = time.monotonic()
                divergence_result.alt_frames = await run_frame_survival_check(
                    self._llm, divergence_result.alt_frames, round_result.texts, round_num=2,
                    is_analysis_mode=is_analysis_mode,
                )
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                st.divergence = divergence_result.to_dict()
                log._print(f"  [FRAMING] Frame survival R2 done ({time.monotonic() - t0:.1f}s)")
                self._checkpoint("frame_survival_r2")

            # --- V9: Post-R3 frame survival ---
            if round_num == 3 and not self._stage_done("frame_survival_r3"):
                log._print("  [FRAMING] Running frame survival check (R3)...")
                t0 = time.monotonic()
                divergence_result.alt_frames = await run_frame_survival_check(
                    self._llm, divergence_result.alt_frames, round_result.texts, round_num=3,
                    is_analysis_mode=is_analysis_mode,
                )
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                st.divergence = divergence_result.to_dict()
                log._print(f"  [FRAMING] Frame survival R3 done ({time.monotonic() - t0:.1f}s)")
                self._checkpoint("frame_survival_r3")

            # --- Ungrounded Stat Detection (V9, post-R1 and post-R2, DECIDE only per DOD §9.3) ---
            if round_num in (1, 2) and not is_analysis_mode and not self._stage_done(f"ungrounded_r{round_num}"):
                all_round_text = " ".join(round_result.texts.values())
                ungrounded = find_ungrounded_stats(all_round_text, evidence.active_items)
                if round_num == 1:
                    st.ungrounded_r1_executed = True
                else:
                    st.ungrounded_r2_executed = True
                if ungrounded:
                    log._print(f"  [UNGROUNDED] R{round_num}: {len(ungrounded)} ungrounded stats detected")
                    verification_queries = generate_verification_queries(ungrounded, all_round_text)
                    st.search_queries[f"ungrounded_r{round_num}"] = verification_queries
                    # Track per-claim for DOD §9.2 schema
                    for i, stat in enumerate(ungrounded):
                        st.ungrounded_flagged_claims.append({
                            "claim_id": f"UG-R{round_num}-{i+1}",
                            "text": stat,
                            "numeric": True,
                            "verified": False,
                            "blocker_id": None,
                            "severity": "MEDIUM",
                            "status": "UNVERIFIED_CLAIM",
                        })
                self._checkpoint(f"ungrounded_r{round_num}")

            # --- Post-R3: unresolved ungrounded stats become UNVERIFIED_CLAIM blockers (DECIDE only) ---
            if round_num == 3 and not is_analysis_mode:
                all_r3_text = " ".join(round_result.texts.values())
                ungrounded_r3 = find_ungrounded_stats(all_r3_text, evidence.active_items)
                for i, stat in enumerate(ungrounded_r3):
                    blk = blocker_ledger.add(
                        kind=BlockerKind.UNVERIFIED_CLAIM,
                        source="ungrounded_stat_detector",
                        detected_round=3,
                        detail=f"Unverified numeric claim persists after R3: {stat}",
                        severity="CRITICAL",
                        models=[],
                    )
                    # Update tracked claim with blocker link
                    for fc in st.ungrounded_flagged_claims:
                        if fc["text"] == stat and fc["blocker_id"] is None:
                            fc["blocker_id"] = blk.blocker_id
                            fc["severity"] = "CRITICAL"
                            break
                    else:
                        # New claim at R3 not seen earlier
                        st.ungrounded_flagged_claims.append({
                            "claim_id": f"UG-R3-{i+1}",
                            "text": stat,
                            "numeric": True,
                            "verified": False,
                            "blocker_id": blk.blocker_id,
                            "severity": "CRITICAL",
                            "status": "UNVERIFIED_CLAIM",
                        })
                if ungrounded_r3:
                    log._print(f"  [UNGROUNDED] R3: {len(ungrounded_r3)} unresolved → UNVERIFIED_CLAIM blockers")

            # Search phase — after R1 and R2 only
            if has_search_phase:
                phase = SearchPhase.R1_R2 if round_num == 1 else SearchPhase.R2_R3
                t0 = time.monotonic()

                model_requests = search_orch.collect_model_requests(round_result.texts)
                proactive = await search_orch.generate_proactive_queries(
                    round_result.texts, already_queued=model_requests,
                )
                queries = search_orch.deduplicate(model_requests + proactive)
                log.search_start(phase.value, model_requests, proactive)
                st.search_queries[phase.value] = queries

                total_admitted = 0
                all_search_results: list[SearchResult] = []
                from thinker.types import SearchLogEntry, QueryProvenance, QueryStatus
                # Determine provenance per query
                ungrounded_qs = set(st.search_queries.get(f"ungrounded_r{round_num}", []))
                for query in queries[:self._config.max_search_queries_per_phase]:
                    provenance = QueryProvenance.UNGROUNDED_STAT if query in ungrounded_qs else QueryProvenance.MODEL_CLAIM
                    try:
                        results = await search_orch.execute_query(query, phase)
                    except Exception as e:
                        search_log_entries.append(SearchLogEntry(
                            query_id=f"Q-{len(search_log_entries)+1}", query_text=query[:200],
                            provenance=provenance, issued_after_stage=f"r{round_num}",
                            query_status=QueryStatus.FAILED,
                        ))
                        raise BrainError(
                            f"search_round{round_num}",
                            f"Search query failed: {query[:80]}",
                            error_class="INFRASTRUCTURE",
                            detail=str(e),
                        )
                    search_log_entries.append(SearchLogEntry(
                        query_id=f"Q-{len(search_log_entries)+1}", query_text=query[:200],
                        provenance=provenance, issued_after_stage=f"r{round_num}",
                        pages_fetched=len(results),
                        query_status=QueryStatus.SUCCESS if results else QueryStatus.ZERO_RESULT,
                    ))
                    all_search_results.extend(results)

                # F4: Fetch full page content for top results
                try:
                    await fetch_pages_for_results(all_search_results, max_pages=5)
                except BrainError:
                    raise
                except Exception as e:
                    raise BrainError(
                        f"page_fetch_round{round_num}",
                        f"Page fetch failed",
                        error_class="INFRASTRUCTURE",
                        detail=str(e),
                    )

                # F5: LLM-based extraction from fetched pages, fallback to snippets
                for sr in all_search_results:
                    if sr.full_content:
                        try:
                            extracted_facts = await extract_evidence_from_page(
                                self._llm, sr.url, sr.full_content,
                            )
                            for fact_data in extracted_facts:
                                ev = EvidenceItem(
                                    evidence_id=f"E{len(evidence.items) + 1:03d}",
                                    topic=sr.title[:100] if sr.title else sr.url[:100],
                                    fact=fact_data["fact"][:500],
                                    url=sr.url,
                                    confidence=Confidence.MEDIUM,
                                )
                                if evidence.add(ev):
                                    total_admitted += 1
                        except BrainError:
                            raise
                        except Exception as e:
                            raise BrainError(
                                f"evidence_extract_round{round_num}",
                                f"Evidence extraction failed for {sr.url[:80]}",
                                detail=str(e),
                            )
                    else:
                        # Fallback: use snippet/title as before
                        ev = EvidenceItem_from_search_result(sr, len(evidence.items))
                        if ev and evidence.add(ev):
                            total_admitted += 1

                # Wire evidence contradictions into blocker ledger
                for ctr in evidence.contradictions:
                    if not any(b.detail == ctr.ctr_id for b in blocker_ledger.blockers):
                        blocker_ledger.add(
                            kind=BlockerKind.CONTRADICTION,
                            source="evidence_ledger",
                            detected_round=round_num,
                            detail=ctr.ctr_id,
                            models=[],
                        )

                log.search_result(phase.value, len(queries), total_admitted, time.monotonic() - t0)
                proof.record_research_phase(
                    phase.value, "brave", len(queries), total_admitted,
                )
                st.search_results[phase.value] = total_admitted
                st.evidence_items = [
                    {"evidence_id": e.evidence_id, "topic": e.topic,
                     "fact": e.fact, "url": e.url, "score": e.score,
                     "confidence": e.confidence.value}
                    for e in evidence.items
                ]
                st.evidence_count = len(evidence.items)

                if self._checkpoint(f"search{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT SEARCH{round_num}]", preflight=preflight_result)

            # Compare arguments (after R2+)
            if round_num > 1:
                t0 = time.monotonic()
                unaddressed = await argument_tracker.compare_with_round(
                    round_num - 1, round_result.texts,
                )
                addressed = len(argument_tracker.arguments_by_round.get(round_num - 1, [])) - len(unaddressed)
                ignored = [a for a in unaddressed if a.status == ArgumentStatus.IGNORED]
                mentioned = [a for a in unaddressed if a.status == ArgumentStatus.MENTIONED]
                log.arg_compare(round_num - 1, addressed, len(mentioned), len(ignored),
                                time.monotonic() - t0, unaddressed)
                unaddressed_text = argument_tracker.format_reinjection(unaddressed)
                st.unaddressed_text = unaddressed_text

            prior_views = round_result.texts

        # --- Classification (deterministic) ---
        final_round = self._config.rounds
        agreement = position_tracker.agreement_ratio(final_round)
        final_positions = position_tracker.positions_by_round.get(final_round, {})

        all_ignored = [a for a in argument_tracker.all_unaddressed if a.status == ArgumentStatus.IGNORED]
        all_mentioned = [a for a in argument_tracker.all_unaddressed if a.status == ArgumentStatus.MENTIONED]

        outcome_class = classify_outcome(
            agreement_ratio=agreement,
            ignored_arguments=len(all_ignored),
            mentioned_arguments=len(all_mentioned),
            evidence_count=len(evidence.items),
            contradictions=len(evidence.contradictions),
            open_blockers=len(blocker_ledger.open_blockers()),
            search_enabled=search_enabled,
        )
        st.agreement_ratio = agreement
        st.outcome_class = outcome_class

        # --- Semantic Contradiction (V9, DOD §12.2: only when shortlist criteria are met) ---
        if not self._stage_done("semantic_contradiction"):
            if not self._stage_done("decisive_claims"):
                log._print("  [CLAIMS] Extracting decisive claims...")
                t0 = time.monotonic()
                decisive_claims = await extract_decisive_claims(
                    self._llm, final_views=prior_views, evidence_text=evidence.format_for_prompt(),
                )
                log._print(f"  [CLAIMS] {len(decisive_claims)} decisive claims ({time.monotonic() - t0:.1f}s)")
                proof.set_decisive_claims(decisive_claims)
                self._checkpoint("decisive_claims")
            if len(evidence.active_items) >= 2:
                log._print("  [SEMANTIC] Running semantic contradiction pass...")
                t0 = time.monotonic()
                # DOD §12.2 criterion 3: include decisive-claim-linked and blocker-linked evidence
                open_blocker_ev_ids = {
                    evidence_id
                    for b in blocker_ledger.open_blockers()
                    for evidence_id in b.evidence_ids
                } | {
                    b.source for b in blocker_ledger.open_blockers()
                    if isinstance(b.source, str) and b.source.startswith("E")
                }
                decisive_claim_evidence_ids = {
                    ref for claim in decisive_claims for ref in claim.evidence_refs
                }
                semantic_ctrs = await run_semantic_contradiction_pass(
                    self._llm, evidence.active_items,
                    decisive_claim_evidence_ids=decisive_claim_evidence_ids,
                    open_blocker_ids=open_blocker_ev_ids,
                )
                log._print(f"  [SEMANTIC] {len(semantic_ctrs)} semantic contradictions ({time.monotonic() - t0:.1f}s)")
            else:
                log._print("  [SEMANTIC] Skipped — fewer than 2 evidence items (no pairs possible)")
            self._checkpoint("semantic_contradiction")

        # --- Decisive Claim Extraction (V9) ---
        if not self._stage_done("decisive_claims"):
            log._print("  [CLAIMS] Extracting decisive claims...")
            t0 = time.monotonic()
            decisive_claims = await extract_decisive_claims(
                self._llm, final_views=prior_views, evidence_text=evidence.format_for_prompt(),
            )
            log._print(f"  [CLAIMS] {len(decisive_claims)} decisive claims ({time.monotonic() - t0:.1f}s)")
            proof.set_decisive_claims(decisive_claims)
            self._checkpoint("decisive_claims")

        # --- Synthesis Packet (V9) ---
        packet = build_synthesis_packet(
            brief=brief_for_sonnet,
            final_positions=final_positions,
            arguments=[a for args in argument_tracker.arguments_by_round.values() for a in args],
            frames=divergence_result.alt_frames if hasattr(divergence_result, 'alt_frames') else [],
            blockers=blocker_ledger.blockers,
            decisive_claims=decisive_claims,
            contradictions_numeric=evidence.contradictions,
            contradictions_semantic=semantic_ctrs,
            premise_flags=preflight_result.premise_flags,
            evidence_items=evidence.active_items,
        )
        synthesis_packet_text = format_synthesis_packet_for_prompt(packet)
        if is_analysis_mode:
            synthesis_packet_text += get_analysis_synthesis_contract()
        proof.set_synthesis_packet(packet)
        self._checkpoint("synthesis_packet")

        # Record arguments with resolution status in proof
        all_args = []
        for rnd_args in argument_tracker.arguments_by_round.values():
            all_args.extend(rnd_args)
        proof.set_arguments(all_args, blocker_ledger=blocker_ledger)

        # --- Synthesis Gate ---
        t0 = time.monotonic()
        final_views = prior_views
        synthesis_ran_this_session = True
        report, report_json, dispositions = await run_synthesis(
            self._llm, brief=brief_for_sonnet, final_views=final_views,
            blocker_summary=blocker_ledger.summary(),
            outcome_class=outcome_class,
            evidence_text=evidence.format_for_prompt(),
            synthesis_packet_text=synthesis_packet_text,
        )
        log.synthesis_result(len(report), bool(report_json), time.monotonic() - t0)
        proof.set_synthesis_status("COMPLETE" if report else "FAILED")
        st.report = report[:5000]
        st.report_json = report_json

        if self._checkpoint("synthesis"):
            return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=report, preflight=preflight_result)

        # --- ANALYSIS mode proof additions ---
        if is_analysis_mode:
            # DOD §18.5: "ANALYSIS output contains verdict language → ERROR"
            # Check the header — ANALYSIS must have "EXPLORATORY MAP" header, not verdict/recommendation
            report_text = (report if report else "").lower()
            report_header = report_text[:500]
            if report and "exploratory map" not in report_header:
                # Missing required header — check for explicit decision language
                # DOD §18.5: broad detection — check header and opening section
                decision_phrases = [
                    "we recommend", "our recommendation is", "the answer is",
                    "therefore we decide", "we conclude that you should",
                    "the verdict is", "our verdict", "in conclusion",
                    "the best option is", "the best approach is", "you should",
                    "the right choice is", "the correct answer",
                    "we advise", "our advice is", "the decision is",
                    "based on our analysis, the", "the optimal solution",
                ]
                verdict_found = [p for p in decision_phrases if p in report_text]
                if verdict_found:
                    raise BrainError(
                        "analysis_verdict_check",
                        f"ANALYSIS output contains verdict language: {verdict_found[:3]}",
                        error_class="FATAL_INTEGRITY",
                        detail="DOD §18.5: ANALYSIS mode must produce exploratory map, not verdict.",
                    )

            # Analysis map: DOD §18.3 — hierarchical object keyed by dimension_id
            analysis_map = {
                "header": "EXPLORATORY MAP — NOT A DECISION",
                "dimensions": {},
                "hypothesis_ledger": [],
                "total_argument_count": len(all_args),
                "dimension_coverage_score": dimension_result.dimension_coverage_score,
            }
            if report_json and isinstance(report_json, dict):
                for key in report_json:
                    if key.startswith("DIM-"):
                        analysis_map["dimensions"][key] = report_json[key]
                    elif key == "hypothesis_ledger":
                        analysis_map["hypothesis_ledger"] = report_json[key]
            analysis_map["header"] = "EXPLORATORY MAP — NOT A DECISION"
            proof.set_analysis_map(analysis_map)

            # DOD §18.4: debug sunset enforcement
            # Counter persisted via file in outdir
            sunset_file = Path(self._config.outdir) / ".analysis_debug_remaining"
            if sunset_file.exists():
                try:
                    remaining = int(sunset_file.read_text().strip())
                except (ValueError, OSError):
                    remaining = self._config.analysis_debug_runs_remaining
            else:
                remaining = self._config.analysis_debug_runs_remaining

            debug_active = remaining > 0
            new_remaining = max(0, remaining - 1) if debug_active else 0
            # Persist decremented counter
            try:
                sunset_file.parent.mkdir(parents=True, exist_ok=True)
                sunset_file.write_text(str(new_remaining))
            except OSError:
                pass  # Non-fatal: counter resets next run

            # DOD §18.4 schema: debug_gate2_result and actual_output
            # filled after Gate 2 runs (stored as placeholders, updated below)
            analysis_debug_data = {
                "debug_mode": debug_active,
                "debug_gate2_result": None,  # Filled after Gate 2
                "actual_output": None,  # Filled after Gate 2
                "rules_enforced": not debug_active,  # Rules always enforced; debug affects audit only
                "remaining_debug_runs": new_remaining,
                "analysis_mode_active": True,
                "dimension_coverage_score": dimension_result.dimension_coverage_score,
            }
            proof.set_analysis_debug(analysis_debug_data)

        # --- Stability Tests (V9) ---
        stability_result = run_stability_tests(
            positions=final_positions,
            decisive_claims=decisive_claims,
            assumptions=preflight_result.critical_assumptions,
            round_positions=position_tracker.positions_by_round,
            question_class=preflight_result.question_class,
            stakes_class=preflight_result.stakes_class,
            independent_evidence_present=evidence.high_authority_evidence_present,
        )
        proof.set_stability(stability_result)
        self._checkpoint("stability")
        log._print(f"  [STABILITY] conclusion={stability_result.conclusion_stable} "
                   f"reason={stability_result.reason_stable} "
                   f"assumption={stability_result.assumption_stable} "
                   f"groupthink_warning={stability_result.groupthink_warning}")

        # --- Compute dimension coverage + register COVERAGE_GAP blockers (V9) ---
        if dimension_result and dimension_result.items:
            for dim in dimension_result.items:
                dim_args = [a for a in all_args if a.dimension_id == dim.dimension_id]
                dim.argument_count = len(dim_args)
                dim.coverage_status = "SATISFIED" if len(dim_args) >= 2 else ("PARTIAL" if dim_args else "ZERO")
                # Register COVERAGE_GAP blocker for zero-coverage mandatory dimensions
                if dim.coverage_status == "ZERO" and dim.mandatory and not dim.justified_irrelevance:
                    blocker_ledger.add(
                        kind=BlockerKind.COVERAGE_GAP,
                        source=f"dimension:{dim.dimension_id}",
                        detected_round=self._config.rounds,
                        detail=f"Zero arguments for mandatory dimension: {dim.name}",
                        models=[],
                        severity="CRITICAL",
                    )
            covered = sum(1 for d in dimension_result.items if d.argument_count >= 2)
            # DOD §6.2: denominator is mandatory dimensions only
            mandatory_count = sum(1 for d in dimension_result.items if d.mandatory)
            dimension_result.dimension_coverage_score = covered / mandatory_count if mandatory_count else 0.0

        # --- V9: Evidence refs validation (DOD §10.3) ---
        # "Cited evidence missing from both stores → ERROR"
        # Only validate when evidence was actually collected (search ran).
        # With no search, LLM may hallucinate E-IDs but there's nothing to validate against.
        if evidence.all_evidence_ids():
            all_evidence_refs = []
            for c in decisive_claims:
                all_evidence_refs.extend(c.evidence_refs)
            for a in all_args:
                all_evidence_refs.extend(a.evidence_refs)
            phantom_refs = evidence.validate_refs(all_evidence_refs)
            if phantom_refs:
                # DOD §10.3 + §3.3: cited evidence missing = fatal integrity → ERROR
                raise BrainError(
                    "evidence_validation",
                    f"Cited evidence missing from both stores: {phantom_refs[:5]}",
                    error_class="FATAL_INTEGRITY",
                    detail=f"DOD §10.3: {len(phantom_refs)} phantom evidence refs. FATAL_INTEGRITY.",
                )

        # --- V9: Disposition Coverage Verification (runs BEFORE Gate 2 per DOD §14.6) ---
        from thinker.types import DispositionObject, DispositionTargetType
        disposition_objects = []
        for d in dispositions:
            try:
                disposition_objects.append(DispositionObject(
                    target_type=DispositionTargetType(d["target_type"]),
                    target_id=d["target_id"],
                    status=d["status"],
                    importance=d["importance"],
                    narrative_explanation=d["narrative_explanation"],
                ))
            except (ValueError, KeyError):
                pass

        active_frames_for_residue = [f for f in divergence_result.alt_frames
                         if f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)]
        coverage = check_disposition_coverage(
            dispositions=disposition_objects,
            open_blockers=blocker_ledger.blockers,
            active_frames=active_frames_for_residue,
            decisive_claims=decisive_claims,
            contradictions_numeric=evidence.contradictions,
            contradictions_semantic=semantic_ctrs,
            open_material_arguments=argument_tracker.all_unaddressed,  # DOD §11.3
        )
        proof.set_residue_verification(coverage)
        proof.set_synthesis_dispositions(disposition_objects)

        # DOD §14.5-14.6: coverage_pass=false triggers deep scan path
        # Only enforce when synthesis actually produced disposition data this session.
        # On resume past synthesis, dispositions are not available from checkpoint.
        if not coverage.get("coverage_pass") and coverage.get("total_required", 0) > 0:
            if coverage.get("total_disposed", 0) == 0:
                # Zero dispositions emitted at all → ERROR (DOD §14.6)
                raise BrainError(
                    "disposition_coverage",
                    f"Zero dispositions for {coverage['total_required']} required findings",
                    error_class="FATAL_INTEGRITY",
                    detail="DOD §14.6: Disposition missing for tracked open finding → ERROR.",
                )
            # DOD §14.6: any missing disposition → ERROR (before deep scan opportunity)
            # Deep scan is the recovery path; if omission rate > 20%, run deep scan first
            if not coverage.get("deep_scan_triggered"):
                omissions = coverage.get("omissions", [])
                raise BrainError(
                    "disposition_coverage",
                    f"{len(omissions)} dispositions missing for tracked open findings",
                    error_class="FATAL_INTEGRITY",
                    detail=f"DOD §14.6: Disposition missing → ERROR. Missing: {[o['target_id'] for o in omissions][:5]}",
                )

        if coverage.get("deep_scan_triggered"):
            # DOD §14.6: deep scan MUST run when triggered
            deep_scan_result = run_deep_semantic_scan(report, coverage.get("omissions", []))
            coverage["deep_scan"] = deep_scan_result
            proof.set_residue_verification(coverage)  # Update with deep scan data
            if deep_scan_result["material_omissions_remain"]:
                # DOD §14.6: "Material omissions unresolved after deep scan → ESCALATE"
                # Register CRITICAL blocker so D6 triggers ESCALATE
                blocker_ledger.add(
                    kind=BlockerKind.COVERAGE_GAP,
                    source="deep_semantic_scan",
                    detected_round=self._config.rounds,
                    detail=(f"Deep scan: {deep_scan_result['still_missing']} material omissions "
                            f"remain after scan (omission rate {coverage['omission_rate']:.0%})"),
                    models=[],
                    severity="CRITICAL",
                )

        if not self._stage_done("residue_verification"):
            if self._checkpoint("residue_verification"):
                return BrainResult(
                    outcome=Outcome.ESCALATE,
                    proof=proof.build(),
                    report=report,
                    preflight=preflight_result,
                )

        # DOD §14.3: Orphaned high-authority archive evidence must be explained
        orphaned_high_auth = [
            e for e in evidence.archive_items
            if e.authority_tier in ("HIGH", "AUTHORITATIVE")
            and e.evidence_id not in (report or "")
        ]
        if orphaned_high_auth:
            raise BrainError(
                "orphaned_high_authority_evidence",
                "Archived HIGH/AUTHORITATIVE evidence was not explained in synthesis",
                error_class="FATAL_INTEGRITY",
                detail=f"Missing evidence IDs: {[e.evidence_id for e in orphaned_high_auth[:5]]}",
            )

        # Legacy string-match residue check (supplementary)
        residue_omissions = check_synthesis_residue(
            report=report,
            blockers=blocker_ledger.blockers,
            contradictions=evidence.contradictions,
            unaddressed_arguments=argument_tracker.all_unaddressed,
        )
        proof.set_synthesis_residue(residue_omissions)
        if any(o.get("threshold_violation") for o in residue_omissions):
            proof.add_violation(
                "RESIDUE-THRESHOLD", "WARN",
                f"Synthesis omitted >30% of structural findings ({len(residue_omissions)} omissions)",
            )

        # --- Gate 2 (deterministic) ---
        # Compute stage integrity for D1 (DOD §3.3)
        # Include conditional stages that should have executed
        semantic_pass_required = len(evidence.active_items) >= 2
        required_stages = ["preflight", "dimensions"]
        for i in range(1, self._config.rounds + 1):
            required_stages.append(f"r{i}")
            required_stages.append(f"track{i}")
            if i == 1:
                required_stages.extend(["perspective_cards", "framing_pass"])
                if not is_analysis_mode:  # DOD §9.3: ungrounded DECIDE only
                    required_stages.append("ungrounded_r1")
            if i == 2:
                required_stages.append("frame_survival_r2")
                if not is_analysis_mode:
                    required_stages.append("ungrounded_r2")
            if i == 3:
                required_stages.append("frame_survival_r3")
        if semantic_pass_required:
            required_stages.append("semantic_contradiction")
        required_stages.extend(["decisive_claims", "synthesis_packet", "synthesis", "stability", "residue_verification"])
        completed = set(self.state.completed_stages)
        fatal_stages = [s for s in required_stages if s not in completed]

        # DOD §11.3: broken supersession links → ERROR
        # These are prevented by construction: argument_tracker validates IDs and falls
        # back to REFINED when Sonnet hallucninates a target. superseded_by is never set
        # to a bad ID in proof.json. Violations logged for audit transparency.
        for bl in argument_tracker._broken_supersession_links:
            proof.add_violation(
                "SUPERSESSION-BROKEN", "ERROR",
                f"Argument {bl['argument_id']}: LLM claimed superseded_by {bl['claimed_superseded_by']} "
                f"but target not found — fell back to REFINED (link not written to proof)",
            )

        # Merge numeric + semantic contradictions for Gate 2 (DOD §16 D8)
        all_contradictions = list(evidence.contradictions) + list(semantic_ctrs)

        gate2 = run_gate2_deterministic(
            agreement_ratio=agreement,
            positions=final_positions,
            contradictions=all_contradictions,
            unaddressed_arguments=argument_tracker.all_unaddressed,
            open_blockers=blocker_ledger.open_blockers(),
            evidence_count=len(evidence.items),
            search_enabled=search_enabled,
            preflight=preflight_result,
            divergence=divergence_result,
            stability=stability_result,
            decisive_claims=decisive_claims,
            dimensions=dimension_result,
            total_arguments=len(all_args),
            archive_evidence_count=len(evidence.archive_items),
            evidence_present=True,
            stage_integrity_fatal=fatal_stages if fatal_stages else None,
            synthesis_present=bool(report),
            analysis_map_present=bool(proof._analysis_map) if is_analysis_mode else True,
            analogies=divergence_result.cross_domain_analogies if divergence_result.cross_domain_analogies else None,
            known_evidence_ids=evidence.all_evidence_ids(),
            round_model_counts=[len(st.round_responded.get(str(i), [])) for i in range(1, self._config.rounds + 1)],
            expected_round_model_counts=[len(ROUND_TOPOLOGY[i]) for i in range(1, self._config.rounds + 1)],
        )
        log.gate2_result(
            gate2.outcome.value, agreement, outcome_class,
            len(all_ignored), len(evidence.items),
            len(evidence.contradictions), len(blocker_ledger.open_blockers()),
        )
        st.outcome = gate2.outcome.value

        # Record gate2 trace in proof (V9)
        if gate2.rule_trace:
            proof.set_gate2_trace(
                modality=gate2.modality or "DECIDE",
                rule_trace=gate2.rule_trace,
                final_outcome=gate2.outcome.value,
            )

        # DOD §18.4: fill debug_gate2_result and actual_output after Gate 2
        if is_analysis_mode and proof._analysis_debug:
            proof._analysis_debug["debug_gate2_result"] = gate2.outcome.value
            proof._analysis_debug["actual_output"] = gate2.outcome.value

        self._enforce_post_admission_outcome_contract(gate2.outcome, "gate2")

        self._checkpoint("gate2")

        # --- Invariant validation (F6) ---
        round_responded_ints = {int(k): v for k, v in st.round_responded.items()}
        inv_violations = validate_invariants(
            positions_by_round=position_tracker.positions_by_round,
            round_responded=round_responded_ints,
            evidence=evidence,
            blocker_ledger=blocker_ledger,
            rounds_completed=self._config.rounds,
        )
        for v in inv_violations:
            proof.add_violation(v["id"], v["severity"], v["detail"])

        # --- Final: Wire all remaining proof sections ---
        outcome = gate2.outcome
        proof.set_outcome(outcome, agreement, outcome_class)
        # DOD §1.5: ERROR implies error_class in {INFRASTRUCTURE, FATAL_INTEGRITY}
        if outcome == Outcome.ERROR:
            proof.set_error_class("FATAL_INTEGRITY")
        proof.set_final_status("COMPLETE")
        proof.set_evidence_count(len(evidence.items))

        # Two-tier evidence
        proof.set_evidence_two_tier(evidence.active_items, evidence.archive_items, evidence.eviction_log)

        # Search log
        proof.set_search_log(search_log_entries)

        # Ungrounded stats (DOD §9.2 schema)
        # Mark claims that were verified by evidence after search
        for fc in st.ungrounded_flagged_claims:
            if fc["status"] == "UNVERIFIED_CLAIM" and fc["blocker_id"] is None:
                # Check if the stat now appears in evidence
                stat_text = fc["text"]
                if any(stat_text in ev.fact for ev in evidence.active_items):
                    fc["verified"] = True
                    fc["status"] = "CLEAR"
        proof.set_ungrounded_stats(UngroundedStatResult(
            items=[
                UngroundedStatItem(
                    claim_id=fc["claim_id"],
                    text=fc["text"],
                    numeric=fc.get("numeric", True),
                    verified=fc.get("verified", False),
                    blocker_id=fc.get("blocker_id"),
                    severity=fc.get("severity", "MEDIUM"),
                    status=fc.get("status", "UNVERIFIED_CLAIM"),
                )
                for fc in st.ungrounded_flagged_claims
            ],
            post_r1_executed=st.ungrounded_r1_executed,
            post_r2_executed=st.ungrounded_r2_executed,
        ))

        # Contradictions (numeric + semantic)
        proof.set_contradictions(
            evidence.contradictions,
            semantic_ctrs,
            semantic_pass_executed=semantic_pass_required,
        )

        # Cross-domain analogies from divergence
        if divergence_result.cross_domain_analogies:
            proof.set_analogies(divergence_result.cross_domain_analogies)

        # Stage integrity
        proof.set_stage_integrity(
            required=required_stages + ["gate2"],
            order=self.state.completed_stages,
            fatal=fatal_stages,
        )

        # Diagnostics
        proof.set_diagnostics({
            "total_elapsed_s": round(time.monotonic() - run_start_time, 1),
            "rounds_completed": self._config.rounds,
            "search_enabled": search_enabled,
            "models_used": list(set(m for rnd in st.round_responded.values() for m in rnd)),
        })

        # DOD §19: synthesis_output and timestamp_completed
        proof.set_synthesis_output({
            "report": report[:5000] if report else None,
            "report_json": st.report_json,
        })
        proof.set_timestamp_completed()
        proof.set_error_class(None)  # No error if we reach here

        # --- Acceptance status (F2) — must be computed last, after all violations ---
        proof.compute_acceptance_status()

        log.run_complete(outcome.value, outcome_class)

        return BrainResult(
            outcome=outcome, proof=proof.build(),
            report=report, preflight=preflight_result, gate2=gate2,
            dimensions=dimension_result,
            stability=stability_result,
        )


def EvidenceItem_from_search_result(sr: SearchResult, counter: int):
    """Convert a SearchResult to an EvidenceItem for the ledger."""
    from thinker.types import Confidence
    content = sr.full_content or sr.snippet or sr.title
    if not content:
        return None
    return EvidenceItem(
        evidence_id=f"E{counter + 1:03d}",
        topic=sr.title[:100] if sr.title else sr.url[:100],
        fact=content[:500],
        url=sr.url,
        confidence=Confidence.MEDIUM,
    )


def _get_anthropic_token() -> str:
    """Get the Anthropic OAuth token.

    Priority:
    1. ANTHROPIC_OAUTH_TOKEN env var / .env (should be the 1-year setup-token)
    2. Fall back to ~/.claude/.credentials.json (rotating ~8h token)
    """
    import os
    token = os.environ.get("ANTHROPIC_OAUTH_TOKEN", "")
    if token:
        return token
    import json
    from pathlib import Path
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        try:
            creds = json.loads(creds_path.read_text(encoding="utf-8"))
            return creds.get("claudeAiOauth", {}).get("accessToken", "")
        except Exception:
            pass
    return ""


async def main():
    """CLI entry point for the Brain engine."""
    import argparse
    import json
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Thinker V8 Brain Engine")
    parser.add_argument("--brief", required=True, help="Path to brief markdown file")
    parser.add_argument("--rounds", type=int, default=4, help="Number of rounds (1-4)")
    parser.add_argument("--outdir", default="./output", help="Output directory")
    parser.add_argument("--verbose", action="store_true", help="Full logging at each stage")
    parser.add_argument("--stop-after", default=None,
                        help="Stop after STAGE, save checkpoint (preflight,dimensions,r1,track1,...)")
    parser.add_argument("--resume", default=None,
                        help="Resume from a checkpoint JSON file (skips completed stages)")
    parser.add_argument("--full-run", action="store_true",
                        help="Run all stages without pausing (overrides default step-by-step mode)")
    search_group = parser.add_mutually_exclusive_group()
    search_group.add_argument("--search", action="store_true", default=None,
                              help="Force search on (overrides Gate 1 recommendation)")
    search_group.add_argument("--no-search", action="store_true", default=None,
                              help="Force search off (overrides Gate 1 recommendation)")
    parser.add_argument("--skip-assumption-gate", action="store_true",
                        help="Skip fatal assumption check (for self-review briefs where completeness is attested)")
    args = parser.parse_args()

    brief_text = open(args.brief, encoding="utf-8").read()
    config = BrainConfig(
        rounds=args.rounds,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        anthropic_oauth_token=_get_anthropic_token(),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        zai_api_key=os.environ.get("ZAI_API_KEY", ""),
        brave_api_key=os.environ.get("BRAVE_API_KEY", ""),
        outdir=args.outdir,
        skip_assumption_gate=args.skip_assumption_gate,
    )

    # Load checkpoint if resuming
    resume_state = None
    if args.resume:
        resume_state = PipelineState.load(Path(args.resume))
        print(f"Resuming from checkpoint: {args.resume}")
        print(f"  Last stage: {resume_state.current_stage}")
        print(f"  Completed: {' → '.join(resume_state.completed_stages)}")

    from thinker.llm import LLMClient
    from thinker.brave_search import brave_search
    from thinker.sonar_search import sonar_search
    from functools import partial
    llm = LLMClient(config)

    # Step-by-step is the DEFAULT. --full-run disables it.
    debug_step = not args.full_run
    verbose = args.verbose or args.stop_after is not None or args.resume is not None or debug_step

    # Search: Bing via Playwright (headful, $0). Error if unavailable.
    search_fn = None
    try:
        from thinker.bing_search import bing_search
        search_fn = bing_search
        if verbose:
            print("  [SEARCH] Using Bing via Playwright (headful, $0)")
    except ImportError:
        print("  [SEARCH ERROR] Bing search requires playwright: pip install playwright && playwright install chromium")
        raise SystemExit(1)
    sonar_fn = partial(sonar_search, api_key=config.openrouter_api_key) if config.openrouter_api_key else None
    # Resolve search override from CLI flags
    search_override = None
    if args.search:
        search_override = True
    elif args.no_search:
        search_override = False

    brain = Brain(
        config=config, llm_client=llm, search_fn=search_fn,
        sonar_fn=sonar_fn,
        verbose=verbose, stop_after=args.stop_after, outdir=args.outdir,
        resume_state=resume_state, debug_step=debug_step,
        search_override=search_override,
    )
    try:
        result = await brain.run(brief_text)
    except BrainError as e:
        print(f"\n{'='*60}")
        print(f"  SYSTEM ERROR — Pipeline halted")
        print(f"{'='*60}")
        print(f"  Stage:   {e.stage}")
        print(f"  Error:   {e.message}")
        if e.detail:
            print(f"  Detail:  {e.detail}")
        print(f"  Checkpoint: {os.path.join(args.outdir, 'checkpoint.json')}")
        print(f"{'='*60}")
        # Save what we have so far
        os.makedirs(args.outdir, exist_ok=True)
        # DOD §19: write partial proof.json on ERROR
        if hasattr(e, 'partial_proof') and e.partial_proof:
            error_proof_path = os.path.join(args.outdir, "proof.json")
            with open(error_proof_path, "w", encoding="utf-8") as f:
                json.dump(e.partial_proof, f, indent=2)
            print(f"  Proof:   {error_proof_path} (partial — error_class set)")
        brain.log.save_log(Path(args.outdir) / "debug.log")
        brain.log.save_events_json(Path(args.outdir) / "events.json")
        await llm.close()
        raise SystemExit(1)

    # Save outputs
    os.makedirs(args.outdir, exist_ok=True)
    proof_path = os.path.join(args.outdir, "proof.json")
    with open(proof_path, "w", encoding="utf-8") as f:
        json.dump(result.proof, f, indent=2)
    report_path = os.path.join(args.outdir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result.report)

    # Save debug outputs
    brain.log.save_log(Path(args.outdir) / "debug.log")
    brain.log.save_events_json(Path(args.outdir) / "events.json")

    # Generate auto-populated diagram from stage registry + run data
    # Import all tagged modules so the registry is populated
    import thinker.preflight, thinker.rounds, thinker.argument_tracker  # noqa: F401
    import thinker.tools.position, thinker.search, thinker.synthesis, thinker.gate2  # noqa: F401
    import thinker.invariant, thinker.residue, thinker.page_fetch, thinker.evidence_extractor  # noqa: F401
    import thinker.preflight, thinker.dimension_seeder  # noqa: F401
    import thinker.perspective_cards, thinker.divergent_framing  # noqa: F401
    import thinker.semantic_contradiction, thinker.stability  # noqa: F401
    from thinker.pipeline import generate_architecture_html
    events_data = json.loads((Path(args.outdir) / "events.json").read_text())
    generate_architecture_html(
        Path(args.outdir) / "run-report.html",
        run_events=events_data, proof=result.proof, report=result.report,
    )

    print(f"\nOutcome: {result.outcome.value}")
    print(f"Class: {result.proof.get('v3_outcome_class', 'N/A')}")
    print(f"Proof: {proof_path}")
    print(f"Report: {report_path}")
    print(f"Debug: {os.path.join(args.outdir, 'run-report.html')}")

    await llm.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

---

## Current Implementation: thinker/gate2.py

"""Gate 2: Deterministic trust assessment with D1-D14 and A1-A7 rule sets.

No LLM call. Thresholds on mechanical tool data only.

DECIDE modality: D1-D14 rules, first match wins.
ANALYSIS modality: A1-A7 rules, first match wins.

Every rule evaluated is recorded in rule_trace for auditability.
"""
from __future__ import annotations

from typing import Optional

from thinker.pipeline import pipeline_stage
from thinker.types import (
    AnalogyTestStatus, Argument, ArgumentStatus, Blocker, Contradiction,
    CrossDomainAnalogy, DecisiveClaim, DimensionSeedResult, DivergenceResult,
    EvidenceSupportStatus, FrameSurvivalStatus,
    Gate2Assessment, Modality, Outcome, Position,
    PreflightResult, StabilityResult,
)


@pipeline_stage(
    name="Gate 2",
    description="Fully deterministic trust assessment. No LLM call. Instant. Reproducible. "
                "D1-D14 (DECIDE) and A1-A7 (ANALYSIS) rule sets, first match wins. "
                "Every rule evaluated is recorded in rule_trace.",
    stage_type="deterministic",
    order=7,
    provider="deterministic (no LLM)",
    inputs=["agreement_ratio", "positions", "contradictions", "unaddressed_arguments",
            "open_blockers", "evidence_count", "search_enabled",
            "preflight", "divergence", "stability", "decisive_claims", "dimensions",
            "total_arguments", "archive_evidence_count"],
    outputs=["outcome (DECIDE/ESCALATE/NO_CONSENSUS/ANALYSIS/ERROR/NEED_MORE)", "rule_trace"],
    logic="""DECIDE modality: D1-D14, first match wins.
ANALYSIS modality: A1-A7, first match wins.
See module docstring for full rule definitions.""",
    thresholds={"agreement_ratio >= 0.75": "DECIDE", "agreement_ratio < 0.5": "NO_CONSENSUS/ESCALATE"},
    failure_mode="Cannot fail — deterministic computation.",
    cost="$0 (no LLM call)",
    stage_id="gate2",
)
def classify_outcome(
    agreement_ratio: float,
    ignored_arguments: int,
    mentioned_arguments: int,
    evidence_count: int,
    contradictions: int,
    open_blockers: int,
    search_enabled: bool,
) -> str:
    """Deterministic outcome classification (V8 compat).

    Returns one of: CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, PARTIAL_CONSENSUS,
    INSUFFICIENT_EVIDENCE, NO_CONSENSUS.
    """
    if agreement_ratio < 0.5:
        return "NO_CONSENSUS"

    if search_enabled and evidence_count == 0:
        return "INSUFFICIENT_EVIDENCE"

    if (agreement_ratio >= 0.75
            and ignored_arguments == 0
            and contradictions == 0
            and open_blockers == 0):
        return "CONSENSUS"

    if agreement_ratio >= 0.75 and ignored_arguments <= 2:
        return "CLOSED_WITH_ACCEPTED_RISKS"

    return "PARTIAL_CONSENSUS"


# ---------------------------------------------------------------------------
# Helper: blocker severity (backward-compatible)
# ---------------------------------------------------------------------------

def _blocker_severity(b: Blocker) -> str:
    """Get severity from a Blocker, defaulting to LOW if not present."""
    return getattr(b, "severity", "LOW")


def _all_blockers_low(blockers: list[Blocker]) -> bool:
    """True if every blocker has LOW severity (or list is empty)."""
    return all(_blocker_severity(b) == "LOW" for b in blockers)


# ---------------------------------------------------------------------------
# DECIDE rules D1-D14
# ---------------------------------------------------------------------------

def _eval_decide_rules(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list[Blocker],
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult],
    divergence: Optional[DivergenceResult],
    stability: Optional[StabilityResult],
    decisive_claims: Optional[list[DecisiveClaim]],
    dimensions: Optional[DimensionSeedResult],
    total_arguments: int,
    stage_integrity_fatal: Optional[list[str]] = None,
    analogies: Optional[list[CrossDomainAnalogy]] = None,
    known_evidence_ids: Optional[set[str]] = None,
    round_model_counts: Optional[list[int]] = None,
    expected_round_model_counts: Optional[list[int]] = None,
) -> tuple[Outcome, list[dict]]:
    """Evaluate D1-D14 per DOD-V3 Section 16. First match wins."""
    trace: list[dict] = []

    def _t(rule_id: str, matched: bool, reason: str) -> bool:
        trace.append({"rule_id": rule_id, "evaluated": True, "fired": matched,
                      "outcome_if_fired": None, "reason": reason})
        return matched

    # Pre-compute conditions
    stability = stability or StabilityResult()
    conclusion_stable = stability.conclusion_stable
    reason_stable = stability.reason_stable
    assumption_stable = stability.assumption_stable
    groupthink_warning = stability.groupthink_warning
    independent_evidence = stability.independent_evidence_present

    # CRITICAL blockers — DOD Section 16 D6: "any unresolved CRITICAL blocker"
    critical_blockers = [b for b in open_blockers
                         if getattr(b, 'severity', 'MEDIUM') == "CRITICAL"]

    # Decisive claims without valid evidence (DOD §13.4 + D7)
    # SUPPORTED with empty evidence_refs is also invalid — phantom support
    claims_lacking_evidence = [
        c for c in (decisive_claims or [])
        if c.material_to_conclusion and (
            c.evidence_support_status != EvidenceSupportStatus.SUPPORTED
            or (c.evidence_support_status == EvidenceSupportStatus.SUPPORTED and (
                not c.evidence_refs
                or (
                    known_evidence_ids is not None
                    and any(ref not in known_evidence_ids for ref in c.evidence_refs)
                )
            ))
        )
    ]

    # HIGH/CRITICAL unresolved contradictions (handle both enum and string severity)
    high_contradictions = [
        c for c in contradictions
        if str(getattr(getattr(c, "status", "OPEN"), "value", getattr(c, "status", "OPEN"))) in ("OPEN", "open")
        and str(getattr(getattr(c, "severity", "LOW"), "value", getattr(c, "severity", "LOW"))) in ("HIGH", "CRITICAL")
    ]

    # Unresolved CRITICAL premise flags
    critical_premise_flags = preflight.unresolved_critical_flags if preflight else []

    # Material frames without rebuttal or disposition
    material_frames_unresolved = []
    if divergence:
        for f in divergence.alt_frames:
            if (f.material_to_outcome
                    and f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)
                    and f.synthesis_disposition_status == "UNADDRESSED"):
                material_frames_unresolved.append(f)

    # --- D1: Fatal integrity or infrastructure failure (DOD §16, §3.3) ---
    # Fires when critical pipeline data is completely absent or stage integrity
    # reports fatal failures — indicating infrastructure failure.
    no_pipeline_output = (total_arguments == 0 and len(positions) == 0)
    empty_dimensions = (
        dimensions is not None and len(dimensions.items) == 0
    )
    has_fatal_stages = bool(stage_integrity_fatal)
    topology_mismatch = (
        round_model_counts is not None
        and expected_round_model_counts is not None
        and round_model_counts != expected_round_model_counts
    )
    fatal_integrity = no_pipeline_output or empty_dimensions or has_fatal_stages or topology_mismatch
    if _t("D1", fatal_integrity,
          f"models={len(positions)}, args={total_arguments}, "
          f"dims={'none' if dimensions is None else len(dimensions.items)}, "
          f"fatal_stages={stage_integrity_fatal or []}, "
          f"round_model_counts={round_model_counts}, expected_round_model_counts={expected_round_model_counts}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- D2: Modality mismatch ---
    modality_mismatch = preflight and preflight.modality != Modality.DECIDE if preflight else False
    if _t("D2", modality_mismatch,
          f"preflight.modality={preflight.modality.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- D3: SHORT_CIRCUIT without evidence ---
    short_circuit_without_evidence = (
        preflight is not None
        and preflight.short_circuit_allowed
        and evidence_count == 0
    )
    if _t("D3", short_circuit_without_evidence,
          f"short_circuit_allowed={preflight.short_circuit_allowed if preflight else False}, evidence={evidence_count}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D4: agreement < 0.50 ---
    if _t("D4", agreement_ratio < 0.50,
          f"agreement={agreement_ratio:.2f}<0.50"):
        trace[-1]["outcome_if_fired"] = "NO_CONSENSUS"
        return Outcome.NO_CONSENSUS, trace

    # --- D5: agreement 0.50-0.74 ---
    if _t("D5", 0.50 <= agreement_ratio < 0.75,
          f"agreement={agreement_ratio:.2f} in [0.50,0.75)"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D6: Any unresolved CRITICAL blocker ---
    if _t("D6", len(critical_blockers) > 0,
          f"critical_blockers={len(critical_blockers)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D7: Decisive claim lacks valid evidence binding ---
    if _t("D7", len(claims_lacking_evidence) > 0,
          f"claims_lacking_evidence={len(claims_lacking_evidence)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D8: HIGH/CRITICAL contradiction unresolved ---
    if _t("D8", len(high_contradictions) > 0,
          f"high_contradictions={len(high_contradictions)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D9: Unresolved CRITICAL premise flag ---
    if _t("D9", len(critical_premise_flags) > 0,
          f"critical_premise_flags={len(critical_premise_flags)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D10: Material unresolved (frames or untested decisive analogies) ---
    # DOD §16 D10: material frame ACTIVE/CONTESTED without disposition
    # DOD §13.4: untested analogy used decisively → ESCALATE
    untested_decisive_analogies = []
    if analogies and decisive_claims:
        untested_ids = {a.analogy_id for a in analogies if a.test_status == AnalogyTestStatus.UNTESTED}
        for c in (decisive_claims or []):
            for ref in c.analogy_refs:
                if ref in untested_ids:
                    untested_decisive_analogies.append(ref)
    d10_fired = len(material_frames_unresolved) > 0 or len(untested_decisive_analogies) > 0
    if _t("D10", d10_fired,
          f"material_frames_unresolved={len(material_frames_unresolved)}, "
          f"untested_decisive_analogies={untested_decisive_analogies}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D11: conclusion_stable = false ---
    if _t("D11", not conclusion_stable,
          f"conclusion_stable={conclusion_stable}"):
        trace[-1]["outcome_if_fired"] = "NO_CONSENSUS"
        return Outcome.NO_CONSENSUS, trace

    # --- D12: reason_stable = false OR assumption_stable = false ---
    if _t("D12", not reason_stable or not assumption_stable,
          f"reason_stable={reason_stable}, assumption_stable={assumption_stable}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D13: groupthink + no independent evidence ---
    if _t("D13", groupthink_warning and not independent_evidence,
          f"groupthink={groupthink_warning}, independent_evidence={independent_evidence}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D14: Otherwise → DECIDE ---
    _t("D14", True, "all checks passed")
    trace[-1]["outcome_if_fired"] = "DECIDE"
    return Outcome.DECIDE, trace


# ---------------------------------------------------------------------------
# ANALYSIS rules A1-A7
# ---------------------------------------------------------------------------

def _eval_analysis_rules(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list[Blocker],
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult],
    divergence: Optional[DivergenceResult],
    stability: Optional[StabilityResult],
    decisive_claims: Optional[list[DecisiveClaim]],
    dimensions: Optional[DimensionSeedResult],
    total_arguments: int,
    archive_evidence_count: int = 0,
    evidence_present: bool = True,
    synthesis_present: bool = True,
    analysis_map_present: bool = True,
) -> tuple[Outcome, list[dict]]:
    """Evaluate A1-A7 per DOD-V3 Section 17. First match wins.

    ANALYSIS mode may only emit: ANALYSIS, ESCALATE, ERROR (never NO_CONSENSUS).
    """
    trace: list[dict] = []

    def _t(rule_id: str, matched: bool, reason: str) -> bool:
        trace.append({"rule_id": rule_id, "evaluated": True, "fired": matched,
                      "outcome_if_fired": None, "reason": reason})
        return matched

    from thinker.types import SearchScope

    # --- A1: Missing or invalid PreflightAssessment ---
    preflight_missing = preflight is None or not preflight.executed or not preflight.parse_ok
    if _t("A1", preflight_missing,
          f"preflight={'missing' if preflight is None else f'executed={preflight.executed}, parse_ok={preflight.parse_ok}'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A2: Modality mismatch ---
    modality_mismatch = preflight.modality != Modality.ANALYSIS if preflight else True
    if _t("A2", modality_mismatch,
          f"preflight.modality={preflight.modality.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A3: Missing required shared pipeline artifacts (DOD §17) ---
    # Checks: dimension seeder, analysis_map, synthesis, evidence artifact presence.
    # Note: evidence_count==0 is handled by A4 (ESCALATE, not ERROR).
    missing_artifacts = (
        (dimensions is None or len(dimensions.items) == 0)
        or not evidence_present
        or not synthesis_present
        or not analysis_map_present
    )
    if _t("A3", missing_artifacts,
          f"dimensions={'empty' if not dimensions or not dimensions.items else len(dimensions.items)}, "
          f"args={total_arguments}, evidence={evidence_count}, evidence_present={evidence_present}, "
          f"synthesis_present={synthesis_present}, analysis_map_present={analysis_map_present}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A4: Evidence archive empty AND search_scope != NONE ---
    search_scope_not_none = preflight.search_scope != SearchScope.NONE if preflight else False
    evidence_archive_empty = archive_evidence_count == 0 and evidence_count == 0
    if _t("A4", evidence_archive_empty and search_scope_not_none,
          f"evidence={evidence_count}, archive={archive_evidence_count}, search_scope={preflight.search_scope.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A5: Any mandatory dimension has zero arguments ---
    zero_coverage_dims = []
    if dimensions and dimensions.items:
        zero_coverage_dims = [d for d in dimensions.items
                              if d.mandatory and d.coverage_status == "ZERO"
                              and not d.justified_irrelevance]
    if _t("A5", len(zero_coverage_dims) > 0,
          f"zero_coverage_dimensions={len(zero_coverage_dims)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A6: Total arguments < 8 ---
    if _t("A6", total_arguments < 8,
          f"total_arguments={total_arguments}<8"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A7: Otherwise → ANALYSIS ---
    _t("A7", True, "all checks passed — ANALYSIS")
    trace[-1]["outcome_if_fired"] = "ANALYSIS"
    return Outcome.ANALYSIS, trace


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_gate2_deterministic(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list,
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult] = None,
    divergence: Optional[DivergenceResult] = None,
    stability: Optional[StabilityResult] = None,
    decisive_claims: Optional[list[DecisiveClaim]] = None,
    dimensions: Optional[DimensionSeedResult] = None,
    total_arguments: int = 0,
    archive_evidence_count: int = 0,
    evidence_present: bool = True,
    stage_integrity_fatal: Optional[list[str]] = None,
    analogies: Optional[list[CrossDomainAnalogy]] = None,
    synthesis_present: bool = True,
    analysis_map_present: bool = True,
    known_evidence_ids: Optional[set[str]] = None,
    round_model_counts: Optional[list[int]] = None,
    expected_round_model_counts: Optional[list[int]] = None,
) -> Gate2Assessment:
    """Deterministic Gate 2 — no LLM call.

    Dispatches to D1-D14 (DECIDE modality) or A1-A7 (ANALYSIS modality)
    based on preflight.modality. First matching rule wins.

    All parameters after search_enabled are optional for backward compatibility.
    """
    # Determine modality
    is_analysis = (preflight is not None and preflight.modality == Modality.ANALYSIS)
    modality_label = "ANALYSIS" if is_analysis else "DECIDE"

    # Compute legacy flags for backward-compat fields
    ignored = [a for a in unaddressed_arguments if isinstance(a, Argument) and a.status == ArgumentStatus.IGNORED]
    mentioned = [a for a in unaddressed_arguments if isinstance(a, Argument) and a.status == ArgumentStatus.MENTIONED]

    convergence_ok = agreement_ratio >= 0.75
    evidence_ok = evidence_count >= 3 or not search_enabled
    dissent_ok = len(ignored) <= 2
    data_ok = evidence_count > 0 or not search_enabled
    no_blockers = len(open_blockers) == 0

    # Dispatch to rule engine
    if is_analysis:
        outcome, rule_trace = _eval_analysis_rules(
            agreement_ratio=agreement_ratio,
            positions=positions,
            contradictions=contradictions,
            unaddressed_arguments=unaddressed_arguments,
            open_blockers=open_blockers,
            evidence_count=evidence_count,
            search_enabled=search_enabled,
            preflight=preflight,
            divergence=divergence,
            stability=stability,
            decisive_claims=decisive_claims,
            dimensions=dimensions,
            total_arguments=total_arguments,
            archive_evidence_count=archive_evidence_count,
            evidence_present=evidence_present,
            synthesis_present=synthesis_present,
            analysis_map_present=analysis_map_present,
        )
    else:
        outcome, rule_trace = _eval_decide_rules(
            agreement_ratio=agreement_ratio,
            positions=positions,
            contradictions=contradictions,
            unaddressed_arguments=unaddressed_arguments,
            open_blockers=open_blockers,
            evidence_count=evidence_count,
            search_enabled=search_enabled,
            preflight=preflight,
            divergence=divergence,
            stability=stability,
            decisive_claims=decisive_claims,
            dimensions=dimensions,
            total_arguments=total_arguments,
            stage_integrity_fatal=stage_integrity_fatal,
            analogies=analogies,
            known_evidence_ids=known_evidence_ids,
            round_model_counts=round_model_counts,
            expected_round_model_counts=expected_round_model_counts,
        )

    # Identify which rule fired
    matched_rule = next((r["rule_id"] for r in rule_trace if r.get("fired")), "NONE")

    # Build legacy classification for backward compat
    outcome_class = classify_outcome(
        agreement_ratio=agreement_ratio,
        ignored_arguments=len(ignored),
        mentioned_arguments=len(mentioned),
        evidence_count=evidence_count,
        contradictions=len(contradictions),
        open_blockers=len(open_blockers),
        search_enabled=search_enabled,
    )

    return Gate2Assessment(
        outcome=outcome,
        convergence_ok=convergence_ok,
        evidence_credible=evidence_ok,
        dissent_addressed=dissent_ok,
        enough_data=data_ok,
        report_honest=no_blockers,
        reasoning=(
            f"Deterministic [{modality_label}]: rule={matched_rule}, "
            f"agreement={agreement_ratio:.2f}, "
            f"ignored={len(ignored)}, evidence={evidence_count}, "
            f"contradictions={len(contradictions)}, blockers={len(open_blockers)}, "
            f"class={outcome_class}"
        ),
        modality=modality_label,
        rule_trace=rule_trace,
    )

---

## Current Implementation: thinker/proof.py

"""Proof.json builder — the machine-readable audit trail.

Schema 3.0 (V9). Adds: preflight, dimensions, perspective_cards, divergence,
search_log, ungrounded_stats, two-tier evidence, arguments with resolution,
decisive_claims, cross_domain_analogies, semantic contradictions,
synthesis_packet, synthesis dispositions, stability, gate2 rule_trace,
stage_integrity, analysis_map, analysis_debug, diagnostics.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from thinker.types import Outcome, Position
from thinker.tools.blocker import BlockerLedger


def _serialize_blocker_status(status: str) -> str:
    return "DEFERRED" if status == "DROPPED" else status


_EXPECTED_STAGE_ORDER = [
    "preflight",
    "dimensions",
    "r1",
    "track1",
    "perspective_cards",
    "framing_pass",
    "ungrounded_r1",
    "search1",
    "r2",
    "track2",
    "frame_survival_r2",
    "ungrounded_r2",
    "search2",
    "r3",
    "track3",
    "frame_survival_r3",
    "r4",
    "track4",
    "semantic_contradiction",
    "decisive_claims",
    "synthesis_packet",
    "synthesis",
    "stability",
    "residue_verification",
    "gate2",
]


def _validate_stage_order(order: list[str]) -> tuple[bool, list[str]]:
    expected_positions = {stage: idx for idx, stage in enumerate(_EXPECTED_STAGE_ORDER)}
    violations: list[str] = []
    last_expected_index = -1

    for idx, stage in enumerate(order):
        expected_index = expected_positions.get(stage)
        if expected_index is None:
            violations.append(f"Unknown stage '{stage}' at position {idx + 1}")
            continue
        if expected_index < last_expected_index:
            violations.append(
                f"Stage '{stage}' executed at position {idx + 1} after a later stage"
            )
        else:
            last_expected_index = expected_index

    return len(violations) == 0, violations


class ProofBuilder:
    """Incrementally builds proof.json throughout a Brain run."""

    def __init__(self, run_id: str, brief: str, rounds_requested: int):
        self._run_id = run_id
        self._brief = brief
        self._rounds_requested = rounds_requested
        self._timestamp_started = datetime.now(timezone.utc).isoformat()
        self._timestamp_completed: Optional[str] = None
        self._topology: Optional[dict] = None
        self._error_class: Optional[str] = None
        self._config_snapshot: Optional[dict] = None
        self._rounds: dict[str, dict] = {}
        self._positions: dict[str, dict] = {}
        self._position_changes: list[dict] = []
        self._outcome: dict = {}
        self._final_status: Optional[str] = None
        self._synthesis_status: Optional[str] = None
        self._evidence_items: int = 0
        self._research_phases: list[dict] = []
        self._blocker_ledger: Optional[BlockerLedger] = None
        self._invariant_violations: list[dict] = []
        self._acceptance_status: Optional[str] = None
        self._synthesis_residue_omissions: list[dict] = []
        self._search_decision: Optional[dict] = None
        self._v3_outcome_class: str = "not applicable"
        # V9 additions
        self._preflight: Optional[dict] = None
        self._dimensions: Optional[dict] = None
        self._perspective_cards: Optional[list[dict]] = None
        self._divergence: Optional[dict] = None
        self._search_log: list[dict] = []
        self._ungrounded_stats: list[dict] = []
        self._evidence_active: list[dict] = []
        self._evidence_archive: list[dict] = []
        self._eviction_log: list[dict] = []
        self._arguments: list[dict] = []
        self._decisive_claims: list[dict] = []
        self._cross_domain_analogies: list[dict] = []
        self._contradictions_numeric: list[dict] = []
        self._contradictions_semantic: list[dict] = []
        self._synthesis_packet: Optional[dict] = None
        self._synthesis_dispositions: list[dict] = []
        self._stability: Optional[dict] = None
        self._gate2_trace: Optional[dict] = None
        self._stage_integrity: Optional[dict] = None
        self._analysis_map: list[dict] = []
        self._analysis_debug: Optional[dict] = None
        self._diagnostics: dict = {}
        self._residue_verification: Optional[dict] = None
        self._synthesis_output: Optional[dict] = None
        self._budgeting: Optional[dict] = None

    def record_round(self, round_num: int, responded: list[str], failed: list[str]):
        self._rounds[str(round_num)] = {
            "responded": responded,
            "failed": failed,
        }

    def record_positions(self, round_num: int, positions: dict[str, Position]):
        round_positions = {}
        for model, pos in positions.items():
            round_positions[model] = {
                "model": pos.model,
                "kind": pos.kind,
                "primary_option": pos.primary_option,
                "components": pos.components,
                "confidence": pos.confidence.value,
                "qualifier": pos.qualifier,
            }
        self._positions[str(round_num)] = round_positions

    def record_position_changes(self, changes: list[dict]):
        self._position_changes.extend(changes)

    def record_research_phase(self, phase: str, method: str,
                              queries: int, items_admitted: int):
        self._research_phases.append({
            "phase": phase, "method": method,
            "queries_attempted": queries, "items_admitted": items_admitted,
        })

    def set_evidence_count(self, count: int):
        self._evidence_items = count

    def set_outcome(self, outcome: Outcome, agreement_ratio: float,
                    outcome_class: str):
        self._outcome = {
            "outcome_class": outcome_class,
            "agreement_ratio": agreement_ratio,
            "verdict": outcome.value,
        }
        self._v3_outcome_class = outcome_class

    def set_final_status(self, status: str):
        self._final_status = status

    def set_synthesis_status(self, status: str):
        self._synthesis_status = status

    def set_blocker_ledger(self, ledger: BlockerLedger):
        self._blocker_ledger = ledger

    def compute_acceptance_status(self):
        """Compute acceptance_status from run metrics.

        ACCEPTED: clean run — DECIDE outcome, CONSENSUS class, no violations.
        V9: ACCEPTED_WITH_WARNINGS removed. Now just ACCEPTED or outcome-based.
        Never REJECTED — if fatal, BrainError stops the pipeline before proof.
        """
        from thinker.types import AcceptanceStatus
        is_clean = (
            self._outcome.get("verdict") == "DECIDE"
            and self._outcome.get("outcome_class") == "CONSENSUS"
            and len(self._invariant_violations) == 0
        )
        self._acceptance_status = AcceptanceStatus.ACCEPTED.value if is_clean else "REVIEW_REQUIRED"

    def set_synthesis_residue(self, omissions: list[dict]):
        self._synthesis_residue_omissions = omissions

    def set_search_decision(self, source: str, value: bool, reasoning: str,
                            gate1_recommended: Optional[bool] = None,
                            gate1_search_reasoning: Optional[str] = None):
        """Record who decided search on/off and why.

        source: "gate1" | "cli_override"
        value: True (search on) or False (search off)
        reasoning: Why this decision was made
        gate1_recommended: Gate 1's original recommendation (if overridden)
        gate1_search_reasoning: Gate 1's reasoning for its recommendation (if overridden)
        """
        self._search_decision = {
            "source": source,
            "value": value,
            "reasoning": reasoning,
        }
        if source == "cli_override" and gate1_recommended is not None:
            self._search_decision["gate1_recommended"] = gate1_recommended
            if gate1_search_reasoning:
                self._search_decision["gate1_search_reasoning"] = gate1_search_reasoning

    def add_violation(self, violation_id: str, severity: str, detail: str):
        self._invariant_violations.append({
            "id": violation_id, "severity": severity, "detail": detail,
        })

    # --- V9 Setters ---

    def set_timestamp_completed(self) -> None:
        """Record the completion timestamp."""
        self._timestamp_completed = datetime.now(timezone.utc).isoformat()

    def set_topology(self, topology: dict) -> None:
        """Set the round topology (DOD §19: which models in each round)."""
        self._topology = topology

    def set_error_class(self, error_class: Optional[str]) -> None:
        """Set error_class (DOD §19: null when no error)."""
        self._error_class = error_class

    def set_config_snapshot(self, config: dict) -> None:
        """Set config_snapshot (DOD §19: runtime config at start)."""
        self._config_snapshot = config

    def set_synthesis_output(self, output: dict) -> None:
        """Set synthesis_output (DOD §19: synthesis report + JSON)."""
        self._synthesis_output = output

    def set_budgeting(self, data: dict) -> None:
        """Set budgeting data (DOD §5.1)."""
        self._budgeting = data

    def set_preflight(self, result) -> None:
        """Set preflight assessment result (PreflightResult.to_dict())."""
        self._preflight = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_dimensions(self, result) -> None:
        """Set dimension seeder result (DimensionSeedResult.to_dict())."""
        self._dimensions = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_perspective_cards(self, cards: list) -> None:
        """Set perspective cards list."""
        self._perspective_cards = [c.to_dict() if hasattr(c, 'to_dict') else c for c in cards]

    def set_divergence(self, result) -> None:
        """Set divergence/framing result."""
        self._divergence = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_search_log(self, entries: list) -> None:
        """Set search log entries."""
        self._search_log = [e.to_dict() if hasattr(e, 'to_dict') else e for e in entries]

    def set_ungrounded_stats(self, data) -> None:
        """Set ungrounded statistic detection results (DOD §9.2 schema)."""
        payload = data.to_dict() if hasattr(data, "to_dict") else data
        if isinstance(payload, dict):
            if "items" in payload and "flagged_claims" not in payload:
                payload = {**payload, "flagged_claims": payload.get("items", [])}
            payload.pop("items", None)
        self._ungrounded_stats = payload

    def set_evidence_two_tier(self, active: list, archive: list, eviction_log: list) -> None:
        """Set two-tier evidence data."""
        self._evidence_active = [
            {"evidence_id": e.evidence_id, "topic": e.topic, "fact": e.fact,
             "source_url": e.url, "confidence": e.confidence.value, "score": e.score,
             "topic_cluster": e.topic_cluster, "authority_tier": e.authority_tier,
             "is_active": e.is_active, "is_archived": e.is_archived,
             "referenced_by": e.referenced_by}
            if hasattr(e, 'evidence_id') else e
            for e in active
        ]
        self._evidence_archive = [
            {"evidence_id": e.evidence_id, "topic": e.topic, "fact": e.fact,
             "source_url": e.url, "confidence": e.confidence.value, "score": e.score,
             "topic_cluster": e.topic_cluster, "authority_tier": e.authority_tier,
             "is_active": e.is_active, "is_archived": e.is_archived,
             "referenced_by": e.referenced_by}
            if hasattr(e, 'evidence_id') else e
            for e in archive
        ]
        self._eviction_log = [
            ev.to_dict() if hasattr(ev, 'to_dict') else ev for ev in eviction_log
        ]

    def set_arguments(self, arguments: list, blocker_ledger=None) -> None:
        """Set argument map with resolution status (DOD §19: object keyed by argument_id)."""
        # Build dimension→blocker mapping for blocker_link_ids
        dim_blockers: dict[str, list[str]] = {}
        if blocker_ledger:
            for b in blocker_ledger.blockers:
                if b.source.startswith("dimension:"):
                    dim_id = b.source.split(":", 1)[1]
                    dim_blockers.setdefault(dim_id, []).append(b.blocker_id)

        self._arguments = {}
        for a in arguments:
            if hasattr(a, 'argument_id'):
                links = list(getattr(a, "blocker_link_ids", []))
                if a.dimension_id:
                    for blocker_id in dim_blockers.get(a.dimension_id, []):
                        if blocker_id not in links:
                            links.append(blocker_id)
                self._arguments[a.argument_id] = {
                    "argument_id": a.argument_id, "round_origin": a.round_num,
                    "model_id": a.model, "text": a.text,
                    "status": a.status.value, "resolution_status": a.resolution_status.value,
                    "refines": a.refines,
                    "superseded_by": a.superseded_by, "dimension_id": a.dimension_id,
                    "blocker_link_ids": links, "evidence_refs": a.evidence_refs, "open": a.open,
                }
            else:
                key = a.get("argument_id", f"arg-{len(self._arguments)}")
                self._arguments[key] = a

    def set_decisive_claims(self, claims: list) -> None:
        """Set decisive claims."""
        self._decisive_claims = [c.to_dict() if hasattr(c, 'to_dict') else c for c in claims]

    def set_analogies(self, analogies: list) -> None:
        """Set cross-domain analogies."""
        self._cross_domain_analogies = [a.to_dict() if hasattr(a, 'to_dict') else a for a in analogies]

    def set_contradictions(self, numeric: list, semantic: list, semantic_pass_executed: bool = True) -> None:
        """Set both numeric and semantic contradictions."""
        self._semantic_pass_executed = semantic_pass_executed
        self._contradictions_numeric = [
            {"ctr_id": c.ctr_id,
             "detection_mode": c.detection_mode,
             "evidence_ref_a": c.evidence_ref_a, "evidence_ref_b": c.evidence_ref_b,
             "same_entity": c.same_entity, "same_timeframe": c.same_timeframe,
             "topic": c.topic, "severity": c.severity, "status": c.status,
             "justification": c.justification, "linked_claim_ids": c.linked_claim_ids}
            if hasattr(c, 'ctr_id') else c
            for c in numeric
        ]
        self._contradictions_semantic = [
            c.to_dict() if hasattr(c, 'to_dict') else c for c in semantic
        ]

    def set_synthesis_packet(self, packet: dict) -> None:
        """Set synthesis packet data."""
        if isinstance(packet, dict) and "decisive_claims" in packet and "decisive_claim_bindings" not in packet:
            payload = {**packet, "decisive_claim_bindings": packet.get("decisive_claims", [])}
            payload.pop("decisive_claims", None)
            self._synthesis_packet = payload
            return
        self._synthesis_packet = packet

    def set_synthesis_dispositions(self, dispositions: list) -> None:
        """Set synthesis dispositions."""
        self._synthesis_dispositions = [
            d.to_dict() if hasattr(d, 'to_dict') else d for d in dispositions
        ]

    def set_stability(self, result) -> None:
        """Set stability test results."""
        self._stability = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_gate2_trace(self, modality: str, rule_trace: list[dict], final_outcome: str) -> None:
        """Set gate2 rule evaluation trace."""
        self._gate2_trace = {
            "modality": modality,
            "rule_trace": rule_trace,
            "final_outcome": final_outcome,
        }

    def set_stage_integrity(self, required: list[str], order: list[str], fatal: list[str]) -> None:
        """Set stage integrity tracking (DOD §3.4)."""
        order_valid, order_violations = _validate_stage_order(order)
        if not order_valid:
            self.add_violation("STAGE-ORDER", "ERROR", "; ".join(order_violations))
        self._stage_integrity = {
            "required_stages": required,
            "execution_order": order,
            "fatal_failures": fatal,
            "all_required_present": all(s in order for s in required),
            "order_valid": order_valid,
            "order_violations": order_violations,
            "fatal": len(fatal) > 0 or not order_valid,
        }

    def set_residue_verification(self, data: dict) -> None:
        """Set residue verification results."""
        self._residue_verification = data

    def set_analysis_map(self, entries: list) -> None:
        """Set analysis map entries (ANALYSIS mode)."""
        if not isinstance(entries, dict):
            raise ValueError("analysis_map must be an object")
        if entries.get("header") != "EXPLORATORY MAP — NOT A DECISION":
            raise ValueError("analysis_map.header must match DOD header")
        if not isinstance(entries.get("dimensions"), dict):
            raise ValueError("analysis_map.dimensions must be an object")
        if not isinstance(entries.get("hypothesis_ledger"), list):
            raise ValueError("analysis_map.hypothesis_ledger must be a list")
        if not isinstance(entries.get("total_argument_count"), int):
            raise ValueError("analysis_map.total_argument_count must be an int")
        if not isinstance(entries.get("dimension_coverage_score"), (int, float)):
            raise ValueError("analysis_map.dimension_coverage_score must be numeric")

        for dim_id, dim_data in entries["dimensions"].items():
            if not isinstance(dim_data, dict):
                raise ValueError(f"analysis_map dimension {dim_id} must be an object")
            for field in ("knowns", "inferred", "unknowns", "evidence_for", "evidence_against", "competing_lenses"):
                if not isinstance(dim_data.get(field), list):
                    raise ValueError(f"analysis_map dimension {dim_id}.{field} must be a list")
            if not isinstance(dim_data.get("argument_count"), int):
                raise ValueError(f"analysis_map dimension {dim_id}.argument_count must be an int")

        for idx, hypothesis in enumerate(entries["hypothesis_ledger"]):
            if not isinstance(hypothesis, dict):
                raise ValueError(f"analysis_map hypothesis {idx} must be an object")
            for field in ("hypothesis_id", "dimension_id", "text", "status"):
                value = hypothesis.get(field)
                if not isinstance(value, str) or not value:
                    raise ValueError(f"analysis_map hypothesis {idx}.{field} must be a non-empty string")
            if not isinstance(hypothesis.get("evidence_refs", []), list):
                raise ValueError(f"analysis_map hypothesis {idx}.evidence_refs must be a list")

        self._analysis_map = entries

    def set_analysis_debug(self, data: dict) -> None:
        """Set analysis debug data."""
        self._analysis_debug = data

    def set_diagnostics(self, data: dict) -> None:
        """Set diagnostics data."""
        self._diagnostics = data

    def build(self) -> dict:
        """Build the complete proof.json dict."""
        blocker_list = []
        blocker_summary = {"total_blockers": 0, "by_status": {}, "by_kind": {}, "open_at_end": 0}
        if self._blocker_ledger:
            for b in self._blocker_ledger.blockers:
                serialized_history = []
                for entry in b.status_history:
                    status = entry.get("status")
                    serialized_history.append({
                        **entry,
                        "status": _serialize_blocker_status(status) if status else status,
                    })
                blocker_list.append({
                    "blocker_id": b.blocker_id,
                    "type": b.kind.value,  # DOD §19: "type" not "kind"
                    "severity": b.severity,
                    "source_dimension": b.source,
                    "detected_round": b.detected_round,
                    "status": _serialize_blocker_status(b.status.value),
                    "status_history": serialized_history,
                    "models_involved": b.models_involved,
                    "linked_ids": b.evidence_ids,  # DOD §19: "linked_ids" not "evidence_ids"
                    "detail": b.detail,
                    "resolution_summary": b.resolution_note,  # DOD §19: "resolution_summary"
                })
            blocker_summary = self._blocker_ledger.summary()
            if blocker_summary.get("by_status"):
                by_status = {}
                for status, count in blocker_summary["by_status"].items():
                    serialized = _serialize_blocker_status(status)
                    by_status[serialized] = by_status.get(serialized, 0) + count
                blocker_summary = {**blocker_summary, "by_status": by_status}

        proof = {
            # --- DOD §19 canonical keys ---
            "proof_version": "3.0",
            "run_id": self._run_id,
            "timestamp_started": self._timestamp_started,
            "timestamp_completed": self._timestamp_completed or datetime.now(timezone.utc).isoformat(),
            "topology": self._topology,
            "outcome": self._outcome,
            "error_class": self._error_class,
            "stage_integrity": self._stage_integrity,
            "config_snapshot": self._config_snapshot,
            "preflight": self._preflight,
            "budgeting": self._budgeting,
            "dimensions": self._dimensions,
            "perspective_cards": self._perspective_cards,
            "rounds": self._rounds,
            "divergence": self._divergence,
            "search_log": self._search_log,
            "ungrounded_stats": self._ungrounded_stats,
            "evidence": {
                "active_working_set": self._evidence_active,
                "archive": self._evidence_archive,
                "eviction_log": self._eviction_log,
                "active_count": len(self._evidence_active),
                "archive_count": len(self._evidence_archive),
                "high_authority_evidence_present": any(
                    e.get("authority_tier") in ("HIGH", "AUTHORITATIVE")
                    for e in (self._evidence_active + self._evidence_archive)
                ) if (self._evidence_active or self._evidence_archive) else False,
            },
            "arguments": self._arguments or {},
            "blockers": blocker_list,
            "decisive_claims": self._decisive_claims or [],
            "cross_domain_analogies": self._cross_domain_analogies or [],
            "contradictions": {
                "numeric_records": self._contradictions_numeric,
                "semantic_records": self._contradictions_semantic,
                "semantic_pass_executed": getattr(self, '_semantic_pass_executed', False),
            },
            "synthesis_packet": self._synthesis_packet,
            "synthesis_output": {
                **(self._synthesis_output or {}),
                "dispositions": self._synthesis_dispositions or [],
            },
            "residue_verification": self._residue_verification,
            "positions": self._positions,
            "stability": self._stability,
            "analysis_map": self._analysis_map or [],
            "analysis_debug": self._analysis_debug,
            "diagnostics": self._diagnostics or {},
            "gate2": self._gate2_trace,
            # --- Extended fields (not in DOD §19 but useful) ---
            "protocol_version": "v9",
            "rounds_requested": self._rounds_requested,
            "final_status": self._final_status,
            "synthesis_status": self._synthesis_status,
            "acceptance_status": self._acceptance_status,
            "search_decision": self._search_decision,
            "v3_outcome_class": self._v3_outcome_class,
            "evidence_items": self._evidence_items,
            "research_phases": self._research_phases,
            "position_changes": self._position_changes,
            "blocker_summary": blocker_summary,
            "invariant_violations": self._invariant_violations,
            "synthesis_residue_omissions": self._synthesis_residue_omissions,
        }
        return proof
