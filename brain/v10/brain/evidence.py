"""Evidence Ledger — stores, deduplicates, scores, and formats evidence.

Evidence items are kept in insertion order (search engine's ranking order).
V8-F3 adds relevance scoring: under cap pressure, the lowest-scored item
is evicted instead of blindly rejecting new items.
Cap at max_items. Within the same score tier, insertion order is preserved.

V9: Two-tier ledger — active_items (capped) + archive_items (uncapped).
Eviction moves to archive, never deletes. Referenced evidence always available.
"""
from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import urlparse

from brain.types import Confidence, EvidenceItem, EvictionEvent
from brain.tools.cross_domain import is_cross_domain

# Authoritative domains that get a score boost
_AUTHORITY_DOMAINS = {
    "nvd.nist.gov", "cve.mitre.org", "owasp.org", "sec.gov",
    "who.int", "cdc.gov", "fda.gov", "nih.gov",
    "ieee.org", "acm.org", "arxiv.org",
    "reuters.com", "bloomberg.com", "ft.com",
    "github.com", "docs.python.org", "docs.microsoft.com",
}


def derive_topic_cluster(item: EvidenceItem) -> str:
    """Derive a deterministic topic cluster from source metadata."""
    try:
        domain = urlparse(item.url).netloc.lower().strip()
    except Exception:
        domain = ""
    if domain:
        return domain.removeprefix("www.")

    topic_words = [word for word in item.topic.split() if word][:3]
    if topic_words:
        return " ".join(topic_words).lower()

    fact_words = [word for word in item.fact.split() if word][:3]
    return " ".join(fact_words).lower()


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

    # Source authority + set authority_tier
    try:
        domain = urlparse(item.url).netloc.lower()
        if any(auth in domain for auth in _AUTHORITY_DOMAINS):
            score += 2.0
            item.authority_tier = "HIGH"
    except Exception:
        pass

    return score


class EvidenceLedger:
    """Manages evidence items with dedup, cross-domain filtering, scoring, and cap enforcement.

    V9 two-tier architecture:
    - active_items: capped at max_items, used in prompts
    - archive_items: uncapped, evicted items preserved here
    - eviction_log: tracks all movements
    - Never deletes evidence — eviction moves to archive.
    """

    def __init__(self, max_items: int = 10, brief_domain: Optional[str] = None,
                 brief_keywords: Optional[set[str]] = None):
        self.active_items: list[EvidenceItem] = []
        self.archive_items: list[EvidenceItem] = []
        self.eviction_log: list[EvictionEvent] = []
        self.max_items = max_items
        self.brief_domain = brief_domain
        self.brief_keywords: set[str] = brief_keywords or set()
        self._content_hashes: set[str] = set()
        self._seen_urls: set[str] = set()
        self.cross_domain_rejections: int = 0
        self.contradictions: list = []
        self._eviction_counter: int = 0

    @property
    def items(self) -> list[EvidenceItem]:
        """Backward compatibility: returns active items."""
        return self.active_items

    @property
    def all_items(self) -> list[EvidenceItem]:
        """All evidence items (active + archived)."""
        return self.active_items + self.archive_items

    @property
    def high_authority_evidence_present(self) -> bool:
        """Whether any evidence (active or archive) has HIGH or AUTHORITATIVE authority tier."""
        return any(
            e.authority_tier in ("HIGH", "AUTHORITATIVE")
            for e in self.active_items + self.archive_items
        )

    def get_from_any(self, evidence_id: str) -> Optional[EvidenceItem]:
        """Search both active and archive for an evidence item by ID."""
        for item in self.active_items:
            if item.evidence_id == evidence_id:
                return item
        for item in self.archive_items:
            if item.evidence_id == evidence_id:
                return item
        return None

    def all_evidence_ids(self) -> set[str]:
        """Return all evidence IDs across active and archive."""
        return {e.evidence_id for e in self.active_items} | {e.evidence_id for e in self.archive_items}

    def validate_refs(self, refs: list[str]) -> list[str]:
        """Return any evidence_refs that don't exist in either store.

        DOD §10.3: "Cited evidence missing from both stores → ERROR"
        """
        known = self.all_evidence_ids()
        return [ref for ref in refs if ref and ref not in known]

    def _evict_to_archive(self, item: EvidenceItem, reason: str = "cap_pressure") -> None:
        """Move an item from active to archive."""
        self.active_items.remove(item)
        item.is_active = False
        item.is_archived = True
        self.archive_items.append(item)
        self._eviction_counter += 1
        self.eviction_log.append(EvictionEvent(
            event_id=f"EVICT-{self._eviction_counter}",
            evidence_id=item.evidence_id,
            from_active=True,
            to_archive=True,
            reason=reason,
        ))

    def add(self, item: EvidenceItem) -> bool:
        """Add evidence item. Returns False if rejected.

        Rejection reasons: duplicate content, duplicate URL, cross-domain,
        or lower-scored than all existing items when ledger is full.
        Under cap pressure: if the new item scores higher than the
        lowest-scored existing item, evict that item to archive.
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
        if not item.topic_cluster:
            item.topic_cluster = derive_topic_cluster(item)
        item.score = score_evidence(item, self.brief_keywords)
        item.is_active = True
        item.is_archived = False

        # Cap check with eviction to archive
        if len(self.active_items) >= self.max_items:
            min_item = min(self.active_items, key=lambda e: e.score)
            if item.score > min_item.score:
                # Evict the lowest-scored item to archive
                self._content_hashes.discard(min_item.content_hash)
                self._seen_urls.discard(min_item.url)
                self._evict_to_archive(min_item, reason="cap_pressure_score_eviction")
            else:
                return False

        self._content_hashes.add(content_hash)
        self._seen_urls.add(item.url)
        item.content_hash = content_hash
        self.active_items.append(item)

        # DOD §10.3: "Active exceeds 10 → ERROR" — post-condition check
        if len(self.active_items) > self.max_items:
            from brain.types import BrainError
            raise BrainError(
                "evidence_ledger",
                f"Active evidence exceeds cap: {len(self.active_items)} > {self.max_items}",
                detail="DOD §10.3: Active exceeds 10 → ERROR",
            )

        # Check for contradictions with existing active items
        from brain.tools.contradiction import detect_contradiction
        for existing in self.active_items[:-1]:
            ctr = detect_contradiction(existing, item)
            if ctr:
                self.contradictions.append(ctr)

        return True

    def format_for_prompt(self) -> str:
        """Format evidence for injection into a model prompt.

        DOD §10.2: active evidence first, then high-authority archive items.
        Archive items are marked [ARCHIVED] so models know they are evicted
        but still authoritative.
        """
        if not self.active_items and not self.archive_items:
            return ""
        lines = []
        for item in self.active_items:
            lines.append(
                f"{{{item.evidence_id}}} {item.fact}\n"
                f"Source: {item.url}\n"
            )
        # DOD §10.2: archived high-authority evidence must be visible to Gate 2 reasoning
        high_auth_archive = [
            e for e in self.archive_items
            if e.authority_tier in ("HIGH", "AUTHORITATIVE")
        ]
        if high_auth_archive:
            lines.append("## Archived High-Authority Evidence (evicted from active set but authoritative)\n")
            for item in high_auth_archive:
                lines.append(
                    f"[ARCHIVED] {{{item.evidence_id}}} {item.fact}\n"
                    f"Source: {item.url}\n"
                )
        if lines:
            lines.append(
                "Any specific number, percentage, or dollar figure in your analysis "
                "MUST cite an evidence ID (E001-E999) from above."
            )
        return "\n".join(lines)
