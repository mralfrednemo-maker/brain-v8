"""Tests for Perspective Cards (DoD v3.0 Section 7)."""
import pytest
from thinker.types import BrainError, CoverageObligation, PerspectiveCard, TimeHorizon


def test_extract_cards_from_r1():
    from thinker.perspective_cards import extract_perspective_cards
    r1_texts = {
        "kimi": "PRIMARY_FRAME: Devil's advocate\nHIDDEN_ASSUMPTION_ATTACKED: Cost is fixed\nSTAKEHOLDER_LENS: End users\nTIME_HORIZON: SHORT\nFAILURE_MODE: Adoption resistance",
        "r1": "PRIMARY_FRAME: Technical feasibility\nHIDDEN_ASSUMPTION_ATTACKED: Scale assumptions\nSTAKEHOLDER_LENS: Engineering team\nTIME_HORIZON: MEDIUM\nFAILURE_MODE: Technical debt",
        "reasoner": "PRIMARY_FRAME: Risk analysis\nHIDDEN_ASSUMPTION_ATTACKED: Timeline is realistic\nSTAKEHOLDER_LENS: Management\nTIME_HORIZON: LONG\nFAILURE_MODE: Budget overrun",
        "glm5": "PRIMARY_FRAME: Operational impact\nHIDDEN_ASSUMPTION_ATTACKED: Team capacity\nSTAKEHOLDER_LENS: Operations\nTIME_HORIZON: MEDIUM\nFAILURE_MODE: Downtime",
    }
    cards = extract_perspective_cards(r1_texts)
    assert len(cards) == 4
    assert all(c.primary_frame for c in cards)
    assert all(c.failure_mode for c in cards)


def test_extract_cards_missing_fields_raises_error():
    """DOD §7.3 + zero tolerance: if too few models produce cards → ERROR."""
    from thinker.perspective_cards import extract_perspective_cards
    r1_texts = {
        "kimi": "Some analysis without structured fields",
        "r1": "Another analysis",
        "reasoner": "Third analysis",
        "glm5": "Fourth analysis",
    }
    with pytest.raises(BrainError, match="produced perspective cards"):
        extract_perspective_cards(r1_texts)


def test_coverage_obligations_assigned():
    from thinker.perspective_cards import extract_perspective_cards
    r1_texts = {
        "kimi": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
        "r1": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
        "reasoner": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
        "glm5": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
    }
    cards = extract_perspective_cards(r1_texts)
    obligations = {c.coverage_obligation for c in cards}
    assert CoverageObligation.CONTRARIAN in obligations


def test_cards_to_dict():
    from thinker.perspective_cards import extract_perspective_cards
    r1_texts = {
        "kimi": "PRIMARY_FRAME: test\nHIDDEN_ASSUMPTION_ATTACKED: test\nSTAKEHOLDER_LENS: test\nTIME_HORIZON: SHORT\nFAILURE_MODE: test",
        "r1": "PRIMARY_FRAME: t\nHIDDEN_ASSUMPTION_ATTACKED: t\nSTAKEHOLDER_LENS: t\nTIME_HORIZON: MEDIUM\nFAILURE_MODE: t",
        "reasoner": "PRIMARY_FRAME: t\nHIDDEN_ASSUMPTION_ATTACKED: t\nSTAKEHOLDER_LENS: t\nTIME_HORIZON: LONG\nFAILURE_MODE: t",
        "glm5": "PRIMARY_FRAME: t\nHIDDEN_ASSUMPTION_ATTACKED: t\nSTAKEHOLDER_LENS: t\nTIME_HORIZON: SHORT\nFAILURE_MODE: t",
    }
    cards = extract_perspective_cards(r1_texts)
    dicts = [c.to_dict() for c in cards]
    assert all("model_id" in d for d in dicts)
    assert all("coverage_obligation" in d for d in dicts)
