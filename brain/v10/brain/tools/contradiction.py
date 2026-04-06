"""Contradiction Detector — finds numeric conflicts between evidence items."""
from __future__ import annotations

import re
from typing import Optional

from brain.types import Contradiction, EvidenceItem

_NUMBER_PATTERN = re.compile(r"\b(\d[\d,.]*%?)\b")


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_PATTERN.findall(text))


def _topic_overlap(a: str, b: str) -> int:
    words_a = {w.lower() for w in a.split() if len(w) >= 4}
    words_b = {w.lower() for w in b.split() if len(w) >= 4}
    return len(words_a & words_b)


_CONTRADICTION_COUNTER = 0


def detect_contradiction(
    item_a: EvidenceItem, item_b: EvidenceItem,
) -> Optional[Contradiction]:
    global _CONTRADICTION_COUNTER

    if _topic_overlap(item_a.topic + " " + item_a.fact, item_b.topic + " " + item_b.fact) < 2:
        return None

    nums_a = _extract_numbers(item_a.fact)
    nums_b = _extract_numbers(item_b.fact)

    if not nums_a or not nums_b:
        return None

    # If all numbers in the smaller set appear in the larger set, no contradiction
    # (one item may just have more detail)
    if nums_a.issubset(nums_b) or nums_b.issubset(nums_a):
        return None

    _CONTRADICTION_COUNTER += 1
    # HIGH if the unique numbers differ significantly (both have exclusive numbers)
    exclusive_a = nums_a - nums_b
    exclusive_b = nums_b - nums_a
    severity = "HIGH" if exclusive_a and exclusive_b else "MEDIUM"
    return Contradiction(
        ctr_id=f"CTR{_CONTRADICTION_COUNTER:03d}",
        evidence_ids=[item_a.evidence_id, item_b.evidence_id],
        topic=item_a.topic,
        severity=severity,
        evidence_ref_a=item_a.evidence_id,
        evidence_ref_b=item_b.evidence_id,
        same_entity=item_a.topic_cluster == item_b.topic_cluster if item_a.topic_cluster else False,
        same_timeframe=True,  # Numeric contradictions on same topic assumed same timeframe
    )
