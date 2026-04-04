"""Semantic Contradiction — Sonnet-based contradiction detection (DoD v3.0 Section 12).

Shortlists evidence pairs by topic cluster + polarity/entity/timeframe overlap.
Runs Sonnet per pair to detect contradictions. Complements existing numeric detector.
"""
from __future__ import annotations

import json
from itertools import combinations

from thinker.pipeline import pipeline_stage
from thinker.types import (
    BrainError, ContradictionSeverity, ContradictionStatus,
    DetectionMode, EvidenceItem, SemanticContradiction,
)

CONTRADICTION_PROMPT = """You are a semantic contradiction detector.

Evaluate whether these two evidence items contradict each other.

## Evidence A
- ID: {ev_a_id}
- Topic: {ev_a_topic}
- Fact: {ev_a_fact}
- URL: {ev_a_url}

## Evidence B
- ID: {ev_b_id}
- Topic: {ev_b_topic}
- Fact: {ev_b_fact}
- URL: {ev_b_url}

## Output Format — STRICT JSON

{{
  "contradicts": true/false,
  "severity": "LOW | MEDIUM | HIGH",
  "same_entity": true/false,
  "same_timeframe": true/false,
  "justification": "explanation of the contradiction or why there is none"
}}

## Rules
- Two items contradict if they make claims that cannot both be true
- severity HIGH: directly opposite claims about the same entity/event
- severity MEDIUM: inconsistent implications or conflicting metrics
- severity LOW: tension but not direct contradiction
- same_entity: both items discuss the same organization, product, event
- same_timeframe: both items describe the same time period"""


def shortlist_pairs(
    evidence_items: list[EvidenceItem],
    decisive_claim_evidence_ids: set[str] | None = None,
    open_blocker_ids: set[str] | None = None,
) -> list[tuple[EvidenceItem, EvidenceItem]]:
    """Shortlist evidence pairs for semantic contradiction checking.

    DOD §12.2 criteria: same topic_cluster AND any of:
    - same entity (inferred from topic overlap)
    - linked to decisive claim, blocker, or open contradiction (criterion 3)
    - both high authority
    """
    decisive_claim_evidence_ids = decisive_claim_evidence_ids or set()
    open_blocker_ids = open_blocker_ids or set()

    pairs = []
    for a, b in combinations(evidence_items, 2):
        # Must share topic cluster (or both have empty cluster)
        if a.topic_cluster and b.topic_cluster and a.topic_cluster != b.topic_cluster:
            continue

        qualifies = False

        # Same topic suggests same entity
        if a.topic and b.topic and (
            a.topic.lower() == b.topic.lower()
            or a.topic.lower() in b.topic.lower()
            or b.topic.lower() in a.topic.lower()
        ):
            qualifies = True

        # DOD §12.2 criterion 3: at least one member linked to decisive claim, blocker, or open contradiction
        if (a.evidence_id in decisive_claim_evidence_ids or
                b.evidence_id in decisive_claim_evidence_ids or
                a.referenced_by and b.referenced_by):
            qualifies = True

        # Both have high authority (important to check)
        if a.authority_tier in ("HIGH", "AUTHORITATIVE") and b.authority_tier in ("HIGH", "AUTHORITATIVE"):
            qualifies = True

        if qualifies:
            pairs.append((a, b))

    return pairs


@pipeline_stage(
    name="Semantic Contradiction",
    description="Sonnet-based contradiction detection on shortlisted evidence pairs.",
    stage_type="track",
    order=15,
    provider="sonnet",
    inputs=["evidence_pairs"],
    outputs=["SemanticContradiction[]"],
    logic="Shortlist by topic cluster. Sonnet per pair. Build CTR records.",
    failure_mode="LLM failure: BrainError per pair.",
    cost="1 Sonnet call per shortlisted pair",
    stage_id="semantic_contradiction",
)
async def run_semantic_contradiction_pass(
    client,
    evidence_items: list[EvidenceItem],
    decisive_claim_evidence_ids: set[str] | None = None,
    open_blocker_ids: set[str] | None = None,
) -> list[SemanticContradiction]:
    """Run semantic contradiction detection on shortlisted evidence pairs.

    DOD §12.2: shortlist criteria require linkage to decisive claims or blockers.
    """
    pairs = shortlist_pairs(evidence_items, decisive_claim_evidence_ids, open_blocker_ids)
    if not pairs:
        return []

    contradictions = []
    ctr_counter = 1

    for ev_a, ev_b in pairs:
        prompt = CONTRADICTION_PROMPT.format(
            ev_a_id=ev_a.evidence_id, ev_a_topic=ev_a.topic,
            ev_a_fact=ev_a.fact, ev_a_url=ev_a.url,
            ev_b_id=ev_b.evidence_id, ev_b_topic=ev_b.topic,
            ev_b_fact=ev_b.fact, ev_b_url=ev_b.url,
        )

        resp = await client.call("sonnet", prompt)
        if not resp.ok:
            raise BrainError("semantic_contradiction",
                             f"Semantic contradiction LLM call failed for {ev_a.evidence_id} vs {ev_b.evidence_id}: {resp.error}")

        text = resp.text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = "\n".join(text.split("\n")[:-1])
        text = text.strip()

        try:
            from thinker.types import extract_json
            data = extract_json(text)
        except json.JSONDecodeError as e:
            raise BrainError("semantic_contradiction",
                             f"Failed to parse contradiction JSON for {ev_a.evidence_id} vs {ev_b.evidence_id}: {e}",
                             detail=resp.text[:500])

        if data.get("contradicts", False):
            try:
                severity = ContradictionSeverity(data.get("severity", "MEDIUM"))
            except ValueError:
                severity = ContradictionSeverity.MEDIUM

            contradictions.append(SemanticContradiction(
                ctr_id=f"CTR-SEM-{ctr_counter}",
                detection_mode=DetectionMode.SEMANTIC,
                evidence_ref_a=ev_a.evidence_id,
                evidence_ref_b=ev_b.evidence_id,
                same_entity=data.get("same_entity", False),
                same_timeframe=data.get("same_timeframe", False),
                severity=severity,
                status=ContradictionStatus.OPEN,
                justification=data.get("justification", ""),
            ))
            ctr_counter += 1

    return contradictions
