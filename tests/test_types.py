"""Tests for core types."""
from thinker.types import (
    Argument, ArgumentStatus, BrainResult, Blocker, BlockerKind,
    BlockerStatus, Confidence, Contradiction, EvidenceItem, Gate1Result,
    Gate2Assessment, ModelResponse, Outcome, Position, RoundResult, SearchResult,
)
from thinker.config import ROUND_TOPOLOGY, MODEL_REGISTRY, BrainConfig


def test_outcome_values():
    assert Outcome.DECIDE.value == "DECIDE"
    assert Outcome.ESCALATE.value == "ESCALATE"
    assert Outcome.NEED_MORE.value == "NEED_MORE"


def test_round_topology_narrows():
    assert len(ROUND_TOPOLOGY[1]) == 4
    assert len(ROUND_TOPOLOGY[2]) == 3
    assert len(ROUND_TOPOLOGY[3]) == 2
    assert len(ROUND_TOPOLOGY[4]) == 2


def test_all_topology_models_in_registry():
    for round_num, models in ROUND_TOPOLOGY.items():
        for model_name in models:
            assert model_name in MODEL_REGISTRY, f"{model_name} missing from registry"


def test_round_result_responded():
    rr = RoundResult(round_num=1, responses={
        "r1": ModelResponse(model="r1", ok=True, text="analysis", elapsed_s=10.0),
        "glm5": ModelResponse(model="glm5", ok=False, text="", elapsed_s=5.0, error="timeout"),
    })
    assert rr.responded == ["r1"]
    assert rr.texts == {"r1": "analysis"}


def test_round_result_texts_excludes_failures():
    rr = RoundResult(round_num=1, responses={
        "r1": ModelResponse(model="r1", ok=True, text="yes", elapsed_s=1.0),
        "kimi": ModelResponse(model="kimi", ok=True, text="no", elapsed_s=2.0),
    })
    assert len(rr.texts) == 2


def test_brain_config_defaults():
    cfg = BrainConfig()
    assert cfg.rounds == 4
    assert cfg.max_evidence_items == 10


def test_evidence_item_creation():
    ev = EvidenceItem(
        evidence_id="E001", topic="JWT bypass", fact="CVE-2026-1234",
        url="https://nvd.nist.gov/...", confidence=Confidence.HIGH,
    )
    assert ev.evidence_id == "E001"
    assert ev.confidence == Confidence.HIGH


def test_argument_defaults():
    arg = Argument(argument_id="ARG-1", round_num=1, model="r1", text="The breach is severe")
    assert arg.status == ArgumentStatus.IGNORED
    assert arg.addressed_in_round is None


def test_blocker_lifecycle():
    b = Blocker(
        blocker_id="BLK001", kind=BlockerKind.CONTESTED_POSITION,
        source="position:O3", detected_round=1,
    )
    assert b.status == BlockerStatus.OPEN
    b.status = BlockerStatus.RESOLVED
    b.resolution_note = "All models converged"
    assert b.status == BlockerStatus.RESOLVED
