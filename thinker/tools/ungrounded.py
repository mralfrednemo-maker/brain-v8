"""Ungrounded Stat Detector — flags claims with numbers not backed by evidence."""
from __future__ import annotations

import re

from thinker.types import EvidenceItem

_STAT_PATTERN = re.compile(
    r"(\d[\d,.]*\s*%"
    r"|\$[\d,.]+[BMK]?"
    r"|\d{2,}[\d,]*)"
)

_EVIDENCE_REF = re.compile(r"\{E\d+\}")


def find_ungrounded_stats(
    text: str, evidence: list[EvidenceItem],
) -> list[str]:
    evidence_numbers = set()
    for ev in evidence:
        for m in _STAT_PATTERN.finditer(ev.fact):
            evidence_numbers.add(m.group().strip())

    ungrounded = []
    for match in _STAT_PATTERN.finditer(text):
        stat = match.group().strip()
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end]

        if _EVIDENCE_REF.search(context):
            continue

        if stat in evidence_numbers:
            continue

        ungrounded.append(stat)

    return ungrounded


def generate_verification_queries(ungrounded_stats: list[str], context: str) -> list[str]:
    queries = []
    for stat in ungrounded_stats[:5]:
        idx = context.find(stat)
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(context), idx + len(stat) + 100)
            snippet = context[start:end].strip()
            queries.append(f"verify {stat} {snippet[:50]}")
        else:
            queries.append(f"verify statistic {stat}")
    return queries
