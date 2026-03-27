"""Evidence Ledger — stores, deduplicates, and formats evidence.

Evidence items are kept in insertion order (Google's ranking order).
No confidence re-ranking — we trust Google's authority ranking.
Cap at max_items, FIFO eviction (oldest/lowest-ranked items dropped first).
"""
from __future__ import annotations

import hashlib
from typing import Optional

from thinker.types import Confidence, EvidenceItem
from thinker.tools.cross_domain import is_cross_domain


class EvidenceLedger:
    """Manages evidence items with dedup, cross-domain filtering, and cap enforcement.

    Items are kept in Google's ranking order (insertion order).
    Cap enforced via FIFO eviction — newest items from later searches
    are dropped first, preserving the highest-ranked earliest results.
    """

    def __init__(self, max_items: int = 10, brief_domain: Optional[str] = None):
        self.items: list[EvidenceItem] = []
        self.max_items = max_items
        self.brief_domain = brief_domain
        self._content_hashes: set[str] = set()
        self._seen_urls: set[str] = set()
        self.cross_domain_rejections: int = 0
        self.contradictions: list = []

    def add(self, item: EvidenceItem) -> bool:
        """Add evidence item. Returns False if rejected (duplicate, cross-domain, etc.)."""
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

        # Cap check — reject if full (preserves Google rank order of existing items)
        if len(self.items) >= self.max_items:
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
