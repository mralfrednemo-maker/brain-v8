"""Evidence Ledger — stores, deduplicates, scores, and formats evidence.

Evidence items are kept in insertion order (search engine's ranking order).
V8-F3 adds relevance scoring: under cap pressure, the lowest-scored item
is evicted instead of blindly rejecting new items.
Cap at max_items. Within the same score tier, insertion order is preserved.
"""
from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import urlparse

from thinker.types import Confidence, EvidenceItem
from thinker.tools.cross_domain import is_cross_domain

# Authoritative domains that get a score boost
_AUTHORITY_DOMAINS = {
    "nvd.nist.gov", "cve.mitre.org", "owasp.org", "sec.gov",
    "who.int", "cdc.gov", "fda.gov", "nih.gov",
    "ieee.org", "acm.org", "arxiv.org",
    "reuters.com", "bloomberg.com", "ft.com",
    "github.com", "docs.python.org", "docs.microsoft.com",
}


def score_evidence(item: EvidenceItem, brief_keywords: set[str]) -> float:
    """Score evidence item for relevance.

    Factors:
    - Keyword overlap with brief (0-5 points, 1 per keyword match, capped)
    - Source authority (0 or 2 points for known authoritative domains)
    - Base score of 1.0 so all items have positive score
    """
    score = 1.0

    # Keyword overlap
    text_lower = (item.topic + " " + item.fact).lower()
    kw_hits = 0
    for kw in brief_keywords:
        if kw.lower() in text_lower:
            kw_hits += 1
    score += min(kw_hits, 5)

    # Source authority
    try:
        domain = urlparse(item.url).netloc.lower()
        if any(auth in domain for auth in _AUTHORITY_DOMAINS):
            score += 2.0
    except Exception:
        pass

    return score


class EvidenceLedger:
    """Manages evidence items with dedup, cross-domain filtering, scoring, and cap enforcement.

    Items are kept in search engine ranking order (insertion order).
    Under cap pressure, the lowest-scored item is evicted if the new
    item scores higher. Otherwise the new item is rejected.
    """

    def __init__(self, max_items: int = 10, brief_domain: Optional[str] = None,
                 brief_keywords: Optional[set[str]] = None):
        self.items: list[EvidenceItem] = []
        self.max_items = max_items
        self.brief_domain = brief_domain
        self.brief_keywords: set[str] = brief_keywords or set()
        self._content_hashes: set[str] = set()
        self._seen_urls: set[str] = set()
        self.cross_domain_rejections: int = 0
        self.contradictions: list = []

    def add(self, item: EvidenceItem) -> bool:
        """Add evidence item. Returns False if rejected.

        Rejection reasons: duplicate content, duplicate URL, cross-domain,
        or lower-scored than all existing items when ledger is full.
        Under cap pressure: if the new item scores higher than the
        lowest-scored existing item, evict that item and insert the new one.
        """
        # Cross-domain filter
        if self.brief_domain and is_cross_domain(item.fact + " " + item.topic, self.brief_domain):
            self.cross_domain_rejections += 1
            return False

        # Content dedup
        content_hash = hashlib.sha256(item.fact.encode()).hexdigest()[:16]
        if content_hash in self._content_hashes:
            return False

        # URL dedup
        if item.url in self._seen_urls:
            return False

        # Score the new item
        item.score = score_evidence(item, self.brief_keywords)

        # Cap check with eviction
        if len(self.items) >= self.max_items:
            min_item = min(self.items, key=lambda e: e.score)
            if item.score > min_item.score:
                # Evict the lowest-scored item
                self._content_hashes.discard(min_item.content_hash)
                self._seen_urls.discard(min_item.url)
                self.items.remove(min_item)
            else:
                return False

        self._content_hashes.add(content_hash)
        self._seen_urls.add(item.url)
        item.content_hash = content_hash
        self.items.append(item)

        # Check for contradictions with existing items
        from thinker.tools.contradiction import detect_contradiction
        for existing in self.items[:-1]:
            ctr = detect_contradiction(existing, item)
            if ctr:
                self.contradictions.append(ctr)

        return True

    def format_for_prompt(self) -> str:
        """Format all evidence for injection into a model prompt."""
        if not self.items:
            return ""
        lines = []
        for i, item in enumerate(self.items, 1):
            lines.append(
                f"{{{item.evidence_id}}} {item.fact}\n"
                f"Source: {item.url}\n"
            )
        lines.append(
            "Any specific number, percentage, or dollar figure in your analysis "
            "MUST cite an evidence ID (E001-E999) from above."
        )
        return "\n".join(lines)
