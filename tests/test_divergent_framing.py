"""Tests for Divergent Framing (DoD v3.0 Section 8)."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from thinker.types import (
    BrainError, DivergenceResult, FrameInfo, FrameSurvivalStatus,
    FrameType, QuestionClass, StakesClass,
)


def _make_mock_llm(response_text: str):
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=True, text=response_text, elapsed_s=1.0)
    return mock


def _framing_extract_response(frame_count=3):
    frames = [
        {
            "frame_id": f"FRAME-{i+1}",
            "text": f"Alternative frame {i+1}",
            "origin_model": "r1",
            "frame_type": "INVERSION",
            "material_to_outcome": True,
        }
        for i in range(frame_count)
    ]
    return json.dumps({"frames": frames, "cross_domain_analogies": []})


@pytest.mark.asyncio
async def test_framing_extract_produces_frames():
    from thinker.divergent_framing import run_framing_extract
    mock = _make_mock_llm(_framing_extract_response(3))
    r1_texts = {"r1": "analysis 1", "kimi": "analysis 2", "reasoner": "analysis 3", "glm5": "analysis 4"}
    result = await run_framing_extract(mock, "Test brief", r1_texts)
    assert result.framing_pass_executed is True
    assert len(result.alt_frames) == 3


@pytest.mark.asyncio
async def test_framing_extract_llm_failure():
    from thinker.divergent_framing import run_framing_extract
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=False, text="", error="timeout", elapsed_s=300.0)
    with pytest.raises(BrainError, match="framing"):
        await run_framing_extract(mock, "Brief", {"r1": "text"})


@pytest.mark.asyncio
async def test_frame_survival_r2_needs_3_votes():
    from thinker.divergent_framing import run_frame_survival_check
    frames = [FrameInfo(frame_id="FRAME-1", text="test frame")]
    survival_resp = json.dumps({
        "evaluations": [
            {"frame_id": "FRAME-1", "status": "DROPPED", "drop_vote_models": ["r1", "kimi"], "reasoning": "test"}
        ]
    })
    mock = _make_mock_llm(survival_resp)
    result = await run_frame_survival_check(mock, frames, {"r1": "text", "kimi": "text"}, round_num=2)
    # Only 2 votes, not 3 — should be CONTESTED, not DROPPED
    assert result[0].survival_status == FrameSurvivalStatus.CONTESTED


@pytest.mark.asyncio
async def test_frame_survival_r2_drops_with_3_votes():
    from thinker.divergent_framing import run_frame_survival_check
    frames = [FrameInfo(frame_id="FRAME-1", text="test frame")]
    survival_resp = json.dumps({
        "evaluations": [
            {
                "frame_id": "FRAME-1",
                "status": "DROPPED",
                "drop_vote_models": ["r1", "kimi", "reasoner"],
                "drop_vote_refs": ["argument_id:R2-ARG-1", "evidence_id:E001", "argument_id:R2-ARG-2"],
                "reasoning": "test",
            }
        ]
    })
    mock = _make_mock_llm(survival_resp)
    result = await run_frame_survival_check(mock, frames, {"r1": "t", "kimi": "t", "reasoner": "t"}, round_num=2)
    assert result[0].survival_status == FrameSurvivalStatus.DROPPED
    assert result[0].r2_drop_vote_count == 3
    assert result[0].r2_drop_vote_refs == ["argument_id:R2-ARG-1", "evidence_id:E001", "argument_id:R2-ARG-2"]


@pytest.mark.asyncio
async def test_frame_survival_r2_requires_traceable_refs():
    from thinker.divergent_framing import run_frame_survival_check
    frames = [FrameInfo(frame_id="FRAME-1", text="test frame")]
    survival_resp = json.dumps({
        "evaluations": [
            {
                "frame_id": "FRAME-1",
                "status": "DROPPED",
                "drop_vote_models": ["r1", "kimi", "reasoner"],
                "drop_vote_refs": ["FRAME-1", "justification", "note"],
                "reasoning": "test",
            }
        ]
    })
    mock = _make_mock_llm(survival_resp)
    result = await run_frame_survival_check(mock, frames, {"r1": "t", "kimi": "t", "reasoner": "t"}, round_num=2)
    assert result[0].survival_status == FrameSurvivalStatus.CONTESTED


@pytest.mark.asyncio
async def test_frame_survival_r3_never_drops():
    from thinker.divergent_framing import run_frame_survival_check
    frames = [FrameInfo(frame_id="FRAME-1", text="test frame")]
    survival_resp = json.dumps({
        "evaluations": [
            {"frame_id": "FRAME-1", "status": "DROPPED", "drop_vote_models": ["r1", "kimi", "reasoner"], "reasoning": "test"}
        ]
    })
    mock = _make_mock_llm(survival_resp)
    result = await run_frame_survival_check(mock, frames, {"r1": "t", "reasoner": "t"}, round_num=3)
    # R3 never drops — should be CONTESTED
    assert result[0].survival_status == FrameSurvivalStatus.CONTESTED


def test_exploration_stress_triggers():
    from thinker.divergent_framing import check_exploration_stress
    assert check_exploration_stress(0.8, QuestionClass.OPEN, StakesClass.STANDARD) is True
    assert check_exploration_stress(0.8, QuestionClass.TRIVIAL, StakesClass.HIGH) is True
    assert check_exploration_stress(0.5, QuestionClass.OPEN, StakesClass.HIGH) is False
    assert check_exploration_stress(0.8, QuestionClass.TRIVIAL, StakesClass.LOW) is False


def test_format_frames_for_prompt():
    from thinker.divergent_framing import format_frames_for_prompt
    frames = [
        FrameInfo(frame_id="FRAME-1", text="test", survival_status=FrameSurvivalStatus.ACTIVE),
        FrameInfo(frame_id="FRAME-2", text="test2", survival_status=FrameSurvivalStatus.DROPPED),
    ]
    text = format_frames_for_prompt(frames)
    assert "FRAME-1" in text
    assert "FRAME-2" not in text  # DROPPED frames excluded


def test_format_frames_empty():
    from thinker.divergent_framing import format_frames_for_prompt
    assert format_frames_for_prompt([]) == ""


def test_format_r2_enforcement():
    from thinker.divergent_framing import format_r2_frame_enforcement
    text = format_r2_frame_enforcement()
    assert "ADOPT" in text
    assert "REBUT" in text
    assert "NEW_FRAME" in text


def test_validate_r2_frame_obligations_complete():
    from thinker.divergent_framing import validate_r2_frame_obligations
    result = validate_r2_frame_obligations({
        "r1": "ADOPT: FRAME-1\nREBUT: FRAME-2\nNEW_FRAME: Try a new lens",
    })
    assert result == {}


def test_validate_r2_frame_obligations_missing_markers():
    from thinker.divergent_framing import validate_r2_frame_obligations
    result = validate_r2_frame_obligations({
        "r1": "ADOPT: FRAME-1\nSome other text",
    })
    assert result == {"r1": ["REBUT", "NEW_FRAME"]}
