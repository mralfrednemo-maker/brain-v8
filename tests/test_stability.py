"""Tests for Stability Tests (DoD v3.0 Section 15)."""
import pytest

from thinker.types import (
    AssumptionVerifiability, Confidence, CriticalAssumption, DecisiveClaim,
    EvidenceSupportStatus, Position, QuestionClass, StabilityResult, StakesClass,
)


def _make_position(model, option="Option A", round_num=4):
    return Position(model=model, round_num=round_num, primary_option=option)


def test_conclusion_stable_all_agree():
    from thinker.stability import compute_conclusion_stability
    positions = {
        "r1": _make_position("r1", "Option A"),
        "reasoner": _make_position("reasoner", "Option A"),
    }
    assert compute_conclusion_stability(positions) is True


def test_conclusion_unstable_disagreement():
    from thinker.stability import compute_conclusion_stability
    positions = {
        "r1": _make_position("r1", "Option A"),
        "reasoner": _make_position("reasoner", "Option B"),
    }
    assert compute_conclusion_stability(positions) is False


def test_conclusion_empty_positions():
    from thinker.stability import compute_conclusion_stability
    assert compute_conclusion_stability({}) is False


def test_reason_stable_with_supported_claims():
    from thinker.stability import compute_reason_stability
    claims = [
        DecisiveClaim(claim_id="C1", text="test", material_to_conclusion=True,
                      evidence_support_status=EvidenceSupportStatus.SUPPORTED),
    ]
    positions = {"r1": _make_position("r1")}
    assert compute_reason_stability(positions, claims) is True


def test_reason_unstable_no_claims():
    from thinker.stability import compute_reason_stability
    assert compute_reason_stability({"r1": _make_position("r1")}, []) is False


def test_reason_unstable_unsupported():
    from thinker.stability import compute_reason_stability
    claims = [
        DecisiveClaim(claim_id="C1", text="test", material_to_conclusion=True,
                      evidence_support_status=EvidenceSupportStatus.UNSUPPORTED),
    ]
    assert compute_reason_stability({"r1": _make_position("r1")}, claims) is False


def test_assumption_stable_no_issues():
    from thinker.stability import compute_assumption_stability
    assumptions = [
        CriticalAssumption(assumption_id="CA-1", text="test",
                           verifiability=AssumptionVerifiability.VERIFIABLE, material=True),
    ]
    assert compute_assumption_stability(assumptions) is True


def test_assumption_unstable():
    from thinker.stability import compute_assumption_stability
    assumptions = [
        CriticalAssumption(assumption_id="CA-1", text="test",
                           verifiability=AssumptionVerifiability.UNVERIFIABLE, material=True),
    ]
    assert compute_assumption_stability(assumptions) is False


def test_assumption_stable_empty():
    from thinker.stability import compute_assumption_stability
    assert compute_assumption_stability([]) is True


def test_fast_consensus_detection():
    from thinker.stability import detect_fast_consensus
    r1_pos = {
        "r1": _make_position("r1", "Option A", round_num=1),
        "kimi": _make_position("kimi", "Option A", round_num=1),
        "reasoner": _make_position("reasoner", "Option A", round_num=1),
        "glm5": _make_position("glm5", "Option A", round_num=1),
    }
    assert detect_fast_consensus({1: r1_pos}) is True


def test_no_fast_consensus():
    from thinker.stability import detect_fast_consensus
    r1_pos = {
        "r1": _make_position("r1", "Option A", round_num=1),
        "kimi": _make_position("kimi", "Option B", round_num=1),
    }
    assert detect_fast_consensus({1: r1_pos}) is False


def test_groupthink_warning():
    from thinker.stability import compute_groupthink_warning
    assert compute_groupthink_warning(True, QuestionClass.OPEN, StakesClass.HIGH, False) is True
    assert compute_groupthink_warning(False, QuestionClass.OPEN, StakesClass.HIGH, False) is False
    assert compute_groupthink_warning(True, QuestionClass.TRIVIAL, StakesClass.LOW, False) is False
    assert compute_groupthink_warning(True, QuestionClass.OPEN, StakesClass.HIGH, True) is False


def test_run_stability_tests_full():
    from thinker.stability import run_stability_tests
    positions = {
        "r1": _make_position("r1", "Option A"),
        "reasoner": _make_position("reasoner", "Option A"),
    }
    claims = [
        DecisiveClaim(claim_id="C1", text="test", material_to_conclusion=True,
                      evidence_support_status=EvidenceSupportStatus.SUPPORTED),
    ]
    assumptions = [
        CriticalAssumption(assumption_id="CA-1", text="test",
                           verifiability=AssumptionVerifiability.VERIFIABLE, material=True),
    ]
    r1_pos = {
        "r1": _make_position("r1", "Option A", round_num=1),
        "kimi": _make_position("kimi", "Option B", round_num=1),
    }
    result = run_stability_tests(
        positions, claims, assumptions, {1: r1_pos},
        QuestionClass.OPEN, StakesClass.STANDARD,
    )
    assert isinstance(result, StabilityResult)
    assert result.conclusion_stable is True
    assert result.reason_stable is True
    assert result.assumption_stable is True
    assert result.fast_consensus_observed is False
    assert result.groupthink_warning is False


def test_stability_to_dict():
    sr = StabilityResult(
        conclusion_stable=True, reason_stable=False,
        assumption_stable=True, groupthink_warning=True,
    )
    d = sr.to_dict()
    assert d["conclusion_stable"] is True
    assert d["reason_stable"] is False
    assert d["groupthink_warning"] is True
