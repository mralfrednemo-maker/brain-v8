"""Tests for the Evidence Ledger."""
import pytest

from thinker.types import Confidence, EvidenceItem
from thinker.evidence import EvidenceLedger


class TestEvidenceAdd:
    """Adding evidence to the ledger."""

    def test_add_item(self):
        ledger = EvidenceLedger(max_items=10)
        item = EvidenceItem("E001", "JWT bypass", "CVE found", "https://nvd.nist.gov", Confidence.HIGH)
        assert ledger.add(item) is True
        assert len(ledger.items) == 1

    def test_duplicate_content_rejected(self):
        ledger = EvidenceLedger(max_items=10)
        item1 = EvidenceItem("E001", "JWT", "Same fact", "https://a.com", Confidence.HIGH)
        item2 = EvidenceItem("E002", "JWT", "Same fact", "https://b.com", Confidence.HIGH)
        ledger.add(item1)
        assert ledger.add(item2) is False
        assert len(ledger.items) == 1

    def test_duplicate_url_rejected(self):
        ledger = EvidenceLedger(max_items=10)
        item1 = EvidenceItem("E001", "JWT", "Fact 1", "https://a.com", Confidence.HIGH)
        item2 = EvidenceItem("E002", "JWT", "Fact 2", "https://a.com", Confidence.MEDIUM)
        ledger.add(item1)
        assert ledger.add(item2) is False

    def test_cap_enforced(self):
        ledger = EvidenceLedger(max_items=3)
        for i in range(5):
            ledger.add(EvidenceItem(
                f"E{i:03d}", "topic", f"fact {i}", f"https://{i}.com", Confidence.MEDIUM,
            ))
        assert len(ledger.items) <= 3

    def test_high_confidence_survives_eviction(self):
        ledger = EvidenceLedger(max_items=2)
        ledger.add(EvidenceItem("E001", "t", "low fact", "https://1.com", Confidence.LOW))
        ledger.add(EvidenceItem("E002", "t", "high fact", "https://2.com", Confidence.HIGH))
        ledger.add(EvidenceItem("E003", "t", "med fact", "https://3.com", Confidence.MEDIUM))
        ids = {e.evidence_id for e in ledger.items}
        assert "E002" in ids  # HIGH confidence survives


class TestCrossDomainFilter:
    """Cross-domain evidence filtering."""

    def test_medical_evidence_rejected_for_security_brief(self):
        ledger = EvidenceLedger(max_items=10, brief_domain="security")
        item = EvidenceItem("E001", "dosage", "Patient treatment dosage 500mg daily medication", "https://webmd.com", Confidence.HIGH)
        assert ledger.add(item) is False
        assert ledger.cross_domain_rejections == 1

    def test_security_evidence_accepted_for_security_brief(self):
        ledger = EvidenceLedger(max_items=10, brief_domain="security")
        item = EvidenceItem("E001", "CVE", "RCE vulnerability", "https://nvd.nist.gov", Confidence.HIGH)
        assert ledger.add(item) is True

    def test_no_filter_when_domain_unset(self):
        ledger = EvidenceLedger(max_items=10)
        item = EvidenceItem("E001", "dosage", "Take 500mg", "https://webmd.com", Confidence.HIGH)
        assert ledger.add(item) is True


class TestEvidenceFormat:
    """Formatting evidence for injection into model prompts."""

    def test_format_for_prompt(self):
        ledger = EvidenceLedger(max_items=10)
        ledger.add(EvidenceItem("E001", "JWT", "CVE-2026-1234 is critical",
                                "https://nvd.nist.gov/1234", Confidence.HIGH))
        ledger.add(EvidenceItem("E002", "breach", "847 requests exploited bypass",
                                "https://report.com", Confidence.MEDIUM))
        text = ledger.format_for_prompt()
        assert "{E001}" in text
        assert "{E002}" in text
        assert "CVE-2026-1234" in text
        assert "[HIGH]" in text
        assert "[MEDIUM]" in text

    def test_empty_ledger_format(self):
        ledger = EvidenceLedger(max_items=10)
        text = ledger.format_for_prompt()
        assert text == ""
