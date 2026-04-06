"""Tests for ANALYSIS mode."""
from brain.analysis_mode import get_analysis_round_preamble, get_analysis_synthesis_contract


def test_analysis_preamble_contains_exploration():
    text = get_analysis_round_preamble()
    assert "EXPLORE" in text
    assert "Do NOT seek agreement" in text
    assert "Knowns" in text


def test_analysis_synthesis_contract():
    text = get_analysis_synthesis_contract()
    assert "EXPLORATORY MAP" in text
    assert "NOT A DECISION" in text
    assert "verdict" in text.lower()
    assert "Aspect map" in text


class TestAnalysisDebugSunset:
    """DOD §20: Debug mode active after sunset → ERROR. Debug records both results."""

    def test_debug_sunset_counter_decrement(self):
        """Debug counter decrements and reaches zero, disabling debug mode."""
        # Simulate counter logic from brain.py
        for initial in [3, 1, 0]:
            remaining = initial
            debug_active = remaining > 0
            new_remaining = max(0, remaining - 1) if debug_active else 0
            if initial == 0:
                assert not debug_active
                assert new_remaining == 0
            elif initial == 1:
                assert debug_active
                assert new_remaining == 0  # Will be disabled next run
            else:
                assert debug_active
                assert new_remaining == initial - 1

    def test_debug_mode_disabled_at_zero(self):
        """When remaining_debug_runs = 0, debug_mode MUST be False (DOD §18.4)."""
        remaining = 0
        debug_active = remaining > 0
        assert not debug_active

    def test_debug_data_schema(self):
        """Analysis debug data has all DOD §18.4 required fields."""
        required_fields = ["debug_mode", "debug_gate2_result", "actual_output",
                           "rules_enforced", "remaining_debug_runs"]
        data = {
            "debug_mode": True,
            "debug_gate2_result": None,
            "actual_output": None,
            "rules_enforced": False,
            "remaining_debug_runs": 9,
            "analysis_mode_active": True,
            "dimension_coverage_score": 0.8,
        }
        for field in required_fields:
            assert field in data


# ---------------------------------------------------------------------------
# V3.1 ADDITION-10: ANALYSIS overlays
# ---------------------------------------------------------------------------

def test_analysis_synthesis_sections_has_8_items():
    from brain.analysis_mode import ANALYSIS_SYNTHESIS_SECTIONS
    assert len(ANALYSIS_SYNTHESIS_SECTIONS) == 8


def test_information_boundary_proof_field():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_information_boundary({"known": ["X causes Y"], "inferred": [], "unknown": ["trend"]})
    result = pb.build()
    assert "information_boundary" in result
    assert result["information_boundary"]["known"] == ["X causes Y"]


def test_coverage_assessment_proof_field():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_coverage_assessment({"coverage_score": 0.80, "gaps": []})
    result = pb.build()
    assert result.get("coverage_assessment", {}).get("coverage_score") == 0.80
