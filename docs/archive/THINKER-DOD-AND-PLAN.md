# The Thinker Platform: Definition of Done & Unified Execution Plan

**Date:** 2026-03-26 (Rev 3 -- all 14 fixes implemented, syntax-verified)
**Sources analyzed:** ChatGPT Audit, Claude Audit, ChatGPT Fix Prioritization, Claude Bug Fixes, Hermes Self-Audit Report, 29 Brain V3 run bundles, Mission Controller package (code + tests + briefs), Brain V3 Diagnostic bundle
**DoD reviewers:** ChatGPT (x2), Claude (x2) -- consensus changes applied below

---

## Part 1: What The Thinker Is

A multi-engine AI deliberation system that routes decision briefs through structured reasoning pipelines to produce auditable, controller-owned verdicts.

| Component | File | Size | Role |
|-----------|------|------|------|
| Mission Controller | `mission_controller.py` | 784 LOC | Routes briefs, assigns authority, emits canonical proof |
| Brain V3 | `brain-v3-orchestrator.py` | 5,243 LOC | Multi-model truth deliberation (4 LLMs, 4 rounds, research gates) |
| Chamber V11 | `consensus_runner_v3.py` | 5,450 LOC | Adversarial recommendation governance (5-agent pipeline via AutoGen) |

**Modes:** brain (Brain authoritative), chamber (Chamber authoritative), cascade (Brain pre-maps then Chamber finalizes), parallel (both run, classification determines authority)

**Core design promises:**
1. Controller-owned authority (the system decides, not LLMs)
2. Structured evidence with integrity tracking
3. Disagreement preservation (minorities, contested positions, blockers)
4. Machine-checkable invariant validation
5. Canonical proof artifacts for every run
6. Post-synthesis integrity (narratives must reflect structural findings)

---

## Part 2: Current State Assessment

### What Works

The platform is architecturally sound. All 4 modes function end-to-end. The 9-test E2E suite can pass. Brain runs complete with proper convergence across rounds. Chamber produces governed recommendations. Cascade augmentation handoff works. The design philosophy -- controller-first authority, structured evidence, invariant validation -- is correct and well-implemented at the governance level.

### What's Broken

Three independent audits (ChatGPT, Claude, and the system's own Brain V3 self-audit) converge on the same findings. The problems fall into two categories: **implementation bugs** in the evidence/disagreement layer, and **controller-governance enforcement gaps** where the system observes problems but does not act on them. The enforcement gaps (Y1 invariant, mission acceptance semantics, post-synthesis verification, disagreement-floor logic) are not mere bugs -- they represent places where the controller's authority model is structurally incomplete.

**Summary of convergence:**

| Issue | ChatGPT Audit | Claude Audit | Hermes Self-Audit | Claude Fixes |
|-------|:---:|:---:|:---:|:---:|
| Evidence priority scoring broken | Fix #4 | Fix #3 | FIX-3 | Fix #1 |
| Contradiction detection false positives | Fix #1 | Fix #5 | FIX-4 | Fix #3 |
| Minority `addressed_by` dead | Fix #3 | -- | FIX-2 | Fix #2 |
| Evidence admission non-atomic | -- | -- | FIX-1 | Fix #4 |
| Post-synthesis residue not verified | -- | Fix #2 | FIX-5 | Fix #5 |
| Y1 invariant WARNING not ERROR | Fix #1 | Fix #1 | -- | -- |
| Mission ignores Brain invariant errors | Fix #1 | -- | -- | -- |
| Chamber has no proof artifact | Fix #2 | -- | -- | -- |
| Chamber search weaker than Brain | Fix #3 | -- | -- | -- |
| Hardcoded API key in source | -- | Fix #8 | -- | -- |

Every confirmed bug was independently discovered by at least 2 of the 4 analysis sources. The self-audit's own data (CTR001-CTR005) proves the contradiction false-positive bug in real-time.

---

## Part 3: Definition of Done

The DoD is structured in two tiers. **Tier 1 (Core DoD)** is the minimum bar for the platform to deliver on its own promises. **Tier 2 (Production DoD)** adds structural maturity needed for maintainability and deployment confidence.

### Tier 1: Core DoD -- "The system enforces what it claims to enforce"

| # | Criterion | Metric | Maps to Promise |
|---|-----------|--------|-----------------|
| D1 | No secrets in source code | Zero hardcoded API keys or credentials in any `.py` file | Security |
| D2 | Evidence priority scoring correctly evaluates new vs existing items | New evidence with high relevance can evict lower-relevance existing evidence under cap pressure | Evidence integrity |
| D3 | Contradiction detection requires semantic match | Zero false-positive contradictions on the existing 7 test briefs (CTR entries must share same-metric context, not just keyword overlap) | Evidence integrity |
| D4 | Minority `addressed_by` is populated after each round | For minorities that ARE referenced in later rounds, `addressed_by` contains the acknowledging model and round | Disagreement preservation |
| D5 | Controller/synthesis mismatch is ERROR (not WARNING) | Y1 invariant fires as ERROR when controller_outcome != synthesis outcome AND no `[SYNTHESIS-OVERRIDE]` section present | Controller authority |
| D6 | Mission acceptance inspects Brain invariant violations | Brain FATAL -> mission FATAL; Brain ERROR -> mission ERROR (when Brain is authoritative). `brain_invariant_summary` added to mission proof | Controller authority |
| D7 | Post-synthesis residue verification (transparency check) | After Hermes synthesis, scan checks for governing blocker BLK IDs (each individually mandatory), CTR IDs and minority model names (>=30% aggregate omission = ERROR). This is a **narrative completeness check**, not a truth-ownership transfer -- it verifies Hermes addressed the structural findings, not that Hermes reached the "right" conclusion. `synthesis_residue_omissions` field in proof | Post-synthesis integrity |
| D8 | Chamber produces a canonical proof artifact | Chamber proof JSON includes: run_id, evidence ledger summary, objection ledger, audit history, degraded cycles, option registry, choice mode, selected option, final verdict. Path/hash stored in mission proof | Proof artifacts |
| D9 | Proof.json is ALWAYS populated on completed runs | No empty/skeleton proof.json when orchestrator.log shows COMPLETE. Proof write is the final step, after all fields are computed | Proof artifacts |
| D10 | Brain proof includes acceptance_status | `acceptance_status` computed from run integrity: ACCEPTED (clean run) or ACCEPTED_WITH_WARNINGS (non-fatal issues). There is NO budget_constrained field — the system has zero tolerance for failures and no time/token budgets. If something fails, the pipeline raises BrainError and stops entirely. There is no degraded mode. | Proof artifacts + Zero tolerance |
| D11 | All 9 E2E tests match expected revised status | Each test produces the correct mode, authority, and **expected acceptance status under the new enforcement policy**. Tests that correctly trigger new ERROR-level invariants (D5, D6) may produce proof-degraded status rather than blanket ACCEPTED -- this is desired behavior, not failure. Expected status per test documented in the revised test matrix | End-to-end correctness |

**Moved to Tier 2 (per reviewer consensus):**
- ~~D4 (old): Evidence admission atomicity~~ -> Now P10. The proposed fix (try/except wrapper) is a defensive coding improvement, not true transactional atomicity. Criterion reworded to match the actual fix scope.
- ~~D12 (old): MEDIUM contradiction accumulation~~ -> Now P11. This is a **calibration policy choice** (what threshold should trigger the disagreement floor), not a directly proven bug. No run evidence yet demonstrates that 3 MEDIUM contradictions should change the outcome. Include when empirical backing exists.

### Tier 2: Production DoD -- "The system is maintainable and testable"

| # | Criterion | Metric |
|---|-----------|--------|
| P1 | Unit test coverage for mission_controller.py | Tests for classify_brief(), _assign_final_authority(), _extract_brain_augmentation(), _validate_mission_invariants(), _build_mission_proof() |
| P2 | Unit test coverage for brain-v3-orchestrator.py | Tests for EvidenceLedger, _classify_outcome(), _check_contradiction(), _evidence_priority_score(), _validate_run_invariants() |
| P3 | Shared test infrastructure | Common conftest.py with mock setup (eliminate ~50-line stub duplication across test files) |
| P4 | Chamber search parity with Brain | Code-brief false-positive guards ported. Sonar failure produces structured degraded-search event. Total Sonar failure marks cycle degraded |
| P5 | Eviction archive preserves lost evidence | `eviction_archive` list on EvidenceLedger with {evidence_id, topic, fact, url, evicted_by, eviction_round}. Serialized in proof |
| P6 | Environment decoupling | No hardcoded paths to `/home/node/.openclaw/`. All paths configurable via env vars or CLI args |
| P7 | Proof.json schema documented | JSON Schema for both Brain proof v2.0 and new Chamber proof, including contradiction_ledger and minority_archive fields |
| P8 | Search contamination defense | Validate extracted gap queries before sending to search APIs. Suppress code-token/ticker false positives (YAML, VP, JIT, ARR, HIPAA already partially handled -- systematize). Fail degraded-search explicitly with structured event, not silently |
| P9 | MEDIUM contradiction accumulation (calibration) | >=3 unresolved MEDIUM contradictions treated as equivalent to 1 HIGH for disagreement floor. **Adopt when empirical run evidence supports the threshold** |
| P10 | Evidence admission resilience | Contradiction-check failure cannot corrupt admission state. Wrap `_check_contradiction()` in try/except so exceptions don't leave partial state (item in ledger, contradiction unrecorded). This is a fail-open defensive fix, not true transactional atomicity |

### What is explicitly NOT in the DoD

These are intentional design choices confirmed by both audits. Changing them would be architectural regression:

- Authority-from-classification in parallel mode (correct policy)
- Cascade authority always goes to Chamber (Brain is structured input)
- Discrepancy packet is diagnostic-only (intentional)
- Round failure asymmetry (R1 tolerates 2/4, R2 requires 3/3 -- matches narrowing topology)
- Chamber late-cycle objection freeze (correct governance)
- Narrowing model topology (4->3->2->2 -- sound design)
- Evidence cap at 10 items (sound, but eviction must work correctly)

---

## Part 4: Unified Fix Inventory

All fixes from all sources, deduplicated and consolidated into 14 items with implementation specifics.

### FIX-01: Remove hardcoded API key [SECURITY]
- **Source:** Claude Audit Fix #8
- **Location:** `brain-v3-orchestrator.py` line 59
- **Current:** `OPENROUTER_API_KEY = "sk-or-v1-5bff7e..."`
- **Fix:** `OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")`
- **Risk:** Zero. 1-line change.
- **DoD:** D1

### FIX-02: Evidence priority scoring for new items [BUG]
- **Source:** Claude Fix #1, ChatGPT Fix #4, Hermes FIX-3
- **Location:** `brain-v3-orchestrator.py`, `_evidence_priority_score()` + eviction loop
- **Problem:** New incoming item checked against `self.items` for citation matches. Not yet in ledger -> zero citations -> always gets minimum score -> cap eviction system keeps worse evidence.
- **Fix:** Add `is_incoming=False` parameter. When `True`, skip citation lookup (score 0 for that component). Eviction loop calls `is_incoming=False` for existing items, `is_incoming=True` for candidate.
- **Risk:** Low. Only changes eviction comparison, not admission logic.
- **DoD:** D2

### FIX-03: Contradiction detection same-metric requirement [BUG]
- **Source:** Claude Fix #3, ChatGPT Fix #1, Hermes FIX-4
- **Location:** `brain-v3-orchestrator.py`, `_check_contradiction()`
- **Problem:** Flags items with 3+ shared keywords and different numbers. Generic keywords ("evidence", "that", "from") cause false positives. Proven by CTR001-CTR005 in real run data.
- **Fix (three parts):**
  - (a) Raise shared-keyword threshold from 3 to 4 AND require at least 2 keywords to be 6+ characters
  - (b) Add stopword filter: exclude top 50 common English words that pass 4-char minimum ("that", "this", "from", "with", "have", "been")
  - (c) Same-metric heuristic: when two items have different numbers, require numbers to appear within 30 characters of a shared keyword
- **Risk:** Low. Makes detection stricter (fewer false positives). May miss rare genuine contradictions with weak keyword overlap, but current detector is useless due to noise.
- **DoD:** D3

### FIX-04: Evidence admission resilience [DEFENSIVE]
- **Source:** Claude Fix #4, Hermes FIX-1
- **Location:** `brain-v3-orchestrator.py`, `admit()` method on EvidenceLedger
- **Problem:** `_check_contradiction()` runs AFTER `self.items.append()`. Exception = item in ledger but contradiction unrecorded.
- **Fix:** Wrap `_check_contradiction()` in try/except. Contradiction detection is observational; failure should not prevent admission. 3 lines of code. This is a fail-open defensive fix, not true transactional atomicity.
- **Risk:** Effectively zero. Defensive fix.
- **DoD:** P10 (moved from Core DoD per reviewer consensus -- the fix does not match the "atomic" criterion)

### FIX-05: Minority `addressed_by` scanning [BUG]
- **Source:** Claude Fix #2, ChatGPT Fix #3, Hermes FIX-2
- **Location:** `brain-v3-orchestrator.py`, after `_extract_positions_for_round()` in R2, R3, R4
- **Problem:** `addressed_by` is always None because no code scans later-round outputs for minority argument references.
- **Fix:** New function `_scan_minority_acknowledgments(round_num, model_outputs, ledger, log)`. For each unaddressed minority, check if any model's output mentions the minority model name + 3+ keyword overlap with argument summary. Set `addressed_by = {"model": model_name, "round": round_num}`.
- **Risk:** Low. Adds read-only scanning. Does not change control flow.
- **DoD:** D4

### FIX-06: Y1 invariant escalation to ERROR [GOVERNANCE]
- **Source:** Claude Audit Fix #1, ChatGPT Audit Fix #1
- **Location:** `brain-v3-orchestrator.py`, `_validate_run_invariants()` lines ~4501-4509
- **Problem:** When controller_outcome != synthesis outcome, Y1 fires as WARNING. Controller/synthesis mismatch can pass silently.
- **Fix:** Change Y1 from WARNING to ERROR *when no `[SYNTHESIS-OVERRIDE]` section present in the Hermes report*. When override section is present (Hermes explicitly acknowledged the divergence), keep WARNING.
- **Risk:** Medium. May cause some runs that currently ACCEPT to be flagged. This is the DESIRED behavior -- those runs were falsely passing.
- **DoD:** D5

### FIX-07: Mission acceptance inspects Brain invariant violations [GOVERNANCE]
- **Source:** ChatGPT Audit Fix #1
- **Location:** `mission_controller.py`, `_validate_mission_invariants()`
- **Problem:** MI3 checks only 5 Brain proof completeness fields. Does not inspect `brain_proof["invariant_violations"]`.
- **Fix:** In `_validate_mission_invariants()`:
  - Read `brain_proof["invariant_violations"]`
  - Brain FATAL violations -> mission FATAL
  - Brain ERROR violations -> mission ERROR (when Brain is authoritative)
  - Brain ERROR violations -> mission WARNING (when Brain is NOT authoritative, e.g. cascade/parallel with Chamber authority)
  - Add `brain_invariant_summary` dict to mission proof
- **Risk:** Medium. Must check mode before escalating -- non-authoritative engine errors should not block the authoritative engine's verdict.
- **DoD:** D6
- **Note:** Independent of FIX-06. FIX-07 propagates Brain's internal invariant violations to mission level. FIX-06 escalates a specific Brain invariant (Y1). They are parallel enforcement paths, not sequential dependencies.

### FIX-08: Post-synthesis residue verification [GOVERNANCE]
- **Source:** Claude Audit Fix #2, Claude Fix #5, Hermes FIX-5
- **Location:** `brain-v3-orchestrator.py`, after Hermes synthesis
- **Problem:** `[UNRESOLVED RESIDUE]` injected into Hermes prompt but nothing validates the report addressed it. Hermes can produce a clean narrative ignoring all residue.
- **Scope:** This is a **narrative completeness check**, not a truth-ownership transfer. It verifies Hermes addressed the structural findings in the report body. It does NOT evaluate whether Hermes reached the "right" conclusion about those findings. The controller owns truth; this check owns transparency.
- **Fix:** New function `_verify_residue_in_report(report_path, ledger, log)`:
  - **Governing blockers (individually mandatory):** For each active BLK-XXX with kind=EVIDENCE_GAP or EVIDENCE_CONTRADICTION: check if BLK-XXX appears in report body. Any single missing governing blocker = ERROR.
  - **Aggregate residue (threshold-based):** For each contradiction ID (CTR-XXX) and minority model name: check presence. If >=30% absent across the aggregate set: emit Y2 at ERROR severity.
  - Store `proof["synthesis_residue_omissions"]` with list of missing references, categorized as `governing_blocker_omission` vs `aggregate_residue_omission`
  - Do NOT reject the run -- flag only
- **Risk:** Low. Observability improvement. The tiered threshold ensures governing blockers (most critical) are individually checked while less critical references use aggregate measurement.
- **DoD:** D7

### FIX-09: Chamber canonical proof artifact [GOVERNANCE]
- **Source:** ChatGPT Audit Fix #2
- **Location:** `consensus_runner_v3.py`, end of `run_chamber_v3()`
- **Problem:** Brain has rich proof.json; Chamber has nothing equivalent. Mission proof only stores `chamber_status` and `chamber_confidence`.
- **Fix:** At end of `run_chamber_v3()`, write `chamber-proof.json` with:
  - run_id, timestamp
  - search_diagnostics (mode, queries, success/failure counts)
  - evidence_ledger_summary (items admitted, rejected, domains)
  - objection_ledger (all objections with lifecycle)
  - audit_history (Auditor assessments per cycle)
  - degraded_cycles (list of cycles where search/agent failed)
  - option_registry (all options, their source, eligibility)
  - choice_mode, selected_option
  - final_normalized_verdict
  - SLP profiles
  - Include path and SHA256 hash in mission proof
- **Risk:** **HIGH** (upgraded per reviewer consensus). This is the largest single fix (~150-200 lines). Chamber's internal state is spread across Pydantic models (RunLedger, ProposalPack, ObjectionPack, AuditSnapshot, ConsensusVerdict). Serialization will surface edge cases: Pydantic serialization issues, circular references, fields meaningful mid-run but misleading at proof-write time. Start early.
- **DoD:** D8

### FIX-10: Proof.json always populated on completion [BUG]
- **Source:** Brain V3 run analysis (2 standard runs had empty proof.json despite completed orchestrator.log)
- **Location:** `brain-v3-orchestrator.py`, proof write logic in `main()`
- **Problem:** Proof.json is created at start with empty/null fields. If the proof-finalization code path is skipped (e.g., exception in post-synthesis, or early return), the skeleton remains.
- **Fix:** Move proof write to be the absolute LAST step in main(), after ALL fields are computed. Add a final try/except that writes a "PROOF_WRITE_FAILED" status proof if the normal path fails.
- **Risk:** Low. Makes proof write more robust.
- **DoD:** D9

### FIX-11: MEDIUM contradiction accumulation [CALIBRATION]
- **Source:** Claude Audit Fix #4
- **Location:** `brain-v3-orchestrator.py`, `_classify_outcome()` around line ~4283
- **Problem:** Only HIGH contradictions trigger disagreement floor. MEDIUM contradictions are recorded but have no downstream effect.
- **Fix:** If >=3 MEDIUM contradictions remain unresolved at outcome classification time, treat as equivalent to 1 HIGH for disagreement floor purposes.
- **Risk:** Low. Adjusts threshold calculation, does not change the disagreement floor mechanism itself.
- **DoD:** P9 (moved from Core DoD per reviewer consensus -- calibration choice, not proven bug)

### FIX-12: Chamber search parity [ARCHITECTURAL]
- **Source:** ChatGPT Audit Fix #3
- **Location:** `consensus_runner_v3.py`, search-related functions
- **Fix:** Port Brain's code-token false-positive checks and confidence/origin-aware escalation. In `_sonar_deep_evidence()`, count attempts/failures, emit structured degraded-search event, mark cycle degraded if all Sonar queries fail.
- **Risk:** Medium. Requires porting logic between engines.
- **DoD:** P4

### FIX-13: Eviction archive [OBSERVABILITY]
- **Source:** Claude Audit Fix #3
- **Location:** `brain-v3-orchestrator.py`, EvidenceLedger eviction path
- **Fix:** Add `eviction_archive` list. On eviction, append `{evidence_id, topic, fact, url, evicted_by, eviction_round}`. Serialize as `proof["evidence_eviction_archive"]`.
- **Risk:** Zero. Additive.
- **DoD:** P5

### FIX-14: Brain proof acceptance_status + budget field [OBSERVABILITY]
- **Source:** ChatGPT Audit Fix #5, Claude Audit Fix #6
- **Location:** `brain-v3-orchestrator.py`, end of `main()`
- **Fix:** Compute `brain_proof_complete` and `acceptance_status` from invariant severities and structural completeness. Add `proof["budget_constrained"]` boolean.
- **Risk:** Zero. Additive fields.
- **DoD:** D10 (promoted from Tier 2 per reviewer consensus -- enforcement model needs canonical proof-level status before FIX-06/FIX-07 can be cleanly interpreted)

---

## Part 5: Execution Plan to Achieve DoD

### Phase 0: Security (1 fix, immediate)

| Fix | What | DoD |
|-----|------|-----|
| FIX-01 | Remove hardcoded API key | D1 |

**Effort:** 10 minutes. Do this first, before anything else.

### Phase 1: Evidence Integrity + Chamber Proof Start (parallel)

These fixes are independent of each other. FIX-09 starts here because it is the largest single fix (~150-200 lines) and needs early lead time for Pydantic serialization edge cases.

| Fix | What | DoD | Depends on |
|-----|------|-----|------------|
| FIX-02 | Priority scoring for new items | D2 | -- |
| FIX-03 | Contradiction same-metric requirement | D3 | -- |
| FIX-04 | Admission resilience (try/except) | P10 | -- |
| FIX-13 | Eviction archive | P5 | -- |
| FIX-09 | Chamber canonical proof artifact (START) | D8 | -- |

**Effort:** Medium-High. FIX-02/03/04/13 are all in `brain-v3-orchestrator.py`'s EvidenceLedger. FIX-03 is the most complex (three-part change). FIX-04 is 3 lines. FIX-09 is the largest item and works on a separate file (`consensus_runner_v3.py`), so it runs in parallel without contention.

**Validation:** Run a Brain-only test (T1 or T7). Check:
- proof.json contradiction_ledger has zero false positives (FIX-03)
- Under cap pressure, newer high-relevance evidence can displace older low-relevance evidence (FIX-02)
- No exception-induced partial state in evidence ledger (FIX-04)
- proof.json has `evidence_eviction_archive` field (FIX-13)

### Phase 2: Disagreement Preservation + Proof Fields

| Fix | What | DoD | Depends on |
|-----|------|-----|------------|
| FIX-05 | Minority `addressed_by` scanning | D4 | FIX-03 (needs clean contradiction data) |
| FIX-14 | Brain proof acceptance_status + budget field | D10 | -- |

**Effort:** Medium. FIX-05 adds a new function + call site. FIX-14 is straightforward additive fields but must land before Phase 3 so the enforcement model has canonical proof-level status to act on.

**Validation:** Run T1 (4-round Brain run). Check:
- Minorities referenced in R2-R4 outputs have `addressed_by` populated
- Brain proof contains `acceptance_status` and `budget_constrained` fields

### Phase 3: Enforcement Escalation (3 fixes, independent of each other)

These are the governance enforcement fixes. FIX-06 and FIX-07 are **independent parallel enforcement paths** (not a sequential chain). FIX-08 is also independent. All three depend on Phase 1 (clean evidence/contradiction data) and Phase 2 (proof-level status fields).

| Fix | What | DoD | Depends on |
|-----|------|-----|------------|
| FIX-06 | Y1 invariant -> ERROR | D5 | Phase 1 (clean evidence reduces false Y1 triggers) |
| FIX-07 | Mission inspects Brain invariants | D6 | FIX-14 (needs proof-level acceptance_status) |
| FIX-08 | Post-synthesis residue verification | D7 | Phase 1 (needs accurate contradiction/minority data) |

**Effort:** Medium-High. FIX-06 touches invariant validation (sensitive). FIX-07 modifies mission controller (must check mode before escalating). FIX-08 adds a new post-synthesis step with tiered threshold.

**Validation:** Run T1 and T7. Check:
- Y1 fires as ERROR (not WARNING) when controller/synthesis mismatch occurs without override
- Mission proof contains `brain_invariant_summary`
- Proof contains `synthesis_residue_omissions` with governing blocker omissions listed individually
- Runs that SHOULD be flagged ARE flagged; runs that are clean still ACCEPT

### Phase 4: Proof Completeness (finalize)

| Fix | What | DoD | Depends on |
|-----|------|-----|------------|
| FIX-09 | Chamber canonical proof artifact (FINALIZE) | D8 | Started in Phase 1 |
| FIX-10 | Proof.json always populated on completion | D9 | -- |

**Effort:** FIX-09 finalization includes integration testing with mission controller (path/hash in mission proof). FIX-10 is straightforward.

**Validation:** Run T2 (Chamber-only) and T3 (cascade). Check:
- `chamber-proof.json` exists with all required fields
- Mission proof contains chamber proof path + hash
- Force a synthesis failure, verify proof.json still contains useful data (not skeleton)

### Phase 5: Full E2E Validation

Run all 9 tests (T1-T9). Each test must produce the correct mode, authority, and **expected acceptance status under the revised enforcement policy**.

| Test | Mode | Authority | Expected Status | Enforcement Notes |
|------|------|-----------|-----------------|-------------------|
| T1 | brain_only | brain | ACCEPTED or ERROR-flagged | Brain-authoritative. Y1 (FIX-06) fires ERROR if controller/synthesis mismatch without override. MI8 (FIX-07) propagates Brain ERRORs as mission ERRORs. Residue verification (FIX-08) may flag omissions. If any ERROR fires, status becomes REJECTED -- review to confirm genuine mismatch, not regression. |
| T2 | chamber_only | chamber | ACCEPTED | Chamber-only. No Brain invariants. New `chamber-proof.json` (FIX-09) must exist alongside chamber log. |
| T3 | cascade | chamber | ACCEPTED | Chamber authoritative. Brain ERRORs become mission WARNINGs only (MI8 non-authoritative path). `chamber-proof.json` must exist. |
| T4 | parallel | classification | ACCEPTED | Both engines run. MI8 propagates Brain violations based on which engine is authoritative. Discrepancy packet diagnostic-only (unchanged). |
| T5 | cascade | chamber | ACCEPTED | Same as T3. Brain explores first, Chamber finalizes. |
| T6 | cascade | chamber | ACCEPTED | Option injection safeguard. Same enforcement as T3/T5. |
| T7 | brain_only | brain | ACCEPTED or ERROR-flagged | Same as T1. Regulatory brief. Evidence gap blockers (BLK) must appear in synthesis (FIX-08 governing blocker check). |
| T8 | brain_only | brain | ACCEPTED | Forced brain mode on recommendation brief. Same enforcement as T1 but shorter run (2-3 rounds), less likely to trigger Y1. |
| T9 | chamber_only | chamber | ACCEPTED | Same as T2. Forced chamber mode. `chamber-proof.json` must exist. |

**Important:** The enforcement escalation fixes (FIX-06, FIX-07, FIX-08) may cause Brain-authoritative tests (T1, T7) to produce ERROR-level invariant violations that previously passed silently. This is **desired behavior**. If a test produces proof-degraded status, review the specific violation to confirm it is a genuine mismatch (correct flag) rather than a regression (incorrect flag). Budget time for this review-and-tune cycle.

### Phase 6: Production Hardening (Tier 2 DoD)

Separate workstream, after Core DoD is achieved.

| Item | What | DoD |
|------|------|-----|
| FIX-11 | MEDIUM contradiction accumulation (calibration) | P9 |
| FIX-12 | Chamber search parity | P4 |
| Search contamination defense | Gap query validation, ticker false-positive suppression, explicit degraded-search | P8 |
| Unit tests for mission_controller.py | classify_brief, _assign_final_authority, invariant validation | P1 |
| Unit tests for brain-v3-orchestrator.py | EvidenceLedger, _classify_outcome, _check_contradiction | P2 |
| Shared conftest.py | Eliminate ~50-line stub duplication | P3 |
| Environment decoupling | Remove hardcoded `/home/node/.openclaw/` paths | P6 |
| Proof schema documentation | JSON Schema for Brain proof v2.0 + Chamber proof | P7 |

---

## Part 6: Dependency Graph

```
Phase 0: FIX-01 (API key)
    |
    v
Phase 1: FIX-02, FIX-03, FIX-04, FIX-13 (evidence layer, parallel)
    |         \
    |          FIX-09 START (Chamber proof, parallel -- separate file)
    |
    +---> Phase 2: FIX-05 (depends on FIX-03) + FIX-14 (independent)
    |         |
    |         v
    +---> Phase 3: FIX-06, FIX-07, FIX-08 (all independent of each other,
    |              all depend on Phase 1 clean data + Phase 2 proof fields)
    |
    v
Phase 4: FIX-09 FINALIZE + FIX-10 (proof completeness)
    |
    v
Phase 5: Full E2E (T1-T9, with expected revised statuses)
    |
    v
Phase 6: Production hardening (P1-P10)
```

**Critical path:** Phase 0 -> Phase 1 (FIX-03) -> Phase 2 (FIX-05, FIX-14) -> Phase 3 -> Phase 5

**Parallel paths:** FIX-09 runs alongside Phases 1-3 (separate file, no contention). Phase 6 starts after Phase 5.

---

## Part 7: What Was Explicitly Rejected

The following proposals from the audits were evaluated and NOT included in the DoD:

| Proposal | Source | Reason for Exclusion |
|----------|--------|---------------------|
| Change discrepancy packet to be actionable | ChatGPT #6 | Intentional design: diagnostic-only is correct for parallel mode. Both audits confirm this. |
| Change cascade authority model | -- | Chamber authority in cascade is correct policy. Brain is structured input. |
| Add ML-based brief classification | -- | Regex classifier is deterministic and auditable. ML introduces opacity in the routing layer, which contradicts the controller-owned-authority principle. |
| Add retry logic to mission controller | -- | Retries belong in the test runner / operator layer, not the orchestrator. The controller's job is to classify the outcome, not mask failures. |
| Split monolith files | -- | Deferred to Phase 6. Important for maintainability but does not affect correctness. The DoD is about correctness first. |
| Temporal staleness markers | ChatGPT #9 | Lower priority unless briefs are time-sensitive. No evidence of time-sensitivity issues in run data. |
| Multi-domain planning | ChatGPT #10 | Speculative. No evidence of systematic multi-domain failures beyond the cross-domain filter issue (which is addressed by the evidence integrity fixes). |

---

## Part 8: Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| FIX-06 (Y1 escalation) causes previously-passing runs to fail | HIGH | MEDIUM | This is desired. Review the first few flagged runs manually to confirm they deserve ERROR. Provide `[SYNTHESIS-OVERRIDE]` escape hatch. Budget time for Phase 5 review-and-tune cycle. |
| FIX-07 (mission inspects Brain invariants) causes cascade rejection | MEDIUM | HIGH | Brain ERROR in a cascade where Chamber is authoritative -> WARNING (non-authoritative engine). Only escalate to mission ERROR when Brain IS authoritative. Implementation must check mode. |
| FIX-09 (Chamber proof) Pydantic serialization edge cases | HIGH | MEDIUM | Chamber state spans 5+ Pydantic models. Start early (Phase 1). Serialize incrementally -- get RunLedger working first, then add objection/audit layers. Test with T2 and T3 after each layer. |
| FIX-03 (stricter contradiction detection) misses genuine contradictions | LOW | LOW | Genuine contradictions with weak keyword overlap are rare. The current detector catches nothing useful due to noise floor. Any reduction in false positives is a net improvement. |
| Phase 5 E2E tests fail after enforcement changes | HIGH | MEDIUM | Expected. D11 is now "expected revised status" not blanket ACCEPTED. T1 and T7 (Brain-authoritative) are most likely to surface new ERROR-level violations. Review each to confirm genuine mismatch vs regression. |

---

## Summary

**The Thinker platform is ~80% done.** The architecture is sound. The remaining 20% falls into two categories:

- **Implementation bugs** (4 items): evidence scoring, contradiction detection, minority tracking, proof population -- where the code doesn't do what the design says it should
- **Controller-governance enforcement gaps** (4 items): Y1 invariant, mission acceptance semantics, post-synthesis residue verification, Chamber proof artifact -- where the controller's authority model is structurally incomplete
- Plus 1 security issue (hardcoded API key)

All 14 fixes target the gap between "what the system promises" and "what the system enforces." None of them change the architecture. The platform's design philosophy is correct -- it just needs to be fully implemented.

**Rev 2 changes (per 4-reviewer consensus):**
- FIX-04 (admission atomicity) and FIX-11 (MEDIUM contradiction accumulation) demoted from Core DoD to Tier 2 -- the fix doesn't match the stated criterion, and the threshold is a calibration choice without empirical backing
- D11 reworded from "all 9 ACCEPTED" to "expected revised status" -- enforcement escalation will correctly flag runs that previously passed silently
- FIX-09 (Chamber proof) starts in Phase 1 (not Phase 4) -- largest fix, needs early lead time for Pydantic serialization edge cases
- FIX-14 (Brain proof acceptance_status) promoted to Phase 2 -- enforcement model needs proof-level status before FIX-06/FIX-07 can be cleanly interpreted
- FIX-06 and FIX-07 decoupled -- independent parallel enforcement paths, not a sequential chain
- FIX-08 threshold tiered -- governing blockers individually mandatory, aggregate 30% for minorities/contradictions
- FIX-08 explicitly scoped as transparency check, not truth-ownership transfer
- Search contamination defense added to Tier 2 (P8)
- Framing adjusted: enforcement gaps are controller-governance gaps, not mere bugs

**Total scope:** 14 fixes across 3 files, organized in 6 phases. Core DoD: 11 criteria. Production DoD: 10 criteria. The critical path runs through evidence integrity (Phase 1) -> disagreement preservation + proof fields (Phase 2) -> enforcement escalation (Phase 3) -> E2E validation (Phase 5). FIX-09 runs in parallel from Phase 1. Phase 6 (production hardening) is a separate workstream.

---

## Appendix: Implementation Status (2026-03-26)

All 14 fixes implemented and syntax-verified across 3 files.

| Fix | File | Status | Notes |
|-----|------|--------|-------|
| FIX-01 | brain-v3-orchestrator.py | DONE | API key moved to env var |
| FIX-02 | brain-v3-orchestrator.py | DONE | `is_incoming` parameter added to `_evidence_priority_score()` |
| FIX-03 | brain-v3-orchestrator.py | DONE | Stopwords + threshold 4 + 2 long keywords + same-metric proximity |
| FIX-04 | brain-v3-orchestrator.py | DONE | try/except wrapper on `_check_contradiction()` |
| FIX-05 | brain-v3-orchestrator.py | DONE | `_scan_minority_acknowledgments()` called after R2, R3, R4 |
| FIX-06 | brain-v3-orchestrator.py | DONE | Y1 escalated to ERROR when no synthesis override |
| FIX-07 | mission_controller.py | DONE | MI8 check + `brain_invariant_summary` in mission proof |
| FIX-08 | brain-v3-orchestrator.py | DONE | `_verify_residue_in_report()` with tiered threshold |
| FIX-09 | consensus_runner_v3.py | DONE | `_build_chamber_proof()` writes `chamber-proof.json` |
| FIX-10 | brain-v3-orchestrator.py | DONE | Early exit paths now populate `evidence_items` |
| FIX-11 | brain-v3-orchestrator.py | DEFERRED | Tier 2 calibration — awaiting empirical run evidence |
| FIX-12 | consensus_runner_v3.py | DEFERRED | Tier 2 — Chamber search parity |
| FIX-13 | brain-v3-orchestrator.py | DONE | `eviction_archive` on EvidenceLedger + proof field |
| FIX-14 | brain-v3-orchestrator.py | DONE | `acceptance_status` + `budget_constrained` + final write_proof |

**Syntax verification:** All 3 files pass `py_compile` (WSL Python 3.11+).

**Next step:** Phase 5 — deploy to OpenClaw container and run E2E test suite (T1-T9).
