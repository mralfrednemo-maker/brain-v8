# **Thinker Platform — Master Design & DOD Document v3.0+**

**Date:** 2026-04-03  
**Status:** FINAL — V3.0 baseline with selected V3.0B improvements  
**Baseline:** V3.0 (DESIGN‑V3.md, DOD‑V3.md, current codebase)  
**Delta Philosophy:** Targeted adoption of V3.0B improvements that address critical failure modes while preserving architectural simplicity, zero‑tolerance determinism, and the existing stable implementation.

---

## **PART 1: DESIGN (V3.0 Foundation + Deltas)**

### **1. Common Sense Reasoning**

**V3.0 Baseline:** Single merged `PreflightAssessment` stage (Gate 1 + CS Audit). Handles admission, modality selection, effort calibration, defect routing, hidden‑context discovery, and assumption surfacing.

#### **Delta 1.1: Retroactive Premise Escalation**
- **What it adds:** Mid‑pipeline safety net without happy‑path latency.
- **How it works:** After R1, scan for `premise_challenge` arguments. If ≥2 models independently flag the same flawed premise, trigger a CS‑Audit re‑run with updated context. Log re‑run results separately.
- **Changes in code:**
  - New module `thinker/premise_escalation.py`
  - Modified `thinker/brain.py` to execute scan after R1
  - Updated `thinker/proof.py` to log `retroactive_premise` field
- **Conflicts with existing:** None – adds a conditional stage; does not modify PreflightAssessment.
- **DOD Acceptance Criteria (Delta):**
  - Scan executes after R1 on all admitted runs.
  - Threshold: ≥2 independent models flagging same premise.
  - When threshold met: CS Audit re‑runs; results logged in `proof.cs_audit_rerun`.
  - When threshold not met: pipeline proceeds normally.

#### **Delta 1.2: Auto‑Reformulation for Reparable Flaws**
- **What it replaces:** V3.0’s NEED_MORE for fixable missing assumptions.
- **How it works:** When PreflightAssessment detects a reparable premise defect (missing but inferable assumption), append the assumption to the brief and proceed. Log original and reformulated briefs.
- **Changes in code:**
  - Modify `thinker/preflight.py` to detect reparable vs. requester‑fixable defects.
  - Add `reformulated_brief` and `original_brief` to `PreflightResult` schema.
- **Conflicts with existing:** Alters defect‑routing logic; must not block admission for reparable flaws.
- **DOD Acceptance Criteria (Delta):**
  - Reparable flaws do NOT produce NEED_MORE.
  - Both briefs logged in `proof.preflight`.
  - Reformulation surfaced in synthesis.

#### **Delta 1.3: Compressed‑Mode Invariants**
- **What it adds:** Five mandatory fields in every SHORT_CIRCUIT model response.
- **How it works:** Even in compressed prompts, each model must include:
  1. Premise check
  2. Confidence basis
  3. Known unknowns
  4. One counter‑consideration
  5. Machine‑readable reason for compression
- **Changes in code:**
  - Update `prompts/round*.j2` for SHORT_CIRCUIT to require these fields.
  - Add validation in `thinker/rounds.py` to check presence.
- **Conflicts with existing:** Adds response‑structure requirement; missing field → ERROR.
- **DOD Acceptance Criteria (Delta):**
  - All 5 invariants present in each SHORT_CIRCUIT model response.
  - Missing any invariant → ERROR.

### **2. Multi‑Aspect Exploration**

**V3.0 Baseline:** Dimension Seeder (pre‑R1, 3‑5 mandatory dimensions), Perspective Cards (R1 structured outputs), Frame‑survival reform (R2 drop requires 3 traceable votes, R3/R4 frames cannot drop), Exploration stress trigger (R1 agreement > 0.75 AND OPEN/HIGH injects seed frames).

#### **Delta 2.1: Virtual Frames**
- **What it sits alongside:** Augments Dimension Seeder; does not replace.
- **How it works:** Pre‑R1 Sonnet call generates 3‑5 alternative frames (INVERSION, STAKEHOLDER, etc.). These are **NOT** injected into R1 prompts (preserving independence) but are fed to the Divergent Framing Pass to guarantee frame diversity even if R1 converges.
- **Changes in code:**
  - New module `thinker/virtual_frames.py`
  - Modified `thinker/divergent_framing.py` to accept virtual frames as input.
  - Updated `thinker/proof.py` to log `virtual_frames`.
- **Conflicts with existing:** Coexists with Dimension Seeder; no conflict.
- **DOD Acceptance Criteria (Delta):**
  - Virtual‑frame seeder executes after CS Audit, before R1.
  - Generates 3‑5 frames; fewer than 3 → ERROR.
  - Frames NOT injected into R1 model prompts.
  - Frames ARE available to Divergent Framing Pass.

#### **Delta 2.2: R1 Space‑Mapping Format**
- **What it adds:** Structured R1 output format.
- **How it works:** Every R1 model response must include:
  - Viable options enumerated
  - A declared lean (preferred option)
  - Evidence needed to switch from that lean
- **Changes in code:**
  - Update `prompts/round1.j2` to require space‑mapping format.
  - Modify response extraction to validate presence.
- **Conflicts with existing:** Changes expected R1 output structure; must be backward compatible during transition.
- **DOD Acceptance Criteria (Delta):**
  - All 3 space‑mapping fields present in each R1 response.
  - Missing fields → ERROR.

#### **Delta 2.3: Breadth‑Recovery Pulse**
- **What it adds:** Prevents premature narrowing of deliberation.
- **How it works:** After R2, if >40% of R1 arguments are IGNORED, inject recovery prompt into R3: “Address at least 2 of the following ignored arguments before proceeding.”
- **Changes in code:**
  - New module `thinker/breadth_recovery.py`
  - Modified `thinker/brain.py` to evaluate after R2 and conditionally inject.
  - Updated `thinker/proof.py` to log `breadth_recovery`.
- **Conflicts with existing:** Adds a conditional stage; no conflict.
- **DOD Acceptance Criteria (Delta):**
  - Evaluated after R2 on all admitted runs.
  - Threshold: >40% of R1 arguments have status IGNORED in R2.
  - When triggered: R3 prompt includes specific ignored‑argument IDs.

#### **Delta 2.4: Calibrated Anti‑Groupthink Search**
- **What it adds:** Adversarial search when consensus appears suspicious.
- **How it works:** When R1 agreement_ratio > 0.80 AND (question_class = OPEN OR stakes_class = HIGH), trigger one adversarial search query specifically looking for evidence that disproves/weakens the consensus.
- **Changes in code:**
  - New module `thinker/anti_groupthink.py`
  - Modified `thinker/brain.py` to evaluate after R1 and conditionally issue query.
  - Updated `proof.search_log` with provenance `anti_groupthink`.
- **Conflicts with existing:** Adds a conditional search query; must respect search‑budget caps.
- **DOD Acceptance Criteria (Delta):**
  - Evaluated after R1.
  - When triggered: exactly one adversarial search query issued.
  - Query logged with provenance `anti_groupthink`.

#### **Delta 2.5: Frame‑Argument Coupling**
- **What it adds:** Prevents frames from decaying when their arguments are ignored.
- **How it works:** If arguments belonging to a frame are systematically ignored for ≥2 rounds, re‑activate that frame (bump from CONTESTED back to ACTIVE).
- **Changes in code:**
  - Modify `thinker/divergent_framing.py` to track argument‑frame links and monitor ignored arguments.
  - Update frame‑survival logic to re‑activate coupled frames.
- **Conflicts with existing:** Adds stateful tracking; must integrate with existing frame‑survival rules.
- **DOD Acceptance Criteria (Delta):**
  - Frame‑argument links tracked.
  - After ≥2 rounds of ignored arguments, frame re‑activated.
  - Activation logged in `proof.divergence.coupling_activations`.

#### **Delta 2.6: Moderated Frame Rebuttal**
- **What it adds:** Ensures leading frames are challenged.
- **How it works:** In R2, at least one surviving model must explicitly test the leading frame with a rebuttal before supporting the majority position.
- **Changes in code:**
  - Update `prompts/round2.j2` to include rebuttal obligation.
  - Modify `thinker/divergent_framing.py` to validate rebuttal presence.
- **Conflicts with existing:** Adds a prompt‑level obligation; missing rebuttal → ESCALATE.
- **DOD Acceptance Criteria (Delta):**
  - Each leading frame (by adoption count) must receive at least one explicit rebuttal in R2.
  - Missing rebuttal → ESCALATE (Gate 2 rule D10).

### **3. Pipeline Gap Fixes**

**V3.0 Baseline:** Two‑tier evidence ledger (active + archive), synthesis blindness fix (controller‑curated packet), semantic contradiction detection, argument resolution status, search auditability, residue verification depth, Gate 2 stability tests.

#### **Delta 3.1: Claim‑Aware Pinning + Budget Discipline + Forensic Logging**
- **What it replaces:** Two‑tier ledger eviction logic.
- **How it works:**
  1. **Claim‑aware pinning:** Pin at claim‑contradiction unit level. Evidence involved in OPEN contradictions or active blockers cannot be evicted until resolved.
  2. **Budget discipline:** Hard cap = 15% of context window reserved for pinned items. Max 5 pinned claims. Pin decay only on resolution/supersession/explicit archival.
  3. **Forensic logging:** Every eviction logged with contradiction linkage and severity.
- **Changes in code:**
  - Rewrite `thinker/evidence_ledger.py` to implement pinning.
  - New module `thinker/pin_cap.py` to manage 15% budget.
  - Updated `thinker/proof.py` with `evidence_pinning`, `pin_cap`, `evicted_evidence`.
- **Conflicts with existing:** Replaces score‑based eviction; requires canonical entity IDs (Delta 3.2).
- **DOD Acceptance Criteria (Delta):**
  - Evidence pinned at claim‑contradiction unit level.
  - 15% context budget measured proactively (before prompt assembly).
  - 10% safety margin triggers fallbacks.
  - Max 5 pinned claims; overflow triggers forced archival of lowest‑severity pin + WARNING.
  - Every eviction logged with contradiction linkage.
  - HIGH‑severity evictions count as unresolved for Gate 2.

#### **Delta 3.2: Canonical Cross‑Round Entity IDs**
- **What it replaces:** Fuzzy semantic matching in Position/Argument Tracker.
- **How it works:** Assign deterministic IDs at Gate 1/R1:
  - `claim_{topic}_{nn}` for claims
  - `arg_{round}_{nn}` for arguments
  - `frame_{nn}` for frames
  - `blk_{nn}` for blockers
  - `evidence_binding_{nn}` for claim‑to‑evidence links
- **Changes in code:**
  - New module `thinker/entity_registry.py`
  - Modify `thinker/argument_tracker.py`, `thinker/position_tracker.py`, `thinker/divergent_framing.py`, `thinker/evidence_ledger.py` to use canonical IDs.
  - Update `thinker/proof.py` with `entity_registry` map.
- **Conflicts with existing:** All cross‑round references become ID‑based; fuzzy matching removed.
- **DOD Acceptance Criteria (Delta):**
  - All entities in proof.json have valid canonical IDs.
  - Every cross‑round reference uses canonical IDs (no free‑text references without ID).
  - Dangling references produce WARNING (not ERROR).
  - ID collisions resolved with lineage tags.

#### **Delta 3.3: Argument Auto‑Promotion**
- **What it adds:** Prevents important arguments from being silently ignored.
- **How it works:** An argument unaddressed (MENTIONED or IGNORED) for ≥2 consecutive rounds → automatically promoted to `critical: true`. Deterministic rule, no LLM call. Gated by CS Audit’s `question_class` (applies only to OPEN/AMBIGUOUS questions).
- **Changes in code:**
  - Modify `thinker/argument_tracker.py` to track ignored rounds and auto‑promote.
  - Update argument schema with `critical` and `auto_promoted` flags.
- **Conflicts with existing:** Adds stateful tracking; must not conflict with existing resolution status.
- **DOD Acceptance Criteria (Delta):**
  - Auto‑promotion activates after 2 consecutive rounds of IGNORED/MENTIONED status.
  - Promotion gated by `question_class` in {OPEN, AMBIGUOUS}.
  - Promoted arguments marked `critical: true`.

#### **Delta 3.4: Synthesis with Full Deliberation Arc**
- **What it adds:** Synthesis prompt receives not just R4 outputs but a curated arc of how consensus formed.
- **How it works:** Synthesis packet includes:
  - One‑line R1 position per model (from Position Tracker)
  - Argument evolution summary (from Argument Tracker)
  - Frame lifecycle (from Divergent Framing Pass)
- **Changes in code:**
  - Modify `thinker/synthesis_packet.py` to include deliberation‑arc data.
  - Update `thinker/synthesis.py` to use expanded packet.
- **Conflicts with existing:** Synthesis packet schema expands; backward compatibility maintained.
- **DOD Acceptance Criteria (Delta):**
  - Synthesis packet includes R1 position summaries, argument evolution, and frame lifecycle.
  - Synthesis report describes how consensus formed, not just what it concluded.

#### **Delta 3.5: Residue Violation Blocks DECIDE**
- **What it adds:** Explicit Gate 2 rule for omission violations.
- **How it works:** New Gate 2 rule D13: if `residue.threshold_violation` is True → ESCALATE. Starting threshold: 25% omissions.
- **Changes in code:**
  - Modify `thinker/gate2.py` to add rule D13.
  - Update `thinker/residue.py` to compute `threshold_violation`.
- **Conflicts with existing:** Adds a new DECIDE rule; must be ordered after other ESCALATE rules.
- **DOD Acceptance Criteria (Delta):**
  - `residue.threshold_violation` computed (omission_rate > 25%).
  - If True → ESCALATE (D13).

#### **Delta 3.6: Capped Semantic Contradiction Detection**
- **What it modifies:** Adds a call cap and soft‑signal effect.
- **How it works:**
  - Max 5 Sonnet calls per search phase (feature‑flaggable).
  - Unresolved semantic contradictions lower effective agreement_ratio threshold by 0.05 each for Gate 2 rules D4/D5.
- **Changes in code:**
  - Modify `thinker/semantic_contradiction.py` to enforce call cap.
  - Update `thinker/gate2.py` to apply threshold adjustment.
- **Conflicts with existing:** Adds a configurable cap; existing uncapped implementation must be updated.
- **DOD Acceptance Criteria (Delta):**
  - Semantic calls capped at 5 per search phase.
  - Unresolved semantic contradictions lower agreement threshold by 0.05 each.

#### **Delta 3.7: Paywall Detection**
- **What it adds:** Skip extraction for paywalled pages.
- **How it works:** Before extraction, string‑match fetched pages for paywall phrases (“subscribe”, “premium”, etc.). If >30% match → mark PAYWALLED, skip extraction, log in search_log.
- **Changes in code:**
  - Modify `thinker/page_fetch.py` to run paywall detection.
  - Update `thinker/search_log` entry with `paywall_detected: true`.
- **Conflicts with existing:** Adds a pre‑extraction filter; may reduce evidence yield.
- **DOD Acceptance Criteria (Delta):**
  - Paywall detection runs before extraction.
  - Paywalled pages skipped; extraction not attempted.
  - Logged in search_log with `paywall_detected: true`.

#### **Delta 3.8: Evidence Quality Floor**
- **What it adds:** Minimum average evidence score for DECIDE.
- **How it works:** Gate 2 rule D7 enhanced: require average evidence score ≥ 2.0 (configurable). Below threshold → ESCALATE.
- **Changes in code:**
  - Modify `thinker/evidence_ledger.py` to compute average score.
  - Update `thinker/gate2.py` rule D7 to include score check.
- **Conflicts with existing:** Adds a new requirement; may increase ESCALATE rate.
- **DOD Acceptance Criteria (Delta):**
  - Average evidence score computed and recorded.
  - Score < 2.0 on DECIDE run → ESCALATE (D7).

#### **Delta 3.9: Three‑Tier Failure Taxonomy**
- **What it replaces:** V3.0’s binary failure handling.
- **How it works:**
  - **ERROR:** Infrastructure and integrity only (LLM/search unavailable, missing stage, unparseable output).
  - **ESCALATE:** Mechanism failures (pin cap reached, insufficient evidence, unresolved CRITICAL blocker).
  - **WARNING:** Suboptimal conditions (low diversity score, high eviction rate) – logged but do not alter outcome.
- **Changes in code:**
  - Modify `thinker/brain.py` and `thinker/gate2.py` to classify failures per taxonomy.
  - Add `proof.warnings[]` array.
- **Conflicts with existing:** Reclassifies some previously ERROR conditions as ESCALATE/WARNING.
- **DOD Acceptance Criteria (Delta):**
  - Every failure condition maps to exactly one tier.
  - WARNING events logged in `proof.warnings[]` and do NOT alter outcome.
  - ERROR only for infrastructure/fatal integrity.

### **4. ANALYSIS Mode**

**V3.0 Baseline:** Shared pipeline, modified round prompts (exploration‑focused), ANALYSIS Gate 2 rules (A1‑A7), proof.json additions (analysis_map, analysis_debug), implementation staging.

#### **Delta 4.1: Dimension Tracker**
- **What it replaces:** Position Tracker for ANALYSIS.
- **How it works:** After each round, Sonnet extracts analytical dimensions bottom‑up from model outputs. Tracks coverage status, cross‑dimension interactions.
- **Changes in code:**
  - New module `thinker/dimension_tracker.py`
  - Replace Position Tracker with Dimension Tracker in ANALYSIS mode.
  - Update `thinker/proof.py` with `dimension_tracker` field.
- **Conflicts with existing:** Position Tracker still runs diagnostically; replaced as primary driver for ANALYSIS.
- **DOD Acceptance Criteria (Delta):**
  - Dimension Tracker executes after each round in ANALYSIS.
  - Tracks coverage status per dimension.
  - `dimension_coverage_score` computed.

#### **Delta 4.2: Information Boundary Classification**
- **What it adds:** Distinguishes evidenced vs. speculative claims.
- **How it works:** After each round, Sonnet classifies each claim extractively:
  - **EVIDENCED:** direct citation to evidence.
  - **EXTRAPOLATED:** inferred from evidence but not directly stated.
  - **INFERRED:** no evidence backing.
- **Changes in code:**
  - New module `thinker/information_boundary.py`
  - Integrated into ANALYSIS pipeline after each round.
  - Update `proof.json` with `information_boundary` field.
- **Conflicts with existing:** Adds Sonnet calls per round; increases token cost.
- **DOD Acceptance Criteria (Delta):**
  - Classification is extractive (Sonnet), NOT self‑tagged by models.
  - Every claim classified; classifications recorded in proof.

#### **Delta 4.3: Simplified Gate 2 Rules**
- **What it replaces:** V3.0’s A1‑A7 with A1‑A3.
- **How it works:**
  - **A1:** `dimension_coverage < 0.80` → ESCALATE
  - **A2:** `residue.threshold_violation = true` → ESCALATE
  - **A3:** Otherwise → ANALYSIS
- **Changes in code:**
  - Modify `thinker/gate2.py` ANALYSIS rule set.
- **Conflicts with existing:** Removes evidence‑presence and argument‑count checks; must ensure coverage threshold is sufficient.
- **DOD Acceptance Criteria (Delta):**
  - Only 3 rules evaluated for ANALYSIS.
  - Dimension coverage threshold = 0.80 (configurable).

#### **Delta 4.4: ANALYSIS Semantic Contradiction Tracking**
- **What it adds:** Semantic contradictions marked `track_only: true` in ANALYSIS, bypassing Gate 2 blocker logic.
- **How it works:** In ANALYSIS mode, semantic contradictions are recorded for completeness but do NOT trigger ESCALATE.
- **Changes in code:**
  - Modify `thinker/semantic_contradiction.py` to set `track_only` flag in ANALYSIS.
  - Update `thinker/gate2.py` to ignore `track_only` contradictions.
- **Conflicts with existing:** Contradiction handling differs by modality.
- **DOD Acceptance Criteria (Delta):**
  - ANALYSIS semantic contradictions marked `track_only: true`.
  - `track_only` contradictions do NOT affect Gate 2.

---

## **PART 2: DOD (V3.0 Foundation + Delta Updates)**

### **1. Authoritative Outcome Contract**

**V3.0 Baseline:** Allowed outcomes: DECIDE, ESCALATE, NO_CONSENSUS, ANALYSIS, NEED_MORE, ERROR. Fixed topology 4→3→2→2. ERROR for infrastructure/fatal integrity only.

**Delta Updates:**
- **Three‑Tier Failure Taxonomy:** ERROR (infrastructure/integrity), ESCALATE (mechanism failures), WARNING (suboptimal conditions). WARNING logged in `proof.warnings[]`, no outcome change.
- **Schema Versioning:** `proof.schema_version` = `"3.0+"`. New fields optional during transition (first 10 runs), then mandatory.
- **Acceptance Criteria:**
  - Every failure condition maps to exactly one tier.
  - `proof.warnings[]` exists and captures WARNING‑tier events.
  - `proof.schema_version` present and correct.
  - V3.0 proof files parse without ERROR under V3.0+ code (backward compatibility).

### **2. PreflightAssessment**

**V3.0 Baseline:** Single merged stage; defect routing; admission guards.

**Delta Updates:**
- **Auto‑Reformulation:** Reparable flaws do NOT produce NEED_MORE; both original and reformulated briefs logged in `proof.preflight`.
- **Retroactive Premise Escalation:** Post‑R1 scan for premise challenges; ≥2 independent flags trigger CS‑Audit re‑run. Logged in `proof.retroactive_premise`.
- **Acceptance Criteria:**
  - Reparable flaws logged and reformulated; no NEED_MORE.
  - Retroactive scan executed after R1; threshold met triggers re‑run.
  - Re‑run results logged separately.

### **3. Effort Policy and SHORT_CIRCUIT**

**V3.0 Baseline:** SHORT_CIRCUIT preserves topology; high‑authority evidence required when search_scope ≠ NONE.

**Delta Updates:**
- **Compressed‑Mode Invariants:** SHORT_CIRCUIT responses must contain 5 fields: premise check, confidence basis, known unknowns, one counter‑consideration, machine‑readable compression reason.
- **Acceptance Criteria:**
  - All 5 invariants present in each SHORT_CIRCUIT model response.
  - Missing any invariant → ERROR.

### **4. Dimension Seeder**

**V3.0 Baseline:** 3‑5 mandatory dimensions; zero‑coverage → COVERAGE_GAP blocker.

**Delta Updates:**
- **Virtual Frames:** Generated pre‑R1 (3‑5 frames), NOT injected into R1 prompts, fed to Divergent Framing Pass.
- **Acceptance Criteria:**
  - Virtual‑frame seeder executes after CS Audit, before R1.
  - Generates 3‑5 frames; fewer → ERROR.
  - Frames not injected into R1 prompts.
  - Frames available to Divergent Framing Pass.

### **5. Perspective Cards (R1)**

**V3.0 Baseline:** 4 R1 cards with 5 structured fields each.

**Delta Updates:**
- **R1 Space‑Mapping Format:** Each R1 response must include viable options, declared lean, evidence needed to switch.
- **Acceptance Criteria:**
  - All 3 space‑mapping fields present in each R1 response.
  - Missing fields → ERROR.

### **6. Divergent Framing Pass and Frame Survival**

**V3.0 Baseline:** R2 drop requires 3 traceable votes; R3/R4 frames cannot drop (CONTESTED).

**Delta Updates:**
- **Breadth‑Recovery Pulse:** Evaluated after R2; >40% R1 arguments IGNORED triggers injection into R3.
- **Frame‑Argument Coupling:** If arguments belonging to a frame ignored ≥2 rounds, re‑activate frame.
- **Moderated Frame Rebuttal:** In R2, at least one model must rebut the leading frame before supporting majority.
- **Calibrated Anti‑Groupthink Search:** R1 agreement_ratio > 0.80 AND (OPEN OR HIGH) triggers adversarial search query.
- **Acceptance Criteria:**
  - Breadth‑recovery threshold: >40% IGNORED.
  - Frame‑argument coupling tracked and activated.
  - Leading frame rebuttal present in R2; missing → ESCALATE.
  - Anti‑groupthink search triggered when conditions met; query issued and logged.

### **7. Search, Provenance, and Ungrounded Stats**

**V3.0 Baseline:** Search log with provenance; ungrounded stat detector after R1/R2.

**Delta Updates:**
- **Paywall Detection:** Pages with >30% paywall phrases skipped; logged with `paywall_detected: true`.
- **Evidence Quality Floor:** Average evidence score ≥ 2.0 for DECIDE.
- **Acceptance Criteria:**
  - Paywall detection runs before extraction; paywalled pages skipped.
  - Average evidence score computed; < 2.0 → ESCALATE (D7).

### **8. Evidence Ledger**

**V3.0 Baseline:** Two‑tier (active + archive); eviction logged.

**Delta Updates (Replacement):**
- **Claim‑Aware Pinning:** Evidence pinned at claim‑contradiction unit level. 15% context cap. Max 5 pinned claims. Pin decay only on resolution.
- **Forensic Logging:** Every eviction logged with contradiction linkage. HIGH‑severity evictions count as unresolved.
- **Acceptance Criteria:**
  - Pinning operates at claim‑contradiction level.
  - 15% context budget measured proactively; 10% safety margin.
  - Max 5 pinned claims; overflow triggers forced archival.
  - Every eviction logged; HIGH‑severity evictions affect Gate 2.

### **9. Canonical Cross‑Round Entity IDs**

**New Section (V3.0B Delta):**
- **Purpose:** Foundational deterministic lineage.
- **ID Format:** `claim_{topic}_{nn}`, `arg_{round}_{nn}`, `frame_{nn}`, `blk_{nn}`, `evidence_binding_{nn}`.
- **Entity Registry:** `proof.entity_registry` maps IDs to objects.
- **Collision Handling:** Dangling references → WARNING; collisions disambiguated with lineage tags.
- **Acceptance Criteria:**
  - All entities have canonical IDs.
  - Cross‑round references use IDs.
  - Dangling references produce WARNING.
  - No unresolved ID collisions.

### **10. Argument Tracker and Resolution Status**

**V3.0 Baseline:** Resolution status (ORIGINAL/REFINED/SUPERSEDED).

**Delta Updates:**
- **Argument Auto‑Promotion:** After 2 consecutive rounds IGNORED/MENTIONED, argument promoted to `critical: true` (gated by question_class OPEN/AMBIGUOUS).
- **Acceptance Criteria:**
  - Auto‑promotion activates when conditions met.
  - Promoted arguments marked `critical: true`.

### **11. Synthesis Packet and Residue Verification**

**V3.0 Baseline:** Controller‑curated packet; structured dispositions.

**Delta Updates:**
- **Full Deliberation Arc:** Packet includes R1 position summaries, argument evolution, frame lifecycle.
- **Residue Violation Rule:** New Gate 2 rule D13: `residue.threshold_violation = true` → ESCALATE (threshold = 25% omissions).
- **Acceptance Criteria:**
  - Synthesis packet includes deliberation‑arc data.
  - `residue.threshold_violation` computed; if True → ESCALATE.

### **12. Gate 2 — DECIDE Rules**

**V3.0 Baseline:** D1‑D14.

**Delta Updates:**
- **New Rule D13:** `residue.threshold_violation = true` → ESCALATE.
- **Rule D7 Enhanced:** Includes evidence‑quality floor (average score < 2.0 → ESCALATE).
- **Semantic Contradiction Soft Signal:** Unresolved semantic contradictions lower effective agreement threshold by 0.05 each for D4/D5.
- **Pin‑Cap Rule:** If pin budget >15% at Gate 2 evaluation → ESCALATE (new rule D15).
- **Rule Order:** D1‑D15 (with D13 and D15 inserted appropriately).
- **Acceptance Criteria:**
  - Rule D13 fires when omission rate > 25%.
  - Rule D7 fires when average evidence score < 2.0.
  - Semantic adjustments applied to agreement thresholds.
  - Pin‑cap breach triggers ESCALATE.

### **13. Gate 2 — ANALYSIS Rules**

**V3.0 Baseline:** A1‑A7.

**Delta Updates (Replacement):**
- **Simplified Rules:** A1‑A3 only:
  - **A1:** `dimension_coverage < 0.80` → ESCALATE
  - **A2:** `residue.threshold_violation = true` → ESCALATE
  - **A3:** Otherwise → ANALYSIS
- **Semantic Contradictions:** Marked `track_only: true`; bypass Gate 2 blocker logic.
- **Acceptance Criteria:**
  - Only 3 rules evaluated.
  - Dimension coverage threshold = 0.80.
  - Semantic contradictions do NOT trigger ESCALATE.

### **14. ANALYSIS Mode Contract**

**V3.0 Baseline:** Shared pipeline, modified prompts, analysis_map.

**Delta Updates:**
- **Dimension Tracker:** Replaces Position Tracker as primary driver.
- **Information Boundary Classification:** Claims classified extractively as EVIDENCED/EXTRAPOLATED/INFERRED.
- **Coverage Assessment:** `proof.coverage_assessment` with status COMPREHENSIVE/PARTIAL/GAPPED.
- **Acceptance Criteria:**
  - Dimension Tracker executes in ANALYSIS.
  - Information boundary classification is extractive (Sonnet).
  - Coverage assessment recorded.

### **15. Proof.json Extensions**

**New Section (V3.0B Deltas):**
- **New Fields:**
  - `reasoning_contract`: effort tier, modality, compression status.
  - `premise_defect_log`: original and reformulated briefs.
  - `outcome_confidence`: weighted aggregate of agreement, evidence quality, etc.
  - `evicted_evidence`: content and contradiction linkage.
  - `coverage_assessment`: ANALYSIS coverage status.
  - `warnings`: WARNING‑tier events.
  - `entity_registry`: canonical ID map.
  - `pin_cap`: pin‑budget tracking.
  - `telemetry_hooks`: configurable thresholds.
- **Acceptance Criteria:**
  - All new fields present per their required conditions.
  - Thresholds configurable via config.yaml and recorded in telemetry_hooks.

### **16. Verification and Test Suite**

**Updated Test Matrix (Selected Deltas):**
1. Retroactive premise escalation triggers CS‑Audit re‑run when ≥2 models flag same premise.
2. Virtual frames generated (3‑5) and not injected into R1.
3. Breadth‑recovery pulse triggers when >40% R1 arguments ignored.
4. Anti‑groupthink search triggers when agreement > 0.80 on OPEN/HIGH.
5. Frame‑argument coupling re‑activates ignored frames.
6. Moderated frame rebuttal present in R2.
7. Claim‑aware pinning prevents eviction of pinned evidence.
8. 15% pin budget enforced; breach → ESCALATE.
9. Canonical entity IDs used for all cross‑round references.
10. Argument auto‑promotion after 2 rounds ignored.
11. Residue violation >25% triggers ESCALATE (D13).
12. Evidence quality floor (average score < 2.0) triggers ESCALATE (D7).
13. Paywall detection skips extraction for paywalled pages.
14. ANALYSIS dimension coverage < 0.80 triggers ESCALATE (A1).
15. INFORMATION boundary classification is extractive.

### **17. Failure‑Mode Matrix (Consolidated)**

| Mechanism | Failure | Tier | Outcome |
|-----------|---------|------|---------|
| PreflightAssessment | missing/unparseable | ERROR | ERROR |
| CS Audit | requester‑fixable admitted | ERROR | ERROR |
| Retroactive Premise | scan skipped | ERROR | ERROR |
| SHORT_CIRCUIT | compressed invariant missing | ERROR | ERROR |
| Virtual Frames | missing / <3 frames | ERROR | ERROR |
| Breadth Recovery | trigger met, no injection | ERROR | ERROR |
| Anti‑Groupthink | trigger met, no query | ERROR | ERROR |
| Frame Rebuttal | leading frame not rebutted | ESCALATE | ESCALATE |
| Evidence Pinning | budget >15% at prompt assembly | ESCALATE | ESCALATE |
| Entity IDs | unresolved collision | ERROR | ERROR |
| Argument Auto‑Promotion | not applied when conditions met | ERROR | ERROR |
| Residue Verification | threshold_violation = true | ESCALATE | ESCALATE |
| Evidence Quality | average score < 2.0 on DECIDE | ESCALATE | ESCALATE |
| ANALYSIS Coverage | dimension_coverage < 0.80 | ESCALATE | ESCALATE |
| WARNING Events | any | WARNING | logged, no outcome change |

---

## **Implementation Staging Plan**

1. **Phase 1 (Foundation):** Canonical Entity IDs, Entity Registry. Required for multiple deltas.
2. **Phase 2 (Evidence):** Claim‑aware pinning, forensic logging, pin‑cap management.
3. **Phase 3 (Exploration):** Virtual Frames, Breadth‑Recovery Pulse, Anti‑Groupthink Search, Frame‑Argument Coupling, Moderated Frame Rebuttal.
4. **Phase 4 (Safety):** Retroactive Premise Escalation, Auto‑Reformulation, Compressed‑Mode Invariants.
5. **Phase 5 (ANALYSIS):** Dimension Tracker, Information Boundary Classification, Simplified Gate 2.
6. **Phase 6 (Polish):** Three‑Tier Taxonomy, Proof Extensions, Telemetry Hooks.

Each phase includes:
- Code changes per delta description.
- Schema migration with backward‑compatibility window.
- Test updates per acceptance criteria.
- Operational monitoring for threshold tuning.

---

## **Summary of Selected V3.0B Deltas**

| Delta | V3.0 Equivalent | Strength | Implementation Priority |
|-------|----------------|----------|------------------------|
| Retroactive Premise Escalation | Single‑pass Preflight | Catches missed defects without latency | Medium |
| Virtual Frames | Dimension Seeder only | Guarantees frame diversity without R1 injection | Medium |
| Breadth‑Recovery Pulse | None | Prevents premature narrowing | Low |
| Anti‑Groupthink Search | None | Addresses suspicious consensus | Low |
| Frame‑Argument Coupling | Frame survival only | Keeps frames alive when arguments ignored | Low |
| Moderated Frame Rebuttal | None | Ensures leading frames challenged | Low |
| Claim‑Aware Pinning | Two‑tier ledger | Prevents orphaned contradictions with budget discipline | High |
| Canonical Entity IDs | Fuzzy matching | Foundational for lineage and pinning | High |
| Argument Auto‑Promotion | None | Prevents silent argument death | Medium |
| Residue Violation Rule | None | Explicit ESCALATE for omission violations | Medium |
| Evidence Quality Floor | None | Minimum evidence quality for DECIDE | Medium |
| Paywall Detection | None | Skips paywalled pages | Low |
| Three‑Tier Taxonomy | Binary failure handling | Better operational observability | Medium |
| ANALYSIS Dimension Tracker | Position Tracker | Better fit for exploratory mapping | High |
| INFORMATION Boundary Classification | None | Distinguishes evidenced vs. speculative claims | Medium |
| Simplified ANALYSIS Gate 2 | A1‑A7 | Fewer rules, coverage‑focused | Medium |

**Non‑selected V3.0B features:** Rotating Adversarial Role (overhead), Distant‑Domain Analogical Queries (optional, low value), Concurrent Mechanism Budget (complexity), Stakeholder Perspectives (conflicts with existing R1 roles), Auto‑Reformulation as separate stage (already integrated), Gate 1/CS Audit split (preserve merged Preflight for simplicity).

---

**Final Status:** This Master Design & DOD document represents V3.0 baseline with selected V3.0B improvements. All deltas are backward‑compatible where possible and staged to minimize integration risk. The resulting platform maintains fixed topology, zero‑tolerance for infrastructure failures, and deterministic Gate 2 while addressing key failure modes in exploration, evidence management, and auditability.