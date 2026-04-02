"""Tests for Dimension Seeder (DoD v3.0 Section 6)."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import json

from thinker.types import BrainError, DimensionSeedResult


def _make_mock_llm(response_text: str):
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=True, text=response_text, elapsed_s=1.0)
    return mock


def _valid_dimensions_response(count=4):
    dims = [
        {"dimension_id": f"DIM-{i+1}", "name": f"Dimension {i+1}", "mandatory": True}
        for i in range(count)
    ]
    return json.dumps({"dimensions": dims})


@pytest.mark.asyncio
async def test_seeder_produces_3_to_5_dimensions():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm(_valid_dimensions_response(4))
    result = await run_dimension_seeder(mock, "Test brief")
    assert result.seeded is True
    assert result.dimension_count == 4
    assert len(result.items) == 4


@pytest.mark.asyncio
async def test_seeder_fewer_than_3_raises_error():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm(_valid_dimensions_response(2))
    with pytest.raises(BrainError, match="dimension"):
        await run_dimension_seeder(mock, "Test brief")


@pytest.mark.asyncio
async def test_seeder_caps_at_5():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm(_valid_dimensions_response(7))
    result = await run_dimension_seeder(mock, "Test brief")
    assert result.dimension_count == 5


@pytest.mark.asyncio
async def test_seeder_parse_failure_raises_error():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm("Not JSON")
    with pytest.raises(BrainError, match="dimension"):
        await run_dimension_seeder(mock, "Test brief")


@pytest.mark.asyncio
async def test_seeder_llm_failure_raises_error():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=False, text="", error="timeout", elapsed_s=300.0)
    with pytest.raises(BrainError, match="dimension"):
        await run_dimension_seeder(mock, "Test brief")


@pytest.mark.asyncio
async def test_seeder_to_dict():
    from thinker.dimension_seeder import run_dimension_seeder
    mock = _make_mock_llm(_valid_dimensions_response(3))
    result = await run_dimension_seeder(mock, "Test brief")
    d = result.to_dict()
    assert d["seeded"] is True
    assert len(d["items"]) == 3


@pytest.mark.asyncio
async def test_seeder_formats_for_prompt():
    from thinker.dimension_seeder import run_dimension_seeder, format_dimensions_for_prompt
    mock = _make_mock_llm(_valid_dimensions_response(3))
    result = await run_dimension_seeder(mock, "Test brief")
    text = format_dimensions_for_prompt(result.items)
    assert "DIM-1" in text
    assert "DIM-2" in text
    assert "DIM-3" in text
