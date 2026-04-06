"""Tests for the Ungrounded Stat Detector."""
from brain.tools.ungrounded import find_ungrounded_stats
from brain.types import Confidence, EvidenceItem


def test_finds_ungrounded_percentage():
    text = "This affects approximately 78% of enterprise deployments"
    evidence = []
    stats = find_ungrounded_stats(text, evidence)
    assert len(stats) >= 1
    assert "78%" in stats[0]


def test_grounded_stat_not_flagged():
    text = "According to the report, 847 requests were detected {E001}"
    evidence = [EvidenceItem("E001", "scope", "847 requests", "https://a.com", Confidence.HIGH)]
    stats = find_ungrounded_stats(text, evidence)
    assert len(stats) == 0


def test_multiple_ungrounded_stats():
    text = "The breach affected 340 tenants, with a 99.9% SLA impact and $2.5M in damages"
    evidence = []
    stats = find_ungrounded_stats(text, evidence)
    assert len(stats) >= 2
