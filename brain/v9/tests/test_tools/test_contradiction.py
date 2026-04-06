"""Tests for the Contradiction Detector."""
from brain.types import Confidence, Contradiction, EvidenceItem
from brain.tools.contradiction import detect_contradiction


def test_numeric_conflict_detected():
    e1 = EvidenceItem("E001", "breach scope", "847 requests exploited the bypass",
                      "https://a.com", Confidence.HIGH)
    e2 = EvidenceItem("E002", "breach scope", "Over 2000 requests detected during the incident",
                      "https://b.com", Confidence.MEDIUM)
    result = detect_contradiction(e1, e2)
    assert result is not None
    assert result.severity == "HIGH"
    assert "E001" in result.evidence_ids
    assert "E002" in result.evidence_ids


def test_no_conflict_when_topics_differ():
    e1 = EvidenceItem("E001", "breach scope", "847 requests", "https://a.com", Confidence.HIGH)
    e2 = EvidenceItem("E002", "GDPR timeline", "72 hours to notify", "https://b.com", Confidence.HIGH)
    result = detect_contradiction(e1, e2)
    assert result is None


def test_no_conflict_when_numbers_match():
    e1 = EvidenceItem("E001", "timeline", "847 requests in 33 minutes", "https://a.com", Confidence.HIGH)
    e2 = EvidenceItem("E002", "timeline", "847 anomalous requests detected", "https://b.com", Confidence.MEDIUM)
    result = detect_contradiction(e1, e2)
    assert result is None
