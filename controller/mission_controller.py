#!/usr/bin/env python3
"""
mission_controller.py — Unified orchestrator for Brain V3 + Chamber V11.

Rev 5 — Authority always from brief classification. Discrepancy is diagnostic
only (recorded on proof, never drives authority). Chamber import configurable.
Option injection documented as conservative heuristic.

Authority rules (simple, no exceptions):
  brain mode     → Brain authority
  chamber mode   → Chamber authority
  cascade mode   → Chamber authority (Brain is structured input)
  parallel mode  → brief_type determines: truth_seeking→Brain, else→Chamber

Discrepancy in parallel mode is recorded on the mission proof for operator
review. It does NOT influence authority selection — that would require the
comparator to be stronger than the engines it compares, which it is not.

Usage:
  python3 mission_controller.py --brief /path/to/brief.md
  python3 mission_controller.py --brief /path/to/brief.md --mode parallel
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# Configuration — all paths configurable via environment
# ═══════════════════════════════════════════════════════════════════════════

BRAIN_SCRIPT = Path(os.environ.get(
    "BRAIN_SCRIPT_PATH",
    str(Path(__file__).parent / "brain-v3-orchestrator.py"),
))
CHAMBER_MODULE_DIR = Path(os.environ.get(
    "CHAMBER_MODULE_DIR",
    str(Path(__file__).parent),
))
CHAMBER_MODULE_NAME = os.environ.get("CHAMBER_MODULE_NAME", "consensus_runner_v3")

BRAIN_DEFAULT_ROUNDS = 3
BRAIN_DEFAULT_BUDGET = 3600
REPORTS_DIR = Path(os.environ.get(
    "MISSION_REPORTS_DIR",
    str(Path(__file__).parent / "reports"),
))
MISSION_PROOF_SCHEMA = "1.0"


# ═══════════════════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════════════════

class ControllerLog:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Mission Controller started: {datetime.now().isoformat()}\n\n", encoding="utf-8")

    def log(self, msg: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def close(self) -> None:
        self.log("Controller log closed.")


# ═══════════════════════════════════════════════════════════════════════════
# Brief Classification
# ═══════════════════════════════════════════════════════════════════════════

_BRAIN_SIGNALS = [
    r'\bCVE-\d{4}-\d{4,7}\b',
    r'\b(?:vulnerability|exploit|breach|incident)\b',
    r'\b(?:true|false|fact|factual|verify|validate|confirm)\b',
    r'\b(?:consensus|agree|disagree|converge|diverge)\b',
    r'\b(?:determine|assess|evaluate|judge|adjudicate)\b',
    r'\b(?:what happened|root cause|timeline|forensic)\b',
    r'\b(?:compliance|audit|regulatory)\b',
    r'\b(?:risk assessment|threat assessment|impact analysis)\b',
]

_CHAMBER_SIGNALS = [
    r'\b(?:choose between|pick one|select one|which option|which should)\b',
    r'\b(?:option [a-d]|alternative [a-d]|choice [a-d])\b',
    r'\b(?:portfolio|allocat|rebalance|weight)\b',
    r'\b(?:recommend|recommendation|proposal|propose)\b',
    r'\b(?:top \d+|rank|ranking|prioritize|priority)\b',
    r'\b(?:mutually exclusive|either.*or|one of the following)\b',
    r'\b(?:vendor selection|tool selection|platform selection)\b',
    r'\b(?:what should we do|action plan|next steps|implementation)\b',
    r'\b(?:buy|sell|hold|invest|divest|acquire)\b',
]

_HYBRID_SIGNALS = [
    r'\b(?:evaluate.*and.*recommend)\b',
    r'\b(?:assess.*then.*decide)\b',
    r'\b(?:analyze.*and.*choose)\b',
]

_HIGH_STAKES_SIGNALS = [
    r'\b(?:active exploit|active attack|confirmed breach|ongoing incident)\b',
    r'\b(?:0[- ]?day|zero[- ]?day)\b',
    r'\b(?:critical|emergency|immediate action|urgent)\b',
    r'\b(?:revenue at risk|business continuity|existential)\b',
]

_EXCLUSIVE_CHOICE_SIGNALS = [
    r'\b(?:choose between|pick one|select one|mutually exclusive)\b',
    r'\b(?:either\s+.*\s+or)\b',
    r'\b(?:one of the following)\b',
    r'\bcannot run two\b',
    r'\bpick one\b',
]

_BRIEF_NATIVE_OPTION_PATTERNS = [
    r'\boption [a-d]\b',
    r'\balternative [a-d]\b',
    r'\bchoice [a-d]\b',
    r'\boption \d\b',
    r'\b(?:option|alternative) (?:one|two|three|four)\b',
    r'(?:^|\n)\s*(?:option|alternative)\s+[a-d1-4]\s*[:\-\.]',
]


def _brief_has_explicit_options(brief: str) -> bool:
    """Conservative heuristic: detect whether the brief lists explicit named options.

    This is a pattern-based detector, not proof of true brief-native status.
    It can miss legitimate user-listed options that use unconventional formatting.
    When in doubt, it returns False (safer to NOT inject than to over-constrain Chamber).
    """
    brief_lower = brief.lower()
    return any(re.search(pat, brief_lower, re.MULTILINE) for pat in _BRIEF_NATIVE_OPTION_PATTERNS)


def _brief_has_exclusive_choice_shape(brief: str) -> bool:
    brief_lower = brief.lower()
    return any(re.search(pat, brief_lower) for pat in _EXCLUSIVE_CHOICE_SIGNALS)


def classify_brief(brief: str, log: ControllerLog) -> dict:
    """Classify a brief. Returns dict with brief_type, recommended_mode, etc.

    This classification is the SOLE input to authority selection. It is stored
    on the mission proof and used by _assign_final_authority regardless of
    execution mode or discrepancy results.
    """
    brief_lower = brief.lower()

    brain_hits = []
    for pat in _BRAIN_SIGNALS:
        brain_hits.extend(re.findall(pat, brief_lower))
    chamber_hits = []
    for pat in _CHAMBER_SIGNALS:
        chamber_hits.extend(re.findall(pat, brief_lower))
    hybrid_hits = []
    for pat in _HYBRID_SIGNALS:
        hybrid_hits.extend(re.findall(pat, brief_lower))
    high_stakes_hits = []
    for pat in _HIGH_STAKES_SIGNALS:
        high_stakes_hits.extend(re.findall(pat, brief_lower))

    brain_score = len(set(brain_hits))
    chamber_score = len(set(chamber_hits))
    hybrid_score = len(set(hybrid_hits))
    is_high_stakes = len(set(high_stakes_hits)) >= 1
    has_explicit = _brief_has_explicit_options(brief)
    is_exclusive = _brief_has_exclusive_choice_shape(brief)

    log.log(f"[CLASSIFY] Brain={brain_score} Chamber={chamber_score} Hybrid={hybrid_score} "
            f"HighStakes={is_high_stakes} ExplicitOpts={has_explicit} Exclusive={is_exclusive}")

    # Brief type
    if brain_score >= 2 and chamber_score <= 1 and hybrid_score == 0:
        brief_type = "truth_seeking"
    elif chamber_score >= 2 and brain_score <= 1 and hybrid_score == 0:
        brief_type = "recommendation_seeking"
    elif hybrid_score > 0 or (brain_score >= 2 and chamber_score >= 2):
        brief_type = "hybrid"
    elif brain_score > chamber_score:
        brief_type = "truth_seeking"
    else:
        brief_type = "recommendation_seeking"

    # Recommended execution mode
    #
    # Routing policy (uses Brain+Chamber strengths):
    #   - Brain is better at broad exploration (4 models independently map the space)
    #   - Chamber is better at selection/governance (adversarial stress-testing)
    #   - For open-ended briefs: Brain should explore first, then Chamber selects → cascade
    #   - For explicit-option briefs: option space is already defined → Chamber alone suffices
    #   - For truth-seeking briefs: Brain alone (no recommendation needed)
    #   - For high-stakes dual-lens: both in parallel
    #
    if is_high_stakes and brain_score >= 2 and chamber_score >= 2:
        recommended_mode = "parallel"
    elif brief_type == "truth_seeking":
        recommended_mode = "brain"
    elif has_explicit:
        # Brief provides explicit options — option space is defined, Chamber governs selection
        recommended_mode = "chamber"
    elif brief_type == "hybrid":
        recommended_mode = "cascade"
    elif brief_type == "recommendation_seeking":
        # Open-ended recommendation brief — Brain explores the option space first,
        # then Chamber stress-tests and selects. This uses Brain's strength (4 independent
        # models discovering options) before Chamber's strength (adversarial governance).
        recommended_mode = "cascade"
    else:
        recommended_mode = "chamber"

    classification = {
        "brief_type": brief_type,
        "has_explicit_options": has_explicit,
        "is_exclusive_choice": is_exclusive,
        "is_high_stakes": is_high_stakes,
        "brain_score": brain_score,
        "chamber_score": chamber_score,
        "recommended_mode": recommended_mode,
    }
    log.log(f"[CLASSIFY] type={brief_type} mode={recommended_mode}")
    return classification


# ═══════════════════════════════════════════════════════════════════════════
# Engine Invocation
# ═══════════════════════════════════════════════════════════════════════════

def run_brain(brief_path: Path, outdir: Path, rounds: int, budget: int,
              log: ControllerLog) -> dict | None:
    if not BRAIN_SCRIPT.exists():
        log.log(f"[BRAIN] Not found: {BRAIN_SCRIPT}")
        return None
    cmd = [
        sys.executable, str(BRAIN_SCRIPT),
        "--brief", str(brief_path), "--outdir", str(outdir),
        "--rounds", str(rounds), "--wall-clock-budget", str(budget),
    ]
    log.log(f"[BRAIN] Starting rounds={rounds}")
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=budget + 120, env={**os.environ})
        log.log(f"[BRAIN] {time.time()-t0:.1f}s exit={result.returncode}")
        for line in result.stdout.strip().split("\n"):
            log.log(f"  [BRAIN-OUT] {line}")
        proof_path = outdir / "proof.json"
        if not proof_path.exists():
            return None
        return json.loads(proof_path.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired:
        log.log("[BRAIN] TIMEOUT"); return None
    except Exception as exc:
        log.log(f"[BRAIN] {exc}"); return None


async def run_chamber(task: str, log: ControllerLog,
                      brain_augmentation: dict | None = None) -> dict | None:
    try:
        sys.path.insert(0, str(CHAMBER_MODULE_DIR))
        mod = __import__(CHAMBER_MODULE_NAME)
        run_fn = getattr(mod, "run_chamber_v3")
    except (ImportError, AttributeError) as exc:
        log.log(f"[CHAMBER] Import failed ({CHAMBER_MODULE_NAME}): {exc}")
        return None
    log.log(f"[CHAMBER] Starting" + (" (augmented)" if brain_augmentation else ""))
    t0 = time.time()
    try:
        verdict = await run_fn(task, brain_augmentation=brain_augmentation)
        if verdict is None:
            log.log(f"[CHAMBER] None after {time.time()-t0:.1f}s"); return None
        v = verdict.model_dump()
        log.log(f"[CHAMBER] {time.time()-t0:.1f}s status={v.get('status')} conf={v.get('confidence')}")
        return v
    except Exception as exc:
        log.log(f"[CHAMBER] {exc}"); return None


# ═══════════════════════════════════════════════════════════════════════════
# Brain Augmentation Extraction
# ═══════════════════════════════════════════════════════════════════════════

def _extract_brain_augmentation(proof: dict, brief: str,
                                 classification: dict, log: ControllerLog) -> dict:
    augmentation: dict = {
        "source": "brain_v3",
        "brain_run_id": proof.get("run_id", "unknown"),
        "brain_outcome": proof.get("v3_outcome_class", "unknown"),
        "brain_convergence": proof.get("convergence_trend", "unknown"),
        "brain_shared_ground": proof.get("stable_agreements", []),
        "choice_mode": "exclusive" if classification.get("is_exclusive_choice") else "portfolio",
    }

    # Option injection: conservative heuristic.
    # Only inject when brief-shape detection confirms explicit options AND Brain found them.
    # When the heuristic withholds options, it logs the reason so operators can verify.
    brain_options = proof.get("v3_explicit_options", "not applicable")
    if (classification.get("has_explicit_options")
            and isinstance(brain_options, list) and len(brain_options) >= 2):
        augmentation["options"] = [
            {"id": f"O{i+1}", "label": opt, "text": opt}
            for i, opt in enumerate(brain_options)
        ]
        augmentation["options_source"] = "brief_native_confirmed"
        log.log(f"[AUGMENT] {len(augmentation['options'])} brief-native options injected")
    else:
        augmentation["options"] = []
        if isinstance(brain_options, list) and len(brain_options) >= 2:
            augmentation["options_source"] = "withheld:brain_has_options_but_brief_pattern_not_confirmed"
            log.log(f"[AUGMENT-WITHHELD] Brain found {len(brain_options)} options but brief "
                    f"pattern detector did not confirm explicit options — withholding. "
                    f"This is a conservative heuristic; verify manually if options are real.")
        else:
            augmentation["options_source"] = "none"

    # Advisory positions (context, never brief-native)
    positions = proof.get("model_positions_by_round", {})
    advisory = []
    if positions:
        seen = set()
        for rnd_pos in positions.values():
            for pos in rnd_pos.values():
                p = pos.get("primary_option")
                if p and not p.startswith("__"):
                    seen.add(p)
        advisory = sorted(seen)
    augmentation["advisory_positions"] = advisory

    # Evidence gaps
    augmentation["evidence_gaps"] = [
        {"gap_id": g.get("gap_id", "?"), "text": g.get("text", "")[:200]}
        for g in proof.get("gaps_detected", []) if g.get("text")
    ]
    for g in proof.get("gaps_dropped", []):
        augmentation["evidence_gaps"].append({
            "gap_id": g.get("gap_id", "?"), "text": f"[UNRESOLVED] {g.get('reason', '')}",
        })

    # Contested dimensions
    augmentation["contested_dimensions"] = list(set(
        proof.get("stable_contested", []) + proof.get("unresolved_residual", [])
    ))

    # Final-round position summary
    position_summary = []
    if positions:
        final_round = max(positions.keys(), key=lambda k: int(k))
        for model, pos in positions[final_round].items():
            position_summary.append({
                "model": model, "kind": pos.get("kind", "?"),
                "primary_option": pos.get("primary_option"),
                "confidence": pos.get("confidence", "MEDIUM"),
            })
    augmentation["position_summary"] = position_summary
    augmentation["blocker_summary"] = proof.get("blocker_summary", {})

    log.log(f"[AUGMENT] opts={len(augmentation['options'])} ({augmentation['options_source']}) "
            f"advisory={len(advisory)} gaps={len(augmentation['evidence_gaps'])} "
            f"contested={len(augmentation['contested_dimensions'])}")
    return augmentation


# ═══════════════════════════════════════════════════════════════════════════
# Discrepancy Packet — diagnostic only, does NOT drive authority
# ═══════════════════════════════════════════════════════════════════════════

def _build_discrepancy_packet(brain_proof: dict | None, chamber_verdict: dict | None,
                               log: ControllerLog) -> dict:
    """Build diagnostic discrepancy packet. Recorded on proof for operator review.
    Does NOT influence authority selection."""
    packet: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "brain_available": brain_proof is not None,
        "chamber_available": chamber_verdict is not None,
        "note": "Diagnostic only — does not drive authority selection",
        "agreements": [], "brain_only_findings": [],
        "chamber_only_findings": [], "conflicts": [],
        "action_overlap": {}, "evidence_comparison": {},
        "confidence_comparison": {},
    }

    if brain_proof is None or chamber_verdict is None:
        return packet

    brain_outcome = brain_proof.get("v3_outcome_class", "unknown")
    brain_shared = set(brain_proof.get("stable_agreements", []))
    brain_contested = set(brain_proof.get("stable_contested", []))

    chamber_status = chamber_verdict.get("status", "unknown")
    chamber_approved = set(chamber_verdict.get("approved_items", []))
    chamber_rejected = set(chamber_verdict.get("rejected_items", []))
    chamber_confidence = chamber_verdict.get("confidence", 0)
    chamber_unresolved = chamber_verdict.get("unresolved_points", [])

    # Brain primary actions
    brain_actions = set()
    positions = brain_proof.get("model_positions_by_round", {})
    if positions:
        final_round = max(positions.keys(), key=lambda k: int(k))
        for pos in positions[final_round].values():
            p = pos.get("primary_option")
            if p and not p.startswith("__"):
                brain_actions.add(p)

    packet["action_overlap"] = {
        "brain_primary_actions": sorted(brain_actions),
        "chamber_approved": sorted(chamber_approved),
        "chamber_rejected": sorted(chamber_rejected),
    }

    # Agreements
    if brain_outcome == "CONSENSUS" and chamber_status in ("CONSENSUS", "CLOSED_WITH_ACCEPTED_RISKS"):
        packet["agreements"].append({"type": "convergence",
            "detail": f"Both resolve: Brain={brain_outcome}, Chamber={chamber_status}"})
    if brain_outcome == "NO_CONSENSUS" and chamber_status in ("NO_CONSENSUS", "PARTIAL_CONSENSUS"):
        packet["agreements"].append({"type": "divergence",
            "detail": f"Both irresolved: Brain={brain_outcome}, Chamber={chamber_status}"})
    if brain_shared:
        packet["agreements"].append({"type": "shared_ground",
            "detail": f"Brain shared ground: {sorted(brain_shared)}"})

    # Cross-check contested dims
    stop = {"the", "and", "for", "that", "this", "with", "from", "have",
            "been", "will", "should", "could", "would", "about"}
    chamber_text = " ".join(str(p) for p in chamber_unresolved).lower()
    chamber_text += " " + chamber_verdict.get("rationale", "").lower()
    for dim in brain_contested:
        kw = {w for w in re.findall(r'[a-z]{4,}', str(dim).lower())} - stop
        if kw and any(k in chamber_text for k in kw):
            packet["agreements"].append({"type": "contested_alignment",
                "detail": f"Both flagged: {dim}"})
        else:
            packet["brain_only_findings"].append({"type": "unaddressed_contested",
                "detail": f"Brain contested '{dim}' not reflected in Chamber", "actionable": True})

    if brain_proof.get("convergence_trend") == "degrading":
        packet["brain_only_findings"].append({"type": "convergence_warning",
            "detail": "Brain convergence degrading", "actionable": True})
    if chamber_rejected:
        packet["chamber_only_findings"].append({"type": "rejected_items",
            "detail": f"Chamber rejected: {sorted(chamber_rejected)}", "actionable": True})
    if chamber_unresolved:
        packet["chamber_only_findings"].append({"type": "unresolved_objections",
            "detail": f"{len(chamber_unresolved)} unresolved", "actionable": True})

    # Conflicts
    if brain_outcome == "CONSENSUS" and chamber_rejected:
        packet["conflicts"].append({"type": "consensus_vs_rejection",
            "detail": f"Brain=CONSENSUS but Chamber rejected {sorted(chamber_rejected)}"})
    if brain_outcome == "NO_CONSENSUS" and chamber_approved and chamber_confidence > 0.6:
        packet["conflicts"].append({"type": "split_vs_approval",
            "detail": f"Brain=NO_CONSENSUS but Chamber approved {sorted(chamber_approved)} conf={chamber_confidence}"})

    packet["evidence_comparison"] = {
        "brain_count": brain_proof.get("evidence_items", 0),
        "brain_search_mode": brain_proof.get("final_search_mode", "unknown"),
        "brain_escalated": brain_proof.get("search_mode_escalated", False),
    }
    packet["confidence_comparison"] = {
        "brain_agreement_ratio": brain_proof.get("controller_outcome", {}).get("agreement_ratio"),
        "chamber_confidence": chamber_confidence,
    }

    log.log(f"[DISCREPANCY] {len(packet['agreements'])} agree, {len(packet['conflicts'])} conflicts "
            f"(diagnostic only)")
    return packet


# ═══════════════════════════════════════════════════════════════════════════
# Final Authority — from brief classification ONLY
# ═══════════════════════════════════════════════════════════════════════════

def _assign_final_authority(mode: str, classification: dict,
                            log: ControllerLog) -> tuple[str, str]:
    """Assign final authority based on mode + brief classification.

    Simple rules, no exceptions:
      brain mode            → Brain
      chamber mode          → Chamber
      cascade mode          → Chamber (Brain is structured input, not co-authority)
      parallel mode         → classification.brief_type determines:
                              truth_seeking → Brain
                              hybrid        → Chamber (intentional policy: hybrid briefs ask for
                                              both facts AND recommendation; Chamber's recommendation
                                              governance is the more actionable final answer; Brain's
                                              truth-mapping still runs and is recorded on the proof)
                              recommendation_seeking → Chamber
      parallel_degraded     → REJECTED (parallel contract requires both engines;
                              degraded parallel must not silently become a single-engine run)
    """
    if mode in ("brain_only", "brain"):
        return "brain", "brain-only mode"
    if mode in ("chamber_only", "chamber", "cascade", "cascade_degraded"):
        return "chamber", f"{mode} — Chamber is final authority"
    if mode == "parallel_degraded":
        # Degraded parallel cannot produce a valid authority — this forces MI rejection.
        # The contract of parallel mode is "both run, then compare." One-sided output
        # must be explicitly rejected, not silently converted to single-engine authority.
        return "none", "parallel_degraded — cannot assign authority (parallel contract violated)"

    # Parallel (clean): brief classification determines authority
    brief_type = classification.get("brief_type", "recommendation_seeking")
    if brief_type == "truth_seeking":
        return "brain", "parallel — brief is truth_seeking"
    # hybrid and recommendation_seeking both → Chamber (documented policy)
    return "chamber", f"parallel — brief is {brief_type} (Chamber governs recommendations)"


def _extract_final_verdict(authority: str, brain_proof: dict | None,
                            chamber_verdict: dict | None) -> dict:
    if authority == "brain" and brain_proof:
        o = brain_proof.get("controller_outcome", {})
        return {
            "authority": "brain",
            "outcome_class": o.get("outcome_class", "unknown"),
            "agreement_ratio": o.get("agreement_ratio"),
            "shared_ground": o.get("shared_ground", []),
            "contested_dimension": o.get("contested_dimension"),
            "convergence": o.get("position_trajectory"),
            "evidence_driven": o.get("evidence_driven_convergence", False),
        }
    if authority == "chamber" and chamber_verdict:
        return {
            "authority": "chamber",
            "status": chamber_verdict.get("status"),
            "confidence": chamber_verdict.get("confidence"),
            "approved_items": chamber_verdict.get("approved_items", []),
            "rejected_items": chamber_verdict.get("rejected_items", []),
            "choice_mode": chamber_verdict.get("choice_mode"),
            "selected_option": chamber_verdict.get("selected_option"),
        }
    return {"authority": authority, "status": "NO_RESULT"}


# ═══════════════════════════════════════════════════════════════════════════
# Mission Invariants
# ═══════════════════════════════════════════════════════════════════════════

def _validate_mission_invariants(mode, authority, brain_proof, chamber_verdict,
                                  final_verdict, discrepancy, log) -> list[dict]:
    violations = []
    def _v(i, s, d):
        violations.append({"id": i, "severity": s, "detail": d})
        log.log(f"[MI] {i} ({s}): {d}")

    # MI1: authority engine must have produced output
    if authority == "brain" and brain_proof is None:
        _v("MI1", "FATAL", "authority=brain but no Brain output")
    if authority == "chamber" and chamber_verdict is None:
        _v("MI1", "FATAL", "authority=chamber but no Chamber output")

    # MI2: final verdict must not be empty
    if final_verdict.get("status") == "NO_RESULT":
        _v("MI2", "FATAL", "final verdict NO_RESULT")

    # MI3: Brain-authoritative acceptance requires Brain proof-completeness
    # Brain's own acceptance model requires ALL FIVE:
    #   final_status=COMPLETE, controller_outcome populated,
    #   model_positions_by_round non-empty, synthesis_status=COMPLETE,
    #   proof_schema_version=2.0
    if authority == "brain" and brain_proof is not None:
        bp = brain_proof
        if bp.get("final_status") != "COMPLETE":
            _v("MI3", "ERROR", f"Brain is authority but final_status={bp.get('final_status')}")
        if not bp.get("controller_outcome", {}).get("outcome_class"):
            _v("MI3", "ERROR", "Brain is authority but controller_outcome missing/empty")
        if not bp.get("model_positions_by_round"):
            _v("MI3", "ERROR", "Brain is authority but model_positions_by_round empty")
        if bp.get("synthesis_status") != "COMPLETE":
            _v("MI3", "ERROR", f"Brain is authority but synthesis_status={bp.get('synthesis_status')}")
        if bp.get("proof_schema_version") != "2.0":
            _v("MI3", "ERROR", f"Brain is authority but schema={bp.get('proof_schema_version')}")

    # MI4: discrepancy must exist in parallel mode
    if mode == "parallel" and discrepancy is None:
        _v("MI4", "ERROR", "parallel but no discrepancy")

    # MI5: authority must be a valid engine identifier
    if authority not in ("brain", "chamber"):
        _v("MI5", "FATAL", f"invalid authority '{authority}' — must be 'brain' or 'chamber'")

    # MI6: parallel integrity — both engines must complete
    # Applies to both "parallel" and "parallel_degraded" (the degraded flag means
    # we already know one side failed, but MI6 records it as a formal violation)
    if mode in ("parallel", "parallel_degraded"):
        if brain_proof is None:
            _v("MI6", "ERROR", "parallel mode but Brain did not produce output")
        if chamber_verdict is None:
            _v("MI6", "ERROR", "parallel mode but Chamber did not produce output")

    # MI7: non-authoritative engine warnings (informational)
    if brain_proof and brain_proof.get("final_status") != "COMPLETE" and authority != "brain":
        _v("MI7", "WARNING", f"Brain status={brain_proof.get('final_status')} (non-authoritative)")
    if chamber_verdict and chamber_verdict.get("status") in ("SYSTEM_FAILURE", "", None):
        _v("MI7", "ERROR", f"Chamber status={chamber_verdict.get('status')}")

    if violations:
        f = sum(1 for v in violations if v["severity"] == "FATAL")
        e = sum(1 for v in violations if v["severity"] == "ERROR")
        log.log(f"[MI-SUMMARY] {len(violations)}: {f}F {e}E")
    else:
        log.log("[MI-SUMMARY] clean")
    return violations


# ═══════════════════════════════════════════════════════════════════════════
# Mission Proof
# ═══════════════════════════════════════════════════════════════════════════

def _build_mission_proof(mode, authority, authority_reason, final_verdict,
                          brain_proof, chamber_verdict, discrepancy,
                          violations, brief_path, classification) -> dict:
    fatal = sum(1 for v in violations if v["severity"] == "FATAL")
    error = sum(1 for v in violations if v["severity"] == "ERROR")
    ok = fatal == 0 and error == 0 and final_verdict.get("status") != "NO_RESULT"
    return {
        "proof_schema_version": MISSION_PROOF_SCHEMA,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "protocol": "mission_controller_v5",
        "brief_path": str(brief_path),
        "brief_classification": classification,
        "mode": mode,
        "final_authority": authority,
        "authority_reason": authority_reason,
        "final_verdict": final_verdict,
        "brain_ran": brain_proof is not None,
        "brain_status": brain_proof.get("final_status") if brain_proof else None,
        "brain_outcome": brain_proof.get("v3_outcome_class") if brain_proof else None,
        "chamber_ran": chamber_verdict is not None,
        "chamber_status": chamber_verdict.get("status") if chamber_verdict else None,
        "chamber_confidence": chamber_verdict.get("confidence") if chamber_verdict else None,
        "discrepancy": discrepancy,  # full packet for operator review
        "invariant_violations": violations,
        "invariant_fatal_count": fatal,
        "invariant_error_count": error,
        "proof_complete": ok,
        "acceptance_status": "ACCEPTED" if ok else "REJECTED",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Mode Executors
# ═══════════════════════════════════════════════════════════════════════════

async def execute_brain_only(brief, brief_path, log, rounds, budget):
    outdir = REPORTS_DIR / f"brain-{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    proof = run_brain(brief_path, outdir, rounds, budget, log)
    return {"mode": "brain_only", "brain_proof": proof,
            "chamber_verdict": None, "discrepancy": None}


async def execute_chamber_only(brief, log):
    verdict = await run_chamber(brief, log)
    return {"mode": "chamber_only", "brain_proof": None,
            "chamber_verdict": verdict, "discrepancy": None}


async def execute_cascade(brief, brief_path, log, rounds, budget, classification):
    log.log("\n== CASCADE ==")
    outdir = REPORTS_DIR / f"brain-cascade-{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    brain_proof = run_brain(brief_path, outdir, rounds, budget, log)
    if brain_proof is None:
        log.log("[CASCADE] Brain failed -> Chamber-only")
        verdict = await run_chamber(brief, log)
        return {"mode": "cascade_degraded", "brain_proof": None,
                "chamber_verdict": verdict, "discrepancy": None}
    augmentation = _extract_brain_augmentation(brain_proof, brief, classification, log)
    verdict = await run_chamber(brief, log, brain_augmentation=augmentation)
    return {"mode": "cascade", "brain_proof": brain_proof,
            "chamber_verdict": verdict, "discrepancy": None}


async def execute_parallel(brief, brief_path, log, rounds, budget):
    log.log("\n== PARALLEL ==")
    outdir = REPORTS_DIR / f"brain-parallel-{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    loop = asyncio.get_event_loop()
    brain_future = loop.run_in_executor(
        None, run_brain, brief_path, outdir, rounds, budget, log)
    chamber_future = run_chamber(brief, log)
    brain_proof, chamber_verdict = await asyncio.gather(
        brain_future, chamber_future, return_exceptions=True)
    if isinstance(brain_proof, Exception):
        brain_proof = None
    if isinstance(chamber_verdict, Exception):
        chamber_verdict = None
    if chamber_verdict and hasattr(chamber_verdict, "model_dump"):
        chamber_verdict = chamber_verdict.model_dump()
    log.log(f"[PARALLEL] Brain={'OK' if brain_proof else 'FAIL'} "
            f"Chamber={'OK' if chamber_verdict else 'FAIL'}")
    discrepancy = _build_discrepancy_packet(brain_proof, chamber_verdict, log)

    # Mark as degraded if one side failed (MI6 will catch this)
    actual_mode = "parallel"
    if brain_proof is None or chamber_verdict is None:
        actual_mode = "parallel_degraded"
        log.log(f"[PARALLEL] Degraded — {'Brain' if brain_proof is None else 'Chamber'} missing")

    return {"mode": actual_mode, "brain_proof": brain_proof,
            "chamber_verdict": chamber_verdict, "discrepancy": discrepancy}


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

async def run(brief_path: Path, mode: str = "auto",
              rounds: int = BRAIN_DEFAULT_ROUNDS,
              budget: int = BRAIN_DEFAULT_BUDGET) -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log = ControllerLog(REPORTS_DIR / f"mission-{ts}.log")

    brief = brief_path.read_text(encoding="utf-8").strip()
    if not brief:
        return {"error": "empty brief"}

    log.log(f"Brief: {brief_path} ({len(brief)} chars), mode={mode}")

    # Always classify (stored for authority, independent of execution mode)
    classification = classify_brief(brief, log)

    exec_mode = classification["recommended_mode"] if mode == "auto" else mode
    log.log(f"[MODE] {'Auto' if mode == 'auto' else 'Manual'} -> {exec_mode}")

    if exec_mode == "brain":
        result = await execute_brain_only(brief, brief_path, log, rounds, budget)
    elif exec_mode == "chamber":
        result = await execute_chamber_only(brief, log)
    elif exec_mode == "cascade":
        result = await execute_cascade(brief, brief_path, log, rounds, budget, classification)
    elif exec_mode == "parallel":
        result = await execute_parallel(brief, brief_path, log, rounds, budget)
    else:
        return {"error": f"unknown mode: {exec_mode}"}

    # Authority from classification, not discrepancy
    authority, reason = _assign_final_authority(result["mode"], classification, log)
    log.log(f"[AUTHORITY] {authority} — {reason}")

    final_verdict = _extract_final_verdict(
        authority, result.get("brain_proof"), result.get("chamber_verdict"))

    violations = _validate_mission_invariants(
        result["mode"], authority, result.get("brain_proof"),
        result.get("chamber_verdict"), final_verdict,
        result.get("discrepancy"), log)

    mission_proof = _build_mission_proof(
        result["mode"], authority, reason, final_verdict,
        result.get("brain_proof"), result.get("chamber_verdict"),
        result.get("discrepancy"), violations, str(brief_path), classification)

    proof_path = REPORTS_DIR / f"mission-proof-{ts}.json"
    try:
        proof_path.write_text(json.dumps(mission_proof, indent=2, default=str), encoding="utf-8")
        log.log(f"[PROOF] {proof_path}")
    except Exception as exc:
        log.log(f"[PROOF-ERROR] {exc}")
        mission_proof["proof_complete"] = False
        mission_proof["acceptance_status"] = "REJECTED"

    log.log(f"\n== Complete: mode={result['mode']} authority={authority} "
            f"accepted={mission_proof['acceptance_status']} ==")
    log.close()
    return mission_proof


def main():
    parser = argparse.ArgumentParser(description="Mission Controller v5")
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--mode", default="auto",
                        choices=["auto", "brain", "chamber", "cascade", "parallel"])
    parser.add_argument("--rounds", type=int, default=BRAIN_DEFAULT_ROUNDS)
    parser.add_argument("--budget", type=int, default=BRAIN_DEFAULT_BUDGET)
    args = parser.parse_args()
    if not args.brief.exists():
        print(f"[ERROR] Not found: {args.brief}", file=sys.stderr)
        sys.exit(1)
    result = asyncio.run(run(args.brief, args.mode, args.rounds, args.budget))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
