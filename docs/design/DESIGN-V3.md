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
