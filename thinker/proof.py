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


def _serialize_blocker_status(status: str) -> str:
    return "DEFERRED" if status == "DROPPED" else status


_EXPECTED_STAGE_ORDER = [
    "preflight",
    "dimensions",
    "r1",
    "track1",
    "perspective_cards",
    "framing_pass",
    "ungrounded_r1",
    "search1",
    "r2",
    "track2",
    "frame_survival_r2",
    "ungrounded_r2",
    "search2",
    "r3",
    "track3",
    "frame_survival_r3",
    "r4",
    "track4",
    "semantic_contradiction",
    "decisive_claims",
    "synthesis_packet",
    "synthesis",
    "residue_verification",
    "gate2",
]


def _validate_stage_order(order: list[str]) -> tuple[bool, list[str]]:
    expected_positions = {stage: idx for idx, stage in enumerate(_EXPECTED_STAGE_ORDER)}
    violations: list[str] = []
    last_expected_index = -1

    for idx, stage in enumerate(order):
        expected_index = expected_positions.get(stage)
        if expected_index is None:
            violations.append(f"Unknown stage '{stage}' at position {idx + 1}")
            continue
        if expected_index < last_expected_index:
            violations.append(
                f"Stage '{stage}' executed at position {idx + 1} after a later stage"
            )
        else:
            last_expected_index = expected_index

    return len(violations) == 0, violations


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
        self._budgeting: Optional[dict] = None

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

    def set_budgeting(self, data: dict) -> None:
        """Set budgeting data (DOD §5.1)."""
        self._budgeting = data

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

    def set_ungrounded_stats(self, data) -> None:
        """Set ungrounded statistic detection results (DOD §9.2 schema)."""
        payload = data.to_dict() if hasattr(data, "to_dict") else data
        if isinstance(payload, dict) and "items" in payload and "flagged_claims" not in payload:
            payload = {**payload, "flagged_claims": payload.get("items", [])}
            payload.pop("items", None)
        self._ungrounded_stats = payload

    def set_evidence_two_tier(self, active: list, archive: list, eviction_log: list) -> None:
        """Set two-tier evidence data."""
        self._evidence_active = [
            {"evidence_id": e.evidence_id, "topic": e.topic, "fact": e.fact,
             "source_url": e.url, "confidence": e.confidence.value, "score": e.score,
             "topic_cluster": e.topic_cluster, "authority_tier": e.authority_tier,
             "is_active": e.is_active, "is_archived": e.is_archived,
             "referenced_by": e.referenced_by}
            if hasattr(e, 'evidence_id') else e
            for e in active
        ]
        self._evidence_archive = [
            {"evidence_id": e.evidence_id, "topic": e.topic, "fact": e.fact,
             "source_url": e.url, "confidence": e.confidence.value, "score": e.score,
             "topic_cluster": e.topic_cluster, "authority_tier": e.authority_tier,
             "is_active": e.is_active, "is_archived": e.is_archived,
             "referenced_by": e.referenced_by}
            if hasattr(e, 'evidence_id') else e
            for e in archive
        ]
        self._eviction_log = [
            ev.to_dict() if hasattr(ev, 'to_dict') else ev for ev in eviction_log
        ]

    def set_arguments(self, arguments: list, blocker_ledger=None) -> None:
        """Set argument map with resolution status (DOD §19: object keyed by argument_id)."""
        # Build dimension→blocker mapping for blocker_link_ids
        dim_blockers: dict[str, list[str]] = {}
        if blocker_ledger:
            for b in blocker_ledger.blockers:
                if b.source.startswith("dimension:"):
                    dim_id = b.source.split(":", 1)[1]
                    dim_blockers.setdefault(dim_id, []).append(b.blocker_id)

        self._arguments = {}
        for a in arguments:
            if hasattr(a, 'argument_id'):
                links = list(getattr(a, "blocker_link_ids", []))
                if a.dimension_id:
                    for blocker_id in dim_blockers.get(a.dimension_id, []):
                        if blocker_id not in links:
                            links.append(blocker_id)
                self._arguments[a.argument_id] = {
                    "argument_id": a.argument_id, "round_origin": a.round_num,
                    "model_id": a.model, "text": a.text,
                    "status": a.status.value, "resolution_status": a.resolution_status.value,
                    "refines": a.refines,
                    "superseded_by": a.superseded_by, "dimension_id": a.dimension_id,
                    "blocker_link_ids": links, "evidence_refs": a.evidence_refs, "open": a.open,
                }
            else:
                key = a.get("argument_id", f"arg-{len(self._arguments)}")
                self._arguments[key] = a

    def set_decisive_claims(self, claims: list) -> None:
        """Set decisive claims."""
        self._decisive_claims = [c.to_dict() if hasattr(c, 'to_dict') else c for c in claims]

    def set_analogies(self, analogies: list) -> None:
        """Set cross-domain analogies."""
        self._cross_domain_analogies = [a.to_dict() if hasattr(a, 'to_dict') else a for a in analogies]

    def set_contradictions(self, numeric: list, semantic: list, semantic_pass_executed: bool = True) -> None:
        """Set both numeric and semantic contradictions."""
        self._semantic_pass_executed = semantic_pass_executed
        self._contradictions_numeric = [
            {"ctr_id": c.ctr_id,
             "detection_mode": c.detection_mode,
             "evidence_ref_a": c.evidence_ref_a, "evidence_ref_b": c.evidence_ref_b,
             "same_entity": c.same_entity, "same_timeframe": c.same_timeframe,
             "topic": c.topic, "severity": c.severity, "status": c.status,
             "justification": c.justification, "linked_claim_ids": c.linked_claim_ids}
            if hasattr(c, 'ctr_id') else c
            for c in numeric
        ]
        self._contradictions_semantic = [
            c.to_dict() if hasattr(c, 'to_dict') else c for c in semantic
        ]

    def set_synthesis_packet(self, packet: dict) -> None:
        """Set synthesis packet data."""
        if isinstance(packet, dict) and "decisive_claims" in packet and "decisive_claim_bindings" not in packet:
            payload = {**packet, "decisive_claim_bindings": packet.get("decisive_claims", [])}
            payload.pop("decisive_claims", None)
            self._synthesis_packet = payload
            return
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
        """Set stage integrity tracking (DOD §3.4)."""
        order_valid, order_violations = _validate_stage_order(order)
        if not order_valid:
            self.add_violation("STAGE-ORDER", "ERROR", "; ".join(order_violations))
        self._stage_integrity = {
            "required_stages": required,
            "execution_order": order,
            "fatal_failures": fatal,
            "all_required_present": all(s in order for s in required),
            "order_valid": order_valid,
            "order_violations": order_violations,
            "fatal": len(fatal) > 0 or not order_valid,
        }

    def set_residue_verification(self, data: dict) -> None:
        """Set residue verification results."""
        self._residue_verification = data

    def set_analysis_map(self, entries: list) -> None:
        """Set analysis map entries (ANALYSIS mode)."""
        if not isinstance(entries, dict):
            raise ValueError("analysis_map must be an object")
        if entries.get("header") != "EXPLORATORY MAP — NOT A DECISION":
            raise ValueError("analysis_map.header must match DOD header")
        if not isinstance(entries.get("dimensions"), dict):
            raise ValueError("analysis_map.dimensions must be an object")
        if not isinstance(entries.get("hypothesis_ledger"), list):
            raise ValueError("analysis_map.hypothesis_ledger must be a list")
        if not isinstance(entries.get("total_argument_count"), int):
            raise ValueError("analysis_map.total_argument_count must be an int")
        if not isinstance(entries.get("dimension_coverage_score"), (int, float)):
            raise ValueError("analysis_map.dimension_coverage_score must be numeric")

        for dim_id, dim_data in entries["dimensions"].items():
            if not isinstance(dim_data, dict):
                raise ValueError(f"analysis_map dimension {dim_id} must be an object")
            for field in ("knowns", "inferred", "unknowns", "evidence_for", "evidence_against", "competing_lenses"):
                if not isinstance(dim_data.get(field), list):
                    raise ValueError(f"analysis_map dimension {dim_id}.{field} must be a list")
            if not isinstance(dim_data.get("argument_count"), int):
                raise ValueError(f"analysis_map dimension {dim_id}.argument_count must be an int")

        for idx, hypothesis in enumerate(entries["hypothesis_ledger"]):
            if not isinstance(hypothesis, dict):
                raise ValueError(f"analysis_map hypothesis {idx} must be an object")
            for field in ("hypothesis_id", "dimension_id", "text", "status"):
                value = hypothesis.get(field)
                if not isinstance(value, str) or not value:
                    raise ValueError(f"analysis_map hypothesis {idx}.{field} must be a non-empty string")
            if not isinstance(hypothesis.get("evidence_refs", []), list):
                raise ValueError(f"analysis_map hypothesis {idx}.evidence_refs must be a list")

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
                serialized_history = []
                for entry in b.status_history:
                    status = entry.get("status")
                    serialized_history.append({
                        **entry,
                        "status": _serialize_blocker_status(status) if status else status,
                    })
                blocker_list.append({
                    "blocker_id": b.blocker_id,
                    "type": b.kind.value,  # DOD §19: "type" not "kind"
                    "severity": b.severity,
                    "source_dimension": b.source,
                    "detected_round": b.detected_round,
                    "status": _serialize_blocker_status(b.status.value),
                    "status_history": serialized_history,
                    "models_involved": b.models_involved,
                    "linked_ids": b.evidence_ids,  # DOD §19: "linked_ids" not "evidence_ids"
                    "detail": b.detail,
                    "resolution_summary": b.resolution_note,  # DOD §19: "resolution_summary"
                })
            blocker_summary = self._blocker_ledger.summary()
            if blocker_summary.get("by_status"):
                by_status = {}
                for status, count in blocker_summary["by_status"].items():
                    serialized = _serialize_blocker_status(status)
                    by_status[serialized] = by_status.get(serialized, 0) + count
                blocker_summary = {**blocker_summary, "by_status": by_status}

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
            "budgeting": self._budgeting,
            "dimensions": self._dimensions,
            "perspective_cards": self._perspective_cards,
            "rounds": self._rounds,
            "divergence": self._divergence,
            "search_log": self._search_log,
            "ungrounded_stats": self._ungrounded_stats,
            "evidence": {
                "active_working_set": self._evidence_active,
                "archive": self._evidence_archive,
                "eviction_log": self._eviction_log,
                "active_count": len(self._evidence_active),
                "archive_count": len(self._evidence_archive),
                "high_authority_evidence_present": any(
                    e.get("authority_tier") in ("HIGH", "AUTHORITATIVE")
                    for e in (self._evidence_active + self._evidence_archive)
                ) if (self._evidence_active or self._evidence_archive) else False,
            },
            "arguments": self._arguments or {},
            "blockers": blocker_list,
            "decisive_claims": self._decisive_claims or [],
            "cross_domain_analogies": self._cross_domain_analogies or [],
            "contradictions": {
                "numeric_records": self._contradictions_numeric,
                "semantic_records": self._contradictions_semantic,
                "semantic_pass_executed": getattr(self, '_semantic_pass_executed', False),
            },
            "synthesis_packet": self._synthesis_packet,
            "synthesis_output": {
                **(self._synthesis_output or {}),
                "dispositions": self._synthesis_dispositions or [],
            },
            "residue_verification": self._residue_verification,
            "positions": self._positions,
            "stability": self._stability,
            "analysis_map": self._analysis_map or [],
            "analysis_debug": self._analysis_debug,
            "diagnostics": self._diagnostics or {},
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
