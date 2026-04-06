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

## DESIGN-V3.0B.md (complete text)

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

## DOD-V3.md (for reference only — not for action in this phase)

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

## DOD-V3.0B.md (for reference only — not for action in this phase)

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
