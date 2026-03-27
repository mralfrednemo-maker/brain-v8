"""Evidence Ledger — stores, deduplicates, prioritizes, and formats evidence."""
from __future__ import annotations

import hashlib
from typing import Optional

from thinker.types import Confidence, EvidenceItem
from thinker.tools.cross_domain import is_cross_domain


# Priority score for eviction: higher = more likely to survive
_CONFIDENCE_SCORES = {
    Confidence.HIGH: 3,
    Confidence.MEDIUM: 2,
    Confidence.LOW: 1,
}


class EvidenceLedger:
    """Manages evidence items with dedup, cross-domain filtering, and cap enforcement.

    V8 spec Section 4: MAX_EVIDENCE_ITEMS = 10 per round with priority-based eviction.
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

        self._content_hashes.add(content_hash)
        self._seen_urls.add(item.url)
        item.content_hash = content_hash
        self.items.append(item)

        # Check for contradictions with existing items
        from thinker.tools.contradiction import detect_contradiction
        for existing in self.items[:-1]:  # Compare with all except the new one
            ctr = detect_contradiction(existing, item)
            if ctr:
                self.contradictions.append(ctr)

        # Enforce cap via eviction
        if len(self.items) > self.max_items:
            self._evict()

        return True

    def _evict(self):
        """Evict lowest-priority items to stay within max_items."""
        self.items.sort(key=lambda e: _CONFIDENCE_SCORES.get(e.confidence, 0), reverse=True)
        evicted = self.items[self.max_items:]
        self.items = self.items[:self.max_items]
        # Clean up tracking for evicted items
        for e in evicted:
            self._content_hashes.discard(e.content_hash)
            self._seen_urls.discard(e.url)

    def format_for_prompt(self) -> str:
        """Format all evidence for injection into a model prompt."""
        if not self.items:
            return ""
        lines = ["[RESEARCH CONTEXT — Web-verified evidence]\n"]
        for item in self.items:
            lines.append(
                f"{{{item.evidence_id}}} [{item.confidence.value}] {item.fact}\n"
                f"Source: {item.url}\n"
            )
        lines.append(
            "[EVIDENCE DISCIPLINE]\n"
            "Any specific number, percentage, or dollar figure in your analysis "
            "MUST cite an evidence ID (E001-E999) from the Research Context above."
        )
        return "\n".join(lines)
