"""Tests for PreflightAssessment (DoD v3.0 Section 4)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from thinker.types import (
    Answerability, BrainError, EffortTier, Modality, PreflightResult,
    PremiseFlagRouting, QuestionClass, SearchScope, StakesClass,
)


def _make_mock_llm(response_text: str):
    """Create a mock LLM client that returns the given text."""
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=True, text=response_text, elapsed_s=1.0)
    return mock


def _make_valid_response(**overrides):
    """Build a valid JSON response string for the preflight prompt."""
    import json
    data = {
        "answerability": "ANSWERABLE",
        "question_class": "OPEN",
        "stakes_class": "STANDARD",
        "effort_tier": "STANDARD",
        "modality": "DECIDE",
        "search_scope": "TARGETED",
        "exploration_required": False,
        "short_circuit_allowed": False,
        "fatal_premise": False,
        "follow_up_questions": [],
        "premise_flags": [],
        "hidden_context_gaps": [],
        "critical_assumptions": [
            {"assumption_id": "CA-1", "text": "Data is accurate", "verifiability": "VERIFIABLE", "material": True},
            {"assumption_id": "CA-2", "text": "Timeline is correct", "verifiability": "VERIFIABLE", "material": True},
            {"assumption_id": "CA-3", "text": "Scope is defined", "verifiability": "VERIFIABLE", "material": False},
        ],
        "reasoning": "Brief is well-formed and answerable.",
    }
    data.update(overrides)
    return json.dumps(data)


@pytest.mark.asyncio
async def test_preflight_answerable_brief():
    from thinker.preflight import run_preflight
    mock = _make_mock_llm(_make_valid_response())
    result = await run_preflight(mock, "A well-formed brief about security.")
    assert result.executed is True
    assert result.parse_ok is True
    assert result.answerability == Answerability.ANSWERABLE
    assert result.modality == Modality.DECIDE


@pytest.mark.asyncio
async def test_preflight_need_more_routes_correctly():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        answerability="NEED_MORE",
        follow_up_questions=["What system is affected?", "What is the timeline?"],
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Vague brief.")
    assert result.answerability == Answerability.NEED_MORE
    assert len(result.follow_up_questions) == 2


@pytest.mark.asyncio
async def test_preflight_invalid_form_maps_to_need_more_not_error():
    """DoD v3.0 Section 4.3: INVALID_FORM -> NEED_MORE, never ERROR."""
    from thinker.preflight import run_preflight
    resp = _make_valid_response(answerability="INVALID_FORM")
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Nonsensical brief.")
    assert result.answerability == Answerability.INVALID_FORM


@pytest.mark.asyncio
async def test_preflight_fatal_premise():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        answerability="NEED_MORE",
        fatal_premise=True,
        follow_up_questions=["The premise is fundamentally flawed because..."],
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Brief with broken premise.")
    assert result.fatal_premise is True


@pytest.mark.asyncio
async def test_preflight_parse_failure_raises_brain_error():
    """DoD v3.0 Section 4.5: missing/unparseable -> ERROR."""
    from thinker.preflight import run_preflight
    mock = _make_mock_llm("This is not JSON at all.")
    with pytest.raises(BrainError, match="preflight"):
        await run_preflight(mock, "Some brief.")


@pytest.mark.asyncio
async def test_preflight_llm_failure_raises_brain_error():
    from thinker.preflight import run_preflight
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=False, text="", error="timeout", elapsed_s=300.0)
    with pytest.raises(BrainError, match="preflight"):
        await run_preflight(mock, "Some brief.")


@pytest.mark.asyncio
async def test_preflight_short_circuit_guards():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        question_class="TRIVIAL",
        stakes_class="LOW",
        effort_tier="SHORT_CIRCUIT",
        short_circuit_allowed=True,
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "What color is the sky?")
    assert result.short_circuit_allowed is True
    assert result.effort_tier == EffortTier.SHORT_CIRCUIT


@pytest.mark.asyncio
async def test_preflight_elevated_effort_on_high_stakes():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        stakes_class="HIGH",
        effort_tier="ELEVATED",
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "High stakes brief.")
    assert result.stakes_class == StakesClass.HIGH
    assert result.effort_tier == EffortTier.ELEVATED


@pytest.mark.asyncio
async def test_preflight_analysis_modality():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(modality="ANALYSIS")
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Explore this topic.")
    assert result.modality == Modality.ANALYSIS


@pytest.mark.asyncio
async def test_preflight_premise_flags_with_routing():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        premise_flags=[
            {
                "flag_id": "PFLAG-1",
                "flag_type": "INTERNAL_CONTRADICTION",
                "severity": "CRITICAL",
                "summary": "Section A contradicts Section B",
                "routing": "MANAGEABLE_UNKNOWN",
            },
        ],
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Brief with contradiction.")
    assert len(result.premise_flags) == 1
    assert result.premise_flags[0].severity.value == "CRITICAL"
    assert result.has_critical_flags is True


@pytest.mark.asyncio
async def test_preflight_critical_assumptions():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        critical_assumptions=[
            {"assumption_id": "CA-1", "text": "Data is real-time", "verifiability": "UNVERIFIABLE", "material": True},
            {"assumption_id": "CA-2", "text": "User count is stable", "verifiability": "VERIFIABLE", "material": True},
            {"assumption_id": "CA-3", "text": "Budget exists", "verifiability": "VERIFIABLE", "material": False},
        ],
    )
    mock = _make_mock_llm(resp)
    result = await run_preflight(mock, "Brief with assumptions.")
    assert len(result.critical_assumptions) == 3
    assert result.has_fatal_assumptions is True  # CA-1 is UNVERIFIABLE + material


@pytest.mark.asyncio
async def test_preflight_to_dict_roundtrip():
    from thinker.preflight import run_preflight
    mock = _make_mock_llm(_make_valid_response())
    result = await run_preflight(mock, "Test brief.")
    d = result.to_dict()
    assert d["answerability"] == "ANSWERABLE"
    assert d["executed"] is True
    assert isinstance(d["premise_flags"], list)
    assert isinstance(d["critical_assumptions"], list)


@pytest.mark.asyncio
async def test_requester_fixable_requires_follow_up_questions():
    from thinker.preflight import run_preflight
    resp = _make_valid_response(
        premise_flags=[
            {
                "flag_id": "PFLAG-1",
                "flag_type": "AMBIGUITY",
                "severity": "WARNING",
                "summary": "Scope is unclear",
                "routing": PremiseFlagRouting.REQUESTER_FIXABLE.value,
            },
        ],
        follow_up_questions=[],
    )
    mock = _make_mock_llm(resp)
    with pytest.raises(BrainError, match="follow_up_questions"):
        await run_preflight(mock, "Brief missing scope.")
