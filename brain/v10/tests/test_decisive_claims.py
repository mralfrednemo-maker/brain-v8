"""Tests for Decisive Claim Extraction."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from brain.types import DecisiveClaim, EvidenceSupportStatus


def _make_mock_llm(response_text: str):
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=True, text=response_text, elapsed_s=1.0)
    return mock


@pytest.mark.asyncio
async def test_extracts_claims():
    from brain.decisive_claims import extract_decisive_claims
    resp = json.dumps({"claims": [
        {"claim_id": "DC-1", "text": "CVE is critical", "material_to_conclusion": True,
         "evidence_refs": ["E001"], "evidence_support_status": "SUPPORTED"},
        {"claim_id": "DC-2", "text": "No lateral movement", "material_to_conclusion": True,
         "evidence_refs": [], "evidence_support_status": "UNSUPPORTED"},
    ]})
    mock = _make_mock_llm(resp)
    claims = await extract_decisive_claims(mock, {"r1": "analysis"}, "E001: CVE found")
    assert len(claims) == 2
    assert claims[0].evidence_support_status == EvidenceSupportStatus.SUPPORTED
    assert claims[1].evidence_support_status == EvidenceSupportStatus.UNSUPPORTED


@pytest.mark.asyncio
async def test_llm_failure_returns_empty():
    from brain.decisive_claims import extract_decisive_claims
    mock = AsyncMock()
    mock.call.return_value = MagicMock(ok=False, text="", error="timeout", elapsed_s=300.0)
    claims = await extract_decisive_claims(mock, {"r1": "text"}, "")
    assert claims == []


@pytest.mark.asyncio
async def test_parse_failure_returns_empty():
    from brain.decisive_claims import extract_decisive_claims
    mock = _make_mock_llm("not json at all")
    claims = await extract_decisive_claims(mock, {"r1": "text"}, "")
    assert claims == []


@pytest.mark.asyncio
async def test_caps_at_8():
    from brain.decisive_claims import extract_decisive_claims
    resp = json.dumps({"claims": [
        {"claim_id": f"DC-{i}", "text": f"claim {i}", "material_to_conclusion": True,
         "evidence_refs": [], "evidence_support_status": "UNSUPPORTED"}
        for i in range(12)
    ]})
    mock = _make_mock_llm(resp)
    claims = await extract_decisive_claims(mock, {"r1": "text"}, "")
    assert len(claims) == 8


@pytest.mark.asyncio
async def test_to_dict():
    from brain.decisive_claims import extract_decisive_claims
    resp = json.dumps({"claims": [
        {"claim_id": "DC-1", "text": "test", "material_to_conclusion": True,
         "evidence_refs": ["E001"], "evidence_support_status": "PARTIAL"},
    ]})
    mock = _make_mock_llm(resp)
    claims = await extract_decisive_claims(mock, {"r1": "text"}, "E001: fact")
    d = claims[0].to_dict()
    assert d["evidence_support_status"] == "PARTIAL"
    assert d["claim_id"] == "DC-1"
