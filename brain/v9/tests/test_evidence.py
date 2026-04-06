"""Tests for the Evidence Ledger."""
import pytest

from brain.types import Confidence, EvidenceItem
from brain.evidence import EvidenceLedger, derive_topic_cluster, score_evidence


class TestEvidenceAdd:
    """Adding evidence to the ledger."""

    def test_add_item(self):
        ledger = EvidenceLedger(max_items=10)
        item = EvidenceItem("E001", "JWT bypass", "CVE found", "https://nvd.nist.gov", Confidence.HIGH)
        assert ledger.add(item) is True
        assert len(ledger.items) == 1
        assert ledger.items[0].topic_cluster == "nvd.nist.gov"

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

    def test_cap_enforced_fifo_reject(self):
        """Cap is enforced by rejecting new items when full (FIFO — earliest items preserved)."""
        ledger = EvidenceLedger(max_items=3)
        for i in range(3):
            assert ledger.add(EvidenceItem(
                f"E{i:03d}", "topic", f"fact {i}", f"https://{i}.com", Confidence.MEDIUM,
            )) is True
        # 4th item rejected — ledger is full
        assert ledger.add(EvidenceItem(
            "E003", "topic", "fact 3", "https://3.com", Confidence.MEDIUM,
        )) is False
        assert len(ledger.items) == 3

    def test_fifo_preserves_insertion_order(self):
        """When full, first 2 items are kept, 3rd is rejected (no confidence-based eviction)."""
        ledger = EvidenceLedger(max_items=2)
        ledger.add(EvidenceItem("E001", "t", "first fact", "https://1.com", Confidence.LOW))
        ledger.add(EvidenceItem("E002", "t", "second fact", "https://2.com", Confidence.HIGH))
        # Ledger is full — 3rd item rejected regardless of confidence
        assert ledger.add(EvidenceItem("E003", "t", "third fact", "https://3.com", Confidence.HIGH)) is False
        assert len(ledger.items) == 2
        ids = {e.evidence_id for e in ledger.items}
        assert ids == {"E001", "E002"}


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
        # No confidence tags in formatted output (removed in V8)
        assert "[HIGH]" not in text
        assert "[MEDIUM]" not in text

    def test_format_includes_citation_instruction(self):
        ledger = EvidenceLedger(max_items=10)
        ledger.add(EvidenceItem("E001", "JWT", "CVE found",
                                "https://nvd.nist.gov", Confidence.HIGH))
        text = ledger.format_for_prompt()
        assert "MUST cite an evidence ID" in text

    def test_empty_ledger_format(self):
        ledger = EvidenceLedger(max_items=10)
        text = ledger.format_for_prompt()
        assert text == ""


class TestEvidenceScoring:

    def test_keyword_overlap_increases_score(self):
        item = EvidenceItem("E001", "JWT bypass vulnerability",
                            "Critical JWT bypass found in auth system",
                            "https://a.com", Confidence.HIGH)
        score_high = score_evidence(item, brief_keywords={"jwt", "bypass", "auth"})
        score_low = score_evidence(item, brief_keywords={"cooking", "recipe"})
        assert score_high > score_low

    def test_known_domain_increases_score(self):
        item_good = EvidenceItem("E001", "CVE", "CVE found",
                                 "https://nvd.nist.gov/vuln/123", Confidence.HIGH)
        item_bad = EvidenceItem("E002", "CVE", "CVE found",
                                "https://random-blog.xyz/123", Confidence.HIGH)
        s1 = score_evidence(item_good, brief_keywords={"cve"})
        s2 = score_evidence(item_bad, brief_keywords={"cve"})
        assert s1 > s2

    def test_score_is_numeric(self):
        item = EvidenceItem("E001", "t", "fact", "https://a.com", Confidence.MEDIUM)
        score = score_evidence(item, brief_keywords=set())
        assert isinstance(score, (int, float))
        assert score > 0

    def test_base_score_with_no_keywords(self):
        item = EvidenceItem("E001", "t", "fact", "https://a.com", Confidence.MEDIUM)
        score = score_evidence(item, brief_keywords=set())
        assert score == 1.0

    def test_topic_cluster_falls_back_to_topic_words(self):
        item = EvidenceItem("E001", "JWT bypass vulnerability", "fact", "", Confidence.MEDIUM)
        assert derive_topic_cluster(item) == "jwt bypass vulnerability"


class TestEvidenceEviction:
    """F3: Under cap pressure, evict lowest-scored item instead of rejecting new."""

    def test_higher_scored_item_evicts_lower(self):
        ledger = EvidenceLedger(max_items=2, brief_keywords={"security", "breach"})
        # Add two low-relevance items
        ledger.add(EvidenceItem("E001", "cooking", "recipe for soup",
                                "https://recipes.com", Confidence.LOW))
        ledger.add(EvidenceItem("E002", "gardening", "plant tips",
                                "https://garden.com", Confidence.LOW))
        assert len(ledger.items) == 2
        # Add a high-relevance item — should evict lowest-scored
        result = ledger.add(EvidenceItem("E003", "breach", "Major security breach detected",
                                         "https://nvd.nist.gov/breach", Confidence.HIGH))
        assert result is True
        assert len(ledger.items) == 2
        ids = {e.evidence_id for e in ledger.items}
        assert "E003" in ids

    def test_lower_scored_item_rejected_when_full(self):
        ledger = EvidenceLedger(max_items=2, brief_keywords={"security", "breach"})
        # Add two high-relevance items
        ledger.add(EvidenceItem("E001", "breach", "Major security breach",
                                "https://nvd.nist.gov/1", Confidence.HIGH))
        ledger.add(EvidenceItem("E002", "security", "Authentication vulnerability exploit",
                                "https://nvd.nist.gov/2", Confidence.HIGH))
        # Add a low-relevance item — should be rejected
        result = ledger.add(EvidenceItem("E003", "cooking", "recipe",
                                         "https://recipes.com", Confidence.LOW))
        assert result is False
        assert len(ledger.items) == 2

    def test_insertion_order_preserved_within_same_score(self):
        """Trust search engine ranking: same-score items keep insertion order."""
        ledger = EvidenceLedger(max_items=10, brief_keywords=set())
        for i in range(5):
            ledger.add(EvidenceItem(f"E{i:03d}", "t", f"fact {i}",
                                    f"https://{i}.com", Confidence.MEDIUM))
        ids = [e.evidence_id for e in ledger.items]
        assert ids == ["E000", "E001", "E002", "E003", "E004"]


class TestTwoTierLedger:
    """V9: Two-tier evidence ledger — active + archive."""

    def test_eviction_moves_to_archive(self):
        ledger = EvidenceLedger(max_items=2, brief_keywords={"security", "breach"})
        ledger.add(EvidenceItem("E001", "cooking", "recipe for soup",
                                "https://recipes.com", Confidence.LOW))
        ledger.add(EvidenceItem("E002", "gardening", "plant tips",
                                "https://garden.com", Confidence.LOW))
        # High-relevance evicts lowest-scored to archive
        ledger.add(EvidenceItem("E003", "breach", "Major security breach detected",
                                "https://nvd.nist.gov/breach", Confidence.HIGH))
        assert len(ledger.active_items) == 2
        assert len(ledger.archive_items) == 1
        assert ledger.archive_items[0].is_archived is True
        assert ledger.archive_items[0].is_active is False

    def test_eviction_log_recorded(self):
        ledger = EvidenceLedger(max_items=1, brief_keywords={"security"})
        ledger.add(EvidenceItem("E001", "cooking", "recipe",
                                "https://recipes.com", Confidence.LOW))
        ledger.add(EvidenceItem("E002", "security", "breach detected",
                                "https://nvd.nist.gov/1", Confidence.HIGH))
        assert len(ledger.eviction_log) == 1
        assert ledger.eviction_log[0].evidence_id == "E001"

    def test_get_from_any_searches_both(self):
        ledger = EvidenceLedger(max_items=1, brief_keywords={"security"})
        ledger.add(EvidenceItem("E001", "cooking", "recipe",
                                "https://recipes.com", Confidence.LOW))
        ledger.add(EvidenceItem("E002", "security", "breach detected",
                                "https://nvd.nist.gov/1", Confidence.HIGH))
        # E001 is in archive, E002 is active
        assert ledger.get_from_any("E001") is not None
        assert ledger.get_from_any("E002") is not None
        assert ledger.get_from_any("E999") is None

    def test_all_items_returns_both(self):
        ledger = EvidenceLedger(max_items=1, brief_keywords={"security"})
        ledger.add(EvidenceItem("E001", "cooking", "recipe",
                                "https://recipes.com", Confidence.LOW))
        ledger.add(EvidenceItem("E002", "security", "breach detected",
                                "https://nvd.nist.gov/1", Confidence.HIGH))
        assert len(ledger.all_items) == 2

    def test_items_backward_compat(self):
        ledger = EvidenceLedger(max_items=10)
        ledger.add(EvidenceItem("E001", "t", "fact", "https://a.com", Confidence.HIGH))
        assert ledger.items is ledger.active_items
        assert len(ledger.items) == 1

    def test_high_authority_evidence_present(self):
        ledger = EvidenceLedger(max_items=10)
        ledger.add(EvidenceItem("E001", "t", "fact", "https://a.com", Confidence.HIGH,
                                authority_tier="HIGH"))
        assert ledger.high_authority_evidence_present is True

    def test_high_authority_not_present(self):
        ledger = EvidenceLedger(max_items=10)
        ledger.add(EvidenceItem("E001", "t", "fact", "https://a.com", Confidence.HIGH))
        assert ledger.high_authority_evidence_present is False

    def test_format_only_uses_active(self):
        ledger = EvidenceLedger(max_items=1, brief_keywords={"security"})
        ledger.add(EvidenceItem("E001", "cooking", "recipe for soup",
                                "https://recipes.com", Confidence.LOW))
        ledger.add(EvidenceItem("E002", "security", "breach detected",
                                "https://nvd.nist.gov/1", Confidence.HIGH))
        text = ledger.format_for_prompt()
        assert "{E002}" in text
        assert "{E001}" not in text  # archived, not in prompt

    def test_never_deletes_evidence(self):
        """V9 guarantee: eviction moves to archive, never deletes."""
        ledger = EvidenceLedger(max_items=1, brief_keywords={"security"})
        # Add low-relevance item first
        ledger.add(EvidenceItem("E001", "cooking", "recipe",
                                "https://recipes.com", Confidence.LOW))
        # Higher-relevance evicts to archive
        ledger.add(EvidenceItem("E002", "security", "breach found",
                                "https://nvd.nist.gov/1", Confidence.HIGH))
        # Verify: 1 active + 1 archive = 2 total, nothing deleted
        assert len(ledger.active_items) == 1
        assert len(ledger.archive_items) == 1
        assert len(ledger.all_items) == 2
        # Archived item still accessible
        assert ledger.get_from_any("E001") is not None
