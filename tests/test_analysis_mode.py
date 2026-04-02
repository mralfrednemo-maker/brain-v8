"""Tests for ANALYSIS mode."""
from thinker.analysis_mode import get_analysis_round_preamble, get_analysis_synthesis_contract


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
