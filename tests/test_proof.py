"""Tests for proof.json builder."""
from thinker.proof import ProofBuilder
from thinker.types import Confidence, Outcome, Position
from thinker.tools.blocker import BlockerLedger


class TestProofBuilder:

    def test_schema_version(self):
        pb = ProofBuilder(run_id="test-001", brief="Test brief", rounds_requested=4)
        proof = pb.build()
        assert proof["proof_schema_version"] == "2.0"
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
