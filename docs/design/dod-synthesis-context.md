# DoD v3.0 — Cross-Pollination Synthesis Context

## Original Brief Summary

Write DoD v3.0 for Brain V8 from scratch based on confirmed DESIGN-V3.md. For every mechanism: testable acceptance criteria, Gate 2 rules, proof.json schema, failure modes. Self-contained. Gate 2 fully deterministic. ERROR = infrastructure + fatal integrity only.

Locked: topology 4→3→2→2, outcome taxonomy (DECIDE/ESCALATE/NO_CONSENSUS + ANALYSIS + NEED_MORE/ERROR).

---

## PASS A RESULTS

### Brain V8 (ESCALATE / PARTIAL_CONSENSUS)

Key findings:
1. All 20 locked mechanisms fully specifiable within self-contained DoD
2. Gate 2 DECIDE: 14 ordered rules (integrity → answerability → SHORT_CIRCUIT evidence → blockers → contradictions → agreement → stability → content → DECIDE)
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
- 15 DECIDE rules (D1-D15)
- 5 ANALYSIS rules (A1-A5)
- Complete proof.json field tables per section
- Failure mode matrix
- Test suite (~30 tests)
- Key schema decisions: one schema two branches, stable IDs everywhere, archive is authoritative

---

## PASS B: Three-Way Debate (ChatGPT + Gemini + Claude)

### Full Agreement (all three)

- 14-rule DECIDE Gate 2 + separate ANALYSIS rules
- Two-band agreement: <0.50 → NO_CONSENSUS, 0.50-0.75 → ESCALATE
- NEED_MORE belongs to Preflight only, not Gate 2
- ERROR = infrastructure + fatal integrity only
- gate2.rule_trace[] required for auditability
- query_status enum (SUCCESS/ZERO_RESULT/FAILED/SKIPPED) in search log
- Schema purity: split resolution_status enum from superseded_by pointer
- Authoritative argument store as object map keyed by ARG-ID
- Archive (not active set) is evidence truth for Gate 2
- proof_version field required
- DEBUG sunset condition must be in DoD
- Synthesis must explain orphaned high-relevance evidence
- v3.0 is full rewrite with numbered sections + ordered rules + field tables + test list

### Resolved Disputes

- Agreement bands: two-band split (Gemini conceded)
- ANALYSIS coverage threshold: 0.8 (ChatGPT shifted from 0.67; Gemini wanted 1.0)
- Material frame definition: linked to Dimension Seeder output OR adopted by ≥2 R2 models
- PREFLIGHT_DIRECTED provenance: dropped (premise_defect covers it)
- INVALID_FORM outcome: always NEED_MORE, never ERROR (diagnostic label only)
- SHORT_CIRCUIT evidence: zero evidence OK only when search_scope=NONE AND question_class=TRIVIAL
- Dimension irrelevance: justified_irrelevance counts as covered if recorded; silent omission = blocker

### Remaining Disagreement: Stability Test Thresholds

- ChatGPT + Claude: boolean gates (conclusion_stable, reason_stable, assumption_stable as true/false). Computation in implementation spec, not DoD.
- Gemini: numeric thresholds (Jaccard Distance on claim/evidence sets: conclusion_drift > 0.2 → NO_CONSENSUS, reasoning_drift > 0.3 → ESCALATE)
- Resolution: boolean gates for v3.0. The DoD defines WHAT Gate 2 consumes (booleans); the implementation spec defines HOW they're computed.

### ChatGPT Final Position Updates

- Adopted dimension_coverage_score >= 0.8 for ANALYSIS
- Adopted immutable_archive.size = 0 (precise, not generic "ledger empty")
- Adopted authoritative ARG-ID object map
- Adopted proof_version + DEBUG sunset as DoD requirements
- Adopted orphaned evidence explanation obligation
- Held firm: NEED_MORE is Preflight-only; two-band agreement; no numeric drift in DoD; 9 ambiguities not 3; zero-evidence SHORT_CIRCUIT DECIDE forbidden when search was recommended

### Gemini Final Position Updates

- Conceded two-band agreement split
- Conceded gate2.rule_trace[]
- Conceded schema purity (enum + pointer)
- Conceded query_status field
- Held firm: mandatory dimensions must have 1.0 coverage (but accepts MODEL_INFERENCE basis as valid argument)
- Held firm: stability needs numeric thresholds (Jaccard Distance)
- Proposed material frame = linked to Seeder OR ≥2 R2 adoptions

---

## DECISIONS MADE IN SYNTHESIS

| # | Decision | Chosen |
|---|---|---|
| 1 | DECIDE Gate 2 | 14 ordered rules (D1-D14) |
| 2 | ANALYSIS Gate 2 | 7 rules (A1-A7) including integrity checks |
| 3 | Agreement bands | <0.50 NO_CONSENSUS, 0.50-0.75 ESCALATE |
| 4 | Stability tests | Boolean gates (not numeric drift) |
| 5 | ANALYSIS coverage | 0.8 recommended floor, but permissive if A5 passes |
| 6 | Material frame | Seeder-linked OR ≥2 R2 adoptions |
| 7 | Argument store | Object map keyed by ARG-ID |
| 8 | Evidence truth | Archive is authoritative, not active set |
| 9 | INVALID_FORM | Always NEED_MORE, never ERROR |
| 10 | SHORT_CIRCUIT evidence | Zero OK only when search_scope=NONE + TRIVIAL |
| 11 | proof_version | Required ("3.0") |
| 12 | DEBUG sunset | Counter-based, expires → ERROR |
| 13 | Orphaned evidence | Synthesis must explain non-citation |
| 14 | PREFLIGHT_DIRECTED | Dropped (premise_defect covers it) |

---

## YOUR TASK

Produce a cross-pollination synthesis — a complete DoD v3.0 document. Rules:
- Do NOT introduce any new points. Only use material from Pass A and Pass B above.
- For any remaining disagreements, pick one option and state why.
- Be specific and actionable — numbered sections, ordered Gate 2 rules, proof.json field tables, failure mode matrices, test suite.
- Respect locked constraints (topology, taxonomy, ERROR definition).
- This is a full self-contained DoD, not a summary.
