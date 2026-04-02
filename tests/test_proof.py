"""Tests for proof.json builder."""
from thinker.proof import ProofBuilder
from thinker.types import AcceptanceStatus, Confidence, Outcome, Position
from thinker.tools.blocker import BlockerLedger


class TestProofBuilder:

    def test_schema_version(self):
        pb = ProofBuilder(run_id="test-001", brief="Test brief", rounds_requested=4)
        proof = pb.build()
        assert proof["proof_schema_version"] == "3.0"
        assert proof["run_id"] == "test-001"

    def test_records_round_results(self):
        pb = ProofBuilder(run_id="test-001", brief="Brief", rounds_requested=3)
        pb.record_round(1, responded=["r1", "glm5", "kimi", "reasoner"], failed=[])
        pb.record_round(2, responded=["r1", "glm5", "reasoner"], failed=[])
        proof = pb.build()
        assert len(proof["rounds"]) == 2
        assert proof["rounds"]["1"]["responded"] == ["r1", "glm5", "kimi", "reasoner"]

    def test_records_positions(self):
        pb = ProofBuilder(run_id="test-001", brief="Brief", rounds_requested=3)
        pb.record_positions(1, {
            "r1": Position("r1", 1, "O3", confidence=Confidence.HIGH),
            "glm5": Position("glm5", 1, "O4", confidence=Confidence.HIGH),
        })
        proof = pb.build()
        assert proof["model_positions_by_round"]["1"]["r1"]["primary_option"] == "O3"

    def test_records_outcome(self):
        pb = ProofBuilder(run_id="test-001", brief="Brief", rounds_requested=3)
        pb.set_outcome(Outcome.DECIDE, agreement_ratio=1.0, outcome_class="CONSENSUS")
        proof = pb.build()
        assert proof["controller_outcome"]["outcome_class"] == "CONSENSUS"

    def test_includes_blocker_summary(self):
        pb = ProofBuilder(run_id="test-001", brief="Brief", rounds_requested=3)
        ledger = BlockerLedger()
        pb.set_blocker_ledger(ledger)
        proof = pb.build()
        assert "blocker_summary" in proof

    def test_acceptance_status_in_proof(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.compute_acceptance_status()
        proof = pb.build()
        assert "acceptance_status" in proof

    def test_synthesis_residue_in_proof(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_synthesis_residue([{"type": "blocker", "id": "BLK001"}])
        proof = pb.build()
        assert len(proof["synthesis_residue_omissions"]) == 1

    def test_compatible_with_v7_schema(self):
        """V8 proof must contain all fields present in V7 proof."""
        required_fields = [
            "proof_schema_version", "run_id", "rounds_requested",
            "final_status", "evidence_items", "controller_outcome",
            "model_positions_by_round", "blocker_ledger", "blocker_summary",
        ]
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        proof = pb.build()
        for field in required_fields:
            assert field in proof, f"Missing required field: {field}"


class TestAcceptanceStatus:

    def test_accepted_on_clean_run(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_outcome(Outcome.DECIDE, agreement_ratio=1.0, outcome_class="CONSENSUS")
        pb.compute_acceptance_status()
        proof = pb.build()
        assert proof["acceptance_status"] == "ACCEPTED"

    def test_review_required_non_consensus(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_outcome(Outcome.DECIDE, agreement_ratio=0.8, outcome_class="CLOSED_WITH_ACCEPTED_RISKS")
        pb.compute_acceptance_status()
        proof = pb.build()
        assert proof["acceptance_status"] == "REVIEW_REQUIRED"

    def test_review_required_on_violations(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_outcome(Outcome.DECIDE, agreement_ratio=1.0, outcome_class="CONSENSUS")
        pb.add_violation("INV-1", "WARN", "minor issue")
        pb.compute_acceptance_status()
        proof = pb.build()
        assert proof["acceptance_status"] == "REVIEW_REQUIRED"

    def test_review_required_on_escalate(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_outcome(Outcome.ESCALATE, agreement_ratio=0.4, outcome_class="NO_CONSENSUS")
        pb.compute_acceptance_status()
        proof = pb.build()
        assert proof["acceptance_status"] == "REVIEW_REQUIRED"

    def test_never_rejected(self):
        """acceptance_status is never REJECTED — BrainError stops pipeline before proof."""
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_outcome(Outcome.ESCALATE, agreement_ratio=0.0, outcome_class="NO_CONSENSUS")
        pb.add_violation("INV-1", "ERROR", "bad")
        pb.add_violation("INV-2", "ERROR", "worse")
        pb.compute_acceptance_status()
        proof = pb.build()
        assert proof["acceptance_status"] in ("ACCEPTED", "REVIEW_REQUIRED")


class TestSearchDecision:

    def test_gate1_decision_recorded(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_search_decision(source="gate1", value=True, reasoning="Regulatory facts need verification")
        proof = pb.build()
        assert proof["search_decision"]["source"] == "gate1"
        assert proof["search_decision"]["value"] is True

    def test_cli_override_recorded(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_search_decision(
            source="cli_override", value=False, reasoning="Forced off via --no-search",
            gate1_recommended=True,
        )
        proof = pb.build()
        sd = proof["search_decision"]
        assert sd["source"] == "cli_override"
        assert sd["value"] is False
        assert sd["gate1_recommended"] is True

    def test_no_gate1_recommended_when_not_overridden(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=3)
        pb.set_search_decision(source="gate1", value=True, reasoning="needs search")
        proof = pb.build()
        assert "gate1_recommended" not in proof["search_decision"]


class TestProofV9:
    """V9 proof schema 3.0 additions."""

    def test_v9_sections_present(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=4)
        proof = pb.build()
        assert proof["protocol_version"] == "v9"
        assert "preflight" in proof
        assert "dimensions" in proof
        assert "stability" in proof
        assert "gate2" in proof

    def test_set_preflight(self):
        from thinker.types import PreflightResult
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=4)
        pf = PreflightResult()
        pb.set_preflight(pf)
        proof = pb.build()
        assert proof["preflight"]["answerability"] == "ANSWERABLE"

    def test_set_dimensions(self):
        from thinker.types import DimensionSeedResult, DimensionItem
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=4)
        ds = DimensionSeedResult(items=[DimensionItem("DIM-1", "Legal")], dimension_count=1)
        pb.set_dimensions(ds)
        proof = pb.build()
        assert proof["dimensions"]["dimension_count"] == 1

    def test_set_stability(self):
        from thinker.types import StabilityResult
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=4)
        sr = StabilityResult(groupthink_warning=True)
        pb.set_stability(sr)
        proof = pb.build()
        assert proof["stability"]["groupthink_warning"] is True

    def test_set_gate2_trace(self):
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=4)
        pb.set_gate2_trace("DECIDE", [{"rule": "D1", "matched": True}], "DECIDE")
        proof = pb.build()
        assert proof["gate2"]["modality"] == "DECIDE"
        assert len(proof["gate2"]["rule_trace"]) == 1

    def test_set_evidence_two_tier(self):
        from thinker.types import EvidenceItem, Confidence, EvictionEvent
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=4)
        active = [EvidenceItem("E001", "t", "f", "https://a.com", Confidence.HIGH)]
        archive = [EvidenceItem("E002", "t", "f2", "https://b.com", Confidence.LOW)]
        evlog = [EvictionEvent("EVICT-1", "E002")]
        pb.set_evidence_two_tier(active, archive, evlog)
        proof = pb.build()
        assert proof["evidence"]["active_count"] == 1
        assert proof["evidence"]["archive_count"] == 1

    def test_set_contradictions(self):
        from thinker.types import Contradiction, SemanticContradiction
        pb = ProofBuilder(run_id="test", brief="b", rounds_requested=4)
        numeric = [Contradiction("CTR-1", ["E1", "E2"], "t", "HIGH")]
        semantic = [SemanticContradiction(ctr_id="CTR-SEM-1")]
        pb.set_contradictions(numeric, semantic)
        proof = pb.build()
        assert len(proof["contradictions"]["numeric"]) == 1
        assert len(proof["contradictions"]["semantic"]) == 1
