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
| D11 | All E2E tests pass | DONE | 103 tests pass |
| -- | Zero-tolerance error handling | DONE | `BrainError` on any LLM/extraction failure. Pipeline halts. |
| -- | Search working (Bing free + Brave fallback + Sonar repeat) | DONE | Bing via curl_cffi primary ($0), Brave fallback, Sonar for repeats |
| -- | Per-framework position extraction | DONE | model/FRAMEWORK: POSITION [CONF] format, framework-level agreement |
| -- | Position validation against known models | DONE | Only MODEL_REGISTRY names accepted, no spurious positions |
| -- | Checkpoint/resume system | DONE | Full state save/restore, stage-level granularity |
| -- | Step-by-step default mode | DONE | `--full-run` to override, TTY check for non-interactive |

### NOT DONE — Features to Build

| # | Criterion | What's needed | Parent DoD |
|---|-----------|---------------|------------|
| V8-F1 | Post-synthesis residue verification | After synthesis, scan report for BLK IDs, CTR IDs, and argument IDs. Verify synthesis addressed all structural findings. Add `synthesis_residue_omissions` to proof. | D7 |
| V8-F2 | acceptance_status in proof | Add `acceptance_status` field to proof.json: ACCEPTED (clean) or ACCEPTED_WITH_WARNINGS (non-fatal issues like 0 evidence). Computed from run metrics after Gate 2. | D10 |
| V8-F3 | Evidence priority scoring | Current V8 uses FIFO cap (first items kept, later rejected). Should evaluate incoming evidence relevance and evict lower-quality items under cap pressure. | D2 |
| V8-F4 | Full page content fetch | V8 spec Section 6 says "models get real articles, not snippets." Bing returns URLs without snippets. Need httpx fetch of top result pages to get full content for evidence. | Spec §6 |
| V8-F5 | LLM-based evidence extraction | V8 spec Section 6: "LLM extracts relevant facts from full pages." Currently evidence uses raw snippets. Need Sonnet call to extract facts from fetched page content. | Spec §6 |
| V8-F6 | Invariant validator | Run validation checks on proof before output. Check: all positions extracted, all rounds have responses, evidence IDs consistent, no orphaned references. Add violations to proof. | Spec §4 |

### NOT DONE — Bug Fixes (from Daedalus audit, validated)

| # | Issue | Fix |
|---|-------|-----|
| V8-B1 | Bing search returns URLs without titles/snippets | Parse `<cite>` tags and surrounding text for titles. Or fetch pages via httpx for content. Tied to V8-F4. |
| V8-B2 | Checkpoint schema not versioned | Add `checkpoint_version` field to PipelineState. On load, validate version matches current code. |
| V8-B3 | Position components lost on resume | When restoring positions from checkpoint, `components` list only has `[option]`. Per-framework components should be stored and restored. |
| V8-B4 | 9 modules with zero test coverage | checkpoint, debug, pipeline, brave_search, sonar_search, bing_search, blocker, cross_domain, playwright_search. Add at least 1 test per module for regression safety. |

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
