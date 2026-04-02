"""Tests for Semantic Contradiction (DoD v3.0 Section 12)."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from thinker.types import (
    BrainError, Confidence, ContradictionSeverity, ContradictionStatus,
    DetectionMode, EvidenceItem, SemanticContradiction,
)


def _make_mock_llm(response_text: str):
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=True, text=response_text, elapsed_s=1.0)
    return mock


def _make_evidence(eid, topic, fact="fact", cluster="security", authority="STANDARD"):
    return EvidenceItem(
        evidence_id=eid, topic=topic, fact=fact,
        url=f"https://example.com/{eid}", confidence=Confidence.HIGH,
        topic_cluster=cluster, authority_tier=authority,
    )


def test_shortlist_pairs_same_topic():
    from thinker.semantic_contradiction import shortlist_pairs
    items = [
        _make_evidence("E1", "JWT bypass", cluster="auth"),
        _make_evidence("E2", "JWT bypass", cluster="auth"),
        _make_evidence("E3", "Database migration", cluster="infra"),
    ]
    pairs = shortlist_pairs(items)
    # E1-E2 share topic and cluster. E3 has different cluster.
    assert len(pairs) == 1
    assert (items[0], items[1]) in pairs


def test_shortlist_pairs_high_authority():
    from thinker.semantic_contradiction import shortlist_pairs
    items = [
        _make_evidence("E1", "topic A", cluster="same", authority="HIGH"),
        _make_evidence("E2", "topic B", cluster="same", authority="AUTHORITATIVE"),
    ]
    pairs = shortlist_pairs(items)
    assert len(pairs) == 1


def test_shortlist_pairs_no_match():
    from thinker.semantic_contradiction import shortlist_pairs
    items = [
        _make_evidence("E1", "JWT bypass", cluster="auth"),
        _make_evidence("E2", "Database migration", cluster="infra"),
    ]
    pairs = shortlist_pairs(items)
    assert len(pairs) == 0


@pytest.mark.asyncio
async def test_semantic_contradiction_detected():
    from thinker.semantic_contradiction import run_semantic_contradiction_pass
    items = [
        _make_evidence("E1", "JWT bypass", fact="CVSS 9.8", cluster="auth"),
        _make_evidence("E2", "JWT bypass", fact="CVSS 4.0", cluster="auth"),
    ]
    resp = json.dumps({
        "contradicts": True,
        "severity": "HIGH",
        "same_entity": True,
        "same_timeframe": True,
        "justification": "Conflicting CVSS scores for same vulnerability",
    })
    mock = _make_mock_llm(resp)
    result = await run_semantic_contradiction_pass(mock, items)
    assert len(result) == 1
    assert result[0].detection_mode == DetectionMode.SEMANTIC
    assert result[0].severity == ContradictionSeverity.HIGH
    assert result[0].status == ContradictionStatus.OPEN


@pytest.mark.asyncio
async def test_semantic_contradiction_not_detected():
    from thinker.semantic_contradiction import run_semantic_contradiction_pass
    items = [
        _make_evidence("E1", "JWT bypass", fact="Patch available", cluster="auth"),
        _make_evidence("E2", "JWT bypass", fact="Fix deployed", cluster="auth"),
    ]
    resp = json.dumps({
        "contradicts": False,
        "severity": "LOW",
        "same_entity": True,
        "same_timeframe": True,
        "justification": "Consistent information",
    })
    mock = _make_mock_llm(resp)
    result = await run_semantic_contradiction_pass(mock, items)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_semantic_contradiction_empty_input():
    from thinker.semantic_contradiction import run_semantic_contradiction_pass
    mock = _make_mock_llm("")
    result = await run_semantic_contradiction_pass(mock, [])
    assert result == []


@pytest.mark.asyncio
async def test_semantic_contradiction_llm_failure():
    from thinker.semantic_contradiction import run_semantic_contradiction_pass
    items = [
        _make_evidence("E1", "JWT bypass", cluster="auth"),
        _make_evidence("E2", "JWT bypass", cluster="auth"),
    ]
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=False, text="", error="timeout", elapsed_s=300.0)
    with pytest.raises(BrainError, match="semantic_contradiction"):
        await run_semantic_contradiction_pass(mock, items)


@pytest.mark.asyncio
async def test_semantic_contradiction_to_dict():
    ctr = SemanticContradiction(
        ctr_id="CTR-SEM-1",
        evidence_ref_a="E1", evidence_ref_b="E2",
        severity=ContradictionSeverity.HIGH,
    )
    d = ctr.to_dict()
    assert d["detection_mode"] == "SEMANTIC"
    assert d["severity"] == "HIGH"
