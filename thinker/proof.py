"""Proof.json builder — the machine-readable audit trail.

Schema 3.0 (V9). Adds: preflight, dimensions, perspective_cards, divergence,
search_log, ungrounded_stats, two-tier evidence, arguments with resolution,
decisive_claims, cross_domain_analogies, semantic contradictions,
synthesis_packet, synthesis dispositions, stability, gate2 rule_trace,
stage_integrity, analysis_map, analysis_debug, diagnostics.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from thinker.types import Outcome, Position
from thinker.tools.blocker import BlockerLedger


class ProofBuilder:
    """Incrementally builds proof.json throughout a Brain run."""

    def __init__(self, run_id: str, brief: str, rounds_requested: int):
        self._run_id = run_id
        self._brief = brief
        self._rounds_requested = rounds_requested
        self._timestamp_started = datetime.now(timezone.utc).isoformat()
        self._timestamp_completed: Optional[str] = None
        self._topology: Optional[dict] = None
        self._error_class: Optional[str] = None
        self._config_snapshot: Optional[dict] = None
        self._rounds: dict[str, dict] = {}
        self._positions: dict[str, dict] = {}
        self._position_changes: list[dict] = []
        self._outcome: dict = {}
        self._final_status: Optional[str] = None
        self._synthesis_status: Optional[str] = None
        self._evidence_items: int = 0
        self._research_phases: list[dict] = []
        self._blocker_ledger: Optional[BlockerLedger] = None
        self._invariant_violations: list[dict] = []
        self._acceptance_status: Optional[str] = None
        self._synthesis_residue_omissions: list[dict] = []
        self._search_decision: Optional[dict] = None
        self._v3_outcome_class: str = "not applicable"
        # V9 additions
        self._preflight: Optional[dict] = None
        self._dimensions: Optional[dict] = None
        self._perspective_cards: Optional[list[dict]] = None
        self._divergence: Optional[dict] = None
        self._search_log: list[dict] = []
        self._ungrounded_stats: list[dict] = []
        self._evidence_active: list[dict] = []
        self._evidence_archive: list[dict] = []
        self._eviction_log: list[dict] = []
        self._arguments: list[dict] = []
        self._decisive_claims: list[dict] = []
        self._cross_domain_analogies: list[dict] = []
        self._contradictions_numeric: list[dict] = []
        self._contradictions_semantic: list[dict] = []
        self._synthesis_packet: Optional[dict] = None
        self._synthesis_dispositions: list[dict] = []
        self._stability: Optional[dict] = None
        self._gate2_trace: Optional[dict] = None
        self._stage_integrity: Optional[dict] = None
        self._analysis_map: list[dict] = []
        self._analysis_debug: Optional[dict] = None
        self._diagnostics: dict = {}
        self._residue_verification: Optional[dict] = None
        self._synthesis_output: Optional[dict] = None

    def record_round(self, round_num: int, responded: list[str], failed: list[str]):
        self._rounds[str(round_num)] = {
            "responded": responded,
            "failed": failed,
        }

    def record_positions(self, round_num: int, positions: dict[str, Position]):
        round_positions = {}
        for model, pos in positions.items():
            round_positions[model] = {
                "model": pos.model,
                "kind": pos.kind,
                "primary_option": pos.primary_option,
                "components": pos.components,
                "confidence": pos.confidence.value,
                "qualifier": pos.qualifier,
            }
        self._positions[str(round_num)] = round_positions

    def record_position_changes(self, changes: list[dict]):
        self._position_changes.extend(changes)

    def record_research_phase(self, phase: str, method: str,
                              queries: int, items_admitted: int):
        self._research_phases.append({
            "phase": phase, "method": method,
            "queries_attempted": queries, "items_admitted": items_admitted,
        })

    def set_evidence_count(self, count: int):
        self._evidence_items = count

    def set_outcome(self, outcome: Outcome, agreement_ratio: float,
                    outcome_class: str):
        self._outcome = {
            "outcome_class": outcome_class,
            "agreement_ratio": agreement_ratio,
            "verdict": outcome.value,
        }
        self._v3_outcome_class = outcome_class

    def set_final_status(self, status: str):
        self._final_status = status

    def set_synthesis_status(self, status: str):
        self._synthesis_status = status

    def set_blocker_ledger(self, ledger: BlockerLedger):
        self._blocker_ledger = ledger

    def compute_acceptance_status(self):
        """Compute acceptance_status from run metrics.

        ACCEPTED: clean run — DECIDE outcome, CONSENSUS class, no violations.
        V9: ACCEPTED_WITH_WARNINGS removed. Now just ACCEPTED or outcome-based.
        Never REJECTED — if fatal, BrainError stops the pipeline before proof.
        """
        from thinker.types import AcceptanceStatus
        is_clean = (
            self._outcome.get("verdict") == "DECIDE"
            and self._outcome.get("outcome_class") == "CONSENSUS"
            and len(self._invariant_violations) == 0
        )
        self._acceptance_status = AcceptanceStatus.ACCEPTED.value if is_clean else "REVIEW_REQUIRED"

    def set_synthesis_residue(self, omissions: list[dict]):
        self._synthesis_residue_omissions = omissions

    def set_search_decision(self, source: str, value: bool, reasoning: str,
                            gate1_recommended: Optional[bool] = None,
                            gate1_search_reasoning: Optional[str] = None):
        """Record who decided search on/off and why.

        source: "gate1" | "cli_override"
        value: True (search on) or False (search off)
        reasoning: Why this decision was made
        gate1_recommended: Gate 1's original recommendation (if overridden)
        gate1_search_reasoning: Gate 1's reasoning for its recommendation (if overridden)
        """
        self._search_decision = {
            "source": source,
            "value": value,
            "reasoning": reasoning,
        }
        if source == "cli_override" and gate1_recommended is not None:
            self._search_decision["gate1_recommended"] = gate1_recommended
            if gate1_search_reasoning:
                self._search_decision["gate1_search_reasoning"] = gate1_search_reasoning

    def add_violation(self, violation_id: str, severity: str, detail: str):
        self._invariant_violations.append({
            "id": violation_id, "severity": severity, "detail": detail,
        })

    # --- V9 Setters ---

    def set_timestamp_completed(self) -> None:
        """Record the completion timestamp."""
        self._timestamp_completed = datetime.now(timezone.utc).isoformat()

    def set_topology(self, topology: dict) -> None:
        """Set the round topology (DOD §19: which models in each round)."""
        self._topology = topology

    def set_error_class(self, error_class: Optional[str]) -> None:
        """Set error_class (DOD §19: null when no error)."""
        self._error_class = error_class

    def set_config_snapshot(self, config: dict) -> None:
        """Set config_snapshot (DOD §19: runtime config at start)."""
        self._config_snapshot = config

    def set_synthesis_output(self, output: dict) -> None:
        """Set synthesis_output (DOD §19: synthesis report + JSON)."""
        self._synthesis_output = output

    def set_preflight(self, result) -> None:
        """Set preflight assessment result (PreflightResult.to_dict())."""
        self._preflight = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_dimensions(self, result) -> None:
        """Set dimension seeder result (DimensionSeedResult.to_dict())."""
        self._dimensions = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_perspective_cards(self, cards: list) -> None:
        """Set perspective cards list."""
        self._perspective_cards = [c.to_dict() if hasattr(c, 'to_dict') else c for c in cards]

    def set_divergence(self, result) -> None:
        """Set divergence/framing result."""
        self._divergence = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_search_log(self, entries: list) -> None:
        """Set search log entries."""
        self._search_log = [e.to_dict() if hasattr(e, 'to_dict') else e for e in entries]

    def set_ungrounded_stats(self, data: list[dict]) -> None:
        """Set ungrounded statistic detection results."""
        self._ungrounded_stats = data

    def set_evidence_two_tier(self, active: list, archive: list, eviction_log: list) -> None:
        """Set two-tier evidence data."""
        self._evidence_active = [
            {"evidence_id": e.evidence_id, "topic": e.topic, "fact": e.fact,
             "url": e.url, "confidence": e.confidence.value, "score": e.score,
             "topic_cluster": e.topic_cluster, "authority_tier": e.authority_tier}
            if hasattr(e, 'evidence_id') else e
            for e in active
        ]
        self._evidence_archive = [
            {"evidence_id": e.evidence_id, "topic": e.topic, "fact": e.fact,
             "url": e.url, "confidence": e.confidence.value, "score": e.score,
             "topic_cluster": e.topic_cluster, "authority_tier": e.authority_tier}
            if hasattr(e, 'evidence_id') else e
            for e in archive
        ]
        self._eviction_log = [
            ev.to_dict() if hasattr(ev, 'to_dict') else ev for ev in eviction_log
        ]

    def set_arguments(self, arguments: list) -> None:
        """Set argument map with resolution status."""
        self._arguments = [
            {"argument_id": a.argument_id, "round_num": a.round_num, "model": a.model,
             "text": a.text, "status": a.status.value, "resolution_status": a.resolution_status.value,
             "superseded_by": a.superseded_by, "dimension_id": a.dimension_id,
             "evidence_refs": a.evidence_refs, "open": a.open}
            if hasattr(a, 'argument_id') else a
            for a in arguments
        ]

    def set_decisive_claims(self, claims: list) -> None:
        """Set decisive claims."""
        self._decisive_claims = [c.to_dict() if hasattr(c, 'to_dict') else c for c in claims]

    def set_analogies(self, analogies: list) -> None:
        """Set cross-domain analogies."""
        self._cross_domain_analogies = [a.to_dict() if hasattr(a, 'to_dict') else a for a in analogies]

    def set_contradictions(self, numeric: list, semantic: list) -> None:
        """Set both numeric and semantic contradictions."""
        self._contradictions_numeric = [
            {"contradiction_id": c.contradiction_id, "evidence_ids": c.evidence_ids,
             "topic": c.topic, "severity": c.severity, "status": c.status,
             "detection_mode": c.detection_mode}
            if hasattr(c, 'contradiction_id') else c
            for c in numeric
        ]
        self._contradictions_semantic = [
            c.to_dict() if hasattr(c, 'to_dict') else c for c in semantic
        ]

    def set_synthesis_packet(self, packet: dict) -> None:
        """Set synthesis packet data."""
        self._synthesis_packet = packet

    def set_synthesis_dispositions(self, dispositions: list) -> None:
        """Set synthesis dispositions."""
        self._synthesis_dispositions = [
            d.to_dict() if hasattr(d, 'to_dict') else d for d in dispositions
        ]

    def set_stability(self, result) -> None:
        """Set stability test results."""
        self._stability = result.to_dict() if hasattr(result, 'to_dict') else result

    def set_gate2_trace(self, modality: str, rule_trace: list[dict], final_outcome: str) -> None:
        """Set gate2 rule evaluation trace."""
        self._gate2_trace = {
            "modality": modality,
            "rule_trace": rule_trace,
            "final_outcome": final_outcome,
        }

    def set_stage_integrity(self, required: list[str], order: list[str], fatal: list[str]) -> None:
        """Set stage integrity tracking."""
        self._stage_integrity = {
            "required_stages": required,
            "execution_order": order,
            "fatal_failures": fatal,
        }

    def set_residue_verification(self, data: dict) -> None:
        """Set residue verification results."""
        self._residue_verification = data

    def set_analysis_map(self, entries: list) -> None:
        """Set analysis map entries (ANALYSIS mode)."""
        self._analysis_map = entries

    def set_analysis_debug(self, data: dict) -> None:
        """Set analysis debug data."""
        self._analysis_debug = data

    def set_diagnostics(self, data: dict) -> None:
        """Set diagnostics data."""
        self._diagnostics = data

    def build(self) -> dict:
        """Build the complete proof.json dict."""
        blocker_list = []
        blocker_summary = {"total_blockers": 0, "by_status": {}, "by_kind": {}, "open_at_end": 0}
        if self._blocker_ledger:
            for b in self._blocker_ledger.blockers:
                blocker_list.append({
                    "blocker_id": b.blocker_id,
                    "kind": b.kind.value,
                    "source_dimension": b.source,
                    "detected_round": b.detected_round,
                    "status": b.status.value,
                    "status_history": b.status_history,
                    "models_involved": b.models_involved,
                    "evidence_ids": b.evidence_ids,
                    "detail": b.detail,
                    "resolution_note": b.resolution_note,
                })
            blocker_summary = self._blocker_ledger.summary()

        proof = {
            # --- DOD §19 canonical keys ---
            "proof_version": "3.0",
            "run_id": self._run_id,
            "timestamp_started": self._timestamp_started,
            "timestamp_completed": self._timestamp_completed or datetime.now(timezone.utc).isoformat(),
            "topology": self._topology,
            "outcome": self._outcome,
            "error_class": self._error_class,
            "stage_integrity": self._stage_integrity,
            "config_snapshot": self._config_snapshot,
            "preflight": self._preflight,
            "budgeting": None,  # Deferred per user "no budgets" rule
            "dimensions": self._dimensions,
            "perspective_cards": self._perspective_cards,
            "rounds": self._rounds,
            "divergence": self._divergence,
            "search_log": self._search_log,
            "ungrounded_stats": self._ungrounded_stats,
            "evidence": {
                "active": self._evidence_active,
                "archive": self._evidence_archive,
                "eviction_log": self._eviction_log,
                "active_count": len(self._evidence_active),
                "archive_count": len(self._evidence_archive),
            } if self._evidence_active or self._evidence_archive else None,
            "arguments": self._arguments if self._arguments else None,
            "blockers": blocker_list,
            "decisive_claims": self._decisive_claims if self._decisive_claims else None,
            "cross_domain_analogies": self._cross_domain_analogies if self._cross_domain_analogies else None,
            "contradictions": {
                "numeric": self._contradictions_numeric,
                "semantic": self._contradictions_semantic,
            } if self._contradictions_numeric or self._contradictions_semantic else None,
            "synthesis_packet": self._synthesis_packet,
            "synthesis_output": self._synthesis_output,
            "synthesis_dispositions": self._synthesis_dispositions if self._synthesis_dispositions else None,
            "residue_verification": self._residue_verification,
            "positions": self._positions,
            "stability": self._stability,
            "analysis_map": self._analysis_map if self._analysis_map else None,
            "analysis_debug": self._analysis_debug,
            "diagnostics": self._diagnostics if self._diagnostics else None,
            "gate2": self._gate2_trace,
            # --- Extended fields (not in DOD §19 but useful) ---
            "protocol_version": "v9",
            "rounds_requested": self._rounds_requested,
            "final_status": self._final_status,
            "synthesis_status": self._synthesis_status,
            "acceptance_status": self._acceptance_status,
            "search_decision": self._search_decision,
            "v3_outcome_class": self._v3_outcome_class,
            "evidence_items": self._evidence_items,
            "research_phases": self._research_phases,
            "position_changes": self._position_changes,
            "blocker_summary": blocker_summary,
            "invariant_violations": self._invariant_violations,
            "synthesis_residue_omissions": self._synthesis_residue_omissions,
        }
        return proof
