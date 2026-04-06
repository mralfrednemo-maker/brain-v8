# DoD v3.0 — Cross-Pollination Synthesis Context (Unbiased)

## Original Brief Summary

Write DoD v3.0 for Brain V8 from scratch based on confirmed DESIGN-V3.md. For every mechanism: testable acceptance criteria, Gate 2 rules, proof.json schema, failure modes. Self-contained. Gate 2 fully deterministic. ERROR = infrastructure + fatal integrity only.

Locked: topology 4→3→2→2, outcome taxonomy (DECIDE/ESCALATE/NO_CONSENSUS + ANALYSIS + NEED_MORE/ERROR).

---

## PASS A RESULTS

### Brain V8 (ESCALATE / PARTIAL_CONSENSUS)

Full deliberation: 4 models R1, 3 R2, 2 R3, 2 R4. All responded. No search (closed review).

Key findings:
1. All 20 locked mechanisms fully specifiable within self-contained DoD
2. Gate 2 DECIDE: 14 ordered rules. Ordering: integrity → answerability → SHORT_CIRCUIT evidence → blockers → contradictions → agreement → stability → content → DECIDE
3. ANALYSIS Gate 2: 5 rules (A1-A5, coverage-based)
4. proof.json expands to ~50+ required fields
5. Four resolved ambiguities:
   - Exploration stress trigger = union (OPEN OR HIGH), not intersection
   - SHORT_CIRCUIT: zero evidence OK only when search_scope=NONE
   - Dimension Seeder <3 = ERROR
   - Add PREFLIGHT_DIRECTED search provenance type
6. DEBUG sunset: ~100 runs with <5% misclassifications
7. ESCALATE rate increase ~35% is intentional, not defect
8. proof.json v3.0 not backward compatible — needs proof_version field
9. ~40% token cost increase from new Sonnet calls

### ChatGPT Pass A

Full 22-section DoD draft with:
- 15 DECIDE rules (D1-D15) — slightly different ordering from Brain V8's 14
- 5 ANALYSIS rules (A1-A5)
- Complete proof.json field tables per section
- Failure mode matrix
- Test suite (~30 tests)
- Key schema decisions: one schema two branches, stable IDs everywhere, archive is authoritative

---

## PASS B: Three-Way Debate (ChatGPT + Gemini + Claude)

### ChatGPT Opening Position
- DECIDE Gate 2: 14 ordered rules with explicit modality mismatch → ERROR and illegal SHORT_CIRCUIT → ERROR as distinct integrity rules
- Two-band agreement: <0.50 → NO_CONSENSUS, 0.50-0.75 → ESCALATE
- Found 9 ambiguities in DESIGN-V3.md (INVALID_FORM routing, material hidden-context gap definition, material frame mechanical test, R2 frame enforcement proof shape, shortlisted pairs criteria, dimension irrelevance counting, remaining models in stability tests, ANALYSIS frame tracking without adversarial, SHORT_CIRCUIT evidence floor)
- Added query_status enum (SUCCESS/ZERO_RESULT/FAILED/SKIPPED) to search log
- Added gate2.rule_trace[] for auditability
- Insisted SUPERSEDED_BY[ID] must be split into enum + pointer
- Synthesis_packet as first-class proof object
- Gate 2 should prioritize admissibility over agreement_ratio
- ANALYSIS coverage score operationalized with threshold (initially proposed 0.67)

### Gemini Opening Position
- DECIDE Gate 2: 10 rules. Key differences: "Fatal Premise → NEED_MORE" as rule 3 inside Gate 2. agreement_ratio < 0.75 → NO_CONSENSUS (single band, not split). Numeric stability thresholds: conclusion_drift > 0.2 → NO_CONSENSUS, reasoning_drift > 0.3 → ESCALATE (Jaccard Distance on claim/evidence sets).
- ANALYSIS Gate 2: 6 rules. dimension_coverage_score >= 0.8 as success threshold (later changed to 1.0 in cross-exam)
- Only 3 ambiguities identified (rebuttal definition, SHORT_CIRCUIT evidence minimums, synthesis disposition schema)
- Proposed unified argument_store as object map keyed by ARG-ID
- Added "Consensus Trap" failure mode (stress triggered + all frames DROPPED → ESCALATE)
- Added "Orphaned Evidence" requirement (high-relevance uncited evidence must be explained)

### Claude Opening Position
- Agreed with 14 DECIDE rules
- Agreed with Brain V8's 4 ambiguity resolutions
- Added: proof_version field, DEBUG sunset condition in DoD
- Stability tests should be boolean for v3.0, not numeric drift
- DoD should specify WHAT not HOW for computation methods

### Cross-Examination Results

**Gemini conceded:**
- Two-band agreement split (<0.50 NO_CONSENSUS, 0.50-0.75 ESCALATE)
- gate2.rule_trace[] requirement
- Schema purity (split enum from pointer)
- query_status field for search log

**Gemini held firm:**
- Stability tests need numeric thresholds (Jaccard Distance), not just booleans
- Mandatory dimensions must have 1.0 coverage in ANALYSIS (later modified: accepts MODEL_INFERENCE basis as valid argument)

**ChatGPT final updates:**
- Adopted dimension_coverage_score >= 0.8 (shifted from 0.67)
- Adopted immutable_archive.size = 0 (precise, not generic)
- Adopted authoritative ARG-ID object map
- Adopted proof_version + DEBUG sunset
- Adopted orphaned evidence explanation obligation
- Rejected PREFLIGHT_DIRECTED (premise_defect covers it)
- Rejected numeric drift thresholds (boolean gates sufficient)
- Held: NEED_MORE is Preflight-only; zero-evidence SHORT_CIRCUIT forbidden when search recommended

**Gemini final updates:**
- Proposed material frame = linked to Seeder OR ≥2 R2 adoptions
- Proposed deterministic drift: Jaccard Distance between R3/R4 claim/evidence sets (conclusion >0.2 → NO_CONSENSUS, reasoning >0.3 → ESCALATE)
- Accepted proof_version + DEBUG sunset
- Accepted query_status enum

---

## DISAGREEMENTS REQUIRING YOUR RESOLUTION

These are OPEN. You must pick one option for each and explain why.

### 1. Stability test format
- **Option A (ChatGPT + Claude):** Boolean gates (conclusion_stable, reason_stable, assumption_stable as true/false). Computation method deferred to implementation spec.
- **Option B (Gemini):** Numeric drift thresholds using Jaccard Distance on R3/R4 claim/evidence sets. conclusion_drift > 0.2 → NO_CONSENSUS, reasoning_drift > 0.3 → ESCALATE. Fully specified in DoD.

### 2. ANALYSIS dimension coverage threshold
- **Option A (ChatGPT + Claude):** 0.8 floor, permissive if all mandatory dimensions have some arguments (justified irrelevance counts as covered)
- **Option B (Gemini):** 1.0 required for mandatory dimensions. If dimension has zero searchable evidence, model must produce argument tagged basis: MODEL_INFERENCE.

### 3. DECIDE Gate 2 rule count and ordering
- **Option A (Brain V8 + ChatGPT + Claude):** 14 rules. Integrity → modality mismatch → SHORT_CIRCUIT integrity → agreement bands → blockers → evidence → contradictions → premises → frames → stability → groupthink → DECIDE
- **Option B (Gemini):** Different ordering. Puts Fatal Premise → NEED_MORE inside Gate 2 (vs Preflight-only). Fewer explicit integrity rules.

### 4. ANALYSIS Gate 2 rule count
- **Option A (Brain V8 design):** 5 rules (A1-A5): missing preflight → ERROR, empty evidence → ESCALATE, zero-arg dimension → ESCALATE, total args <8 → ESCALATE, otherwise → ANALYSIS
- **Option B (ChatGPT + Claude):** 7 rules (A1-A7): adds modality mismatch → ERROR, missing artifacts → ERROR before the coverage rules
- **Option C (Gemini):** 7 rules but different ordering, includes coverage score as hard gate

### 5. PREFLIGHT_DIRECTED search provenance
- **Option A (Brain V8):** Add it as a new provenance enum value
- **Option B (ChatGPT):** Drop it — premise_defect already covers preflight-originated searches

### 6. SHORT_CIRCUIT zero-evidence policy
- **Option A (Brain V8):** Zero evidence OK only when search_scope=NONE
- **Option B (ChatGPT):** Zero evidence OK only when search_scope=NONE AND question_class=TRIVIAL. Stricter.

### 7. NEED_MORE inside Gate 2
- **Option A (ChatGPT + Claude):** NEED_MORE belongs to Preflight only. Gate 2 never emits NEED_MORE.
- **Option B (Gemini):** Gate 2 can emit NEED_MORE for fatal premise detection that wasn't caught by Preflight.

### 8. Orphaned evidence requirement
- **Option A (ChatGPT + Gemini):** If high-relevance archive evidence is uncited, synthesis MUST explain why. Failure blocks DECIDE/ANALYSIS.
- **Option B (not proposed):** Orphaned evidence is logged but doesn't block outcomes.

### 9. Material frame mechanical test
- **Option A (Gemini, adopted by ChatGPT):** Frame is material if linked to Dimension Seeder output OR adopted by ≥2 R2 models
- **Option B (no explicit alternative proposed):** Material = qualitative judgment by synthesis

### 10. Argument store structure
- **Option A (all three):** Authoritative object map keyed by ARG-ID with split resolution_status enum + superseded_by pointer
- **Option B (current v2.1):** Round-local arrays with string-encoded status

---

## YOUR TASK

Produce a cross-pollination synthesis — a complete DoD v3.0 document. Rules:
- Do NOT introduce any new points. Only use material from Pass A and Pass B above.
- For each of the 10 disagreements, pick one option and state why.
- Be specific and actionable — numbered sections, ordered Gate 2 rules, proof.json field tables, failure mode matrices, test suite.
- Respect locked constraints (topology, taxonomy, ERROR definition).
