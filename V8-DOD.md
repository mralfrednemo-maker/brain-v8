# Thinker V8 Brain — Definition of Done

**Date:** 2026-03-29
**Scope:** Brain engine only (Chamber and Mission Controller come later)
**Parent DoD:** `_audit_thinker/THINKER-DOD-AND-PLAN.md`
**Philosophy:** Zero tolerance. No budgets. Works fully or ERROR.

---

## V8 DoD Checklist

Mapped from parent DoD (D1-D11, P1-P10) to V8 Brain scope.

### DONE (verified this session)

| # | Criterion | Status | How |
|---|-----------|--------|-----|
| D1 | No secrets in source code | DONE | All keys in `.env`, gitignored |
| D3 | Contradiction detection no false positives | DONE | Keyword threshold + stopword filter in `contradiction.py` |
| D4 | Argument tracking across rounds | DONE | Argument Tracker (extract → compare → re-inject). Replaces minority archive. Cumulative `all_unaddressed`. Round-prefixed IDs (R1-ARG-1). |
| D9 | proof.json always populated | DONE | Proof written on every complete run |
| D11 | All E2E tests pass | DONE | 211 tests pass (was 103) |
| -- | Zero-tolerance error handling | DONE | `BrainError` on any LLM/extraction failure. Pipeline halts. |
| -- | Search working (Bing free + Brave fallback + Sonar repeat) | DONE | Bing via curl_cffi primary ($0), Brave fallback, Sonar for repeats |
| -- | Per-framework position extraction | DONE | model/FRAMEWORK: POSITION [CONF] format, framework-level agreement |
| -- | Position validation against known models | DONE | Only MODEL_REGISTRY names accepted, no spurious positions |
| -- | Checkpoint/resume system | DONE | Full state save/restore, stage-level granularity |
| -- | Step-by-step default mode | DONE | `--full-run` to override, TTY check for non-interactive |

### DONE — Features (completed 2026-03-29)

| # | Criterion | How | Parent DoD |
|---|-----------|-----|------------|
| V8-F1 | Post-synthesis residue verification | `thinker/residue.py` — scans report for BLK/CTR/ARG IDs, flags >30% omission threshold. `synthesis_residue_omissions` added to proof.json. 8 tests. | D7 |
| V8-F2 | acceptance_status in proof | `AcceptanceStatus` enum in types.py. `compute_acceptance_status()` on ProofBuilder. ACCEPTED (clean) or ACCEPTED_WITH_WARNINGS. 5 tests. | D10 |
| V8-F3 | Evidence priority scoring | `score_evidence()` in evidence.py — keyword overlap + authority domain scoring. Under cap pressure, lowest-scored item evicted. FIFO preserved within same score. 7 tests. | D2 |
| V8-F4 | Full page content fetch | `thinker/page_fetch.py` — httpx fetch, HTML stripping, 50k char truncation. Populates `SearchResult.full_content`. 11 tests. | Spec §6 |
| V8-F5 | LLM-based evidence extraction | `thinker/evidence_extractor.py` — Sonnet call per page, parses FACT-N structured output. 11 tests. | Spec §6 |
| V8-F6 | Invariant validator | `thinker/invariant.py` — checks positions/rounds/evidence IDs/orphaned BLK+CTR refs. Returns violations with WARN/ERROR severity. 7 tests. | Spec §4 |

### DONE — Bug Fixes (completed 2026-03-29)

| # | Issue | Fix |
|---|-------|-----|
| V8-B1 | Bing search returns URLs without titles/snippets | Fixed by V8-F4 — page fetch provides content. Title auto-filled from page text when missing. |
| V8-B2 | Checkpoint schema not versioned | `CHECKPOINT_VERSION = "1.0"` constant. `PipelineState.load()` raises `ValueError` on mismatch. 4 tests. |
| V8-B3 | Position components lost on resume | Checkpoint now stores `components` list and `kind` field. Restore uses full components instead of `[option]`. 2 tests. |
| V8-B4 | 9 modules with zero test coverage | Added tests for: checkpoint (12), debug (9), pipeline (4), blocker (9), cross_domain (13), bing_search (5), brave_search (3), sonar_search (2). Total: 211 tests (was 103). |

### NOT APPLICABLE to V8 Brain (deferred to Chamber/Mission Controller)

| # | Criterion | Why |
|---|-----------|-----|
| D5 | Controller/synthesis mismatch ERROR | No Mission Controller yet |
| D6 | Mission inspects Brain invariants | No Mission Controller yet |
| D8 | Chamber proof artifact | Chamber not built yet |
| P1 | Mission controller test coverage | Not built yet |
| P4 | Chamber search parity | Chamber not built yet |

---

## Design Constraints (non-negotiable)

1. **Zero tolerance.** Any failure → BrainError → pipeline stops. No degraded mode.
2. **No budgets.** No wall clock limits, no token limits. Generous timeouts for all models.
3. **Thinking models get 30k tokens and 720s.** R1, Reasoner. Don't touch.
4. **Non-thinking models get 8k-16k tokens.** GLM-5, Kimi, Sonnet. Don't touch.
5. **Evidence FIFO cap.** Trust search engine ranking. No re-ranking. (V8-F3 would add eviction scoring but keep insertion order.)
6. **Gate 2 is deterministic.** No LLM call. Pure threshold computation. (Note: V8 spec §4 originally said LLM judgment — we chose deterministic. This is a deliberate simplification for V8.)
7. **Step-by-step is default.** `--full-run` to override.
