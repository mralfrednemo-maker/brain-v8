# Cross-Pollination Synthesis Context

## Original Brief (4 questions)

Brain V8 is a multi-model deliberation pipeline (4 LLMs in adversarial debate). Four expansions are being designed:
1. Common sense reasoning — calibrate effort, detect flawed premises, reject trivially broken questions
2. Multi-aspect exploration — models explore multiple angles before converging
3. Gap analysis — what's missing/suboptimal in the pipeline (except round topology 4->3->2->2 which is FIXED)
4. ANALYSIS mode — new outcome for understanding-seeking questions (not decisions)

**Locked constraints:**
- Round topology FIXED: 4->3->2->2
- Outcome taxonomy: DECIDE modality (DECIDE/ESCALATE/NO_CONSENSUS), ANALYSIS modality (ANALYSIS), Universal (NEED_MORE, ERROR)
- ERROR = infrastructure only (LLM/search unavailable)

---

## PASS A: Brain V8 + ChatGPT (evaluated brief independently)

### Brain V8 Result (ESCALATE / PARTIAL_CONSENSUS, agreement 0.50)

Full deliberation: 4 models in R1, 3 in R2, 2 in R3, 2 in R4. All models responded. No search (closed review).

**Q1 — Common Sense:**
- LLMs do not exhibit common sense intrinsically; it must be produced by structured pipeline forcing functions.
- CS Audit is necessary but insufficient — detects but does not enforce.
- Dual CS Audit (two parallel Sonnet calls, disagreement → ESCALATE)
- SHORT_CIRCUIT path: effort_tier=SHORT_CIRCUIT + TRIVIAL/WELL_ESTABLISHED + LOW stakes → skip R2-R4, run targeted search, produce lightweight synthesis. Requires high-authority evidence; otherwise falls back to full deliberation.
- Strict premise resolution semantics for Gate 2 Rule 9: "resolved" requires E-ID citation or ARG-ID rebuttal reference.
- Activate Ungrounded Stat Detector in proactive search phase.
- Argument Tracker sanity-check classifier: flag arguments defying basic logic → COMMON_SENSE_VIOLATION blocker.

**Q2 — Multi-Aspect Exploration:**
- Dimension Seeder (pre-R1): one Sonnet call generates 3-5 mandatory exploration dimensions, injected into R1 prompts. Zero-coverage → COVERAGE_GAP blocker.
- R1 exploration mandate: models propose ≥2 alternative framings before stating position.
- Frame survival: R2 drop threshold raised to 3 votes. R3/R4 frames cannot be dropped (CONTESTED or ADOPTED only).
- R2 frame enforcement: each model must adopt one frame, rebut one, generate one new.
- Low-divergence seeding: if R1 agreement_ratio > 0.75, inject seed frames into R2.

**Q3 — Gap Analysis (6 gaps):**
1. Synthesis blindness: synthesis only sees R4. Fix: condensed argument lifecycle (max 20 args) passed to synthesis.
2. DC-5/V8-F3 evidence eviction: cascade eviction with 5-item floor + EVIDENCE_CONFLICT_LOST blocker conversion.
3. Search auditability: add proof.json.search_log with every query, source, pages fetched, yield count.
4. Residue verification depth: check surrounding ±150 words for semantic resolution tokens. >30% shallow → threshold_violation.
5. Semantic contradiction detection: Sonnet compares top evidence items for non-numeric conflicts → BLOCKER items.
6. Gate 1 assumption validation: surface 3-5 critical unstated assumptions. Unverifiable → NEED_MORE.

**Q4 — ANALYSIS Mode:**
- ~75-80% reuse of existing pipeline.
- Keep: Gate 1, CS Audit, R1-R4, Search, Evidence, Argument Tracker, Framing, Invariants, proof.json.
- Omit: Position Tracker, Kimi adversarial role, all Gate 2 consensus rules.
- Modify: prompts shift to "deepen exploration by dimension." Frame statuses become EXPLORED/NOTED/UNEXPLORED. Synthesis produces analysis map per dimension.
- ANALYSIS Gate 2: A1=missing CS Audit→ERROR, A2=empty evidence+search recommended→ESCALATE, A3=mandatory dimension zero args→ESCALATE, A4=total args<8→ESCALATE, A5=otherwise→ANALYSIS.
- proof.json: replace positions with analysis_map, add dimension_coverage_score.
- Staged: deploy as synthesis-prompt variant first, then formalize Gate 2 rules.

### ChatGPT Pass A Result (Advisor role)

**Q1 — Common Sense:**
- Pipeline-induced, not raw model property.
- Typed PreflightAssessment: merge Gate 1 + CS Audit into single schema (answerability, question_class, stakes_class, effort_tier, premise_flags[], hidden_context_gaps[], exploration_required, short_circuit_allowed, search_required).
- Typed defect taxonomy: Type A (requester-fixable→NEED_MORE), Type B (manageable unknowns→keep run, register blockers), Type C (framing defect→inject reframed version).
- Tighter SHORT_CIRCUIT conditions.
- Fix INVALID→ERROR taxonomy misalignment (ERROR is infrastructure only).
- Effort calibration: SHORT_CIRCUIT shrinks search budget, prohibits speculative expansion.

**Q2 — Multi-Aspect Exploration:**
- Perspective cards for R1: 4 distinct epistemic roles, not just 1 contrarian. Each gets: primary_frame, hidden_assumption_attacked, stakeholder_lens, time_horizon, failure_mode.
- Explicit breadth triggers from preflight (HIGH stakes, OPEN class, CRITICAL premise flags, fast agreement).
- Structured Aspect Map (not just list of frames): aspect_kind, materiality, testability, effect_if_true.
- Frame-scoped search: every query carries provenance (supports_claim, tests_frame, tests_blocker, fills_context_gap, checks_ungrounded_stat).

**Q3 — Gap Analysis:**
- Two-tier evidence ledger: Active Working Set (capped) + Immutable Evidence Archive (uncapped). Nothing referenced by contradiction/blocker/claim/synthesis ever physically evicted.
- ARG core lineage: canonical argument identity (ARG_CORE_###) + round instances (ARG_INST_###) + relationship types (restates, narrows, rebuts, supports, splits_into, merges_with). Status expanded: SUPPORTED, REBUTTED, PARTIALLY_RESOLVED, SUPERSEDED.
- Gate 2: add conclusion stability, reason stability, assumption stability tests.
- Controller-curated synthesis packet: final positions, decisive claims+bindings, open/resolved blockers, surviving/dropped frames, major argument lineage, contradiction summary, assumption register, why non-winning alternatives lost.
- Structured narrative obligations for residue verification (schema contract per finding).
- proof.json additions: mode, mode_reason, hidden_dependencies, query_provenance, assumption_ledger, active_evidence_set, pinned_evidence_ids, claim_records, contradiction_resolution_status, why_not_decide[]/why_decide[].
- Evidence type classification: DIRECT, ANALOGICAL, BACKGROUND.
- Cross-domain filter relaxed for analogical evidence (allowed for exploration, not decisive weight).

**Q4 — ANALYSIS Mode:**
- Shared pipeline, forked controller contract.
- Keep all deliberation infrastructure. Omit majority logic as primary.
- Expand: Aspect Ledger + Hypothesis Ledger. Coverage accounting replaces consensus accounting.
- ANALYSIS Gate 2: required aspects covered, uncertainties listed, evidence bindings present, frames preserved, evidence gaps surfaced.
- Synthesis: framing, aspect map, competing hypotheses, evidence for/against, unresolved uncertainties, what would change the map.
- Implementation: recommended priority order from most to least impactful.

---

## PASS B: ChatGPT + Gemini + Claude (three-way debate)

### Opening Positions

**ChatGPT (Pass B):**
- Q1: Forced protocol. Assumption & Framing Audit as part of CS Audit (hidden_dependencies[], decision_without_X_is_useless, mode_recommendation, search_scope_hint). CS Audit gates search/prompting strategy. INVALID→ERROR is taxonomy mismatch.
- Q2: Perspective Cards (5 fields), frame quotas (mandatory premise challenge, objective rewrite, opposite stance, remove-the-problem). Deterministic breadth triggers.
- Q3: Immutable evidence store + active_evidence_set. Claim-level contradiction (evidence-vs-evidence, model-vs-evidence, model-vs-model). Argument genealogy (parent_id, refines, rebuts, depends_on_evidence[]). Synthesis fed deterministic state bundle. Structured narrative obligations. Gate 2: admissibility primary, agreement secondary.
- Q4: Same pipeline, different contract. Aspect Ledger + Hypothesis Ledger. ANALYSIS Gate 2 with coverage checks.

**Gemini (Pass B):**
- Q1: "Premise-Reality Friction." Physicality & Logic Unit Test (Gate 1.5) — deterministic check against Violation Library. Dynamic token budgeting (TRIVIAL=2k, not 30k). R2 mandatory "Sanity Rebuttal" if premises flagged.
- Q2: Functional Hats (Optimist, Skeptic, Systems Thinker, Contrarian). Exploration Threshold — if R1 agreement=1.0 on OPEN/HIGH → Synthetic Stress Test. Cross-domain analogy injection.
- Q3: Eviction Immunity (contradiction-linked items can't be evicted). Semantic contradiction via Core Claims extraction. Residue: hard-link requirement (structural map table).
- Q4: Keep topology+search, omit agreement_ratio from Gate 2. Taxonomy of Perspectives (Schools of Thought). Confidence Heatmap per topic in proof.json.

**Claude (Pass B):**
- Q1: Pipeline property. CS Audit prescriptive (routes defects to NEED_MORE / inject-and-debate / blocker). SHORT_CIRCUIT with guardrails. Wire Ungrounded Stat Detector. INVALID→ERROR is taxonomy violation.
- Q2: Pre-R1 dimension seeding + 4 epistemic lenses. Raise frame drop to 3 votes. Freeze frames R3/R4.
- Q3: Two-tier evidence ledger (active + immutable archive). Synthesis blindness fix. Semantic contradiction. Gate 1 assumption surfacing. Argument cross-round lineage. Search auditability.
- Q4: Shared pipeline, forked controller. ~80% reuse. Agreement_ratio doesn't drive ANALYSIS. Stage implementation (synthesis variant first).

### Cross-Examination Results

**Gemini shifted:**
- Conceded REJECTED outcome — adopted NEED_MORE with fatal_premise flag instead.
- Shifted from Eviction Immunity to supporting two-tier evidence ledger.
- Accepted 3-vote threshold for R2 frame drops.
- Proposed middle ground on argument tracking: ORIGINAL/REFINED/SUPERSEDED_BY[ID] status tags instead of full genealogy.
- Held firm: frames must NOT be frozen in R3/R4 (become CONTESTED, not ACTIVE).
- Held firm: ANALYSIS Gate 2 rules must come first, not synthesis variant.

**ChatGPT shifted:**
- Accepted prescriptive CS Audit routing (Claude's strongest point).
- Accepted two-tier evidence model over pinned-evidence approach.
- Accepted dynamic token budgeting from Gemini.
- Accepted early exploration stress trigger from Gemini.
- Opposed: Violation Library as main common-sense mechanism (too narrow).
- Opposed: Personality-style "hats" (prefer concrete coverage obligations).
- Opposed: 3-vote frame drop and frame freezing (prefers strengthened justification standard).
- Ranked: Claude's controller-first corrections > Gemini's operational additions.

**Claude shifted:**
- Shifted from frame freezing to Gemini's CONTESTED compromise for R3/R4.

### Full Agreement Across All Three (Pass B)

- Common sense is a pipeline property, not a model property
- CS Audit INVALID→ERROR violates locked taxonomy
- CS Audit must become prescriptive (route defects, not just classify)
- Wire Ungrounded Stat Detector
- DC-5/V8-F3 evidence eviction must be fixed
- Semantic contradiction detection needed beyond numeric
- Synthesis blindness is a structural flaw
- Residue verification needs depth beyond string matching
- ANALYSIS reuses ~80% with forked controller contract
- ANALYSIS: agreement_ratio does not drive outcomes
- R1 needs structural de-homogenization
- Fast R1 consensus on OPEN/HIGH should trigger exploration stress test
- Search needs provenance tracking

---

## DISAGREEMENTS REQUIRING RESOLUTION

1. **Evidence eviction fix:** Two-tier ledger (ChatGPT+Claude+Gemini converged) vs Cascade eviction (Brain V8)
2. **R1 breadth mechanism:** Perspective Cards (ChatGPT) vs Functional Hats (Gemini) vs Dimension Seeder (Brain V8+Claude). Note: Cards and Seeder can coexist.
3. **Frame survival R3/R4:** Keep current 2-vote (ChatGPT) vs CONTESTED not dropped (Gemini+Claude) vs Frozen ACTIVE (Claude original)
4. **Argument tracking depth:** Full genealogy (ChatGPT) vs Resolution status tags ORIGINAL/REFINED/SUPERSEDED (Gemini) vs Keep current (Brain V8)
5. **ANALYSIS staging:** Synthesis variant first (Claude) vs Gate 2 rules first (Gemini) vs Gate 2 rules with DEBUG flag (Claude's revised)
6. **Gate 1 + CS Audit structure:** Merge into one PreflightAssessment (ChatGPT) vs Keep separate + dual audit (Brain V8)
7. **Gate 2 enhancements:** Add reason/assumption stability tests (ChatGPT) vs Current structure sufficient (Brain V8)

---

## YOUR TASK

You are Claude (Opus, high effort). Produce a cross-pollination synthesis — ONE recommendation per question. Rules:
- Do NOT introduce any new points. Only use material from Pass A and Pass B above.
- For each disagreement, pick one option and state why.
- Be specific and actionable — this becomes the design document.
- Respect locked constraints (topology 4->3->2->2, outcome taxonomy, ERROR=infrastructure only).
