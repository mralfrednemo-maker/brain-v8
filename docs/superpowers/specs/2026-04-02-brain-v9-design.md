# Brain V9 Implementation Spec

**Date:** 2026-04-02
**Source:** DESIGN-V3.md + DOD-V3.md (confirmed via two-pass multi-platform deliberation)
**Baseline:** GitHub commit `07d6628` (Brain V8, 218 tests, proof schema 2.0)
**Target:** Full DOD-V3.0 implementation, proof schema 3.0

---

## 1. Scope

Evolve Brain V8 into Brain V9 by implementing DESIGN-V3.md against the clean GitHub baseline. All uncommitted v2.1 work is ignored — this is a clean implementation from the committed codebase.

## 2. Hard Constraints

- **Zero tolerance**: any failure = BrainError, stop, fix. No degraded mode, no partial results.
- **No budgets**: thinking models get 30k tokens, 720s. Non-thinking get 8k-16k. No enforcement.
- **Fixed topology**: 4->3->2->2 always, regardless of effort tier or modality.
- **Gate 2 deterministic**: no LLM calls in Gate 2.
- **Step-by-step default**: debug_step pauses at every stage. Every stage checkpointable/resumable.
- **Bing Playwright headful**: no fallback search provider.

## 3. LLM Roster (unchanged from V8)

| Model | Code Name | Provider | API | Role | Tokens | Timeout |
|---|---|---|---|---|---|---|
| DeepSeek R1 | `r1` | OpenRouter | OpenAI-compat | R1-R4 deliberation | 30k | 720s |
| DeepSeek Reasoner | `reasoner` | DeepSeek direct | OpenAI-compat | R1-R4 deliberation | 30k | 720s |
| GLM-5 Turbo | `glm5` | Z.AI direct | OpenAI-compat | R1-R2 deliberation | 16k | 480s |
| Kimi K2 | `kimi` | OpenRouter | OpenAI-compat | R1 + adversarial | 16k | 480s |
| Claude Sonnet 4.6 | `sonnet` | Anthropic OAuth | Messages API | All Sonnet stages | 16k | 300s |

## 4. Pipeline Flow (V9)

```
PreflightAssessment → [NEED_MORE exit] → DimensionSeeder →
R1(4)[adversarial+cards] → Args → Pos → FramingPass → UngroundedStats →
Search → Fetch → Extract →
R2(3)[frame enforcement] → Args → Pos → FrameSurvival → UngroundedStats →
Search → Fetch → Extract →
R3(2) → Args → Pos → FrameSurvival →
R4(2) → Args → Pos →
SemanticContradiction → SynthesisPacket → Synthesis →
StabilityTests → Gate2[D1-D14 or A1-A7] → Invariants → Residue
```

Each stage gets a `@pipeline_stage` decorator for the auto-generated HTML run report.
Each stage gets a checkpoint stage ID for pause/resume.

## 5. New Modules (7)

### 5.1 preflight.py (DoD Section 4)
- Replaces gate1.py. Single Sonnet call.
- Output: PreflightResult with typed schema (answerability, question_class, stakes_class, effort_tier, modality, premise_flags[], hidden_context_gaps[], critical_assumptions[], search_scope, exploration_required, short_circuit_allowed, fatal_premise).
- Defect routing: REQUESTER_FIXABLE→NEED_MORE, MANAGEABLE_UNKNOWN→inject+blocker, FRAMING_DEFECT→inject reframe, FATAL_PREMISE→NEED_MORE.
- INVALID_FORM → NEED_MORE, never ERROR.
- Parse failure → BrainError.

### 5.2 dimension_seeder.py (DoD Section 6)
- Pre-R1 Sonnet call generating 3-5 mandatory dimensions.
- Output: DimensionSeedResult with items[], dimension_count, coverage tracking.
- < 3 dimensions → BrainError.
- Dimensions injected into all R1 prompts.

### 5.3 perspective_cards.py (DoD Section 7)
- Parses R1 model outputs to extract 5 structured fields per model.
- Fields: primary_frame, hidden_assumption_attacked, stakeholder_lens, time_horizon, failure_mode.
- Coverage obligations: CONTRARIAN (kimi), MECHANISM_ANALYSIS, OPERATIONAL_RISK, OBJECTIVE_REFRAMING.
- Missing card or field → BrainError.

### 5.4 divergent_framing.py (DoD Section 8)
- Framing pass: Sonnet extracts alt frames from R1 outputs.
- Frame types: INVERSION, OBJECTIVE_REWRITE, PREMISE_CHALLENGE, CROSS_DOMAIN_ANALOGY, OPPOSITE_STANCE, REMOVE_PROBLEM.
- Frame survival: 3-vote R2 drop (traceable), CONTESTED in R3/R4 (never dropped).
- R2 frame enforcement: each model must adopt one, rebut one, generate one.
- Exploration stress trigger: R1 agreement > 0.75 on OPEN/HIGH → inject seed frames.

### 5.5 semantic_contradiction.py (DoD Section 12)
- Sonnet-based contradiction pass on shortlisted evidence pairs.
- Shortlist criteria: same topic cluster + (opposite polarity OR same entity+timeframe) + linked to claim/blocker/contradiction.
- Produces structured CTR records. Complements existing numeric detector.

### 5.6 stability.py (DoD Section 15)
- Deterministic computation (no LLM).
- Three booleans: conclusion_stable, reason_stable, assumption_stable.
- Plus: fast_consensus_observed, groupthink_warning, independent_evidence_present.

### 5.7 analysis_mode.py (DoD Section 18)
- Modified round prompts (exploration, not convergence).
- Frame survival: EXPLORED/NOTED/UNEXPLORED (no dropping).
- Analysis map schema per dimension.
- Hypothesis ledger.
- DEBUG flag with counter-based sunset.
- Staged with A1-A7 Gate 2 rules.

## 6. Modified Existing Modules (9)

### 6.1 types.py
- Outcome: add NO_CONSENSUS, ERROR, ANALYSIS. Keep NEED_MORE.
- Remove ACCEPTED_WITH_WARNINGS.
- New enums: Modality, Answerability, SearchScope, CoverageObligation, TimeHorizon, PremiseFlagRouting, ResolutionStatus, DispositionTargetType, AnalysisFrameStatus.
- New dataclasses: PreflightResult, DimensionItem, DimensionSeedResult, PerspectiveCard, FrameInfo, DivergenceResult, SearchLogEntry, EvictionEvent, DecisiveClaim, CrossDomainAnalogy, StabilityResult, SynthesisPacket, DispositionObject, AnalysisMapEntry, HypothesisEntry.
- Existing dataclasses modified: EvidenceItem (add is_active, is_archived, authority_tier, referenced_by, topic_cluster), Argument (add resolution_status, superseded_by, dimension_id, evidence_refs), Blocker (add type COVERAGE_GAP/UNVERIFIED_CLAIM), Contradiction (add detection_mode NUMERIC/SEMANTIC, structured fields), Gate2Assessment (add modality, rule_trace), BrainResult (add all new result objects).

### 6.2 evidence.py — Two-Tier Ledger (DoD Section 10)
- Split into active_working_set (capped 10) + archive (uncapped).
- Eviction moves to archive, never deletes.
- eviction_log[] tracks all movements.
- high_authority_evidence_present flag.
- Evidence referenced by contradiction/blocker/claim always available.

### 6.3 rounds.py (DoD Sections 7, 8)
- R1: adversarial preamble for kimi, dimension injection, perspective card extraction instructions.
- R2: frame injection (active/contested frames), frame enforcement instructions (adopt/rebut/generate).
- R2+: alt_frames_text added to prompts.
- Search request section unchanged.

### 6.4 proof.py — Schema 3.0 (DoD Section 19)
- proof_version: "3.0"
- New sections: preflight, budgeting, dimensions, perspective_cards, divergence, search_log, ungrounded_stats, evidence (two-tier), arguments (map with resolution), decisive_claims, cross_domain_analogies, contradictions (numeric+semantic), synthesis_packet, synthesis_output (with dispositions), residue_verification, stability, analysis_map, analysis_debug, diagnostics, gate2 (with rule_trace), stage_integrity.

### 6.5 synthesis.py — Controller-Curated Packet (DoD Section 14)
- Synthesis receives curated state bundle, not just R4 outputs.
- Packet: final positions, argument lifecycle (max 20), frame summary, blocker summary, decisive claim bindings, contradiction summary, premise flag summary.
- Output requires structured dispositions for every open finding.
- Orphaned high-authority evidence requires explanation.

### 6.6 residue.py — Structured Verification (DoD Section 14)
- Schema validation + coverage validation replaces string matching.
- Disposition object for every: open blocker, active frame, decisive claim, contradiction.
- omission_rate > 0.20 triggers deep semantic scan.
- coverage_pass = true required.

### 6.7 gate2.py — Full Rewrite (DoD Sections 16, 17)
- DECIDE rules D1-D14, evaluated in order, first match wins.
- ANALYSIS rules A1-A7, evaluated in order, first match wins.
- rule_trace[] records every rule evaluation.
- Modality-aware: uses preflight.modality to select rule set.
- Frame drop votes do NOT affect agreement_ratio.

### 6.8 checkpoint.py
- CHECKPOINT_VERSION bump to "2.0".
- New stage IDs: preflight, dimensions, perspective_cards, framing_pass, frame_survival_r2, frame_survival_r3, ungrounded_r1, ungrounded_r2, semantic_contradiction, synthesis_packet, stability.
- New state fields for all new data objects.

### 6.9 brain.py — Orchestrator Rewiring
- Replace gate1 call with preflight call.
- Add dimension_seeder call pre-R1.
- Wire adversarial model assignment.
- Add perspective card extraction post-R1.
- Add framing pass post-R1.
- Add ungrounded stat detection post-R1, post-R2.
- Add frame survival checks post-R2, post-R3.
- Add semantic contradiction pass pre-synthesis.
- Build synthesis packet.
- Add stability computation.
- Pass all new objects to gate2.
- Wire ANALYSIS mode fork.
- Update all checkpoint/resume logic for new stages.
- Update HTML report generation for new stages.

## 7. Search Auditability (DoD Section 9)

- proof.search_log[]: query_id, query_text, provenance, issued_after_stage, pages_fetched, evidence_yield_count, query_status.
- Wire existing ungrounded stat detector: post-R1 and post-R2 on DECIDE runs.
- Post-R3 unresolved material unverified numeric claim → UNVERIFIED_CLAIM blocker.

## 8. Argument Resolution Status (DoD Section 11)

- Each argument: resolution_status (ORIGINAL/REFINED/SUPERSEDED), superseded_by link, dimension_id.
- Restatement without explicit linkage is NOT resolution.
- Open material arguments at synthesis require structured dispositions.

## 9. Testing Strategy

### Unit Tests
- Each new module gets isolated unit tests.
- Target: maintain or exceed 258 test count.

### Integration Testing (3 briefs, sequential)
1. **b1** (Security incident) — STANDARD effort, DECIDE path expected.
2. **b9** (DB migration) — OPEN question, search-heavy, DECIDE likely.
3. **b10** (LLM banking risk) — HIGH stakes, ELEVATED effort, ESCALATE likely.

Each brief runs step-by-step:
- Pause at every stage, inspect output.
- Any error → stop, fix code, resume from last good checkpoint.
- If fix is upstream of failure → restart brief from scratch.
- Brief passes only when all stages complete with zero errors.
- All 3 briefs must pass clean.

## 10. Implementation Order (Bottom-Up)

1. **Layer 1 — Types**: All new enums, dataclasses, outcome taxonomy.
2. **Layer 2 — New standalone modules**: preflight, dimension_seeder, perspective_cards, divergent_framing, semantic_contradiction, stability, analysis_mode. Each with unit tests.
3. **Layer 3 — Modified infrastructure**: evidence (two-tier), proof (schema 3.0), checkpoint (new stages), search log.
4. **Layer 4 — Modified pipeline modules**: rounds (adversarial/frames/dimensions), synthesis (curated packet), residue (structured), gate2 (D1-D14/A1-A7).
5. **Layer 5 — Orchestrator**: brain.py rewiring, all stages connected, pipeline_stage decorators.
6. **Layer 6 — Integration testing**: b1, b9, b10 sequential step-by-step runs.

## 11. Files Reference

### Source documents
- `output/design-session/DESIGN-V3.md` — confirmed design
- `output/design-session/DOD-V3.md` — Definition of Done v3.0

### Validation briefs
- `tests/fixtures/briefs/b1.md` — Security incident (JWT/GDPR)
- `tests/fixtures/briefs/b9.md` — DB migration (ClickHouse/Snowflake/PG)
- `tests/fixtures/briefs/b10.md` — LLM banking risk (EU AI Act)
