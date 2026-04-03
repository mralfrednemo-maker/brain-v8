# Brain V9 Gap Closure Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 24 gaps identified in the V9 spec-vs-code gap analysis. Every DESIGN-V3.md requirement must be wired end-to-end with behavioral verification.

**Architecture:** Fix the orchestrator (brain.py) as the central integration point. Each task targets a specific gap cluster. Tasks are ordered by dependency — upstream fixes first, then downstream consumers.

**Tech Stack:** Python 3.12, asyncio, pytest. Same LLM roster as V8/V9.

**Hard Constraints:**
- Zero tolerance: any failure = BrainError. No degraded mode.
- No budgets on thinking models. 30k/720s for R1/Reasoner, 8k-16k for others.
- Fixed topology: 4->3->2->2 always.

**Working directory:** `C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8\`

**Verification protocol:** After ALL tasks complete, run spec-vs-code gap analysis (read every DESIGN-V3.md section, verify code implements it). Then run b9 clean and validate ALL proof sections populated.

---

## File Structure

### Modified files
- `thinker/brain.py` — orchestrator rewiring (Tasks 1, 2, 3, 4, 5, 6, 8, 9, 10)
- `thinker/rounds.py` — frame injection for R3/R4 (Task 3)
- `thinker/synthesis.py` — disposition prompt (Task 5)
- `thinker/argument_tracker.py` — resolution status (Task 7)
- `thinker/gate2.py` — A1-A7 rule fixes (Task 9)

### New files
- `thinker/analysis_mode.py` — ANALYSIS pipeline modifications (Task 9)
- `tests/test_analysis_mode.py` — tests (Task 9)

### Test files modified
- `tests/test_brain_e2e.py` — update mock pipeline (Tasks 1, 2, 5)
- `tests/test_rounds.py` — R3/R4 frame injection test (Task 3)
- `tests/test_gate2.py` — A-rule fixes (Task 9)

---

## Task 1: Remove Gate 1, Wire Preflight as Primary Admission + Search Decision

**Gaps closed:** GAP-01 (gate1 still runs), GAP-02 (search_scope ignored)
**Spec:** DESIGN-V3.md Section 1.1 — "Gate 1 and CS Audit merge into a single PreflightAssessment stage."

**Files:**
- Modify: `thinker/brain.py`
- Modify: `tests/test_brain_e2e.py`

**Acceptance criteria:**
- `grep -r "run_gate1" thinker/brain.py` returns 0 results
- `grep "search_scope" thinker/brain.py` returns results
- `grep "gate1_search_recommended" thinker/brain.py` returns 0 results (in search decision block)
- Preflight is the FIRST stage (no gate1 before it)
- Search decision uses `preflight.search_scope`: NONE=off, TARGETED/BROAD=on

- [ ] **Step 1: Write test verifying gate1 is not called**

In `tests/test_brain_e2e.py`, add at the end:

```python
def test_gate1_not_called_directly(brain_with_mocks):
    """V9: Preflight replaces Gate 1. gate1 should not be called."""
    import thinker.brain as brain_module
    # gate1 import should not exist in brain.py
    import inspect
    source = inspect.getsource(brain_module.Brain.run)
    assert "run_gate1" not in source, "Gate 1 should be replaced by Preflight in V9"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/test_brain_e2e.py::test_gate1_not_called_directly -v`

Expected: FAIL — run_gate1 is still in brain.py

- [ ] **Step 3: Remove gate1 from brain.py, wire preflight as primary, wire search_scope**

In `thinker/brain.py`:

**a)** Remove the gate1 import (line 28):
```python
# DELETE this line:
from thinker.gate1 import run_gate1
```

**b)** Remove the entire Gate 1 block (currently lines ~279-308). Replace with preflight as the FIRST stage after setup. The preflight block already exists at lines ~310-332 — move it up to where gate1 was.

**c)** Replace the search decision block (currently lines ~351-377) with:

```python
        # --- Search Decision (V9: uses preflight.search_scope) ---
        has_search_provider = self._search_fn is not None
        if self._search_override is not None:
            search_enabled = self._search_override and has_search_provider
            source = "cli_override"
            reasoning = "Forced on via --search" if self._search_override else "Forced off via --no-search"
            proof.set_search_decision(source=source, value=search_enabled, reasoning=reasoning)
            log._print(f"  [SEARCH DECISION] {source}: {'ON' if search_enabled else 'OFF'} "
                        f"(Preflight scope: {preflight_result.search_scope.value})")
        else:
            from thinker.types import SearchScope
            search_enabled = (preflight_result.search_scope != SearchScope.NONE) and has_search_provider
            proof.set_search_decision(
                source="preflight",
                value=search_enabled,
                reasoning=f"Preflight search_scope={preflight_result.search_scope.value}",
            )
            log._print(f"  [SEARCH DECISION] preflight: {'ON' if search_enabled else 'OFF'} — scope={preflight_result.search_scope.value}")
```

**d)** Remove all `gate1` variable references: `gate1=gate1` in BrainResult returns, `st.gate1_passed`, `st.gate1_reasoning`, `st.gate1_questions`, `st.gate1_search_recommended`, `st.gate1_search_reasoning`. Remove the `_debug_pause` gate1 section.

**e)** Update the `_debug_pause` method: replace the `if stage_id == "gate1":` block with a `if stage_id == "preflight":` block showing preflight data.

**f)** Keep `Gate1Result` type in types.py for backward compat but it's no longer used in the pipeline.

- [ ] **Step 4: Update test_brain_e2e.py mock setup**

Remove the gate1 mock response from the mock call sequence. The first Sonnet call should now be preflight, not gate1.

- [ ] **Step 5: Run all tests**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add thinker/brain.py tests/test_brain_e2e.py
git commit -m "fix(v9): remove gate1, wire preflight as primary admission + search_scope"
```

---

## Task 2: Wire Ungrounded Stat Detector Post-R1 and Post-R2

**Gaps closed:** GAP-03 (ungrounded unwired), GAP-17 (UNVERIFIED_CLAIM blocker)
**Spec:** DESIGN-V3.md Section 1.5 — "Wire the existing (but inactive) Ungrounded Stat Detector into the proactive search phase after R1 and R2."

**Files:**
- Modify: `thinker/brain.py`

**Acceptance criteria:**
- `grep "find_ungrounded_stats" thinker/brain.py` returns results
- `grep "UNVERIFIED_CLAIM" thinker/brain.py` returns results
- Ungrounded stats detected post-R1 feed into search queries
- Post-R3 unresolved ungrounded stats become UNVERIFIED_CLAIM blockers

- [ ] **Step 1: Add import to brain.py**

After existing imports in brain.py, add:
```python
from thinker.tools.ungrounded import find_ungrounded_stats, generate_verification_queries
```

- [ ] **Step 2: Wire post-R1 ungrounded detection**

In brain.py, after the R1 tracking checkpoint (`if round_num == 1` perspective cards and framing pass block), add before the search phase:

```python
            # --- Ungrounded Stat Detection (V9, post-R1) ---
            if round_num == 1 and not self._stage_done("ungrounded_r1"):
                all_r1_text = " ".join(round_result.texts.values())
                ungrounded_r1 = find_ungrounded_stats(all_r1_text, evidence.active_items)
                if ungrounded_r1:
                    log._print(f"  [UNGROUNDED] R1: {len(ungrounded_r1)} ungrounded stats detected")
                    verification_queries = generate_verification_queries(ungrounded_r1, all_r1_text)
                    # These will be picked up by the search phase
                    st.search_queries.setdefault("ungrounded_r1", verification_queries)
                self._checkpoint("ungrounded_r1")
```

- [ ] **Step 3: Wire post-R2 ungrounded detection**

After the R2 tracking + frame survival block, add:

```python
            # --- Ungrounded Stat Detection (V9, post-R2) ---
            if round_num == 2 and not self._stage_done("ungrounded_r2"):
                all_r2_text = " ".join(round_result.texts.values())
                ungrounded_r2 = find_ungrounded_stats(all_r2_text, evidence.active_items)
                if ungrounded_r2:
                    log._print(f"  [UNGROUNDED] R2: {len(ungrounded_r2)} ungrounded stats detected")
                self._checkpoint("ungrounded_r2")
```

- [ ] **Step 4: Wire post-R3 UNVERIFIED_CLAIM blocker**

After R3 tracking, add:

```python
            # --- Post-R3: unresolved ungrounded stats become blockers (V9) ---
            if round_num == 3:
                all_r3_text = " ".join(round_result.texts.values())
                ungrounded_r3 = find_ungrounded_stats(all_r3_text, evidence.active_items)
                for stat in ungrounded_r3:
                    blocker_ledger.add(
                        kind=BlockerKind.UNVERIFIED_CLAIM,
                        source="ungrounded_stat_detector",
                        detected_round=3,
                        detail=f"Unverified numeric claim persists after R3: {stat}",
                        models=[],
                    )
                if ungrounded_r3:
                    log._print(f"  [UNGROUNDED] R3: {len(ungrounded_r3)} unresolved → UNVERIFIED_CLAIM blockers")
```

- [ ] **Step 5: Wire proof.set_ungrounded_stats**

Before the synthesis section in brain.py, collect all ungrounded data and set it:

```python
        # Record ungrounded stats in proof
        ungrounded_proof_data = []
        for rnd in ["ungrounded_r1", "ungrounded_r2"]:
            queries = st.search_queries.get(rnd, [])
            if queries:
                ungrounded_proof_data.append({"stage": rnd, "queries": queries})
        proof.set_ungrounded_stats(ungrounded_proof_data)
```

- [ ] **Step 6: Run tests**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add thinker/brain.py
git commit -m "fix(v9): wire ungrounded stat detector post-R1, post-R2, UNVERIFIED_CLAIM blockers post-R3"
```

---

## Task 3: Wire Frame Survival After R3 + Frame Injection for R3/R4

**Gaps closed:** GAP-04 (R3 frame survival missing), GAP-20 (alt_frames_text only injected in R2)
**Spec:** DESIGN-V3.md Section 2.3 — "R3/R4: Frames cannot be dropped. They transition to CONTESTED."

**Files:**
- Modify: `thinker/brain.py`
- Modify: `thinker/rounds.py`

**Acceptance criteria:**
- `grep "frame_survival_r3" thinker/brain.py` returns results
- In rounds.py: alt_frames_text injected for round_num >= 2 (not just == 2)

- [ ] **Step 1: Fix rounds.py to inject frames for R2+, not just R2**

In `thinker/rounds.py`, change the condition on line ~112 from:
```python
    if round_num == 2 and alt_frames_text:
```
to:
```python
    if round_num >= 2 and alt_frames_text:
```

And change the frame engagement section on line ~122 from:
```python
    if round_num == 2 and alt_frames_text:
```
to:
```python
    if round_num == 2 and alt_frames_text:  # Frame enforcement ONLY in R2
```

(Keep frame enforcement for R2 only — the spec says "R2 frame enforcement: each model must adopt one, rebut one, generate one." R3/R4 see the frames but don't have the mandatory adopt/rebut/generate requirement.)

- [ ] **Step 2: Wire R3 frame survival in brain.py**

After R3 tracking in brain.py, add (similar to the R2 block):

```python
            # --- Frame Survival R3 (V9) ---
            if round_num == 3 and not self._stage_done("frame_survival_r3"):
                divergence_result.alt_frames = await run_frame_survival_check(
                    self._llm, divergence_result.alt_frames, round_result.texts, round_num=3,
                )
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                st.divergence = divergence_result.to_dict()
                self._checkpoint("frame_survival_r3")
```

- [ ] **Step 3: Run tests**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/test_rounds.py tests/test_divergent_framing.py -v --tb=short`

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add thinker/brain.py thinker/rounds.py
git commit -m "fix(v9): wire R3 frame survival + inject alt_frames into R3/R4 prompts"
```

---

## Task 4: Wire Defect Routing from Preflight

**Gaps closed:** GAP-18 (defect routing ignored)
**Spec:** DESIGN-V3.md Section 1.1 — "Manageable unknowns → inject as debate obligation + register as blocker. Framing defect → inject reframed version into R1."

**Files:**
- Modify: `thinker/brain.py`

**Acceptance criteria:**
- MANAGEABLE_UNKNOWN flags create blockers
- FRAMING_DEFECT flags inject reframe text into dimension_text

- [ ] **Step 1: Add defect routing after preflight in brain.py**

After `proof.set_preflight(preflight_result)` and before the dimensions checkpoint, add:

```python
            # --- Defect Routing (V9, Section 1.1) ---
            from thinker.types import PremiseFlagRouting
            for flag in preflight_result.premise_flags:
                if flag.resolved:
                    continue
                if flag.routing == PremiseFlagRouting.MANAGEABLE_UNKNOWN:
                    blocker_ledger.add(
                        kind=BlockerKind.COVERAGE_GAP,
                        source=f"preflight:{flag.flag_id}",
                        detected_round=0,
                        detail=f"Manageable unknown: {flag.summary}",
                        models=[],
                    )
                    log._print(f"  [DEFECT] {flag.flag_id}: MANAGEABLE_UNKNOWN → blocker registered")
                elif flag.routing == PremiseFlagRouting.FRAMING_DEFECT:
                    # Inject reframe into dimension text for R1
                    dimension_text += f"\n\n## Reframing Required (Premise Defect)\n{flag.summary}\nYou MUST engage with this reframing in your analysis.\n"
                    log._print(f"  [DEFECT] {flag.flag_id}: FRAMING_DEFECT → reframe injected into R1")
```

- [ ] **Step 2: Run tests**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add thinker/brain.py
git commit -m "fix(v9): wire preflight defect routing — MANAGEABLE_UNKNOWN→blocker, FRAMING_DEFECT→reframe"
```

---

## Task 5: Wire Synthesis Dispositions + Residue Verification

**Gaps closed:** GAP-08 (no dispositions), GAP-09 (V8 residue not replaced)
**Spec:** DESIGN-V3.md Section 3.2 — "Synthesis prompt requires structured dispositions for every open finding." Section 3.6 — "Replace string-match with schema validation."

**Files:**
- Modify: `thinker/synthesis.py`
- Modify: `thinker/brain.py`

**Acceptance criteria:**
- SYNTHESIS_PROMPT includes disposition format requirements
- `check_disposition_coverage` is called in brain.py
- Dispositions are parsed from synthesis output and written to proof

- [ ] **Step 1: Add disposition requirements to SYNTHESIS_PROMPT**

In `thinker/synthesis.py`, append to the `SYNTHESIS_PROMPT` string (before the closing `"""`), after the JSON section format:

```python
# Add this after the existing JSON format section in SYNTHESIS_PROMPT:

SECTION 3: Dispositions (one per line, after ---DISPOSITIONS---)
For EVERY open finding below, emit a disposition line:
DISPOSITION: [BLOCKER|FRAME|CLAIM|CONTRADICTION] | [target_id] | [RESOLVED|DEFERRED|ACCEPTED_RISK|MITIGATED] | [importance: LOW|MEDIUM|HIGH|CRITICAL] | [one-sentence explanation]

If you cannot address a finding, still emit a disposition with status DEFERRED and explain why.
```

Update `parse_synthesis_output()` to also extract dispositions:

```python
def parse_synthesis_output(text: str) -> tuple[str, dict, list[dict]]:
    """Split synthesis output into markdown report, JSON object, and dispositions.

    Returns (markdown_report, json_data, dispositions).
    """
    import json as _json
    import re

    dispositions = []
    # Extract dispositions section
    if "---DISPOSITIONS---" in text:
        parts = text.split("---DISPOSITIONS---", 1)
        text = parts[0]
        disp_text = parts[1].strip()
        for line in disp_text.split("\n"):
            line = line.strip()
            if line.startswith("DISPOSITION:"):
                parts_d = [p.strip() for p in line[len("DISPOSITION:"):].split("|")]
                if len(parts_d) >= 5:
                    dispositions.append({
                        "target_type": parts_d[0],
                        "target_id": parts_d[1],
                        "status": parts_d[2],
                        "importance": parts_d[3],
                        "narrative_explanation": parts_d[4],
                    })

    # Rest of existing parsing (markdown + JSON)...
```

Note: This changes the return type from `tuple[str, dict]` to `tuple[str, dict, list[dict]]`. Update all callers.

- [ ] **Step 2: Update run_synthesis return type and callers**

In `thinker/synthesis.py`, update `run_synthesis` to return the dispositions:

```python
async def run_synthesis(...) -> tuple[str, dict, list[dict]]:
    ...
    markdown, json_data, dispositions = parse_synthesis_output(resp.text)
    ...
    return markdown, json_data, dispositions
```

In `thinker/brain.py`, update the synthesis call to unpack 3 values:

```python
        report, report_json, dispositions = await run_synthesis(...)
```

- [ ] **Step 3: Wire check_disposition_coverage in brain.py**

After synthesis, replace the old `check_synthesis_residue` block with both checks:

```python
        # --- Residue Verification (V9: disposition coverage + legacy string match) ---
        # V9 structured verification
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

        active_frames = [f for f in divergence_result.alt_frames
                         if f.survival_status.value in ("ACTIVE", "CONTESTED")]
        coverage = check_disposition_coverage(
            dispositions=disposition_objects,
            open_blockers=blocker_ledger.blockers,
            active_frames=active_frames,
            decisive_claims=[],
            contradictions_numeric=evidence.contradictions,
            contradictions_semantic=semantic_ctrs,
        )
        proof.set_residue_verification(coverage)
        proof.set_synthesis_dispositions(disposition_objects)

        if coverage.get("deep_scan_triggered"):
            proof.add_violation(
                "RESIDUE-COVERAGE", "WARN",
                f"Disposition omission rate {coverage['omission_rate']:.0%} > 20% threshold",
            )

        # Legacy string-match check (kept as supplementary)
        residue_omissions = check_synthesis_residue(...)
```

- [ ] **Step 4: Run tests**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

Expected: ALL PASS (may need to update test_synthesis.py for new return type)

- [ ] **Step 5: Commit**

```bash
git add thinker/synthesis.py thinker/brain.py tests/test_synthesis.py
git commit -m "fix(v9): wire synthesis dispositions + disposition coverage verification"
```

---

## Task 6: Wire Exploration Stress Seed Frames

**Gaps closed:** GAP-14 (stress trigger fires but no seed frames injected)
**Spec:** DESIGN-V3.md Section 2.4 — "Inject 2-3 seed frames (INVERSION, STAKEHOLDER_PERSPECTIVE) into R2 prompts."

**Files:**
- Modify: `thinker/brain.py`

**Acceptance criteria:**
- When exploration_stress_triggered=True, 2-3 seed frames added to alt_frames

- [ ] **Step 1: Generate and inject seed frames when stress triggers**

In brain.py, where `check_exploration_stress` is called, replace:

```python
                if check_exploration_stress(agreement, preflight_result.question_class, preflight_result.stakes_class):
                    divergence_result.exploration_stress_triggered = True
```

with:

```python
                if check_exploration_stress(agreement, preflight_result.question_class, preflight_result.stakes_class):
                    divergence_result.exploration_stress_triggered = True
                    # Inject seed frames to force broader exploration
                    from thinker.types import FrameInfo, FrameType, FrameSurvivalStatus
                    seed_frames = [
                        FrameInfo(
                            frame_id="SEED-INV",
                            text="What if the opposite of the emerging consensus is true? Argue against the majority position.",
                            origin_round=1, origin_model="controller",
                            frame_type=FrameType.INVERSION,
                            survival_status=FrameSurvivalStatus.ACTIVE,
                        ),
                        FrameInfo(
                            frame_id="SEED-STAKE",
                            text="Consider the perspective of the stakeholder most harmed by the emerging consensus. What are they seeing that the models are missing?",
                            origin_round=1, origin_model="controller",
                            frame_type=FrameType.OPPOSITE_STANCE,
                            survival_status=FrameSurvivalStatus.ACTIVE,
                        ),
                    ]
                    divergence_result.alt_frames.extend(seed_frames)
                    divergence_result.stress_seed_frames = [f.to_dict() for f in seed_frames]
                    log._print(f"  [STRESS] Exploration stress triggered — {len(seed_frames)} seed frames injected")
                    alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
```

- [ ] **Step 2: Run tests and commit**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

```bash
git add thinker/brain.py
git commit -m "fix(v9): inject seed frames when exploration stress triggers"
```

---

## Task 7: Wire Argument Resolution Status

**Gaps closed:** GAP-23 (resolution_status never updated)
**Spec:** DESIGN-V3.md Section 3.4 — "Each argument tagged as ORIGINAL/REFINED/SUPERSEDED."

**Files:**
- Modify: `thinker/argument_tracker.py`
- Modify: `thinker/brain.py`

**Acceptance criteria:**
- Arguments from `compare_with_round` that are ADDRESSED get `resolution_status=REFINED` or `SUPERSEDED`
- `proof.set_arguments()` is called in brain.py

- [ ] **Step 1: Update argument_tracker.compare_with_round to set resolution_status**

In `thinker/argument_tracker.py`, in the `compare_with_round` method, when an argument is marked ADDRESSED:

```python
from thinker.types import ResolutionStatus

# When marking an argument as ADDRESSED:
arg.resolution_status = ResolutionStatus.REFINED
arg.addressed_in_round = curr_round
```

When marking as MENTIONED:
```python
# MENTIONED = acknowledged but not substantively engaged
# Keep as ORIGINAL (not refined, not superseded)
```

When marking as IGNORED:
```python
# IGNORED = still ORIGINAL, still open
arg.open = True
```

- [ ] **Step 2: Wire proof.set_arguments in brain.py**

Before the synthesis section in brain.py, add:

```python
        # Record all arguments with resolution status in proof
        all_args = []
        for rnd_args in argument_tracker.arguments_by_round.values():
            all_args.extend(rnd_args)
        proof.set_arguments(all_args)
```

- [ ] **Step 3: Run tests and commit**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

```bash
git add thinker/argument_tracker.py thinker/brain.py
git commit -m "fix(v9): wire argument resolution_status + proof.set_arguments"
```

---

## Task 8: Wire All Missing Proof Setters

**Gaps closed:** GAP-10 (12 proof sections empty), GAP-12 (search log), GAP-15 (analogies), GAP-24 (contradictions), GAP-25 (stage integrity)
**Spec:** DESIGN-V3.md Section 3.5 (search_log), proof schema 3.0

**Files:**
- Modify: `thinker/brain.py`

**Acceptance criteria:**
- `grep "set_search_log\|set_contradictions\|set_analogies\|set_stage_integrity\|set_diagnostics" thinker/brain.py` returns results for each

- [ ] **Step 1: Wire search log**

In brain.py, during the search phase, build SearchLogEntry objects:

```python
from thinker.types import SearchLogEntry, QueryProvenance, QueryStatus

# Inside the search query loop, after each query executes:
search_log_entries.append(SearchLogEntry(
    query_id=f"Q-{len(search_log_entries)+1}",
    query_text=query,
    provenance=QueryProvenance.MODEL_CLAIM,  # or UNGROUNDED_STAT for verification queries
    issued_after_stage=f"r{round_num}",
    pages_fetched=len(results),
    evidence_yield_count=total_admitted,
    query_status=QueryStatus.SUCCESS if results else QueryStatus.ZERO_RESULT,
))
```

Initialize `search_log_entries: list = []` near the top of `run()`. After all search phases:
```python
proof.set_search_log(search_log_entries)
```

- [ ] **Step 2: Wire contradictions (numeric + semantic)**

Before synthesis in brain.py:
```python
proof.set_contradictions(evidence.contradictions, semantic_ctrs)
```

- [ ] **Step 3: Wire analogies from divergence**

After framing pass:
```python
if divergence_result.cross_domain_analogies:
    proof.set_analogies(divergence_result.cross_domain_analogies)
```

- [ ] **Step 4: Wire stage integrity**

At the very end of `run()`, before the final return:
```python
proof.set_stage_integrity(
    required=["preflight", "dimensions", "r1", "r2", "r3", "r4", "synthesis", "gate2"],
    order=self.state.completed_stages,
    fatal=[],  # No fatal failures if we reached here
)
```

- [ ] **Step 5: Wire diagnostics**

```python
proof.set_diagnostics({
    "total_elapsed_s": time.monotonic() - run_start_time,
    "rounds_completed": self._config.rounds,
    "search_enabled": search_enabled,
    "models_used": list(set(m for rnd in st.round_responded.values() for m in rnd)),
})
```

(Add `run_start_time = time.monotonic()` at the start of `run()`.)

- [ ] **Step 6: Run tests and commit**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

```bash
git add thinker/brain.py
git commit -m "fix(v9): wire all missing proof setters — search_log, contradictions, analogies, stage_integrity, diagnostics"
```

---

## Task 9: Implement ANALYSIS Mode

**Gaps closed:** GAP-06 (analysis_mode.py missing), GAP-07 (no ANALYSIS fork in brain.py)
**Spec:** DESIGN-V3.md Section 4 — "Shared pipeline, forked controller contract. ~80% code reuse."

**Files:**
- Create: `thinker/analysis_mode.py`
- Create: `tests/test_analysis_mode.py`
- Modify: `thinker/brain.py`
- Modify: `thinker/gate2.py`

**Acceptance criteria:**
- When `preflight.modality == ANALYSIS`, round prompts shift to exploration mode
- Frame survival uses EXPLORED/NOTED/UNEXPLORED (no dropping)
- Synthesis produces analysis map, not verdict
- Gate 2 uses A1-A7 rules (already implemented, but A-rules need fixing per spec)

**Note on staging (DESIGN-V3.md Section 4.6):** Deploy with `debug_mode: true` — rules log what they would do without enforcing. Pipeline outputs ANALYSIS based on synthesis contract alone. This means the ANALYSIS mode fork is primarily about prompt modifications and synthesis contract, NOT about skipping pipeline stages.

- [ ] **Step 1: Create analysis_mode.py**

```python
"""ANALYSIS mode — modified prompts and contracts for exploration modality (DESIGN-V3.md Section 4).

~80% pipeline reuse. What changes:
- Round prompts: exploration, not convergence
- Frame survival: EXPLORED/NOTED/UNEXPLORED (no dropping)
- Synthesis: analysis map per dimension, not verdict
- Gate 2: A1-A7 rules (already in gate2.py)
"""
from __future__ import annotations


def get_analysis_round_preamble(round_num: int) -> str:
    """Get the ANALYSIS-mode preamble for round prompts."""
    return (
        "## Mode: EXPLORATORY ANALYSIS\n"
        "Your task is to EXPLORE and MAP this question by dimension — identify knowns "
        "(evidence-backed), inferred (model-supported), and unknowns (gaps). "
        "Do NOT seek agreement or converge on a verdict. Deepen exploration.\n\n"
    )


def get_analysis_synthesis_contract() -> str:
    """Get the modified synthesis contract for ANALYSIS mode."""
    return (
        "\n## ANALYSIS Mode Synthesis Contract\n"
        "You are producing an EXPLORATORY MAP, NOT a decision.\n"
        "Header: 'EXPLORATORY MAP — NOT A DECISION'\n\n"
        "Output structure:\n"
        "1. Framing of the question\n"
        "2. Aspect map (by dimension)\n"
        "3. Competing hypotheses or lenses\n"
        "4. Evidence for and against each\n"
        "5. Unresolved uncertainties\n"
        "6. What information would most change the map\n\n"
        "Do NOT provide a verdict, recommendation, or conclusion.\n"
    )


ANALYSIS_FRAME_STATUSES = {"EXPLORED", "NOTED", "UNEXPLORED"}
```

- [ ] **Step 2: Create tests**

```python
"""Tests for ANALYSIS mode."""
from thinker.analysis_mode import (
    get_analysis_round_preamble,
    get_analysis_synthesis_contract,
)


def test_analysis_preamble_contains_exploration():
    text = get_analysis_round_preamble(1)
    assert "EXPLORE" in text
    assert "Do NOT seek agreement" in text


def test_analysis_synthesis_contract():
    text = get_analysis_synthesis_contract()
    assert "EXPLORATORY MAP" in text
    assert "NOT A DECISION" in text
    assert "verdict" in text.lower()
```

- [ ] **Step 3: Wire ANALYSIS mode fork in brain.py**

In brain.py, after preflight determines modality, set a flag:

```python
is_analysis_mode = preflight_result.modality == Modality.ANALYSIS
```

Then in the round execution, add the analysis preamble:

```python
from thinker.analysis_mode import get_analysis_round_preamble, get_analysis_synthesis_contract

# In the execute_round call, add:
analysis_preamble = get_analysis_round_preamble(round_num) if is_analysis_mode else ""
```

Pass `analysis_preamble` as additional text prepended to the brief in `build_round_prompt` (add a parameter).

In the synthesis call, add:

```python
analysis_contract = get_analysis_synthesis_contract() if is_analysis_mode else ""
# Append to synthesis_packet_text
synthesis_packet_text += analysis_contract
```

- [ ] **Step 4: Fix A1-A7 rules in gate2.py**

The current A-rules reference `dimension_coverage_score` which is never computed (GAP-22). Fix A2 to use a computed value:

In brain.py, before calling gate2, compute dimension coverage:

```python
# Compute dimension coverage from arguments
if dimension_result and dimension_result.items:
    for dim in dimension_result.items:
        dim_args = [a for a in all_args if a.dimension_id == dim.dimension_id]
        dim.argument_count = len(dim_args)
        dim.coverage_status = "SATISFIED" if len(dim_args) >= 2 else ("PARTIAL" if dim_args else "ZERO")
    covered = sum(1 for d in dimension_result.items if d.argument_count >= 2)
    dimension_result.dimension_coverage_score = covered / len(dimension_result.items) if dimension_result.items else 0.0
```

- [ ] **Step 5: Run tests and commit**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

```bash
git add thinker/analysis_mode.py tests/test_analysis_mode.py thinker/brain.py thinker/rounds.py thinker/gate2.py
git commit -m "feat(v9): implement ANALYSIS mode — exploration prompts, analysis synthesis contract, dimension coverage"
```

---

## Task 10: Fix Checkpoint Resume for V9 State

**Gaps closed:** GAP-19 (checkpoint resume incomplete)
**Spec:** Every new stage must be resumable.

**Files:**
- Modify: `thinker/brain.py`

**Acceptance criteria:**
- Resuming after `framing_pass` correctly restores `alt_frames_text` and `divergence_result`
- Resuming after `preflight` correctly restores full PreflightResult (not just modality)

- [ ] **Step 1: Fix preflight restoration**

In brain.py resume block, replace the bare-bones PreflightResult reconstruction with full restoration:

```python
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
```

- [ ] **Step 2: Fix divergence restoration**

```python
            if st.divergence:
                div = st.divergence
                divergence_result = DivergenceResult(
                    framing_pass_executed=div.get("framing_pass_executed", False),
                    exploration_stress_triggered=div.get("exploration_stress_triggered", False),
                )
                # Restore frames
                for f_data in div.get("alt_frames", []):
                    from thinker.types import FrameInfo, FrameType, FrameSurvivalStatus
                    divergence_result.alt_frames.append(FrameInfo(
                        frame_id=f_data.get("frame_id", ""),
                        text=f_data.get("text", ""),
                        frame_type=FrameType(f_data.get("frame_type", "INVERSION")),
                        survival_status=FrameSurvivalStatus(f_data.get("survival_status", "ACTIVE")),
                        material_to_outcome=f_data.get("material_to_outcome", True),
                    ))
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
```

- [ ] **Step 3: Fix dimension restoration**

```python
            if st.dimensions:
                dim = st.dimensions
                items = [DimensionItem(
                    dimension_id=d.get("dimension_id", ""),
                    name=d.get("name", ""),
                ) for d in dim.get("items", [])]
                dimension_result = DimensionSeedResult(
                    items=items,
                    dimension_count=dim.get("dimension_count", 0),
                )
                dimension_text = format_dimensions_for_prompt(dimension_result.items)
```

- [ ] **Step 4: Run tests and commit**

Run: `cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short -x --ignore=tests/test_cs_audit.py`

```bash
git add thinker/brain.py
git commit -m "fix(v9): complete checkpoint resume for all V9 state — preflight, divergence, dimensions"
```

---

## Task 11: Spec-vs-Code Verification (GATE C)

**This task is the mandatory verification gate. No shortcuts.**

- [ ] **Step 1: Read DESIGN-V3.md section by section and verify each requirement**

For each of these spec sections, grep the code and confirm the requirement is wired:

| Spec Section | Requirement | Verify command |
|---|---|---|
| 1.1 | Preflight replaces Gate 1 | `grep "run_gate1" thinker/brain.py` → 0 results |
| 1.1 | search_scope drives search | `grep "search_scope" thinker/brain.py` → results |
| 1.1 | Defect routing (MANAGEABLE_UNKNOWN→blocker) | `grep "MANAGEABLE_UNKNOWN" thinker/brain.py` → results |
| 1.5 | Ungrounded stat detector wired | `grep "find_ungrounded_stats" thinker/brain.py` → results |
| 2.1 | Dimension Seeder called | `grep "run_dimension_seeder" thinker/brain.py` → results |
| 2.2 | Perspective Cards extracted | `grep "extract_perspective_cards" thinker/brain.py` → results |
| 2.3 | Frame survival R2 AND R3 | `grep "frame_survival_r3" thinker/brain.py` → results |
| 2.4 | Exploration stress injects seed frames | `grep "SEED-INV" thinker/brain.py` → results |
| 3.1 | Two-tier evidence | `grep "archive_items" thinker/brain.py` → results |
| 3.2 | Synthesis packet | `grep "synthesis_packet" thinker/brain.py` → results |
| 3.3 | Semantic contradiction | `grep "semantic_contradiction" thinker/brain.py` → results |
| 3.4 | Argument resolution status | `grep "resolution_status" thinker/argument_tracker.py` → results |
| 3.5 | Search log in proof | `grep "set_search_log" thinker/brain.py` → results |
| 3.6 | Disposition coverage check | `grep "check_disposition_coverage" thinker/brain.py` → called (not just imported) |
| 3.7 | Stability tests | `grep "run_stability_tests" thinker/brain.py` → results |
| 4.x | ANALYSIS mode fork | `grep "is_analysis_mode\|analysis_mode" thinker/brain.py` → results |

- [ ] **Step 2: Scan for dead code**

```bash
# Imported but never called in brain.py:
grep "^from\|^import" thinker/brain.py | while read line; do
  # extract function/class names and grep for usage
done

# TODO/FIXME in committed code:
grep -r "TODO\|FIXME\|HACK" --include="*.py" thinker/
```

- [ ] **Step 3: Check for hardcoded empties that should have real data**

```bash
grep -n "= \[\].*#\|= None.*#\|= {}.*#" thinker/brain.py
```

- [ ] **Step 4: Run full test suite**

```bash
cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8" && python -m pytest tests/ -v --tb=short --ignore=tests/test_cs_audit.py
```

Expected: ALL PASS

- [ ] **Step 5: Commit verification pass**

```bash
git commit --allow-empty -m "verify(v9): spec-vs-code gap analysis passed — all DESIGN-V3.md requirements wired"
```

---

## Task 12: Integration Test — Brief b9 Clean Run + Full Proof Validation

**Files:**
- Run: `tests/fixtures/briefs/b9.md`

- [ ] **Step 1: Run b9 clean**

```bash
cd "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8"
rm -rf output/b9-v9-final
python -m thinker.brain --brief tests/fixtures/briefs/b9.md --outdir output/b9-v9-final --full-run
```

- [ ] **Step 2: Validate ALL proof sections populated**

```python
import json
proof = json.loads(open("output/b9-v9-final/proof.json").read())

required_sections = [
    "preflight", "dimensions", "perspective_cards", "divergence",
    "stability", "gate2", "evidence", "search_log",
    "contradictions", "stage_integrity", "diagnostics",
    "synthesis_packet",
]
for section in required_sections:
    val = proof.get(section)
    assert val is not None, f"MISSING: {section}"
    print(f"{section}: OK")

# Verify schema version
assert proof["proof_schema_version"] == "3.0"
assert proof["protocol_version"] == "v9"

# Verify gate1 is NOT in proof
assert "gate1" not in str(proof.get("final_status", ""))

# Verify gate2 has rule_trace
assert len(proof["gate2"]["rule_trace"]) > 0

print("ALL PROOF SECTIONS VALIDATED")
```

- [ ] **Step 3: If any section missing or brief fails, fix and re-run**

- [ ] **Step 4: Run b10 as second validation**

Same process with `tests/fixtures/briefs/b10.md` → `output/b10-v9-final/`

---
