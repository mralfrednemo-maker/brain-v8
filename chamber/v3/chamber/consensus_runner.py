from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import datetime as _dt
from pathlib import Path
from typing import Any

from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage
from pydantic import BaseModel, Field, ValidationError

from consensus_runner import (
    AnthropicChatCompletionClient,
    DeepSeekChatCompletionClient,
    DeepSeekReasonerChatCompletionClient,
    KimiK2ChatCompletionClient,
    SonarProSearchClient,
    ZhipuChatCompletionClient,
    _load_dotenv_if_present,
    _normalize_finish_reason,
)

# Load .env early so BRAVE_API_KEY is available at module level
_load_dotenv_if_present()
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
BRAVE_SEARCH_ENABLED = bool(BRAVE_API_KEY)
MAX_BRAVE_QUERIES_PER_CYCLE = 3
MAX_BRAVE_RESULTS_PER_QUERY = 3

# Sonar Pro deep-dive (targeted, after Auditor, on unresolved blocking objections)
SONAR_DEEP_ENABLED = bool(os.environ.get("OPENROUTER_API_KEY", "")) and not os.environ.get("SONAR_DISABLED")
MAX_SONAR_DEEP_QUERIES = 2  # Only 1-2 targeted queries on hardest objections


class Evidence(BaseModel):
    evidence_id: str
    topic: str
    source_type: str
    fact: str
    value: str | None = None
    units: str | None = None
    confidence: str
    supports_claim_ids: list[str] = Field(default_factory=list)


class EvidencePack(BaseModel):
    evidence: list[Evidence]


class Claim(BaseModel):
    claim_id: str
    claim_text: str
    importance: str
    evidence_ids: list[str] = Field(default_factory=list)
    superseded_by: str | None = None


class Recommendation(BaseModel):
    item_id: str
    name: str
    rank: int
    role_in_portfolio: str
    thesis: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    known_risks: list[str] = Field(default_factory=list)


class ProposalPack(BaseModel):
    proposal_id: str
    claims: list[Claim]
    recommendations: list[Recommendation]


class ObjectionResponse(BaseModel):
    objection_id: str
    response: str
    action: str


class StrategistPatch(BaseModel):
    patch_id: str
    revised_claims: list[Claim] = Field(default_factory=list)
    dropped_claim_ids: list[str] = Field(default_factory=list)
    revised_recommendations: list[Recommendation] = Field(default_factory=list)
    rank_changes: list[dict] = Field(default_factory=list)
    objection_responses: list[ObjectionResponse] = Field(default_factory=list)


class Objection(BaseModel):
    objection_id: str
    claim_id: str
    severity: str
    type: str
    objection_text: str
    requested_evidence: list[str] = Field(default_factory=list)
    status: str = "OPEN"
    controller_status: str = "OPEN"
    scope: str = "ITEM"
    blocking: bool = True
    issue_key: str = ""
    raised_in_cycle: int = 0
    last_seen_cycle: int = 0
    introduced_by_revision: bool = False
    disposition: str = "OPEN"
    blocking_class: str = "RISK_ONLY"
    guard_held: bool = False
    non_gating: bool = False


class ObjectionPack(BaseModel):
    objections: list[Objection]


class ClaimScore(BaseModel):
    claim_id: str
    support_level: str
    support_reason: str
    missing_evidence: list[str] = Field(default_factory=list)


class RecommendationDecision(BaseModel):
    item_id: str
    decision: str
    reason: str


class ObjectionFinding(BaseModel):
    objection_id: str
    disposition: str
    rationale: str
    upgrade_to_blocking: bool = False


class PortfolioAssessment(BaseModel):
    concentration_risk: str = "NONE"
    overlap_risk: str = "NONE"
    thematic_overexposure: str = "NONE"
    valuation_regime_risk: str = "NONE"
    confidence_penalty: float = 0.0
    summary: str = ""


class AuditSnapshot(BaseModel):
    overall_evidence_quality: str
    claim_scores: list[ClaimScore]
    recommendation_decisions: list[RecommendationDecision] = Field(default_factory=list)
    unresolved_objections: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    progress_assessment: str
    eligible_for_judgment: bool
    objection_findings: list[ObjectionFinding] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)
    portfolio_assessment: PortfolioAssessment | None = None


class ConsensusVerdict(BaseModel):
    status: str
    confidence: float
    approved_items: list[str] = Field(default_factory=list)
    rejected_items: list[str] = Field(default_factory=list)
    unresolved_points: list[str] = Field(default_factory=list)
    rationale: str
    next_action: str = ""
    # SLP — supplementary, added by controller at verdict time
    standalone_leverage_profiles: list[dict] = Field(default_factory=list)
    highest_standalone_leverage: dict | None = None
    # Exclusive-choice mode — added by controller when brief requires single selection
    choice_mode: str = "portfolio"  # "portfolio" or "exclusive"
    selected_option: dict | None = None  # {item_id, label, source_type, selection_rationale} or None


# ---------------------------------------------------------------------------
# Standalone Leverage Profile (SLP) — schema models
# Controller-synthesized from final adjudicated state.  V-next only.
# ---------------------------------------------------------------------------

# Allowed categorical bands per dimension
SLP_IMPACT_BANDS = ("CRITICAL", "HIGH", "MODERATE", "LOW")
SLP_FEASIBILITY_BANDS = ("HIGH", "MODERATE", "LOW", "UNCERTAIN")
SLP_TIME_BANDS = ("IMMEDIATE", "NEAR_TERM", "FLEXIBLE", "UNCERTAIN")
SLP_REVERSIBILITY_BANDS = ("BOUNDED", "MANAGEABLE", "HEAVY", "SEVERE")
SLP_EVIDENCE_BANDS = ("STRONG", "ADEQUATE", "LIMITED", "WEAK")
SLP_ELIGIBILITY_STATES = ("ELIGIBLE", "CONDITIONALLY_ELIGIBLE", "INELIGIBLE_FOR_HIGHLIGHT")
SLP_HIGHLIGHT_CONFIDENCE = ("CLEAR", "MARGINAL", "INDETERMINATE")


class SLPDimension(BaseModel):
    rating: str
    rationale: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    constraining_objections: list[str] = Field(default_factory=list)


class SLPEligibility(BaseModel):
    status: str  # ELIGIBLE | CONDITIONALLY_ELIGIBLE | INELIGIBLE_FOR_HIGHLIGHT
    reason: str = ""
    applicability_condition: str | None = None


class StandaloneLeverageProfile(BaseModel):
    item_id: str
    standalone_eligibility: SLPEligibility
    standalone_impact: SLPDimension
    execution_feasibility: SLPDimension
    time_to_protective_effect: SLPDimension
    reversibility_downside: SLPDimension
    evidence_confidence: SLPDimension
    standalone_summary: str = ""
    portfolio_dependency_note: str = ""


class SLPHighlight(BaseModel):
    item_id: str | None = None
    confidence: str = "INDETERMINATE"  # CLEAR | MARGINAL | INDETERMINATE
    rationale: str = ""
    caveat: str = ""


class RunLedger(BaseModel):
    run_id: str
    task: str
    cycle_index: int = 0
    max_cycles: int = 3
    evidence_ledger: list[Evidence] = Field(default_factory=list)
    proposal_history: list[ProposalPack] = Field(default_factory=list)
    objection_history: list[ObjectionPack] = Field(default_factory=list)
    audit_history: list[AuditSnapshot] = Field(default_factory=list)
    transcript: list[dict] = Field(default_factory=list)
    max_repair_attempts: int = 2
    claim_registry: dict[str, str] = Field(default_factory=dict)
    evidence_seen_ids: set[str] = Field(default_factory=set)
    evidence_content_hashes: dict[str, str] = Field(default_factory=dict)
    evidence_counter: int = 0
    evidence_cycle_boundaries: list[int] = Field(default_factory=list)
    objection_ledger: dict[str, str] = Field(default_factory=dict)
    degraded_cycles: list[int] = Field(default_factory=list)
    strategist_cited_evidence: dict[int, list[str]] = Field(default_factory=dict)
    seen_brave_queries: set[str] = Field(default_factory=set)
    strategist_addressed_ids: set[str] = Field(default_factory=set)
    supersession_map: dict[str, str] = Field(default_factory=dict)
    critic_collapse_penalty: float = 0.0
    deferred_objection_store: dict[str, "Objection"] = Field(default_factory=dict)
    search_mode: str = "full"
    topic_class: str = ""
    topic_keywords: set[str] = Field(default_factory=set)
    # Search-gate observability diagnostics (observability only — no behavior)
    search_diag_router_confidence: str = ""          # "CLEAR" | "BORDERLINE" | "AMBIGUOUS"
    search_diag_training_only_skips: int = 0         # retrieval opportunities skipped due to training_only ceiling
    search_diag_live_evidence_candidates: int = 0    # [LIVE-EVIDENCE-CANDIDATE] events fired this run
    search_diag_live_retrieval_attempted: bool = False  # True if live retrieval was ever invoked (not training_only)
    search_mode_escalated: bool = False                  # True if mid-run escalation fired (training_only → minimal)
    search_diag_upfront_mode: str = ""                   # immutable snapshot of search mode as initially resolved (before any escalation)
    # Explicit-option preservation mode
    explicit_option_mode: bool = False                   # True when brief presents a clear finite option set
    brief_option_registry: list[dict] = Field(default_factory=list)  # [{id: "O1", label: "...", text: "..."}, ...]
    choice_mode: str = "portfolio"                       # "portfolio" (approve many) or "exclusive" (select one)
    # V4 (Mission Controller): Brain augmentation data for cascade mode
    brain_augmentation: dict | None = None                   # Structured pre-work from Brain V3

    class Config:
        arbitrary_types_allowed = True


RESEARCHER_SYSTEM = """You are the Researcher in a structured decision workflow. Your ONLY job is to gather factual evidence.

OUTPUT FORMAT: Return ONLY a JSON object matching this schema:
{
  "evidence": [
    {
      "evidence_id": "E001",
      "topic": "adoption rate",
      "source_type": "training_knowledge",
      "fact": "The adoption rate for this category grew 40% year-over-year",
      "value": "40",
      "units": "percent",
      "confidence": "HIGH",
      "supports_claim_ids": []
    }
  ]
}

RULES:
- Every fact must be atomic (one data point per evidence item)
- No recommendations or conclusions
- No duplicate evidence IDs
- Use sequential IDs: E001, E002, E003...
- For Round 2+, only fetch evidence for gaps identified by the Auditor
- source_type is "training_knowledge" for knowledge from training data, or "web_search" for live retrieval results
- confidence: HIGH = well-known public fact, MEDIUM = approximate/dated, LOW = uncertain/estimated
- For Round 2+: research ONLY evidence needed to close specific open objections
- You will receive a list of open objections and their evidence needs
- Do NOT do broad research sweeps in Round 2+ — only targeted gap-filling
- Maximum 10 evidence items per round

EVIDENCE CATEGORIES: Identify 4-7 evidence categories most relevant to this specific task. Categories should cover the key factual dimensions needed for informed decision-making.

ETF_CATEGORIES_PLACEHOLDER

BREVITY: Keep each fact field under 80 words. Keep value and units short. Omit obvious context.
"""

_ETF_CATEGORIES_BLOCK = """REQUIRED CATEGORIES for ETF tasks:
1. Expense ratios and fees
2. AUM and liquidity
3. Top holdings and concentration
4. Historical returns (1yr, 3yr, 5yr, 10yr if available)
5. Sector/theme exposure
6. Overlap between proposed ETFs
7. Key risks per ETF
"""

_ETF_KEYWORDS = frozenset({
    "etf", "fund", "ticker", "portfolio", "holdings", "aum", "expense ratio",
    "equity", "bond", "index", "vanguard", "ishares", "spdr", "nasdaq", "s&p",
    "dividend", "yield", "sector", "allocation", "rebalance",
})


def _build_researcher_system(task: str) -> str:
    """Return RESEARCHER_SYSTEM with ETF categories block only for ETF/finance tasks."""
    task_lower = task.lower()
    is_etf_task = any(kw in task_lower for kw in _ETF_KEYWORDS)
    if is_etf_task:
        return RESEARCHER_SYSTEM.replace("ETF_CATEGORIES_PLACEHOLDER", _ETF_CATEGORIES_BLOCK.strip())
    else:
        return RESEARCHER_SYSTEM.replace(
            "ETF_CATEGORIES_PLACEHOLDER",
            "Identify 4-7 evidence categories most relevant to this specific task. "
            "Categories should cover the key factual dimensions needed for informed decision-making.",
        )

STRATEGIST_SYSTEM = """You are the Strategist in a structured decision workflow.

ROUND 1: You propose a full evidence-linked recommendation set.
ROUND 2+: You submit a PATCH — only changes to address open objections.

ROUND 1 OUTPUT FORMAT: Return ONLY a JSON object:
{
  "proposal_id": "P001",
  "claims": [...],
  "recommendations": [...]
}

ROUND 1 STRICT RULES:
- proposal_id: exactly "P001"
- claims: array of objects, each with claim_id (string "C001", "C002"...), claim_text (string), importance (one of "CORE", "SUPPORTING", "CONTEXTUAL"), evidence_ids (array of strings)
- recommendations: one object per recommendation, each with item_id (string "R001"...), name (string, descriptive label for the recommendation), rank (integer starting at 1), role_in_portfolio (string), thesis (string), claim_ids (array), evidence_ids (array), known_risks (array of strings)
- Do NOT add extra fields not in the schema
- Do NOT use nested objects where strings are expected
- known_risks must be an array of strings, NOT an array of objects

ROUND 2+ OUTPUT FORMAT: Return ONLY a JSON object:
{
  "patch_id": "PATCH001",
  "revised_claims": [...],
  "dropped_claim_ids": ["C003"],
  "revised_recommendations": [...],
  "rank_changes": [{"item_id": "R001", "old_rank": 1, "new_rank": 2}],
  "objection_responses": [
    {
      "objection_id": "OBJ001",
      "response": "objection_id=OBJ001, status_target=resolve|downgrade|cannot_resolve, evidence_ids_used=[E001,E002], claim/recommendation_changed=C001, one_sentence_repair_summary=<one sentence describing the fix>",
      "action": "REVISED_CLAIM"
    }
  ]
}

ROUND 2+ RULES:
- Every CORE claim MUST cite at least one evidence_id
- objection_responses is REQUIRED and MUST be non-empty when open objections exist
- ONE entry per live objection — do not skip any
- Claim/recommendation revisions do NOT replace objection_responses mapping — both are required
- Returning objection_responses=[] when open objections exist will cause your patch to be REJECTED and retried
- action must be one of: REVISED_CLAIM, DROPPED_CLAIM, REVISED_RECOMMENDATION, REBUTTED, ACKNOWLEDGED
- REBUTTED = you disagree with the objection and explain why with evidence
- ACKNOWLEDGED = you accept the risk but keep the recommendation
- Do NOT regenerate unchanged claims or recommendations
- Do NOT add new claims unless directly needed to address an objection

REPAIR TARGETING RULES (MANDATORY):
- DIRECT REPAIR: If your repair directly updates the claim or recommendation named in the objection, set claim/recommendation_changed to that exact ID. This is the preferred path.
- INDIRECT REPAIR: If your repair works through a new or linked claim/recommendation, you MUST:
  a) Set claim/recommendation_changed to the new/linked ID
  b) In your one_sentence_repair_summary, explicitly state: "Indirect repair via [NEW_CLAIM_ID]: [brief explanation of linkage]"
  c) Include evidence IDs that directly relate to the objection topic
- WRONG TARGET: Do NOT set claim/recommendation_changed to a claim unrelated to the objection. If you are repairing OBJ on C003, do not say you changed C001 without explicit linkage.
- ACKNOWLEDGE ≠ REPAIR: Simply acknowledging an objection or citing general evidence without updating a claim or recommendation does NOT count as a repair. Make a concrete change.

QUANTIFICATION RULE (MANDATORY):
- Do NOT introduce specific probabilities, percentages, base rates, or expected-value figures into a claim unless that figure is directly supported by an evidence item in your current evidence list.
- When addressing a logical-gap or probabilistic-comparison objection, prefer a QUALITATIVE DOMINANCE argument: show that the magnitude of one risk clearly outweighs the other using evidence, without inventing a specific number.
- Example of what to AVOID: "The probability of a breach is approximately 5%, making the expected cost..."
- Example of what to DO: "The evidence shows RCE in authentication middleware has catastrophic blast radius (E007, E008), which clearly dominates the bounded regression risk of the patch (E005), even without a precise probability figure."
- If you need a number, USE ONE ALREADY IN THE EVIDENCE (e.g., "$4.45M average breach cost from E006") rather than deriving a new one.

BREVITY: Keep rationale fields under 60 words each. Keep claim_text under 80 words. Omit unchanged recommendations in patches.
"""

CRITIC_SYSTEM = """You are the Critic in a structured decision workflow. Your ONLY job is adversarial stress-testing.

OUTPUT FORMAT: Return ONLY a JSON object matching this schema:
{
  "objections": [
    {
      "objection_id": "OBJ001",
      "claim_id": "C001",
      "severity": "HIGH",
      "scope": "ITEM",
      "type": "concentration",
      "objection_text": "Option A depends on a single vendor for a critical component, creating supply chain concentration risk",
      "requested_evidence": ["vendor market share data", "alternative supplier availability"],
      "status": "OPEN"
    }
  ]
}

RULES:
- Every objection MUST reference a claim_id from the proposal
- severity: HIGH = threatens the recommendation, MEDIUM = weakens it, LOW = minor concern
- type must be one of: factual_contradiction, evidence_gap, logical_gap, concentration, overlap, valuation, regime_risk, timing, benchmark_issue, other
- BLOCKING vs NON-BLOCKING objections:
- BLOCKING types (factual contradiction, evidence_gap, logical_gap, benchmark_issue): these can FAIL an item
- NON-BLOCKING types (concentration, overlap, valuation, regime_risk, timing): these should map to PASS_WITH_RISK, rank downgrade, or thesis narrowing — NOT automatic failure
- A serious concentration risk is a valid concern but should not kill a recommendation by itself
- Classify each objection as scope "ITEM" (targets one specific recommendation) or "PORTFOLIO" (affects the entire proposal thesis)
- PORTFOLIO objections should NOT automatically FAIL every item - they affect confidence and rationale instead
- Example ITEM: "Recommendation R004 lacks supporting evidence for feasibility claim" -> scope: "ITEM", target: R004
- Example PORTFOLIO: "Core growth thesis relies on unverified market assumptions" -> scope: "PORTFOLIO", target: overall thesis
- For Round 2+: only challenge revised claims or unresolved objections
- Do NOT propose alternative recommendations
- Do NOT issue verdicts
- Do NOT demand evidence that requires live tools, real-time data, or computation
- Evidence may be training_knowledge or web_search (controller-managed retrieval)
- Feasible demands: historical facts, known ratios, public data, qualitative analysis
- Infeasible demands: live correlation calculations, real-time prices, Monte Carlo simulations
- Do NOT demand evidence that presupposes a specific real-world entity (CVE ID, company name, product name, ticker symbol) unless that entity is explicitly named in the task. If the task describes a hypothetical scenario, demand evidence in general/categorical terms only.
- If you reference a prior objection ID that is still unresolved, keep the SAME objection_id
- Only assign a NEW objection_id to genuinely new issues not raised before
- YOUR JOB after Round 1 is NARROW:
- Confirm an existing objection remains valid (restate with same ID)
- Withdraw an objection if the revision addressed it (do not include it)
- Restate an objection more precisely (same ID, refined text)
- In Round 2 ONLY: flag at most ONE new issue if directly caused by a Strategist revision
- Do NOT broaden the portfolio thesis, create fresh macro angles, or change the battlefield late
- OBJECTION FREEZE RULES:
- Round 1: full objection discovery - raise all concerns
- Round 2: only unresolved objections, plus at most ONE genuinely new objection IF caused directly by a revision
- Round 3: NO new objections. Only confirm existing objections still valid, or withdraw them.
- Reuse the SAME objection_id for the SAME issue. Do NOT recycle an objection_id for a different concern.
"""

AUDITOR_SYSTEM = """You are the Auditor in a structured decision workflow. You are a GATEKEEPER with explicit adjudication power.

OUTPUT FORMAT: Return ONLY a JSON object:
{
  "overall_evidence_quality": "MEDIUM",
  "claim_scores": [
    {"claim_id": "C001", "support_level": "ADEQUATE", "support_reason": "...", "missing_evidence": []}
  ],
  "recommendation_decisions": [
    {
      "item_id": "R001",
      "decision": "PASS_WITH_RISK",
      "reason": "..."
    }
  ],
  "objection_findings": [
    {
      "objection_id": "OBJ001",
      "disposition": "DOWNGRADED_TO_RISK",
      "rationale": "Concentration risk is real but does not invalidate the thesis. PASS_WITH_RISK.",
      "upgrade_to_blocking": false
    }
  ],
  "residual_risks": ["Recommendations R002 and R003 share a common dependency that amplifies execution risk"],
  "portfolio_assessment": {
    "concentration_risk": "MEDIUM",
    "overlap_risk": "LOW",
    "thematic_overexposure": "MEDIUM",
    "valuation_regime_risk": "LOW",
    "confidence_penalty": 0.05,
    "summary": "Portfolio has moderate concentration in semiconductors..."
  },
  "unresolved_objections": ["OBJ003"],
  "missing_evidence": [],
  "progress_assessment": "2 objections resolved, 1 downgraded, 1 remains",
  "eligible_for_judgment": true
}

Your total JSON output should be under 4000 tokens. Be concise.

DISPOSITION VALUES for objection_findings (use exactly these):
- RESOLVED: evidence + strategist revision fully addresses the concern
- UPHELD: objection remains valid and unaddressed
- DOWNGRADED_TO_RISK: concern is real but not thesis-breaking - maps to PASS_WITH_RISK
- WITHDRAWN: no longer applicable (e.g., claim dropped or revised to eliminate the issue)

upgrade_to_blocking: set to true ONLY if a normally non-blocking type (concentration, overlap, etc.) is SO extreme that it makes the proposal thesis internally inconsistent. This is rare - most concentration/valuation risks are DOWNGRADED_TO_RISK.

SUPPORT LEVELS (use exactly these):
- UNSUPPORTED, WEAK, ADEQUATE, STRONG

DECISION VALUES per recommendation:
- PASS: fully supported, all objections resolved
- PASS_WITH_RISK: supported but material risks remain (non-blocking objections)
- FAIL: insufficient evidence or unresolved BLOCKING objection
- NEEDS_EVIDENCE: specific evidence gaps remain

eligible_for_judgment = true ONLY when:
- Every recommendation has a decision (not NEEDS_EVIDENCE)
- No BLOCKING-class objection has disposition UPHELD
- overall_evidence_quality is at least MEDIUM

IMPORTANT: You MUST provide an objection_finding for EVERY open objection. Do not omit any.

BREVITY: Keep reason/rationale fields under 60 words each. Keep risk_summary under 40 words. Only include fields shown in the example above.

Evidence sources may include training_knowledge and web_search. Treat web_search as valid controller-managed evidence already normalized into the ledger.
"""

JUDGE_SYSTEM = """You are the Judge in a structured decision workflow. You receive the full run state and emit a final verdict.

OUTPUT FORMAT: Return ONLY a JSON object matching this schema:
{
  "status": "CONSENSUS",
  "confidence": 0.72,
  "approved_items": ["R001", "R002", "R003", "R004", "R005", "R006"],
  "rejected_items": [],
  "unresolved_points": ["long-term vendor concentration risk"],
  "rationale": "...",
  "next_action": "Monitor key risk indicators at the next review checkpoint"
}

STATUS RULES:
- CONSENSUS: all recommendations pass, no blocking objections remain, no deferred objections, residual risks are minor
- CLOSED_WITH_ACCEPTED_RISKS: all recommendations pass or pass_with_risk, but material non-blocking risks remain acknowledged
- PARTIAL_CONSENSUS: subset passes, but some items failed or material blocking disputes remain
- INSUFFICIENT_EVIDENCE: research couldn't fill gaps, evidence still LOW
- NO_CONSENSUS: evidence exists but fundamental disagreements remain unresolved
- SYSTEM_FAILURE: pipeline error prevented adjudication

Use CLOSED_WITH_ACCEPTED_RISKS (not CONSENSUS) when:
- Items passed but with PASS_WITH_RISK decisions
- Non-blocking risks were downgraded but not eliminated
- Portfolio-level concerns remain as accepted caveats

DEFERRED objections: list them in unresolved_points using this exact format: "OBJ{id} (deferred — {severity} {type} on {claim_id}: {text[:150]})" — use the text provided in the deferred_objs section. Do NOT write "content unknown".

AGGREGATION RULES:
- You are an AGGREGATOR. Do NOT invent new portfolio logic or analysis.
- If the Auditor marked a recommendation FAIL, you MUST reject it.
- If the Auditor marked PASS_WITH_RISK, you MAY approve it but MUST note the risk.
- BLOCKING RULES (STRICT):
- Only ITEM-scope, BLOCKING-type objections can cause an item to be rejected
- NON-BLOCKING objections (concentration, overlap, valuation, regime_risk, timing) -> PASS_WITH_RISK, never FAIL
- PORTFOLIO-scope objections -> reduce confidence, add to unresolved_points, but do NOT reject items
- A HIGH concentration risk on a recommendation means PASS_WITH_RISK with the risk noted, NOT automatic rejection
- If the Auditor marked FAIL due to a non-blocking type, override to PASS_WITH_RISK
- Keep rationale under 500 words — summarize, do not re-argue.
- next_action should be concrete and brief (one sentence).

OUTPUT raw confidence based on your assessment. Do not apply caps — the controller handles all confidence adjustments.

BREVITY: Keep rationale under 300 words total. Keep next_action to one sentence.

You are a terminal extractor. Never ask for more rounds. Issue the verdict.
"""


def _build_clients() -> dict[str, ChatCompletionClient]:
    return {
        "researcher": AnthropicChatCompletionClient(model="claude-sonnet-4-6", temperature=0.1, max_tokens=60000),
        "strategist_r1": AnthropicChatCompletionClient(model="claude-opus-4-6", temperature=0.3, max_tokens=60000),
        "strategist_r2": KimiK2ChatCompletionClient(temperature=0.3, max_tokens=30000),
        "critic": DeepSeekReasonerChatCompletionClient(temperature=0.2, max_tokens=30000),
        "auditor": DeepSeekChatCompletionClient(temperature=0.1, max_tokens=8000),
        "judge": AnthropicChatCompletionClient(model="claude-sonnet-4-6", temperature=0.0, max_tokens=60000),
    }


def _strip_think_tags(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<reasoning>.*?</reasoning>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(
        r"</?(?:analysis|chain_of_thought|cot|internal_reasoning|scratchpad)[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def _log_turn(log_path: Path, node_name: str, text: str) -> None:
    block = f"\n{'=' * 60}\n[{node_name}]\n{text}\n"
    print(block, flush=True)
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(block)
            fh.flush()
    except OSError as exc:
        print(f"[Chamber] Failed to write live log {log_path}: {exc}", file=sys.stderr, flush=True)


def _log_text(log_path: Path, text: str) -> None:
    print(text, flush=True)
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(text + "\n")
            fh.flush()
    except OSError as exc:
        print(f"[Chamber] Failed to write live log {log_path}: {exc}", file=sys.stderr, flush=True)


def _log_event(log_path: Path, event_type: str, data: dict) -> None:
    event = {"ts": _dt.now().isoformat(), "event": event_type, **data}
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
            fh.flush()
    except OSError:
        pass


def _extract_json(text: str) -> dict | list | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            obj, end = decoder.raw_decode(text[idx:])
        except ValueError:
            continue
        trailing = text[idx + end :].strip()
        if trailing and not trailing.startswith("```"):
            return obj
        return obj
    return None


def _check_semantic_progress(
    ledger: RunLedger,
    current_audit: AuditSnapshot,
    log_path: Path,
) -> dict:
    """Measure adjudicative progress: explicit disposition changes, not just movement."""
    if len(ledger.audit_history) < 1:
        return {"progress": True, "details": "first audit", "semantic_changes": 0}

    changes = []

    previous = ledger.audit_history[-1]
    # Compare objection dispositions against previous audit to find NEW transitions
    prev_dispositions = {}
    if previous.objection_findings:
        prev_dispositions = {f.objection_id: f.disposition for f in previous.objection_findings}

    new_resolved = 0
    new_downgraded = 0
    new_withdrawn = 0
    for f in current_audit.objection_findings:
        prev_disp = prev_dispositions.get(f.objection_id)
        if f.disposition == "RESOLVED" and prev_disp != "RESOLVED":
            new_resolved += 1
        elif f.disposition == "DOWNGRADED_TO_RISK" and prev_disp != "DOWNGRADED_TO_RISK":
            new_downgraded += 1
        elif f.disposition == "WITHDRAWN" and prev_disp != "WITHDRAWN":
            new_withdrawn += 1
    if new_resolved > 0:
        changes.append(f"objections newly resolved: {new_resolved}")
    if new_downgraded > 0:
        changes.append(f"objections newly downgraded: {new_downgraded}")
    if new_withdrawn > 0:
        changes.append(f"objections newly withdrawn: {new_withdrawn}")

    if current_audit.recommendation_decisions and previous.recommendation_decisions:
        prev_decisions = {rd.item_id: rd.decision for rd in previous.recommendation_decisions}
        improvement_order = {"NEEDS_EVIDENCE": 0, "FAIL": 1, "PASS_WITH_RISK": 2, "PASS": 3}
        for rd in current_audit.recommendation_decisions:
            old = prev_decisions.get(rd.item_id)
            if old and improvement_order.get(rd.decision, 0) > improvement_order.get(old, 0):
                changes.append(f"{rd.item_id}: {old} -> {rd.decision}")

    quality_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    if quality_order.get(current_audit.overall_evidence_quality, 0) > quality_order.get(
        previous.overall_evidence_quality, 0
    ):
        changes.append(f"evidence: {previous.overall_evidence_quality} -> {current_audit.overall_evidence_quality}")

    prev_weak = sum(1 for c in previous.claim_scores if c.support_level in ("UNSUPPORTED", "WEAK"))
    curr_weak = sum(1 for c in current_audit.claim_scores if c.support_level in ("UNSUPPORTED", "WEAK"))
    if curr_weak < prev_weak:
        changes.append(f"claims strengthened: {prev_weak - curr_weak}")

    has_progress = len(changes) > 0
    _log_text(log_path, f"[PROGRESS] Adjudicative: {len(changes)} changes - {'; '.join(changes) if changes else 'none'}")
    return {"progress": has_progress, "details": "; ".join(changes) if changes else "no adjudicative change", "semantic_changes": len(changes)}


# --- Round-5: Patch outcome taxonomy ---
PATCH_VALIDATED_DIRECT = "VALIDATED_DIRECT"
PATCH_VALIDATED_INDIRECT = "VALIDATED_INDIRECT"
PATCH_MISMATCH = "MISMATCH"
PATCH_UNREPAIRED = "UNREPAIRED"

_PATCH_MATCH_STOPWORDS = frozenset({
    "the", "and", "for", "not", "with", "this", "that", "from", "are",
    "was", "were", "have", "has", "been", "will", "would", "could", "should",
    "may", "might", "can", "also", "more", "some", "about", "such", "only",
    "each", "both", "when", "what", "does", "into", "over", "then", "than",
    "their", "there", "they", "them", "very", "just", "even", "all", "any",
    "its", "our", "your", "these", "those", "but", "which", "how", "why",
    "claim", "objection", "response", "issue", "risk", "item", "point",
    "review", "change", "address", "update", "revised", "revise", "modify",
    "modified", "reason", "because", "however", "therefore", "thus", "hence",
})


def _extract_patch_kw(text: str) -> set[str]:
    words = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {w for w in words if len(w) >= 4 and w not in _PATCH_MATCH_STOPWORDS}


def _classify_patch_outcome(
    response: ObjectionResponse,
    objection: Objection,
    log_path: "Path | None" = None,
) -> str:
    """Classify an objection response into one of four patch outcome constants.

    Order of checks:
      1. UNREPAIRED — no evidence_ids_used or empty repair summary
      2. MISMATCH — claim differs AND keyword overlap < 2
      3. VALIDATED_INDIRECT — claim differs BUT overlap >= 2 (explicit indirect repair)
      4. VALIDATED_DIRECT — claim matches AND overlap >= 2
      5. Fallback — claim matches, overlap < 2 → VALIDATED_DIRECT with [PATCH-WEAK] warning
    """
    oid = objection.objection_id
    obj_claim = (objection.claim_id or "").strip()
    obj_text = (objection.objection_text or "")[:200]
    resp_text = response.response or ""
    resp_action = response.action or ""
    combined_resp = resp_text + " " + resp_action

    # 1) UNREPAIRED: no evidence_ids_used or empty/template repair summary
    evidence_match = re.search(r'evidence_ids_used=\[([^\]]*)\]', resp_text)
    has_evidence = bool(evidence_match and evidence_match.group(1).strip())
    summary_match = re.search(r'one_sentence_repair_summary=(.+)', resp_text, re.IGNORECASE)
    summary_val = summary_match.group(1).strip() if summary_match else ""
    is_template_summary = not summary_val or summary_val.startswith("<one sentence") or summary_val.lower() in ("none", "n/a", "")
    if not has_evidence or is_template_summary:
        _log_text(log_path, f"[PATCH-UNREPAIRED] {oid} → UNREPAIRED (no evidence or repair summary)")
        return PATCH_UNREPAIRED

    # Compute keyword overlap
    obj_kw = _extract_patch_kw(obj_text)
    resp_kw = _extract_patch_kw(combined_resp)
    overlap = obj_kw & resp_kw
    overlap_count = len(overlap)
    evidence_topics = sorted(overlap)[:3]

    # Extract declared repair-target from claim/recommendation_changed field (authoritative).
    # Do NOT scan all IDs from the full response — that mixes evidence IDs (E-prefix) with
    # claim/rec IDs and produces false mismatches.
    _target_match = re.search(r'claim/recommendation_changed\s*=\s*([A-Z]\d{3})', resp_text, re.IGNORECASE)
    if _target_match:
        resp_claim_ids: set[str] = {_target_match.group(1).upper()}
    else:
        # No declared target field: fall back to C/R-prefix IDs only, excluding evidence IDs (E-prefix)
        resp_claim_ids = set(re.findall(r'\b[CR]\d{3}\b', combined_resp))
    claim_matches_obj = (not obj_claim) or (obj_claim.upper() in {c.upper() for c in resp_claim_ids})
    claim_changed_str = ", ".join(sorted(resp_claim_ids)) if resp_claim_ids else "n/a"

    # 2) MISMATCH: claim differs AND overlap < 2
    if obj_claim and not claim_matches_obj and overlap_count < 2:
        _log_text(
            log_path,
            f"[PATCH-MISMATCH] {oid} → MISMATCH (claim: {claim_changed_str} vs {obj_claim}, overlap: {overlap_count})",
        )
        return PATCH_MISMATCH

    # 3) VALIDATED_INDIRECT: claim differs BUT overlap >= 2
    if obj_claim and not claim_matches_obj:
        _log_text(
            log_path,
            f"[PATCH-INDIRECT] {oid} → VALIDATED_INDIRECT (claim: {obj_claim} → {claim_changed_str}, evidence link: {evidence_topics})",
        )
        return PATCH_VALIDATED_INDIRECT

    # 4) VALIDATED_DIRECT: claim matches AND overlap >= 2
    if overlap_count >= 2:
        _log_text(
            log_path,
            f"[PATCH-DIRECT] {oid} → VALIDATED_DIRECT (claim: {obj_claim or 'n/a'}, overlap: {overlap_count})",
        )
        return PATCH_VALIDATED_DIRECT

    # 5) Fallback: claim matches but overlap < 2 — admit with warning
    _log_text(log_path, f"[PATCH-WEAK] {oid} → VALIDATED_DIRECT with low overlap ({overlap_count}) — admitted")
    return PATCH_VALIDATED_DIRECT


def _validate_response_semantic_match(
    response: ObjectionResponse,
    objection: Objection,
    log_path: "Path | None" = None,
) -> bool:
    """Legacy wrapper — delegates to _classify_patch_outcome. Returns True for VALIDATED_* outcomes."""
    outcome = _classify_patch_outcome(response, objection, log_path)
    return outcome in (PATCH_VALIDATED_DIRECT, PATCH_VALIDATED_INDIRECT)


def _check_unsupported_quantification(
    patch: "StrategistPatch",
    ledger: "RunLedger",
    log_path: "Path | None" = None,
) -> list[str]:
    """Check revised_claims for new quantitative figures not grounded in the evidence ledger.

    Returns a list of claim_ids where the patch introduced an unsupported specific number.
    Only checks claims listed in patch.revised_claims (not original proposal claims).
    """
    invalid_claim_ids: list[str] = []
    if not patch.revised_claims:
        return invalid_claim_ids

    # Build a combined string of all evidence facts for substring search
    all_facts = [e.fact.lower() for e in ledger.evidence_ledger]

    for claim in patch.revised_claims:
        claim_text = claim.claim_text or ""
        # Extract percentages: "5%", "10.5%", etc.
        pct_matches = re.findall(r"\b(\d+(?:\.\d+)?)\s*%", claim_text)
        # Extract bare numbers preceding probability/chance/rate keywords
        prob_matches = re.findall(
            r"\b(\d+(?:\.\d+)?)\s*(?:probability|chance|likelihood|rate)\b",
            claim_text,
            re.IGNORECASE,
        )
        # Extract "1 in N" ratio patterns
        ratio_matches = re.findall(r"\b1\s+in\s+(\d+)\b", claim_text, re.IGNORECASE)

        all_figures = set(pct_matches + prob_matches + ratio_matches)

        for figure in all_figures:
            found_in_evidence = any(figure in fact for fact in all_facts)
            if not found_in_evidence:
                _log_text(
                    log_path,
                    f"[PATCH-UNSUPPORTED-QUANT] claim={claim.claim_id}: new figure \"{figure}\" not grounded in evidence ledger",
                )
                if claim.claim_id not in invalid_claim_ids:
                    invalid_claim_ids.append(claim.claim_id)

    return invalid_claim_ids


# ---------------------------------------------------------------------------
# SLP — Controller-synthesized Standalone Leverage Profile
# Derived entirely from final adjudicated state.  No LLM call.
# ---------------------------------------------------------------------------

# Dominance comparison definitions (per design doc §8.1)
#   not_worse:       same band or better (lower index in the band tuple)
#   materially_worse: one+ full adverse band on a critical viability dimension

def _slp_band_index(value: str, bands: tuple[str, ...]) -> int:
    """Return the index of *value* in *bands* (0 = best). Returns len(bands) if unknown."""
    try:
        return bands.index(value)
    except ValueError:
        return len(bands)


def _slp_not_worse(a: str, b: str, bands: tuple[str, ...]) -> bool:
    """True if *a* is same band or better than *b*."""
    return _slp_band_index(a, bands) <= _slp_band_index(b, bands)


def _slp_materially_worse(a: str, b: str, bands: tuple[str, ...]) -> bool:
    """True if *a* is one+ full adverse band worse than *b* on a critical dimension."""
    return _slp_band_index(a, bands) > _slp_band_index(b, bands)


def _slp_map_evidence_confidence(support_level: str) -> str:
    """Map Auditor claim support_level to SLP evidence_confidence band."""
    mapping = {"STRONG": "STRONG", "ADEQUATE": "ADEQUATE", "WEAK": "LIMITED", "UNSUPPORTED": "WEAK"}
    return mapping.get(support_level, "LIMITED")


def _slp_derive_eligibility(
    rec: Recommendation,
    decision: str,
    ledger: RunLedger,
    log_path: Path,
) -> SLPEligibility:
    """Derive standalone eligibility from structured final state.

    Rules (structured state first, text heuristic as logged fallback):
    - FAIL / NEEDS_EVIDENCE → INELIGIBLE
    - role_in_portfolio containing 'escalation' / 'fallback' / 'contingency' → CONDITIONALLY_ELIGIBLE
    - role_in_portfolio containing 'component' / 'rejected' → INELIGIBLE
    - Otherwise → ELIGIBLE
    """
    # Rule 1: decision-based (structured state)
    if decision in ("FAIL", "NEEDS_EVIDENCE"):
        return SLPEligibility(
            status="INELIGIBLE_FOR_HIGHLIGHT",
            reason=f"Recommendation {rec.item_id} has decision {decision}",
        )

    role_lower = (rec.role_in_portfolio or "").lower()

    # Rule 2: explicit rejection language (structured — role field)
    if "rejected" in role_lower:
        return SLPEligibility(
            status="INELIGIBLE_FOR_HIGHLIGHT",
            reason=f"{rec.item_id} role indicates rejected standalone option",
        )

    # Rule 3: component-only (structured — role field)
    if "component" in role_lower and "standalone" not in role_lower:
        _log_text(log_path, f"[SLP-ELIGIBILITY] {rec.item_id} INELIGIBLE — role_in_portfolio contains 'component' (heuristic fallback)")
        return SLPEligibility(
            status="INELIGIBLE_FOR_HIGHLIGHT",
            reason=f"{rec.item_id} is a component-only action per role_in_portfolio",
        )

    # Rule 4: conditional / escalation (structured — role field)
    # EXCEPTION: brief-native explicit options are protected from false CONDITIONALLY_ELIGIBLE.
    # Soft editorial language like "appropriate only if" in the Strategist's role text should
    # not downgrade a brief-stated option. Only real trigger-dependent structure counts.
    conditional_keywords = ("escalation", "fallback", "contingency", "if ", "only when", "only if")
    has_conditional_language = any(kw in role_lower for kw in conditional_keywords)

    if has_conditional_language:
        # Check if this is a brief-native option (protected from false conditionality)
        is_brief_native = False
        if ledger.explicit_option_mode and ledger.brief_option_registry:
            name_lower = (rec.name or "").lower()
            for opt in ledger.brief_option_registry:
                opt_id_lower = opt["id"].lower()
                # Match by option ID in name (e.g., "Option O1: ...") or by text overlap
                if opt_id_lower in name_lower or "brief-native" in role_lower:
                    is_brief_native = True
                    break
                # Also match by keyword overlap with option text
                opt_keywords = set(re.findall(r'[a-z]{4,}', opt["text"].lower()))
                rec_text = f"{name_lower} {role_lower}".lower()
                if opt_keywords and sum(1 for kw in opt_keywords if kw in rec_text) >= max(3, len(opt_keywords) * 0.3):
                    is_brief_native = True
                    break

        if is_brief_native:
            _log_text(log_path, f"[SLP-ELIGIBILITY] {rec.item_id} ELIGIBLE — brief-native option protected from conditional downgrade")
            return SLPEligibility(status="ELIGIBLE", reason=f"{rec.item_id} is a brief-native explicit option (protected)")

        # Not brief-native — apply normal conditional logic
        condition = ""
        for risk in rec.known_risks:
            risk_lower = risk.lower()
            if any(kw in risk_lower for kw in ("trigger", "escalat", "if ", "only when")):
                condition = risk[:200]
                break
        if not condition:
            condition = rec.role_in_portfolio[:200]
        _log_text(log_path, f"[SLP-ELIGIBILITY] {rec.item_id} CONDITIONALLY_ELIGIBLE — role contains conditional language (heuristic fallback)")
        return SLPEligibility(
            status="CONDITIONALLY_ELIGIBLE",
            reason=f"{rec.item_id} is a conditional/escalation action",
            applicability_condition=condition,
        )

    # Default: eligible
    return SLPEligibility(status="ELIGIBLE", reason=f"{rec.item_id} is an approved standalone action")


def _slp_derive_dimensions(
    rec: Recommendation,
    decision: str,
    claim_scores: dict[str, str],
    deferred_obj_ids: list[str],
    all_objections: dict[str, "Objection"],
    ledger: RunLedger,
    log_path: Path,
) -> dict[str, SLPDimension]:
    """Derive the five SLP dimensions from final adjudicated state.

    Uses action archetype mapping + decision-class calibration profiles.
    Each dimension is derived from structured state first, with text heuristics
    as fallback.  Objection types drive caps on relevant dimensions.
    """
    # Gather evidence IDs cited by this recommendation
    rec_evidence = list(rec.evidence_ids) if rec.evidence_ids else []

    # Gather constraining objections (deferred or unresolved targeting this rec's claims)
    constraining = [oid for oid in deferred_obj_ids
                    if oid in all_objections and all_objections[oid].claim_id in (rec.claim_ids or [])]

    # Combined text for signal detection
    role_lower = (rec.role_in_portfolio or "").lower()
    thesis_lower = (rec.thesis or "").lower()
    name_lower = (rec.name or "").lower()
    risks_text = " ".join(r.lower() for r in (rec.known_risks or []))
    combined_text = f"{name_lower} {role_lower} {thesis_lower}"

    # --- Detect task domain ---
    if not ledger.topic_class:
        ledger.topic_class = _extract_topic_class(ledger.task)
    task_domain = _detect_task_domain(ledger.topic_class, ledger.task)

    # --- Classify action archetype ---
    archetype = _classify_action_archetype(combined_text, risks_text, role_lower)

    # --- standalone_impact (primary axis) ---
    impact = _calibrate_impact(archetype, task_domain, decision, role_lower, combined_text, log_path, rec.item_id)

    # --- execution_feasibility ---
    feasibility = _calibrate_feasibility(rec, constraining, all_objections, risks_text, combined_text, log_path)

    # --- time_to_protective_effect ---
    time_rating = _calibrate_time(rec, constraining, all_objections, thesis_lower, combined_text, task_domain, log_path)

    # --- reversibility_downside ---
    reversibility = _calibrate_reversibility(rec, risks_text, thesis_lower, combined_text, log_path)

    # --- evidence_confidence ---
    ev_conf = _calibrate_evidence_confidence(rec, claim_scores, constraining, all_objections, log_path)

    # --- Calibration trace ---
    _log_text(
        log_path,
        f"[SLP-CALIBRATION] {rec.item_id}: domain={task_domain}, archetype={archetype}, "
        f"impact={impact}, feasibility={feasibility}, time={time_rating}, "
        f"reversibility={reversibility}, evidence={ev_conf}",
    )

    return {
        "standalone_impact": SLPDimension(
            rating=impact,
            rationale=f"Archetype: {archetype}; domain: {task_domain}; decision: {decision}",
            evidence_ids=rec_evidence[:5], constraining_objections=constraining,
        ),
        "execution_feasibility": SLPDimension(
            rating=feasibility,
            rationale=f"{len([r for r in (rec.known_risks or []) if any(kw in r.lower() for kw in ('fail', 'risk', 'complex', 'untested'))])} risk concern(s), "
                      f"{len([o for o in constraining if o in all_objections and all_objections[o].type in ('timing', 'evidence_gap')])} feasibility objection(s)",
            evidence_ids=rec_evidence[:5],
            constraining_objections=[o for o in constraining if o in all_objections
                                     and any(kw in all_objections[o].objection_text.lower()
                                             for kw in ("feasib", "deploy", "rollback", "implement", "capacity", "complex"))],
        ),
        "time_to_protective_effect": SLPDimension(
            rating=time_rating,
            rationale=f"Domain: {task_domain}; timing signals from thesis",
            evidence_ids=rec_evidence[:3],
            constraining_objections=[o for o in constraining if o in all_objections
                                     and all_objections[o].type == "timing"],
        ),
        "reversibility_downside": SLPDimension(
            rating=reversibility,
            rationale=f"Action-downside from known_risks; domain: {task_domain}",
            evidence_ids=rec_evidence[:3], constraining_objections=[],
        ),
        "evidence_confidence": SLPDimension(
            rating=ev_conf,
            rationale=f"Claim support levels; {len(constraining)} constraining deferred objection(s)",
            evidence_ids=rec_evidence[:5], constraining_objections=constraining,
        ),
    }


# ---------------------------------------------------------------------------
# Action archetype classification
# ---------------------------------------------------------------------------

_ARCHETYPE_SIGNALS: dict[str, tuple[str, ...]] = {
    "definitive_remediation": (
        "eliminat", "definitive", "root cause", "remediat", "permanent fix",
        "complete fix", "full remediation", "removes the vulnerability",
        "fixes the vulnerability", "patches the", "upgrade to",
        "restore gating", "rebuild the test", "reintroduce trustworthy",
        "stops the active", "contain data exposure",
        "removes bottleneck", "restores service stability",
        "fixes root cause", "addresses root cause",
        # Engineering hybrid signals — targeted rebuild / fix-first patterns
        "critical-path", "highest-risk code path", "targeted fix",
        "test rebuild", "rebuild test", "fix the schema",
        "tdd mandate", "tdd", "test-driven",
    ),
    "containment_mitigation": (
        "partial", "compensat", "temporary", "bridge", "buys time",
        "reduces probability", "reduces risk", "not a fix",
        "insufficient alone", "limited coverage", "bypass rate",
        "waf rule", "rate limit", "throttl", "acl",
        "compensating control", "interim", "stop-gap",
        "reduce active exploit", "narrow attack surface",
    ),
    "containment_elimination": (
        "shutdown", "kill", "take offline", "eliminates all attack surface",
        "full containment", "zero attack surface", "full lockdown",
        "suspend", "disable globally",
    ),
    "freeze_halt": (
        "feature freeze", "freeze all", "halt", "moratorium",
        "stop all deployment", "code freeze",
        # Engineering hybrid signals — targeted/partial freeze patterns
        "critical-path freeze", "targeted freeze", "2-week freeze",
        "short freeze", "focused freeze", "sprint freeze",
    ),
    "monitoring_observability": (
        "monitor", "observability", "alert", "canary", "detect",
        "attribution", "collect data", "investigate", "triage",
        "log analysis", "forensic",
    ),
    "staffing_process": (
        "hire", "recruit", "team of", "dedicated team", "add headcount",
        "training program", "process reinforcement", "review board",
        "governance", "policy review", "documentation",
        "sunset governance", "formal", "compliance program",
    ),
    "capacity_scaling": (
        "auto-scal", "scale up", "scale out", "add capacity",
        "increase resources", "provision", "horizontal scal",
    ),
    "rollback_revert": (
        "rollback", "revert", "undo", "disable the feature",
        "disable jit", "turn off", "roll back",
    ),
}


def _classify_action_archetype(combined_text: str, risks_text: str, role_lower: str) -> str:
    """Classify a recommendation into an action archetype based on its text signals.

    Returns the best-matching archetype name, or 'unclassified' if no strong signal.

    Priority rule for hybrids: when multiple archetype signals are present,
    remediation and containment archetypes win over monitoring/observability.
    A hybrid plan that includes monitoring as one component is a remediation,
    not monitoring.
    """
    scores: dict[str, int] = {}
    search_text = f"{combined_text} {risks_text}"
    for archetype, signals in _ARCHETYPE_SIGNALS.items():
        scores[archetype] = sum(1 for sig in signals if sig in search_text)

    # Explicit rejection should always override
    if "rejected" in role_lower or "not recommended" in role_lower:
        return "rejected_alternative"

    # Priority resolution for multi-signal cases:
    # If both remediation/containment AND monitoring signals are present,
    # the remediation/containment archetype wins.
    _REMEDIATION_ARCHETYPES = ("definitive_remediation", "containment_mitigation",
                                "containment_elimination", "freeze_halt", "rollback_revert")
    has_remediation = any(scores.get(a, 0) >= 1 for a in _REMEDIATION_ARCHETYPES)
    has_monitoring = scores.get("monitoring_observability", 0) >= 1

    if has_remediation and has_monitoring:
        # Pick the best remediation archetype, not monitoring
        best_remediation = max(_REMEDIATION_ARCHETYPES, key=lambda a: scores.get(a, 0))
        if scores.get(best_remediation, 0) >= 1:
            return best_remediation

    best = max(scores, key=scores.get)
    if scores[best] >= 1:
        return best
    return "unclassified"


# ---------------------------------------------------------------------------
# Domain-calibrated dimension derivation
# ---------------------------------------------------------------------------

# Impact calibration: maps (archetype, domain) → impact rating.
# The archetype determines the base rating; the domain can adjust.
_IMPACT_BY_ARCHETYPE: dict[str, str] = {
    "definitive_remediation": "CRITICAL",
    "containment_elimination": "HIGH",
    "containment_mitigation": "MODERATE",
    "freeze_halt": "MODERATE",
    "capacity_scaling": "MODERATE",
    "rollback_revert": "HIGH",
    "monitoring_observability": "LOW",
    "staffing_process": "LOW",
    "rejected_alternative": "LOW",
    "unclassified": "MODERATE",
}

# Domain-specific overrides: some archetypes have higher impact in certain domains
_IMPACT_DOMAIN_OVERRIDES: dict[tuple[str, str], str] = {
    # Compliance: lockdown/forensic audit is definitive remediation, not just containment
    ("monitoring_observability", "compliance"): "MODERATE",  # forensic audit is more than monitoring
    ("staffing_process", "compliance"): "MODERATE",  # governance matters more in compliance
    ("staffing_process", "ai_policy"): "HIGH",  # governance/sunset is crucial for AI policy
    # Infrastructure: rollback/revert is often the strongest immediate action
    ("rollback_revert", "infrastructure"): "HIGH",
    # Operations: capacity scaling directly resolves the immediate problem
    ("capacity_scaling", "operations"): "HIGH",
    # Engineering: freeze can be high-impact if the core problem is uncontrolled deploys
    ("freeze_halt", "engineering"): "HIGH",
}


def _calibrate_impact(
    archetype: str, domain: str, decision: str,
    role_lower: str, combined_text: str,
    log_path: Path, item_id: str,
) -> str:
    """Calibrate standalone_impact from archetype + domain."""
    # Check domain-specific override first
    override = _IMPACT_DOMAIN_OVERRIDES.get((archetype, domain))
    if override:
        impact = override
    else:
        impact = _IMPACT_BY_ARCHETYPE.get(archetype, "MODERATE")

    # Cap if PASS_WITH_RISK
    if decision == "PASS_WITH_RISK" and impact == "CRITICAL":
        impact = "HIGH"

    # Cap if FAIL (should already be INELIGIBLE, but defensive)
    if decision in ("FAIL", "NEEDS_EVIDENCE") and impact in ("CRITICAL", "HIGH"):
        impact = "MODERATE"

    # Log archetype derivation
    if archetype == "unclassified":
        _log_text(log_path, f"[SLP-IMPACT] {item_id} defaulted to MODERATE — no archetype signal detected (heuristic fallback)")

    return impact


def _calibrate_feasibility(
    rec: Recommendation,
    constraining: list[str],
    all_objections: dict[str, "Objection"],
    risks_text: str,
    combined_text: str,
    log_path: Path,
) -> str:
    """Calibrate execution_feasibility from known_risks + objection types."""
    feasibility_risk_keywords = ("fail", "rollback", "risk", "untested", "complex",
                                 "uncertain outcome", "iterative", "coordination",
                                 "prerequisite", "dependency", "capacity")
    feasibility_concerns = [r for r in (rec.known_risks or [])
                           if any(kw in r.lower() for kw in feasibility_risk_keywords)]

    # Objection-driven cap: unresolved feasibility/timing objections
    feasibility_objections = [oid for oid in constraining
                             if oid in all_objections
                             and (all_objections[oid].type in ("timing", "evidence_gap")
                                  and any(kw in all_objections[oid].objection_text.lower()
                                          for kw in ("feasib", "deploy", "rollback", "implement",
                                                     "capacity", "complex", "coordinat", "prerequisite")))]
    if feasibility_objections:
        return "UNCERTAIN"
    elif len(feasibility_concerns) >= 3:
        return "LOW"
    elif len(feasibility_concerns) >= 2:
        return "MODERATE"
    elif feasibility_concerns:
        return "HIGH"
    else:
        return "HIGH"


def _calibrate_time(
    rec: Recommendation,
    constraining: list[str],
    all_objections: dict[str, "Objection"],
    thesis_lower: str,
    combined_text: str,
    domain: str,
    log_path: Path,
) -> str:
    """Calibrate time_to_protective_effect from timing signals + domain."""
    # Objection-driven cap
    time_objections = [oid for oid in constraining
                      if oid in all_objections and all_objections[oid].type == "timing"]
    if time_objections:
        return "UNCERTAIN"

    # Timing signals — domain-calibrated
    immediate_signals = ("immediately", "instant", "t+0", "within minutes", "right now",
                         "deploy now", "execute now", "activate immediately")
    near_term_signals = ("30 min", "within hour", "1-2 hour", "fast", "rapid",
                         "within 30", "2 week", "2-week", "3 week")
    slow_signals = ("month", "quarter", "4 month", "6 week", "8 week",
                    "long-term", "long term", "major version upgrade")

    has_immediate = any(sig in combined_text for sig in immediate_signals)
    has_near_term = any(sig in combined_text for sig in near_term_signals)
    has_slow = any(sig in combined_text for sig in slow_signals)

    if has_immediate and not has_slow:
        return "IMMEDIATE"
    elif has_near_term and not has_slow:
        return "NEAR_TERM"
    elif has_slow:
        return "FLEXIBLE"
    elif has_immediate:
        return "NEAR_TERM"
    else:
        return "FLEXIBLE"


def _calibrate_reversibility(
    rec: Recommendation,
    risks_text: str,
    thesis_lower: str,
    combined_text: str,
    log_path: Path,
) -> str:
    """Calibrate reversibility_downside from action-specific signals.

    Primary source: known_risks (structured, action-specific).
    Secondary source: thesis text — but only action-downside signals, not threat language.
    """
    action_bounded_signals = ("bounded", "recoverable", "rollback", "reversible",
                              "low disruption", "minutes", "revert", "restore",
                              "easily reversed", "re-enable", "can be undone")
    action_severe_signals = ("shutdown", "full outage", "service unavailability",
                             "irrecoverable", "cannot roll back", "permanent",
                             "all users affected", "existential")
    action_heavy_signals = ("extended outage", "prolonged", "unpredictable recovery",
                            "cascading", "data loss", "significant disruption",
                            "churn", "reputational")

    has_action_bounded = any(sig in risks_text for sig in action_bounded_signals)
    has_action_severe = any(sig in risks_text for sig in action_severe_signals)
    has_action_heavy = any(sig in risks_text for sig in action_heavy_signals)

    thesis_bounded = any(sig in thesis_lower for sig in action_bounded_signals)
    thesis_shutdown = "shutdown" in thesis_lower or "take offline" in thesis_lower or "full outage" in thesis_lower

    # Priority: action-level signals from known_risks beat thesis-level signals
    if has_action_bounded:
        reversibility = "BOUNDED"
    elif has_action_severe or thesis_shutdown:
        reversibility = "SEVERE"
    elif has_action_heavy:
        reversibility = "HEAVY"
    elif thesis_bounded:
        reversibility = "BOUNDED"
    else:
        reversibility = "MANAGEABLE"

    # Log when thesis threat language was present but overridden
    threat_words = [kw for kw in ("catastrophic", "irreversible", "severe", "devastating")
                    if kw in thesis_lower]
    if threat_words and reversibility in ("BOUNDED", "MANAGEABLE"):
        _log_text(
            log_path,
            f"[SLP-REVERSIBILITY] {rec.item_id} rated {reversibility} — "
            f"threat language ({', '.join(threat_words)}) present in thesis "
            f"but action-downside signal ({reversibility}) takes priority",
        )
    return reversibility


def _calibrate_evidence_confidence(
    rec: Recommendation,
    claim_scores: dict[str, str],
    constraining: list[str],
    all_objections: dict[str, "Objection"],
    log_path: Path,
) -> str:
    """Calibrate evidence_confidence from Auditor claim scores + objection types."""
    rec_claim_levels = [claim_scores.get(cid, "ADEQUATE") for cid in (rec.claim_ids or []) if cid in claim_scores]
    if not rec_claim_levels:
        ev_conf = "LIMITED"
    else:
        mapped = [_slp_map_evidence_confidence(lvl) for lvl in rec_claim_levels]
        worst_idx = max(_slp_band_index(m, SLP_EVIDENCE_BANDS) for m in mapped)
        ev_conf = SLP_EVIDENCE_BANDS[min(worst_idx, len(SLP_EVIDENCE_BANDS) - 1)]

    # Objection-driven cap: evidence_gap and logical_gap objections constrain confidence
    evidence_gap_objections = [oid for oid in constraining
                               if oid in all_objections
                               and all_objections[oid].type in ("evidence_gap", "logical_gap")]

    if len(evidence_gap_objections) >= 2 and _slp_band_index(ev_conf, SLP_EVIDENCE_BANDS) < 2:
        ev_conf = "LIMITED"
        _log_text(log_path, f"[SLP-CAP] {rec.item_id} evidence_confidence capped to LIMITED — {len(evidence_gap_objections)} evidence/logical gap objections")
    elif evidence_gap_objections and ev_conf == "STRONG":
        ev_conf = "ADEQUATE"
        _log_text(log_path, f"[SLP-CAP] {rec.item_id} evidence_confidence capped to ADEQUATE — evidence gap objections present")
    elif constraining and ev_conf == "STRONG":
        ev_conf = "ADEQUATE"
        _log_text(log_path, f"[SLP-CAP] {rec.item_id} evidence_confidence capped to ADEQUATE — deferred objections present")

    return ev_conf

    return {
        "standalone_impact": SLPDimension(
            rating=impact, rationale=f"Action semantics: {'definitive' if has_definitive else 'partial' if has_partial else 'containment' if has_containment else 'unclassified'}; decision: {decision}",
            evidence_ids=rec_evidence[:5], constraining_objections=constraining,
        ),
        "execution_feasibility": SLPDimension(
            rating=feasibility,
            rationale=f"{len(feasibility_concerns)} known risk(s), {len(feasibility_objections)} feasibility objection(s)",
            evidence_ids=rec_evidence[:5], constraining_objections=feasibility_objections,
        ),
        "time_to_protective_effect": SLPDimension(
            rating=time_rating, rationale=f"Timing signals from thesis and {len(time_objections)} timing objection(s)",
            evidence_ids=rec_evidence[:3], constraining_objections=time_objections,
        ),
        "reversibility_downside": SLPDimension(
            rating=reversibility, rationale=f"Downside assessment from thesis and known_risks",
            evidence_ids=rec_evidence[:3], constraining_objections=[],
        ),
        "evidence_confidence": SLPDimension(
            rating=ev_conf,
            rationale=f"Claim support levels: {rec_claim_levels[:5]}; {len(constraining)} deferred objection(s)",
            evidence_ids=rec_evidence[:5], constraining_objections=constraining,
        ),
    }


def _build_slp_profiles(
    final_audit: AuditSnapshot,
    ledger: RunLedger,
    latest_proposal: ProposalPack,
    log_path: Path,
) -> list[StandaloneLeverageProfile]:
    """Build SLP for each recommendation from final adjudicated state."""
    # Build lookup tables
    decision_map: dict[str, str] = {}
    for rd in final_audit.recommendation_decisions:
        decision_map[rd.item_id] = rd.decision

    claim_scores: dict[str, str] = {}
    for cs in final_audit.claim_scores:
        claim_scores[cs.claim_id] = cs.support_level

    deferred_ids = [oid for oid, s in ledger.objection_ledger.items() if s == "DEFERRED"]

    all_objections: dict[str, Objection] = {}
    for oh in ledger.objection_history:
        for obj in oh.objections:
            all_objections[obj.objection_id] = obj
    for oid, obj in ledger.deferred_objection_store.items():
        all_objections[oid] = obj

    profiles: list[StandaloneLeverageProfile] = []
    for rec in latest_proposal.recommendations:
        decision = decision_map.get(rec.item_id, "NEEDS_EVIDENCE")
        eligibility = _slp_derive_eligibility(rec, decision, ledger, log_path)
        dimensions = _slp_derive_dimensions(
            rec, decision, claim_scores, deferred_ids, all_objections, ledger, log_path,
        )

        summary_parts = [f"{rec.name}: {eligibility.status}."]
        if eligibility.status == "INELIGIBLE_FOR_HIGHLIGHT":
            summary_parts.append(f"Not viable as standalone action ({eligibility.reason}).")
        else:
            summary_parts.append(
                f"Impact={dimensions['standalone_impact'].rating}, "
                f"Feasibility={dimensions['execution_feasibility'].rating}, "
                f"Evidence={dimensions['evidence_confidence'].rating}."
            )

        dep_note = ""
        if eligibility.status == "CONDITIONALLY_ELIGIBLE":
            dep_note = f"Value depends on: {eligibility.applicability_condition or 'trigger condition'}."
        elif "component" in (rec.role_in_portfolio or "").lower():
            dep_note = "Primarily valuable as part of the layered portfolio, not standalone."
        elif rec.rank == 1:
            dep_note = "Primary action; portfolio adds escalation/fallback options."
        else:
            dep_note = f"Portfolio role: {rec.role_in_portfolio[:100]}."

        profile = StandaloneLeverageProfile(
            item_id=rec.item_id,
            standalone_eligibility=eligibility,
            standalone_impact=dimensions["standalone_impact"],
            execution_feasibility=dimensions["execution_feasibility"],
            time_to_protective_effect=dimensions["time_to_protective_effect"],
            reversibility_downside=dimensions["reversibility_downside"],
            evidence_confidence=dimensions["evidence_confidence"],
            standalone_summary=" ".join(summary_parts),
            portfolio_dependency_note=dep_note,
        )
        profiles.append(profile)
        _log_text(
            log_path,
            f"[SLP] {rec.item_id}: eligibility={eligibility.status}, "
            f"impact={dimensions['standalone_impact'].rating}, "
            f"feasibility={dimensions['execution_feasibility'].rating}, "
            f"time={dimensions['time_to_protective_effect'].rating}, "
            f"reversibility={dimensions['reversibility_downside'].rating}, "
            f"evidence={dimensions['evidence_confidence'].rating}",
        )
    return profiles


def _slp_check_condition_satisfied(profile: StandaloneLeverageProfile, task: str) -> bool:
    """Check whether a CONDITIONALLY_ELIGIBLE item's applicability condition is explicitly satisfied.

    Evaluates the condition text against the brief/task text.  Returns True only when
    the task contains explicit language that satisfies the stated condition.
    """
    condition = (profile.standalone_eligibility.applicability_condition or "").lower()
    if not condition:
        return False
    task_lower = task.lower()

    # Extract key trigger phrases from the condition
    trigger_phrases = []
    for phrase in ("confirmed", "detected", "verified", "active exploitation", "patch failure",
                   "failed", "breached", "compromised"):
        if phrase in condition:
            trigger_phrases.append(phrase)

    if not trigger_phrases:
        # No recognizable trigger pattern — cannot confirm satisfaction from task text alone
        return False

    # The condition is satisfied only if the task explicitly states the trigger is active
    return any(phrase in task_lower for phrase in trigger_phrases)


def _build_slp_highlight(
    profiles: list[StandaloneLeverageProfile],
    log_path: Path,
    task: str = "",
) -> SLPHighlight:
    """Apply structured dominance rules to determine optional single-action highlight.

    Pool formation → candidate-local caps → structured dominance (§8 of design doc).
    No dimension-counting.  No weighted scores.
    Dominance compares best candidate against ALL other pool members, not just runner-up.
    """
    # --- Pool formation ---
    pool: list[StandaloneLeverageProfile] = []
    for p in profiles:
        if p.standalone_eligibility.status == "ELIGIBLE":
            pool.append(p)
        elif p.standalone_eligibility.status == "CONDITIONALLY_ELIGIBLE":
            if _slp_check_condition_satisfied(p, task):
                pool.append(p)
                _log_text(log_path, f"[SLP-HIGHLIGHT] {p.item_id} admitted to pool — CONDITIONALLY_ELIGIBLE with condition satisfied")
            else:
                _log_text(log_path, f"[SLP-HIGHLIGHT] {p.item_id} excluded from pool — CONDITIONALLY_ELIGIBLE (condition not satisfied by brief)")
        else:
            _log_text(log_path, f"[SLP-HIGHLIGHT] {p.item_id} excluded from pool — {p.standalone_eligibility.status}")

    if not pool:
        _log_text(log_path, "[SLP-HIGHLIGHT] No eligible candidates — INDETERMINATE")
        return SLPHighlight(
            item_id=None, confidence="INDETERMINATE",
            rationale="No eligible candidates in the pool.",
            caveat="All recommendations are conditional, component-only, or failed.",
        )

    # --- Candidate-local caps: remove WEAK evidence candidates ---
    viable: list[StandaloneLeverageProfile] = []
    for p in pool:
        if p.evidence_confidence.rating == "WEAK":
            _log_text(log_path, f"[SLP-CAP] {p.item_id} removed from highlight pool — WEAK evidence")
            continue
        viable.append(p)

    if not viable:
        _log_text(log_path, "[SLP-HIGHLIGHT] All pool candidates have WEAK evidence — INDETERMINATE")
        return SLPHighlight(
            item_id=None, confidence="INDETERMINATE",
            rationale="All eligible candidates have WEAK evidence confidence.",
            caveat="Evidence base insufficient across all standalone options.",
        )

    if len(viable) == 1:
        candidate = viable[0]
        conf = "CLEAR"
        cap_reasons: list[str] = []
        # Local caps: UNCERTAIN on execution_feasibility (impact bands don't include UNCERTAIN)
        if candidate.execution_feasibility.rating == "UNCERTAIN":
            conf = "MARGINAL"
            cap_reasons.append("UNCERTAIN on execution_feasibility")
        if candidate.evidence_confidence.rating == "LIMITED":
            conf = "MARGINAL"
            cap_reasons.append("evidence confidence is LIMITED")
        _log_text(log_path, f"[SLP-HIGHLIGHT] {candidate.item_id} — sole viable candidate — {conf}" +
                  (f" (capped: {'; '.join(cap_reasons)})" if cap_reasons else ""))
        return SLPHighlight(
            item_id=candidate.item_id, confidence=conf,
            rationale=f"{candidate.item_id} is the only viable standalone action." +
                      (f" Capped to {conf}: {'; '.join(cap_reasons)}." if cap_reasons else ""),
            caveat="Portfolio provides additional escalation and fallback options not captured by standalone assessment.",
        )

    # --- Structured dominance (2+ viable candidates) ---
    # Sort by standalone_impact (best first)
    viable.sort(key=lambda p: _slp_band_index(p.standalone_impact.rating, SLP_IMPACT_BANDS))

    best = viable[0]
    others = viable[1:]

    # Check if best strictly leads on impact vs ALL others
    tied_on_impact = [o for o in others if o.standalone_impact.rating == best.standalone_impact.rating]
    if tied_on_impact:
        tied_ids = [o.item_id for o in tied_on_impact]
        _log_text(
            log_path,
            f"[SLP-HIGHLIGHT] {best.item_id} tied on standalone_impact "
            f"({best.standalone_impact.rating}) with {tied_ids} — INDETERMINATE",
        )
        return SLPHighlight(
            item_id=None, confidence="INDETERMINATE",
            rationale=f"{best.item_id} and {', '.join(tied_ids)} share the same standalone impact rating ({best.standalone_impact.rating}). Profile comparison does not yield a clear single-action leader.",
            caveat="Portfolio layering is the recommended approach when no single action clearly dominates.",
        )

    # Best leads on impact — check viability dimensions against ALL other pool members
    conf = "CLEAR"
    cap_reasons = []
    viability_worse_count = 0

    for other in others:
        if _slp_materially_worse(best.execution_feasibility.rating, other.execution_feasibility.rating, SLP_FEASIBILITY_BANDS):
            cap_reasons.append(f"materially worse on execution_feasibility vs {other.item_id}")
            viability_worse_count += 1
        if _slp_materially_worse(best.reversibility_downside.rating, other.reversibility_downside.rating, SLP_REVERSIBILITY_BANDS):
            cap_reasons.append(f"materially worse on reversibility_downside vs {other.item_id}")
            viability_worse_count += 1

    # Translate viability comparison into confidence
    if viability_worse_count >= 2:
        conf = "INDETERMINATE"
    elif viability_worse_count == 1:
        conf = "MARGINAL"

    # Candidate-local dimension caps (execution_feasibility only — impact bands don't include UNCERTAIN)
    if best.execution_feasibility.rating == "UNCERTAIN":
        if conf == "CLEAR":
            conf = "MARGINAL"
        cap_reasons.append("UNCERTAIN on execution_feasibility")

    # Evidence confidence cap (qualifier, not peer)
    if best.evidence_confidence.rating == "LIMITED":
        if conf == "CLEAR":
            conf = "MARGINAL"
        cap_reasons.append("evidence confidence is LIMITED")

    if conf == "INDETERMINATE":
        _log_text(log_path, f"[SLP-HIGHLIGHT] {best.item_id} leads on impact but INDETERMINATE — {'; '.join(cap_reasons)}")
        return SLPHighlight(
            item_id=None, confidence="INDETERMINATE",
            rationale=f"{best.item_id} leads on standalone impact ({best.standalone_impact.rating}) but is materially worse on critical viability dimensions: {'; '.join(cap_reasons)}.",
            caveat="Portfolio layering compensates for the tradeoffs that prevent a clear standalone recommendation.",
        )

    _log_text(log_path, f"[SLP-HIGHLIGHT] {best.item_id} — {conf}" +
              (f" (qualified: {'; '.join(cap_reasons)})" if cap_reasons else " (no tradeoffs)"))
    return SLPHighlight(
        item_id=best.item_id, confidence=conf,
        rationale=f"{best.item_id} leads on standalone impact ({best.standalone_impact.rating}) "
                  f"and is {'not worse' if not cap_reasons else 'qualified'} on viability dimensions."
                  + (f" Tradeoffs: {'; '.join(cap_reasons)}." if cap_reasons else ""),
        caveat="Portfolio provides additional escalation and fallback options not captured by standalone assessment.",
    )


def _build_final_verdict(
    raw_verdict: ConsensusVerdict,
    final_audit: AuditSnapshot | None,
    ledger: RunLedger,
    log_path: Path,
    latest_proposal: ProposalPack | None,
) -> ConsensusVerdict:
    """Build the ONE final authoritative verdict from Judge's raw output + controller state.
    Steps: A (item normalization) -> B (status normalization) -> C (confidence) -> D (field sync)."""
    import copy

    verdict = copy.deepcopy(raw_verdict)

    # --- Step A: normalize item lists to final live set ---
    live_item_ids = set()
    if latest_proposal:
        live_item_ids = {r.item_id for r in latest_proposal.recommendations}

    pruned_approved = [item for item in verdict.approved_items if item not in live_item_ids]
    pruned_rejected = [item for item in verdict.rejected_items if item not in live_item_ids]
    if pruned_approved or pruned_rejected:
        verdict.approved_items = [item for item in verdict.approved_items if item in live_item_ids]
        verdict.rejected_items = [item for item in verdict.rejected_items if item in live_item_ids]
        _log_text(
            log_path,
            f"[FINAL-NORM] Step A: removed pruned items: approved={pruned_approved}, rejected={pruned_rejected}",
        )
    overlap = set(verdict.approved_items) & set(verdict.rejected_items)
    if overlap:
        for item in overlap:
            verdict.rejected_items.remove(item)
        _log_text(log_path, f"[FINAL-NORM] Step A: removed overlap from rejected: {overlap}")
    _log_text(log_path, f"[FINAL-NORM] Step A: live set={sorted(live_item_ids)} ({len(live_item_ids)} items)")

    # --- Step A2: Weak-core-claim veto ---
    status_norm_fired = False
    if final_audit and latest_proposal:
        weak_core_claims = set()
        for cs in final_audit.claim_scores:
            if cs.support_level in ("WEAK", "UNSUPPORTED"):
                for claim in latest_proposal.claims:
                    if claim.claim_id == cs.claim_id and claim.importance == "CORE":
                        weak_core_claims.add(cs.claim_id)
                        break
        if weak_core_claims:
            demoted_items = []
            for rec in latest_proposal.recommendations:
                rec_core_claims = set(rec.claim_ids) & weak_core_claims
                if rec_core_claims:
                    if rec.item_id in verdict.approved_items:
                        verdict.approved_items.remove(rec.item_id)
                        if rec.item_id not in verdict.rejected_items:
                            verdict.rejected_items.append(rec.item_id)
                        demoted_items.append(f"{rec.item_id} ({', '.join(rec_core_claims)})")
                        _log_text(
                            log_path,
                            f"[FINAL-NORM] Step A2 VETO: {rec.item_id} demoted — CORE claim(s) {rec_core_claims} WEAK/UNSUPPORTED",
                        )
            if demoted_items:
                _log_text(log_path, f"[FINAL-NORM] Step A2: weak-core-claim veto: {', '.join(demoted_items)}")

    # --- Step B: normalize status from final state ---
    if verdict.status == "CONSENSUS" and verdict.unresolved_points:
        verdict.status = "CLOSED_WITH_ACCEPTED_RISKS"
        import re as _re  # noqa: PLC0415
        rationale_sentences = _re.split(r'(?<=[.!?])\s+', (verdict.rationale or "").strip())
        rationale_sentences = [
            sentence
            for sentence in rationale_sentences
            if "CONSENSUS is appropriate" not in sentence
            and "CLOSED_WITH_ACCEPTED_RISKS is not required" not in sentence
        ]
        normalization_note = (
            f"[Normalized from CONSENSUS: {len(verdict.unresolved_points)} deferred/unresolved item(s) present"
            " — CLOSED_WITH_ACCEPTED_RISKS per policy.]"
        )
        verdict.rationale = (
            f"{' '.join(rationale_sentences).strip()} {normalization_note}".strip()
            if rationale_sentences
            else normalization_note
        )
        status_norm_fired = True
        _log_text(
            log_path,
            f"[FINAL-NORM] Step B: CONSENSUS -> CLOSED_WITH_ACCEPTED_RISKS ({len(verdict.unresolved_points)} unresolved/deferred)",
        )
    if verdict.status == "CONSENSUS" and verdict.rejected_items:
        verdict.status = "CLOSED_WITH_ACCEPTED_RISKS"
        status_norm_fired = True
        _log_text(log_path, "[FINAL-NORM] Step B: CONSENSUS -> CLOSED_WITH_ACCEPTED_RISKS (rejected items exist)")

    # B3: If nothing is approved after normalization, status cannot be CONSENSUS or PARTIAL_CONSENSUS
    if not verdict.approved_items and verdict.status not in ("NO_CONSENSUS", "SYSTEM_FAILURE"):
        old_status = verdict.status
        verdict.status = "NO_CONSENSUS"
        status_norm_fired = True
        _log_text(
            log_path,
            f"[FINAL-NORM] Step B: {old_status} -> NO_CONSENSUS (zero approved items — "
            f"chamber did not reach an approvable answer)",
        )

    # --- Step C: compute confidence from NORMALIZED final status + final-state counts ---
    raw_confidence = verdict.confidence
    penalty_sum = 0.0
    penalty_details = []

    deferred_count = sum(1 for st in ledger.objection_ledger.values() if st == "DEFERRED")
    if deferred_count > 0:
        p = deferred_count * 0.04
        penalty_sum += p
        penalty_details.append(f"deferred={deferred_count}x0.04={p:.2f}")

    pwr_count = 0
    fail_count = 0
    if final_audit:
        for rd in final_audit.recommendation_decisions:
            if rd.item_id in live_item_ids:
                if rd.decision == "PASS_WITH_RISK":
                    pwr_count += 1
                elif rd.decision == "FAIL":
                    fail_count += 1
    if pwr_count > 0:
        p = pwr_count * 0.03
        penalty_sum += p
        penalty_details.append(f"PWR={pwr_count}x0.03={p:.2f}")

    if fail_count > 0:
        p = fail_count * 0.10
        penalty_sum += p
        penalty_details.append(f"FAIL={fail_count}x0.10={p:.2f}")

    if status_norm_fired:
        penalty_sum += 0.05
        penalty_details.append("STATUS-NORM=0.05")

    final_confidence = max(raw_confidence - penalty_sum, 0.20)

    if ledger.critic_collapse_penalty > 0:
        final_confidence = max(final_confidence - ledger.critic_collapse_penalty, 0.10)
        penalty_details.append(f"critic-collapse={ledger.critic_collapse_penalty:.2f}")

    verdict.confidence = round(final_confidence, 2)
    _log_text(
        log_path,
        f"[FINAL-NORM] Step C: confidence {raw_confidence:.2f} → {verdict.confidence} (penalties: {', '.join(penalty_details) if penalty_details else 'none'}, total: -{penalty_sum:.2f})",
    )

    # --- Step D: sync supporting fields ---
    pruned_ids: set[str] = set()
    if pruned_approved or pruned_rejected:
        pruned_ids = set(pruned_approved + pruned_rejected)
        verdict.unresolved_points = [
            pt for pt in verdict.unresolved_points if not any(pid in pt for pid in pruned_ids)
        ]

    # D2: rebuild rationale to reflect the final normalized state
    # Strip references to pruned items and stale confidence from prose
    if pruned_ids or raw_confidence != verdict.confidence:
        rationale = verdict.rationale
        # Remove sentences that reference pruned item IDs
        if pruned_ids:
            import re
            sentences = re.split(r'(?<=[.!?])\s+', rationale)
            filtered = [s for s in sentences if not any(pid in s for pid in pruned_ids)]
            rationale = " ".join(filtered) if filtered else rationale

        # Replace stale confidence values in prose
        raw_str_2 = f"{raw_confidence:.2f}"
        raw_str_1 = f"{raw_confidence:.1f}"
        final_str = f"{verdict.confidence:.2f}"
        if raw_str_2 in rationale:
            rationale = rationale.replace(raw_str_2, final_str)
        elif raw_str_1 in rationale:
            rationale = rationale.replace(raw_str_1, f"{verdict.confidence:.1f}")

        # Replace stale item counts in prose (e.g. "All six" → "All five")
        num_words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
        original_count = len(live_item_ids) + len(pruned_ids)
        final_count = len(live_item_ids)
        if original_count != final_count:
            old_word = num_words.get(original_count, str(original_count))
            new_word = num_words.get(final_count, str(final_count))
            # Case-insensitive replacement for "all six" → "all five" etc.
            import re as _re
            rationale = _re.sub(
                rf'\b[Aa]ll\s+{old_word}\b',
                lambda m: f"{'A' if m.group()[0] == 'A' else 'a'}ll {new_word}",
                rationale,
            )
            rationale = rationale.replace(f" {original_count} recommendations", f" {final_count} recommendations")

        if rationale != verdict.rationale:
            verdict.rationale = rationale
            _log_text(log_path, "[FINAL-NORM] Step D: rationale synced to final normalized state")

    # D3: strip pruned items from next_action if present
    if pruned_ids and verdict.next_action:
        import re as _re2  # noqa: PLC0415
        sentences = _re2.split(r'(?<=[.!?])\s+', verdict.next_action)
        filtered = [s for s in sentences if not any(pid in s for pid in pruned_ids)]
        new_next = " ".join(filtered) if filtered else verdict.next_action
        if new_next != verdict.next_action:
            verdict.next_action = new_next
            _log_text(log_path, "[FINAL-NORM] Step D: next_action synced to final normalized state")

    _log_text(
        log_path,
        f"[FINAL-NORM] Step D: verdict finalized — status={verdict.status}, confidence={verdict.confidence}, approved={verdict.approved_items}, rejected={verdict.rejected_items}",
    )

    # --- Step E: enrich deferred-objection entries in unresolved_points ---
    # Replace "content unknown" placeholders with actual substance from the ledger.
    deferred_obj_details: dict[str, "Objection | None"] = {}
    for _oid, _st in ledger.objection_ledger.items():
        if _st == "DEFERRED":
            # Check deferred_objection_store first (populated at freeze time, not in objection_history)
            _detail = ledger.deferred_objection_store.get(_oid)
            if _detail is None:
                for _oh in ledger.objection_history:
                    for _obj in _oh.objections:
                        if _obj.objection_id == _oid:
                            _detail = _obj
                            break
                    if _detail:
                        break
            deferred_obj_details[_oid] = _detail

    if deferred_obj_details:
        import re as _re_e
        enriched_points = []
        for pt in verdict.unresolved_points:
            found_oids = _re_e.findall(r'\bOBJ\d+\b', pt)
            enriched = pt
            for _oid in found_oids:
                if _oid in deferred_obj_details:
                    _detail = deferred_obj_details[_oid]
                    if _detail is not None:
                        _rich = (
                            f"{_oid} (deferred — {_detail.severity} {_detail.type} "
                            f"on {_detail.claim_id or 'portfolio'}: "
                            f"{_detail.objection_text[:150]})"
                        )
                        # Replace "content unknown" variant
                        enriched = _re_e.sub(
                            rf'\b{_re_e.escape(_oid)}\s*\([^)]*content\s+unknown[^)]*\)',
                            _rich,
                            enriched,
                        )
                        # Replace "not adjudicated" variant
                        enriched = _re_e.sub(
                            rf'\b{_re_e.escape(_oid)}\s*\([^)]*not\s+adjudicated[^)]*\)',
                            _rich,
                            enriched,
                        )
            enriched_points.append(enriched)
        if enriched_points != verdict.unresolved_points:
            verdict.unresolved_points = enriched_points
            _log_text(log_path, f"[FINAL-NORM] Step E: enriched {len(deferred_obj_details)} deferred objection(s) in unresolved_points")

    # --- Step F: Standalone Leverage Profile (supplementary, controller-synthesized) ---
    if final_audit is not None and latest_proposal is not None:
        try:
            slp_profiles = _build_slp_profiles(final_audit, ledger, latest_proposal, log_path)
            slp_highlight = _build_slp_highlight(slp_profiles, log_path, task=ledger.task)
            verdict.standalone_leverage_profiles = [p.model_dump() for p in slp_profiles]
            verdict.highest_standalone_leverage = slp_highlight.model_dump()
            _log_text(
                log_path,
                f"[SLP-FINAL] {len(slp_profiles)} profiles generated, "
                f"highlight={slp_highlight.item_id or 'none'} ({slp_highlight.confidence})",
            )
        except Exception as exc:
            _log_text(log_path, f"[SLP-ERROR] SLP generation failed (non-fatal): {exc}")
            # SLP is supplementary — failure must not break the verdict
            verdict.standalone_leverage_profiles = []
            verdict.highest_standalone_leverage = SLPHighlight(
                item_id=None, confidence="INDETERMINATE",
                rationale=f"SLP generation failed: {exc}",
            ).model_dump()

    # ===================================================================
    # Step G: Exclusive-choice selection (only when choice_mode == "exclusive")
    # ===================================================================
    verdict.choice_mode = ledger.choice_mode
    if ledger.choice_mode == "exclusive" and verdict.approved_items:
        verdict.selected_option = _select_exclusive_winner(
            verdict, ledger, latest_proposal, log_path,
        )

    return verdict


def _select_exclusive_winner(
    verdict: ConsensusVerdict,
    ledger: RunLedger,
    proposal: ProposalPack,
    log_path: Path,
) -> dict | None:
    """Select a single winner from approved items for exclusive-choice briefs.

    Selection policy:
    1. Score ALL approved candidates together (brief-native and composite in one pool)
    2. If the highest-scoring candidate is brief-native, select it
    3. If the highest-scoring candidate is composite and strictly dominates all
       brief-native options, select it with explicit composite labeling
    4. If scores are tied between brief-native and composite, prefer brief-native
    5. If multiple candidates tie with no clear winner, return INDETERMINATE

    Returns a dict: {item_id, label, source_type, selection_rationale} or None.
    """
    if not proposal or not verdict.approved_items:
        return None

    approved_recs = [r for r in proposal.recommendations if r.item_id in verdict.approved_items]
    if not approved_recs:
        return None

    # Classify each as brief-native or composite
    brief_native_ids = set()
    if ledger.brief_option_registry:
        for rec in approved_recs:
            name_lower = (rec.name or "").lower()
            role_lower = (rec.role_in_portfolio or "").lower()
            for opt in ledger.brief_option_registry:
                if opt["id"].lower() in name_lower or "brief-native" in role_lower:
                    brief_native_ids.add(rec.item_id)
                    break

    brief_native_approved = [r for r in approved_recs if r.item_id in brief_native_ids]
    composite_approved = [r for r in approved_recs if r.item_id not in brief_native_ids]

    _log_text(log_path,
              f"[EXCLUSIVE-SELECTION] Pool: {len(brief_native_approved)} brief-native, "
              f"{len(composite_approved)} composite, {len(verdict.approved_items)} total approved")

    # --- Score each candidate using the FINAL adjudicated state ---
    slp_profiles = {p.get("item_id"): p for p in verdict.standalone_leverage_profiles}

    # Get the FINAL audit decisions (last audit snapshot, not intermediate ones)
    final_decisions: dict[str, str] = {}
    if ledger.audit_history:
        last_audit = ledger.audit_history[-1]
        for rd in last_audit.recommendation_decisions:
            final_decisions[rd.item_id] = rd.decision

    def _score_candidate(rec: Recommendation) -> tuple[int, int, int, int]:
        """Return a sortable tuple (higher = better).
        Components: (decision_strength, impact_rank, feasibility_rank, evidence_rank)"""
        decision = final_decisions.get(rec.item_id, "PASS_WITH_RISK")
        decision_score = {"PASS": 3, "PASS_WITH_RISK": 2}.get(decision, 1)

        profile = slp_profiles.get(rec.item_id, {})
        impact = profile.get("standalone_impact", {}).get("rating", "MODERATE") if isinstance(profile, dict) else "MODERATE"
        feasibility = profile.get("execution_feasibility", {}).get("rating", "MODERATE") if isinstance(profile, dict) else "MODERATE"
        evidence = profile.get("evidence_confidence", {}).get("rating", "ADEQUATE") if isinstance(profile, dict) else "ADEQUATE"

        impact_score = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1}.get(impact, 2)
        feasibility_score = {"HIGH": 3, "MODERATE": 2, "LOW": 1, "UNCERTAIN": 0}.get(feasibility, 2)
        evidence_score = {"STRONG": 4, "ADEQUATE": 3, "LIMITED": 2, "WEAK": 1}.get(evidence, 2)

        return (decision_score, impact_score, feasibility_score, evidence_score)

    # --- Score ALL candidates in one pool ---
    scored = [(rec, _score_candidate(rec)) for rec in approved_recs]
    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        _log_text(log_path, "[EXCLUSIVE-SELECTION] No candidates — INDETERMINATE")
        return {"item_id": None, "label": "INDETERMINATE", "source_type": "none",
                "selection_rationale": "No approved candidates available"}

    # Log all scores for auditability
    for rec, score in scored:
        src = "brief-native" if rec.item_id in brief_native_ids else "composite"
        _log_text(log_path,
                  f"[EXCLUSIVE-SELECTION] Scored {rec.item_id} ({src}): "
                  f"decision={score[0]}, impact={score[1]}, feasibility={score[2]}, evidence={score[3]}")

    best_rec, best_score = scored[0]

    # --- Tie handling ---
    if len(scored) >= 2:
        second_rec, second_score = scored[1]
        if best_score == second_score:
            best_is_native = best_rec.item_id in brief_native_ids
            second_is_native = second_rec.item_id in brief_native_ids

            if best_is_native and not second_is_native:
                pass  # brief-native wins tie over composite
            elif not best_is_native and second_is_native:
                # Composite tied with brief-native — prefer brief-native
                best_rec = second_rec
                best_score = second_score
                _log_text(log_path,
                          f"[EXCLUSIVE-SELECTION] Tie: preferring brief-native {best_rec.item_id} over composite")
            elif best_is_native and second_is_native:
                # Two brief-native options tied — INDETERMINATE
                _log_text(log_path,
                          f"[EXCLUSIVE-SELECTION] Tie between brief-native {best_rec.item_id} and "
                          f"{second_rec.item_id} — INDETERMINATE")
                return {"item_id": None, "label": "INDETERMINATE", "source_type": "tie",
                        "selection_rationale": (
                            f"Tie between brief-native {best_rec.item_id} ({best_score}) and "
                            f"{second_rec.item_id} ({second_score}); no clear winner"
                        )}
            else:
                _log_text(log_path, "[EXCLUSIVE-SELECTION] Tie between composites — INDETERMINATE")
                return {"item_id": None, "label": "INDETERMINATE", "source_type": "tie",
                        "selection_rationale": "Multiple composites tied; no clear winner"}

    # --- Composite winner validation ---
    source_type = "brief-native" if best_rec.item_id in brief_native_ids else "strategist-composite"

    if source_type == "strategist-composite" and brief_native_approved:
        # Composite won on score — verify it strictly dominates ALL brief-native options
        all_native_dominated = True
        for native_rec in brief_native_approved:
            native_score = _score_candidate(native_rec)
            if best_score <= native_score:
                all_native_dominated = False
                break

        if not all_native_dominated:
            # Composite doesn't strictly dominate — select best brief-native instead
            best_native = max(brief_native_approved, key=lambda r: _score_candidate(r))
            native_score = _score_candidate(best_native)
            _log_text(log_path,
                      f"[EXCLUSIVE-SELECTION] Composite {best_rec.item_id} ({best_score}) leads but does not "
                      f"strictly dominate brief-native {best_native.item_id} ({native_score}) — "
                      f"selecting brief-native as preferred")
            best_rec = best_native
            best_score = native_score
            source_type = "brief-native"
        else:
            _log_text(log_path,
                      f"[EXCLUSIVE-SELECTION] Composite {best_rec.item_id} strictly dominates all brief-native options")

    label = best_rec.name[:80]
    rationale = (
        f"Selected {best_rec.item_id} ({source_type}): "
        f"decision={best_score[0]}, impact={best_score[1]}, "
        f"feasibility={best_score[2]}, evidence={best_score[3]}"
    )
    _log_text(log_path, f"[EXCLUSIVE-SELECTION] {rationale}")

    return {
        "item_id": best_rec.item_id,
        "label": label,
        "source_type": source_type,
        "selection_rationale": rationale,
    }

def _apply_patch(
    proposal: ProposalPack,
    patch: StrategistPatch,
    ledger: RunLedger,
    log_path: Path,
) -> ProposalPack:
    """Apply a StrategistPatch to the current proposal, producing an updated ProposalPack."""
    import copy

    updated = copy.deepcopy(proposal)
    updated.proposal_id = patch.patch_id

    if patch.dropped_claim_ids:
        # Guard: block drops that would leave a recommendation with no supporting claims
        # AND no direct evidence links (fully orphaned recommendation).
        _live_claim_ids = {c.claim_id for c in updated.claims}
        _drop_set = set(patch.dropped_claim_ids)
        _blocked_drops: list[str] = []
        for _drop_id in patch.dropped_claim_ids:
            for _rec in updated.recommendations:
                if _drop_id not in _rec.claim_ids:
                    continue
                _remaining_claims = [
                    cid for cid in _rec.claim_ids
                    if cid != _drop_id and cid in _live_claim_ids and cid not in _drop_set
                ]
                if not _remaining_claims and not _rec.evidence_ids:
                    _log_text(log_path, f"[CLAIM-DROP-BLOCKED] {_drop_id} blocked — would fully orphan {_rec.item_id} (no surviving claims or direct evidence)")
                    if _drop_id not in _blocked_drops:
                        _blocked_drops.append(_drop_id)
                elif not _remaining_claims:
                    _log_text(log_path, f"[CLAIM-DROP-ORPHAN-RISK] {_drop_id} → {_rec.item_id} would have no supporting claims (direct evidence only)")
        _effective_drops = [cid for cid in patch.dropped_claim_ids if cid not in _blocked_drops]
        if _blocked_drops:
            _log_text(log_path, f"[CLAIM-DROP-BLOCKED] Drops blocked to protect orphan-risk recs: {_blocked_drops}")
        updated.claims = [c for c in updated.claims if c.claim_id not in _effective_drops]
        if _effective_drops:
            _log_text(log_path, f"[PATCH] Dropped claims: {_effective_drops}")

    for revised in patch.revised_claims:
        found = False
        for i, existing in enumerate(updated.claims):
            if existing.claim_id == revised.claim_id:
                updated.claims[i] = revised
                found = True
                break
        if not found:
            updated.claims.append(revised)
        _log_text(log_path, f"[PATCH] Revised claim: {revised.claim_id}")

    for revised_rec in patch.revised_recommendations:
        found = False
        for i, existing in enumerate(updated.recommendations):
            if existing.item_id == revised_rec.item_id:
                updated.recommendations[i] = revised_rec
                found = True
                break
        if not found:
            updated.recommendations.append(revised_rec)
        _log_text(log_path, f"[PATCH] Revised recommendation: {revised_rec.item_id}")

    dropped_item_ids = []
    for rc in patch.rank_changes:
        for rec in updated.recommendations:
            if rec.item_id == rc.get("item_id"):
                new_rank = rc.get("new_rank")
                if new_rank is None:
                    dropped_item_ids.append(rec.item_id)
                    _log_text(log_path, f"[PATCH] Recommendation {rec.item_id} dropped by Strategist (new_rank: null)")
                else:
                    rec.rank = new_rank
    # Remove dropped recommendations from the active set
    if dropped_item_ids:
        updated.recommendations = [r for r in updated.recommendations if r.item_id not in dropped_item_ids]
        _log_text(log_path, f"[PATCH] Pruned {len(dropped_item_ids)} ghost recommendations: {dropped_item_ids}")

    for resp in patch.objection_responses:
        _log_text(log_path, f"[PATCH] Objection {resp.objection_id}: {resp.action} - {resp.response[:100]}")

    return updated


def _brave_search(query: str, log_path: Path | None = None) -> list[dict] | None:
    """Call Brave Search API, return list of {title, url, snippet}.
    Returns None on failure (not empty list) so callers can distinguish
    'no results' from 'search broken'."""
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {
            "q": query,
            "count": MAX_BRAVE_RESULTS_PER_QUERY,
        }
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": BRAVE_API_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for item in data.get("web", {}).get("results", []):
            snippet = item.get("description", "")
            # V6 Fix 6: Append extra excerpts for deeper context
            extra = item.get("extra_snippets", [])
            if extra and isinstance(extra, list):
                extra_text = " ".join(s.strip() for s in extra[:3] if isinstance(s, str) and s.strip())
                if extra_text:
                    snippet = f"{snippet} {extra_text}"[:500]
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": snippet,
                }
            )
        return results
    except Exception as exc:
        if log_path:
            _log_text(log_path, f"[BRAVE-ERROR] Query failed: {exc}")
        return None  # None = failure, [] = no results


_HYPO_CLASSIFIER_COMMON_WORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "but", "is", "are", "was", "be", "by", "from", "that", "this", "it",
    "as", "if", "with", "not", "which", "their", "they", "have", "has",
    "been", "will", "can", "may", "should", "could", "would", "its",
    "we", "us", "do", "any", "all", "more", "than", "when", "how",
    "what", "who", "why", "where", "our", "your", "my", "his", "her",
    "there", "here", "then", "so", "no", "yes", "also",
    "about", "some", "into", "over", "after", "before", "while", "during",
})

# Generic vulnerability/security class terms — these are category labels, NOT concrete identifiers.
# Matching one of these as a "ticker" must not push the task into full-search mode.
_SECURITY_CLASS_TERMS = frozenset({
    "RCE", "XSS", "SQLI", "SQL", "CSRF", "SSRF", "LFI", "RFI", "XXE",
    "IDOR", "SSTI", "DOS", "DDOS", "UAF", "OOB", "BOF", "APT",
    "CVE", "CWE", "IOC", "TTP", "ATT", "CKM", "MITRE",
    "API", "JWT", "SAML", "LDAP", "SMB", "HTTP", "HTTPS",
    "TLS", "SSL", "SSH", "VPN", "IP", "TCP", "UDP",
    "POC", "CMD", "SYN", "ACK", "ACL", "IAM", "MFA",
    "EXEC", "VULN", "EXPLOIT", "PAYLOAD", "BYPASS", "FUZZ",
    # P1b round-3: security/networking/standards acronyms — never treat as financial tickers
    "WAF", "IDS", "IPS", "SIEM", "SOC", "EDR", "XDR", "MDR",
    "SAST", "DAST", "RASP", "RBAC", "DMZ", "CDN", "DNS", "SDK",
    "OAUTH", "PKI", "PEM", "CVSS", "OWASP", "NIST", "CISA",
    "CKT", "TTPS", "IOA", "DLP", "CASB", "UEBA", "SOAR",
})

# Cloud/platform/infrastructure acronyms — never treat as financial tickers (P3 round-4).
_INFRA_CLASS_TERMS = frozenset({
    "EKS", "GKE", "AKS", "ECS", "EC2", "RDS", "VPC", "ALB", "NLB", "ELB",
    "ASG", "AMI", "GCE", "GCS", "ACI", "ACR", "ARO", "ADF", "CDK", "SAM",
    "CLI", "SQS", "SNS", "SES", "DMS", "EMR", "MSK", "EFS", "FSX", "KMS",
    "HSM", "STS", "SSM", "NAT", "IGW", "TGW", "BGP", "OSPF", "MPLS", "LXC",
    "OCI", "OVH", "ARM", "GPU", "TPU", "NPU", "CPU", "RAM", "SSD", "NVME",
    "IOPS", "QPS", "TPS", "RPO", "RTO", "SLA", "SLO", "SLI", "K8S", "K8",
    "HELM", "ISTIO", "ETCD", "S3",
})

# Business, regulatory, currency, and general acronyms — hard stoplist.
# These are clearly non-finance operational tokens that should never be treated as
# stock tickers regardless of context. Confirmed false positives from cross-domain
# bundle testing: HIPAA, ARR, JIT, RPS, USD, AI (in non-finance contexts).
_BUSINESS_CLASS_TERMS = frozenset({
    # Business metrics
    "ARR", "MRR", "NRR", "CAC", "LTV", "GMV", "DAU", "MAU",
    "KPI", "OKR", "ROI", "NPS", "TAM", "SAM", "SOM", "MVP",
    # Technical concepts
    "JIT", "AOT", "OOM", "TTL", "FIFO", "LIFO", "CRUD", "REST",
    "IDE", "TDD", "BDD", "ETL", "ELT", "CDC",
    # Regulatory / legal / compliance — clearly not tickers
    "HIPAA", "GDPR", "CCPA", "SOX", "FERPA", "COPPA", "GLBA",
    "FISMA", "ITAR", "PII", "PHI", "PCI", "DORA", "NYDFS",
    # Units / currency codes — not tickers
    "USD", "EUR", "GBP", "JPY", "CNY", "INR", "AUD", "CAD", "CHF",
    # General / role acronyms
    "CEO", "CTO", "CFO", "COO", "CIO", "CISO", "CSO",
    "SVP", "EVP", "PMO", "SRE", "DBA",
    "FAQ", "TBD", "POC", "WIP", "EOD", "ETA", "FYI",
    "SAAS", "PAAS", "IAAS", "CICD",
    # Software metrics
    "LOC", "KLOC", "SLOC",
    # Cloud platform names (not financial tickers in tech briefs)
    "AWS", "GCP", "OCI",
    # Framework / runtime names (not financial tickers)
    "NET",
    # Data / ML acronyms (non-finance)
    "NLP", "LLM", "AGI", "RAG", "GPT", "CNN", "RNN", "GAN",
})

_SECURITY_CLASS_TERMS = _SECURITY_CLASS_TERMS | _INFRA_CLASS_TERMS | _BUSINESS_CLASS_TERMS

# Finance-context signals — if the task contains at least one of these, ambiguous uppercase
# tokens (e.g. AI, BTC, ETH) may be promoted to ticker classification.  Without these
# signals, no uppercase token should be classified as a ticker.
_FINANCE_CONTEXT_SIGNALS = frozenset({
    "stock", "share", "equity", "fund", "etf", "portfolio", "exchange",
    "nyse", "nasdaq", "s&p", "dow", "market cap", "dividend", "yield",
    "trading", "invest", "broker", "securities", "ticker", "holdings",
    "options", "futures", "derivatives", "hedge", "mutual fund",
    "expense ratio", "aum", "bond", "treasury", "ipo", "earnings",
})

# Domain substance patterns — used to detect real domain content in hypothetically-framed tasks.
# If a task uses hypothetical framing but contains these, it's BORDERLINE (not pure training_only).
_DOMAIN_SUBSTANCE_PATTERN = re.compile(
    r'\b(?:'
    r'remote\s*code\s*execution|buffer\s*overflow|sql\s*injec|cross.site\s*scripting|'
    r'path\s*traversal|privilege\s*escalat|memory\s*corrupt|arbitrary\s*code|'
    r'denial.of.service|race\s*condition|heap\s*overflow|stack\s*overflow|'
    r'authentication\s*bypass|command\s*inject|deserialization|use.after.free|'
    r'vulnerability|exploit|malware|ransomware|phishing|'
    r'etf|fund|portfolio|expense\s*ratio|holdings|aum|dividend|yield|'
    r'server|database|application|network|endpoint|firewall|encryption|'
    r'certificate|authorization|authentication|inject|bypass|overflow|'
    r'cve|regulation|compliance|audit|risk\s*assessment'
    r')\b',
    re.IGNORECASE,
)


def _has_domain_substance(task: str) -> bool:
    """Return True if task contains domain-specific content beyond pure hypothetical framing.

    Used to distinguish "pure hypothetical" (no domain substance → training_only) from
    "hypothetical framing + real domain content" (BORDERLINE → LLM tiebreaker).
    """
    task_lower = task.lower()
    if any(kw in task_lower for kw in _ETF_KEYWORDS):
        return True
    if _DOMAIN_SUBSTANCE_PATTERN.search(task):
        return True
    return False


def _classify_search_mode(task: str, log_path: Path | None = None) -> tuple[str, str]:
    """Classify task into search_mode: 'full', 'minimal', or 'training_only'.

    - 'full'          : concrete real-world identifiers found (CVE with number, ticker,
                        named company/product with version, regulation number)
    - 'minimal'       : no concrete identifiers, no hypothetical markers
    - 'training_only' : hypothetical scenario with no concrete identifiers

    Generic vulnerability/security classes (RCE, XSS, SQLI, etc.) are NOT identifiers.
    Only CVE IDs with numeric suffixes (e.g. CVE-2024-12345) count as CVE identifiers.
    """
    identifiers: list[str] = []
    identifier_reasons: list[str] = []
    hypothetical_markers: list[str] = []

    # CVE ID detection — MUST have the numeric year and sequence (not bare "CVE")
    cve_matches = re.findall(r'\bCVE-\d{4}-\d{4,7}\b', task, re.IGNORECASE)
    for m in cve_matches:
        identifiers.append(m)
        identifier_reasons.append(f"CVE-ID:{m}")

    # Ticker symbol detection: 2-5 uppercase letters that are NOT common words,
    # NOT generic security/vuln/infra/business class terms, AND require finance
    # context before promotion to ticker classification.
    _ticker_detected = False
    if not identifiers:  # only bother if no CVE found yet
        # Check for finance context in the task (case-insensitive)
        task_lower_for_finance = task.lower()
        has_finance_context = any(sig in task_lower_for_finance for sig in _FINANCE_CONTEXT_SIGNALS)

        ticker_candidates = re.findall(r'\b([A-Z]{2,5})\b', task)
        for t in ticker_candidates[:15]:
            if (
                t.lower() not in _HYPO_CLASSIFIER_COMMON_WORDS
                and t.upper() not in _SECURITY_CLASS_TERMS
                and len(t) >= 2
            ):
                if has_finance_context:
                    # Finance context present — promote to ticker
                    identifiers.append(t)
                    identifier_reasons.append(f"ticker:{t}")
                    _ticker_detected = True
                    break  # one ticker is enough to classify as full
                else:
                    # No finance context — log and skip, do not promote
                    if log_path is not None:
                        _log_text(
                            log_path,
                            f"[SEARCH-ROUTER-SIGNAL] type=ticker_skipped token={t} "
                            f"reason=no_finance_context (token survived stoplist but brief lacks finance signals)",
                        )
                    # Do not add to identifiers or reasons

    # Proper noun / company / product name: two or more consecutive Title-Cased words
    # (e.g. "Apache Struts", "Microsoft Exchange", "NIST SP")
    proper_noun_matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', task)
    for pn in proper_noun_matches:
        identifiers.append(pn)
        identifier_reasons.append(f"proper-noun:{pn}")

    # Regulation/standard numbers: e.g. "NIST SP 800-61", "ISO 27001", "PCI DSS 4.0"
    reg_matches = re.findall(r'\b(?:NIST|ISO|PCI|SOC|GDPR|HIPAA|FedRAMP)\s+[\w\-\.]+', task, re.IGNORECASE)
    for rm in reg_matches:
        identifiers.append(rm)
        identifier_reasons.append(f"regulation:{rm}")

    # Hypothetical marker detection
    _HYPO_PATTERNS = [
        r'\bhypothetical\b', r'\bscenario\b',
        r'\bwhat\s+if\b', r'\bimagine\b', r'\bsuppose\b',
    ]
    for pat in _HYPO_PATTERNS:
        matches = re.findall(pat, task, re.IGNORECASE)
        hypothetical_markers.extend(matches)

    # Deduplicate preserving order
    identifiers = list(dict.fromkeys(identifiers))
    identifier_reasons = list(dict.fromkeys(identifier_reasons))
    hypothetical_markers = list(dict.fromkeys(m.lower() for m in hypothetical_markers))

    # Decision logic:
    # - concrete identifiers found → "full" (real-world artifact exists to search for)
    # - hypothetical markers + no concrete identifiers → "training_only"
    # - neither → "minimal"
    if identifiers:
        mode = "full"
        reason = f"concrete identifiers found: {identifier_reasons}"
        # confidence: CLEAR if CVE/ticker-with-finance-context/regulation found;
        # BORDERLINE if only proper-noun or if ticker was the only strong signal
        # but finance context was weak.
        has_strong_id = any(
            r.startswith("CVE-ID:") or r.startswith("regulation:")
            for r in identifier_reasons
        )
        # Ticker is only "strong" if finance context was confirmed
        if not has_strong_id and _ticker_detected:
            has_strong_id = True  # finance context was already verified above
        routing_confidence = "CLEAR" if has_strong_id else "BORDERLINE"
    elif hypothetical_markers:
        if _has_domain_substance(task):
            # Hypothetical framing but real domain content present → BORDERLINE (LLM tiebreaker)
            mode = "minimal"  # regex best-guess; LLM may override
            reason = (
                f"hypothetical markers present but domain substance detected: "
                f"markers={hypothetical_markers}"
            )
            routing_confidence = "BORDERLINE"
        else:
            # Pure hypothetical with no domain substance → training_only, CLEAR
            mode = "training_only"
            reason = f"hypothetical markers present, no domain substance: markers={hypothetical_markers}"
            routing_confidence = "CLEAR"
    else:
        mode = "minimal"
        reason = "no concrete identifiers and no hypothetical markers"
        routing_confidence = "AMBIGUOUS"

    hard_ceiling = mode == "training_only"

    if log_path is not None:
        # Per-signal log lines
        for sig in identifier_reasons:
            _log_text(log_path, f"[SEARCH-ROUTER-SIGNAL] type=identifier signal={sig}")
        for hm in hypothetical_markers:
            _log_text(log_path, f"[SEARCH-ROUTER-SIGNAL] type=hypothetical_marker signal={hm}")
        if not identifier_reasons and not hypothetical_markers:
            _log_text(log_path, "[SEARCH-ROUTER-SIGNAL] type=none — no classifiable signals found (default fallback)")
        # Summary router event
        _log_text(
            log_path,
            f"[SEARCH-ROUTER] selected_mode={mode} routing_confidence={routing_confidence} "
            f"hard_live_retrieval_ceiling={hard_ceiling} "
            f"decision_basis={reason!r}",
        )
        # Keep legacy [SEARCH-MODE] line for backward compat with any existing log parsers
        _log_text(log_path, f"[SEARCH-MODE] Classified as: {mode} — reason: {reason}")

    return mode, routing_confidence


async def _llm_tiebreaker_classify(
    task: str,
    client: "ChatCompletionClient",
    log_path: "Path | None",
) -> tuple[str, str]:
    """One-shot LLM call to resolve BORDERLINE/AMBIGUOUS search mode.

    Returns (mode, rationale). Mode is one of: "full", "minimal", "training_only".
    Falls back to "minimal" on any error — never raises.
    """
    system_prompt = (
        "You are a search routing classifier. Your job is to decide whether a task query "
        "requires live web search.\n\n"
        "Definitions:\n"
        "- full: task references specific real-world identifiable entities (named CVEs, "
        "company names, specific products, regulation numbers, financial instruments like "
        "ETF tickers) where live web search would return authoritative, current information.\n"
        "- minimal: task has concrete domain content but no specific searchable identifiers; "
        "web context might help but training knowledge is the primary source.\n"
        "- training_only: purely hypothetical or abstract scenario with no real-world referents; "
        "web search would return nothing relevant; training knowledge is fully sufficient.\n\n"
        "Respond ONLY with a JSON object — no markdown, no explanation outside JSON:\n"
        '{"mode": "full|minimal|training_only", "rationale": "<one concise sentence>"}'
    )
    user_prompt = f"Task: {task}\n\nClassify the search mode."

    messages = [SystemMessage(content=system_prompt), UserMessage(content=user_prompt, source="user")]
    try:
        result = await asyncio.wait_for(client.create(messages), timeout=120)
        text = _strip_think_tags(str(result.content)).strip()
        # Extract JSON — handle potential markdown fencing
        json_match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")
        parsed = json.loads(json_match.group())
        mode = parsed.get("mode", "minimal")
        rationale = parsed.get("rationale", "")
        if mode not in ("full", "minimal", "training_only"):
            mode = "minimal"
        if log_path is not None:
            _log_text(
                log_path,
                f"[SEARCH-ROUTER] tiebreaker_decision mode={mode} rationale={rationale!r}",
            )
        return mode, rationale
    except Exception as exc:
        if log_path is not None:
            _log_text(log_path, f"[SEARCH-ROUTER] tiebreaker_error={exc!r} fallback=minimal")
        return "minimal", f"tiebreaker error fallback: {exc}"


async def _resolve_search_mode(
    task: str,
    tiebreaker_client: "ChatCompletionClient",
    log_path: "Path | None",
) -> tuple[str, str]:
    """Hybrid two-layer search mode resolution.

    Layer 1: Sync regex hard gate. CLEAR confidence → return immediately (no LLM cost).
    Layer 2: Async LLM tiebreaker for BORDERLINE or AMBIGUOUS confidence.

    Returns (mode, routing_confidence).
    Note: routing_confidence stores the regex confidence (CLEAR/BORDERLINE/AMBIGUOUS), not
    the LLM's determination. The LLM overrides the mode but not the confidence category.
    This is by design — [SEARCH-DIAGNOSTICS] reports original router confidence for audit.
    """
    mode, confidence = _classify_search_mode(task, log_path)

    if confidence == "CLEAR":
        # Hard gate is sufficient — skip LLM entirely
        return mode, confidence

    # BORDERLINE or AMBIGUOUS → invoke LLM tiebreaker
    if log_path is not None:
        _log_text(
            log_path,
            f"[SEARCH-ROUTER] regex_result mode={mode} confidence={confidence} "
            f"→ invoking LLM tiebreaker",
        )

    llm_mode, llm_rationale = await _llm_tiebreaker_classify(task, tiebreaker_client, log_path)

    if llm_mode != mode and log_path is not None:
        _log_text(
            log_path,
            f"[SEARCH-ROUTER] tiebreaker_override regex_mode={mode} "
            f"llm_mode={llm_mode} rationale={llm_rationale!r}",
        )

    return llm_mode, confidence


_SELF_REF_PATTERNS = re.compile(
    r'\b(this\s+CVE|this\s+vulnerability|this\s+organization|this\s+company|'
    r'our\s+API|our\s+system)\b',
    re.IGNORECASE,
)
_DOLLAR_AMOUNT_PATTERN = re.compile(r'\$[\d,]+(?:\.\d+)?[KMBkm]?\b')

# Org-internal / private-document query patterns — these can never be satisfied by web search
_ORG_INTERNAL_PATTERN = re.compile(
    r'\b(?:organization|company|firm|org)\b.{0,25}\b(?:internal|risk\s+policy|cost\s+estimate|'
    r'policy\s+document|budget|headcount)\b'
    r'|'
    r'\b(?:our|the)\s+(?:internal|policy|risk\s+management|cost\s+model)\b',
    re.IGNORECASE,
)

# Conversational fragment prefixes that should be stripped rather than searched verbatim
_CONV_PREFIX_PATTERN = re.compile(
    r'^(?:Clarification\s+on\s+(?:whether|if)\s+'
    r'|Explanation\s+of\s+why\s+'
    r'|Documentation\s+(?:showing|that|of)\s+'
    r'|Evidence\s+that\s+'
    r'|Proof\s+that\s+'
    r'|Confirmation\s+(?:that|of)\s+'
    r'|Information\s+(?:about|on)\s+'
    r')',
    re.IGNORECASE,
)


def _extract_topic_class(task: str) -> str:
    """Extract a short topic-class phrase from the task for self-reference substitution.

    Used to replace unresolvable self-references like "this vulnerability" with a
    meaningful descriptor so queries remain searchable rather than becoming fragments.
    """
    # Security: vulnerability type + affected component
    sec_match = re.search(
        r'\b(remote\s+code\s+execution|buffer\s+overflow|sql\s+injection|'
        r'cross.site\s+scripting|path\s+traversal|privilege\s+escalation|'
        r'use.after.free|heap\s+overflow|stack\s+overflow|authentication\s+bypass|'
        r'command\s+injection|memory\s+corruption|arbitrary\s+code\s+execution|'
        r'denial.of.service|directory\s+traversal|integer\s+overflow|'
        r'race\s+condition|type\s+confusion|null\s+pointer|deserialization)\b',
        task, re.IGNORECASE,
    )
    if sec_match:
        vuln_type = sec_match.group(1).lower()
        # Try to find an affected component ("in <component>")
        comp_match = re.search(
            r'\bin\s+([\w][\w\s\-]{2,40}?)(?=\s+(?:that|which|where|when|allows|could|can|may|is|are)\b|[,\.\)]|$)',
            task[sec_match.end():sec_match.end() + 120], re.IGNORECASE,
        )
        if comp_match:
            return f"{vuln_type} in {comp_match.group(1).strip().lower()}"
        return vuln_type

    # Financial: asset class
    fin_match = re.search(
        r'\b(ETF|mutual\s+fund|bond|equity|stock|option|futures?|commodit(?:y|ies)|'
        r'portfolio|fixed.income|credit\s+default\s+swap|emerging\s+market)\b',
        task, re.IGNORECASE,
    )
    if fin_match:
        return fin_match.group(1).lower()

    return "the topic under analysis"


# ---------------------------------------------------------------------------
# Explicit-option extraction — controller-level brief option preservation
# ---------------------------------------------------------------------------

_OPTION_EXTRACTION_SYSTEM = (
    "You are a structured-output extraction tool. Your job is to determine whether "
    "a decision brief presents a finite set of top-level alternatives that should each "
    "be evaluated independently, and whether the brief requires selecting exactly one "
    "option or allows a portfolio of multiple approved options. You must respond ONLY "
    "with valid JSON, no preamble, no markdown backticks, no explanation."
)

_OPTION_EXTRACTION_PROMPT_TEMPLATE = (
    "Analyze this decision brief:\n\n"
    "---\n{task}\n---\n\n"
    "Question 1: Does this brief present a finite set of top-level alternatives "
    "(options, choices, approaches) that a decision-maker is being asked to choose between?\n\n"
    "Question 2: Does the brief require selecting EXACTLY ONE option (mutually exclusive choice), "
    "or does it allow multiple options to be approved together (portfolio)?\n\n"
    "Signals for exclusive choice mode:\n"
    "- 'select exactly one', 'pick one', 'choose one', 'which one'\n"
    "- 'only one can be executed/done/implemented'\n"
    "- mutually exclusive alternatives where doing one prevents doing others\n\n"
    "Signals for portfolio mode:\n"
    "- 'choose between' without exclusivity constraint\n"
    "- options that could be combined or layered\n"
    "- no explicit single-selection requirement\n\n"
    "Rules:\n"
    "- Only count TOP-LEVEL alternatives (not sub-steps, implementation details, or sequential phases)\n"
    "- The alternatives must be SIBLING CHOICES, not a sequence of steps to execute in order\n"
    "- If the brief describes a situation without presenting explicit alternatives, return no options\n"
    "- Extract the verbatim text of each alternative as it appears in the brief\n"
    "- Provide a short label (under 60 chars) for each option\n\n"
    'Respond with ONLY this JSON structure:\n'
    '{{"explicit_option_mode": true, "confidence": "HIGH", "choice_mode": "exclusive" or "portfolio", '
    '"options": [{{"id": "O1", "label": "short label", "text": "verbatim option text from brief"}}]}}\n\n'
    "If the brief does NOT present explicit alternatives, respond:\n"
    '{{"explicit_option_mode": false, "confidence": "HIGH", "choice_mode": "portfolio", "options": []}}'
)


async def _extract_explicit_options_llm(
    task: str,
    client: "ChatCompletionClient",
    log_path: Path | None = None,
) -> tuple[list[dict], str]:
    """Extract explicit options from a brief using a single LLM call.

    Every brief gets this call at run start. The LLM determines whether the brief
    presents a finite set of top-level alternatives, and whether the brief requires
    an exclusive single choice or allows a portfolio of multiple approved options.

    Returns (options_list, choice_mode) where choice_mode is "exclusive" or "portfolio".
    Uses the same model as the Strategist to keep cost and latency minimal.
    """
    from autogen_core.models import SystemMessage, UserMessage

    prompt = _OPTION_EXTRACTION_PROMPT_TEMPLATE.format(task=task)
    try:
        result = await asyncio.wait_for(
            client.create(
                messages=[
                    SystemMessage(content=_OPTION_EXTRACTION_SYSTEM),
                    UserMessage(content=prompt, source="controller"),
                ]
            ),
            timeout=120,
        )
        raw = str(result.content).strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
        parsed = json.loads(raw)
    except Exception as exc:
        if log_path:
            _log_text(log_path, f"[EXPLICIT-OPTIONS] LLM extraction failed: {exc} — Strategist runs freely")
        return [], "portfolio"

    # Validate structure
    if not isinstance(parsed, dict):
        if log_path:
            _log_text(log_path, "[EXPLICIT-OPTIONS] LLM returned non-dict — Strategist runs freely")
        return [], "portfolio"

    mode = parsed.get("explicit_option_mode", False)
    confidence = parsed.get("confidence", "LOW")
    options = parsed.get("options", [])
    choice_mode = parsed.get("choice_mode", "portfolio")

    # Normalize choice_mode
    if choice_mode not in ("exclusive", "portfolio"):
        choice_mode = "portfolio"

    if not mode or confidence != "HIGH":
        reason = "no explicit options detected" if not mode else "LOW confidence, skipping"
        if log_path:
            _log_text(
                log_path,
                f"[EXPLICIT-OPTIONS] LLM result: mode={mode}, confidence={confidence} — {reason}",
            )
        return [], "portfolio"

    # Validate options
    if not isinstance(options, list) or len(options) < 2 or len(options) > 6:
        n = len(options) if isinstance(options, list) else 0
        if log_path:
            _log_text(
                log_path,
                f"[EXPLICIT-OPTIONS] LLM returned {n} options (need 2-6) — Strategist runs freely",
            )
        return [], "portfolio"

    # Normalize and validate each option
    clean_options: list[dict] = []
    for i, opt in enumerate(options):
        if not isinstance(opt, dict):
            continue
        text = str(opt.get("text", "")).strip()
        label = str(opt.get("label", "")).strip()
        if len(text) < 10:
            continue
        clean_options.append({
            "id": f"O{i+1}",
            "label": label[:60] if label else text[:60],
            "text": text,
        })

    if len(clean_options) < 2:
        if log_path:
            _log_text(log_path, "[EXPLICIT-OPTIONS] After validation, fewer than 2 clean options — Strategist runs freely")
        return [], "portfolio"

    # Deduplicate by label similarity
    seen_labels: set[str] = set()
    deduped: list[dict] = []
    for opt in clean_options:
        norm = opt["label"].lower()[:30]
        if norm not in seen_labels:
            seen_labels.add(norm)
            deduped.append(opt)
    clean_options = deduped

    if log_path:
        opt_summary = ", ".join(f"{o['id']}={o['label'][:40]}" for o in clean_options)
        _log_text(
            log_path,
            f"[EXPLICIT-OPTIONS] LLM extracted {len(clean_options)} brief options "
            f"(HIGH confidence, choice_mode={choice_mode}): {opt_summary}",
        )

    return clean_options, choice_mode


def _extract_explicit_options(task: str, log_path: Path | None = None) -> tuple[list[dict], str]:
    """Synchronous fallback for test environments where no LLM client is available.
    Production path uses _extract_explicit_options_llm instead."""
    if log_path:
        _log_text(log_path, "[EXPLICIT-OPTIONS] Sync fallback (test mode) — no LLM available")
    return [], "portfolio"


def _validate_option_coverage(
    proposal: ProposalPack,
    option_registry: list[dict],
    log_path: Path,
) -> list[str]:
    """Validate that the Strategist's proposal covers all brief-native options.

    Returns a list of missing option IDs. Empty = full coverage.
    """
    if not option_registry:
        return []

    # Build a text-matching check: each option's label/text should appear
    # (at least partially) in at least one recommendation's name, role, or thesis
    missing: list[str] = []
    for opt in option_registry:
        opt_keywords = set(re.findall(r'[a-z]{4,}', opt["text"].lower()))
        if len(opt_keywords) < 2:
            continue  # Option text too short to match meaningfully

        found = False
        for rec in proposal.recommendations:
            rec_text = f"{rec.name} {rec.role_in_portfolio} {rec.thesis}".lower()
            matching = sum(1 for kw in opt_keywords if kw in rec_text)
            # Require at least 30% keyword overlap or 3 matching keywords
            if matching >= max(3, len(opt_keywords) * 0.3):
                found = True
                break

        if not found:
            missing.append(opt["id"])
            _log_text(
                log_path,
                f"[OPTION-COVERAGE] Missing: {opt['id']} ({opt['label'][:50]}) — "
                f"no recommendation covers this brief option",
            )

    if not missing:
        _log_text(log_path, f"[OPTION-COVERAGE] All {len(option_registry)} brief options covered by Strategist proposal")

    return missing


def _sanitize_brave_query(query: str, ledger: "RunLedger", log_path: Path | None = None) -> str | None:
    """Sanitize a proposed BRAVE/SONAR query before submission.

    Returns the (possibly modified) query string, or None to skip the query entirely.
    Guards:
      1. Self-reference detector: substitutes topic-class for unresolvable self-references.
      2. Org-internal/private-document detector: skips queries for private artifacts.
      3. Conversational-fragment rewriter: strips conversational prefixes.
      4. Short-query guard: skips queries with < 4 words after cleanup.
      5. Internal-number detector: skips queries chasing numbers derived inside the chamber.
      6. Truncation guard: truncates queries > 120 chars at a word boundary.
    """
    original_query = query

    # Guard 1: self-reference detector — substitute with topic_class, not empty string
    if _SELF_REF_PATTERNS.search(query):
        # Resolve topic_class once and cache on the ledger
        if not ledger.topic_class:
            ledger.topic_class = _extract_topic_class(ledger.task)
        substituted = _SELF_REF_PATTERNS.sub(ledger.topic_class, query).strip()
        # Collapse double-spaces left by substitution
        substituted = re.sub(r'\s{2,}', ' ', substituted)
        substituted = re.sub(r'^[\s,\-–—:]+|[\s,\-–—:]+$', '', substituted)
        if log_path is not None and substituted != query:
            _log_text(log_path, f"[BRAVE-REWRITE-SELFREF] {query} → {substituted}")
        query = substituted

    # Guard 2: org-internal / private-document detector
    if _ORG_INTERNAL_PATTERN.search(query):
        if log_path is not None:
            _log_text(log_path, f"[BRAVE-SKIP-PRIVATE] Skipping org-internal query: {query}")
        return None

    # Guard 3: conversational-fragment rewriter
    conv_match = _CONV_PREFIX_PATTERN.match(query)
    if conv_match:
        cleaned = query[conv_match.end():].strip()
        if log_path is not None:
            _log_text(log_path, f"[BRAVE-REWRITE-CONVERSATIONAL] {query} → {cleaned}")
        query = cleaned

    # Guard 4: short-query guard (< 4 words is too vague to be useful)
    if len(query.split()) < 4:
        if log_path is not None:
            _log_text(log_path, f"[BRAVE-SKIP-SHORT] Query too short after cleanup: {repr(query)}")
        return None

    # Guard 5: internal-number detector
    dollar_matches = _DOLLAR_AMOUNT_PATTERN.findall(query)
    if dollar_matches:
        existing_facts = " ".join(ev.fact for ev in ledger.evidence_ledger)
        for dollar_val in dollar_matches:
            if dollar_val in existing_facts:
                if log_path is not None:
                    _log_text(log_path, f"[BRAVE-SKIP-INTERNAL] Skipping query chasing internal number: {query}")
                return None  # Chasing a chamber-internal figure

    # Guard 6: truncation guard
    if len(query) > 120:
        truncated = query[:120]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        if log_path is not None:
            _log_text(log_path, f"[BRAVE-TRUNCATED] {query} → {truncated}")
        query = truncated

    return query if query.strip() else None


def _generate_brave_queries(
    open_objections: list[Objection], ledger: RunLedger, log_path: Path | None = None
) -> list[str]:
    """Generate focused search queries from open objections using requested_evidence. Deduplicate.

    Query is built from the evidence gap or objection text ONLY — recommendation names are
    intentionally excluded to prevent domain-pollution (e.g. ETF ticker names or action labels
    prepended to evidence queries, pulling irrelevant results from unrelated domains).
    """
    max_queries = 1 if ledger.search_mode == "minimal" else MAX_BRAVE_QUERIES_PER_CYCLE
    queries = []
    for obj in open_objections[:max_queries * 2]:
        if len(queries) >= max_queries:
            break
        if obj.requested_evidence:
            query_base = obj.requested_evidence[0][:120]
        else:
            query_base = obj.objection_text[:120]
        # Use only the evidence/objection text as the query — do NOT prepend recommendation names.
        # rec.name often contains action labels ("EXECUTE: Deploy validated patch...") that
        # contaminate searches and pull results from unrelated domains.
        query = query_base.strip()
        query = " ".join(query.split()[:14])

        # Apply sanitization guards before dedup check
        query = _sanitize_brave_query(query, ledger, log_path)
        if query is None:
            continue

        query_norm = query.lower().strip()
        if query_norm in ledger.seen_brave_queries:
            continue
        ledger.seen_brave_queries.add(query_norm)
        if query:
            queries.append(query)
    return queries


_RELEVANCE_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "was", "be", "by", "at", "from", "that", "this", "it",
    "as", "if", "but", "not", "which", "their", "they", "have", "has",
    "been", "will", "can", "may", "should", "could", "would", "its",
    "our", "we", "us", "do", "any", "all", "more", "than", "when", "how",
})


def _relevance_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text for overlap-based relevance check."""
    import re as _re
    words = _re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {w for w in words if len(w) >= 4 and w not in _RELEVANCE_STOPWORDS}


def _is_relevant_result(result: dict, query: str, objection_text: str, min_overlap: int = 1) -> bool:
    """Return True if the search result has at least min_overlap keyword matches with the query/objection.

    Rejects results that share no meaningful terms with what was asked — a lightweight
    guard against retrieval poisoning from unrelated domains.
    """
    query_kw = _relevance_keywords(query) | _relevance_keywords(objection_text)
    result_text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    result_kw = _relevance_keywords(result_text)
    overlap = len(query_kw & result_kw)
    return overlap >= min_overlap


# Off-domain signals: terms that indicate evidence is from a clearly unrelated domain.
# Only applied when topic-keyword score is 0 (no overlap with task at all).
_OFF_DOMAIN_SIGNALS = frozenset({
    "fema", "emergency management", "ai adoption", "public sector",
    "government", "federal agency", "municipal", "nonprofit",
    "homeland", "disaster response", "disaster relief",
})

# Domain-family signal sets for cross-domain analog detection.
# When a task belongs to one domain family, evidence containing signals
# from a *different* family is flagged as a cross-domain analog.
_DOMAIN_FAMILY_MEDICAL = frozenset({
    "toxicological", "toxicology", "clinical triage", "clinical deterioration",
    "poisoning", "overdose", "serum levels", "nomogram", "acetaminophen",
    "pharmacokinetic", "pharmacological", "drug absorption", "clinical case series",
    "emergency medicine", "patient", "diagnosis", "pathology", "symptom",
    "epidemiological", "morbidity", "mortality rate", "surgical",
    "therapeutic", "dosage", "bioavailability", "ingestion",
})

_DOMAIN_FAMILY_SECURITY = frozenset({
    "exploit", "vulnerability", "cve", "rce", "payload", "malware",
    "ransomware", "botnet", "lateral movement", "privilege escalation",
    "authentication bypass", "waf", "firewall", "intrusion", "breach",
    "patch", "zero-day", "proof-of-concept", "attack surface",
})

_DOMAIN_FAMILY_FINANCE = frozenset({
    "portfolio", "etf", "equity", "bond", "dividend", "yield",
    "expense ratio", "aum", "ticker", "mutual fund", "hedge fund",
    "options", "futures", "derivatives", "credit default",
})

_DOMAIN_FAMILY_INFRASTRUCTURE = frozenset({
    "kubernetes", "k8s", "redis", "postgres", "postgresql", "mysql",
    "mongodb", "database", "cluster", "pod", "container", "docker",
    "oomkill", "oom", "memory leak", "cpu spike", "latency", "throughput",
    "jit", "query planner", "replication", "failover", "sentinel",
    "load balancer", "nginx", "haproxy", "cdn", "cache", "auto-scaling",
    "microservice", "rps", "qps",
})

_DOMAIN_FAMILY_COMPLIANCE = frozenset({
    "hipaa", "gdpr", "pci", "sox", "ferpa", "ccpa", "phi", "pii",
    "breach notification", "regulatory", "compliance", "audit",
    "data protection", "privacy", "disclosure", "patient record",
    "ehr", "protected health", "covered entity", "hhs", "ocr",
})

_DOMAIN_FAMILY_ENGINEERING = frozenset({
    "test suite", "test coverage", "technical debt", "code quality",
    "feature freeze", "sprint", "velocity", "ci/cd", "pipeline",
    "deployment", "release", "staging", "canary", "rollback",
    "schema drift", "mock", "fixture", "regression test",
    "qa team", "backfill", "refactor",
})

_DOMAIN_FAMILY_AI_POLICY = frozenset({
    "bias", "false positive rate", "content moderation", "fairness",
    "demographic", "disparity", "threshold adjustment", "model retrain",
    "training data", "balanced data", "appeal", "transparency",
    "ai act", "algorithmic", "discrimination", "differential treatment",
})

_DOMAIN_FAMILY_OPERATIONS = frozenset({
    "traffic spike", "ddos", "bot traffic", "auto-scaling", "scaling",
    "load", "capacity", "rate limiting", "throttl", "cdn",
    "cache hit", "backend response", "under attack mode",
    "cloudflare", "akamai", "origin server",
})


def _detect_task_domain(topic_class: str, task: str) -> str:
    """Detect which decision-class domain a task belongs to.

    Returns one of: 'security', 'infrastructure', 'compliance', 'engineering',
    'ai_policy', 'operations', 'finance', 'medical', or 'unknown'.
    """
    combined = f"{topic_class} {task}".lower()
    scores: dict[str, int] = {
        "security": sum(1 for kw in _DOMAIN_FAMILY_SECURITY if kw in combined),
        "infrastructure": sum(1 for kw in _DOMAIN_FAMILY_INFRASTRUCTURE if kw in combined),
        "compliance": sum(1 for kw in _DOMAIN_FAMILY_COMPLIANCE if kw in combined),
        "engineering": sum(1 for kw in _DOMAIN_FAMILY_ENGINEERING if kw in combined),
        "ai_policy": sum(1 for kw in _DOMAIN_FAMILY_AI_POLICY if kw in combined),
        "operations": sum(1 for kw in _DOMAIN_FAMILY_OPERATIONS if kw in combined),
        "finance": sum(1 for kw in _DOMAIN_FAMILY_FINANCE if kw in combined),
        "medical": sum(1 for kw in _DOMAIN_FAMILY_MEDICAL if kw in combined),
    }
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    return "unknown"


def _detect_evidence_domain(ev_text: str) -> str:
    """Detect which domain family an evidence item primarily belongs to."""
    text = ev_text.lower()
    sec_score = sum(1 for kw in _DOMAIN_FAMILY_SECURITY if kw in text)
    med_score = sum(1 for kw in _DOMAIN_FAMILY_MEDICAL if kw in text)
    fin_score = sum(1 for kw in _DOMAIN_FAMILY_FINANCE if kw in text)
    if med_score >= 2 and med_score > sec_score:
        return "medical"
    if fin_score >= 2 and fin_score > sec_score:
        return "finance"
    if sec_score >= 2:
        return "security"
    return "unknown"

# Short domain terms (< 5 chars) that are still meaningful topic keywords.
# Supplements the ≥5-char word filter in _extract_topic_keywords.
_DOMAIN_SHORTTERMS: frozenset[str] = frozenset(t.lower() for t in _SECURITY_CLASS_TERMS) | frozenset({
    "rce", "xss", "api", "waf", "ids", "ips", "dos", "poc", "c2",
    "acl", "iam", "mfa", "vpn", "tls", "ssl", "ssh", "dns", "cdn",
    "sdk", "jwt", "pki", "pem", "soc", "edr", "xdr", "mdr",
})


def _extract_topic_keywords(task: str) -> set[str]:
    """Extract meaningful topic keywords from the task string.

    Keeps words that are either ≥5 chars or are known short domain terms,
    after stripping stopwords. Result is cached on ledger.topic_keywords.
    """
    words = re.sub(r"[^a-z0-9\s]", " ", task.lower()).split()
    keywords: set[str] = set()
    for w in words:
        if w in _RELEVANCE_STOPWORDS:
            continue
        if len(w) >= 5 or w in _DOMAIN_SHORTTERMS:
            keywords.add(w)
    return keywords


def _is_evidence_relevant(
    ev: "Evidence",
    task: str,
    ledger: "RunLedger",
    cycle: int = 0,
    source: str = "unknown",
    log_path: "Path | None" = None,
) -> bool:
    """Evidence-admission topic-relevance gate (P1).

    Returns True if the evidence item is relevant to the task and should be
    admitted to the ledger.  Must be called BEFORE the canonical E### ID is
    assigned so that rejected items never enter the ledger.

    Scoring:
    - score ≥ 1  → passes keyword gate, then domain-coherence check
    - score == 0 and off-domain signal present → REJECT (log [EVIDENCE-REJECTED])
    - score == 0, no off-domain signal → ADMIT with warning (log [EVIDENCE-LOW-RELEVANCE])

    Domain-coherence check (P2):
    - Even if keyword score ≥ 1, reject evidence whose primary domain family
      is clearly different from the task's domain family (cross-domain analog).
    """
    if not ledger.topic_keywords:
        ledger.topic_keywords = _extract_topic_keywords(task)

    # If we can't determine relevance (empty task keywords), admit unconditionally
    if not ledger.topic_keywords:
        return True

    search_text = f"{ev.topic} {ev.fact}".lower()
    score = sum(1 for kw in ledger.topic_keywords if kw in search_text)

    if score >= 1:
        # P2: Domain-coherence check — catch cross-domain analogs that share
        # surface keywords (e.g., "acute", "risk", "hours") but belong to a
        # fundamentally different domain.
        if not ledger.topic_class:
            ledger.topic_class = _extract_topic_class(task)
        task_domain = _detect_task_domain(ledger.topic_class, task)
        if task_domain != "unknown":
            ev_domain = _detect_evidence_domain(search_text)
            if ev_domain != "unknown" and ev_domain != task_domain:
                if log_path is not None:
                    _log_text(
                        log_path,
                        f'[EVIDENCE-REJECTED] cycle={cycle} source={source} topic="{ev.topic[:80]}" '
                        f'reason=cross-domain-analog (task={task_domain}, evidence={ev_domain}) score={score}',
                    )
                return False
        return True

    # score == 0: check for clearly off-domain signals
    combined = f"{ev.topic} {ev.fact}".lower()
    if any(sig in combined for sig in _OFF_DOMAIN_SIGNALS):
        if log_path is not None:
            _log_text(
                log_path,
                f'[EVIDENCE-REJECTED] cycle={cycle} source={source} topic="{ev.topic[:80]}" reason=off-topic score=0',
            )
        return False

    # Ambiguous (score=0 but no clear off-domain signal): admit with warning
    if log_path is not None:
        _log_text(
            log_path,
            f'[EVIDENCE-LOW-RELEVANCE] cycle={cycle} source={source} topic="{ev.topic[:80]}" score=0 (ambiguous, admitted)',
        )
    return True


def _brave_retrieve_evidence(open_objections: list[Objection], ledger: RunLedger, log_path: Path) -> list[Evidence]:
    """Controller-managed Brave retrieval. One step per cycle."""
    if ledger.search_mode == "training_only":
        has_open = bool(open_objections)
        skip_reason = "policy_ceiling" if has_open else "no_retrieval_needed_and_mode_locked"
        open_ids = [o.objection_id for o in open_objections[:5]]
        evidence_gaps = [gap for o in open_objections for gap in o.requested_evidence[:2]][:6]
        ledger.search_diag_training_only_skips += 1
        _log_text(
            log_path,
            f"[SEARCH-MODE-LOCK] engine=brave current_mode=training_only "
            f"retrieval_skipped=brave_retrieve skip_reason={skip_reason} "
            f"open_objections_count={len(open_objections)} open_objection_ids={open_ids} "
            f"evidence_gaps_sample={evidence_gaps} "
            f"policy_blocked={'yes' if has_open else 'no_need'}",
        )
        return []

    if not BRAVE_SEARCH_ENABLED:
        _log_text(log_path, "[BRAVE-SEARCH-UNAVAILABLE] BRAVE_API_KEY not set — cannot retrieve live evidence")
        raise RuntimeError(
            "Brave Search unavailable: BRAVE_API_KEY not set. "
            "Cannot produce evidence-backed results without search. Aborting."
        )

    queries = _generate_brave_queries(open_objections, ledger, log_path)
    if not queries:
        _log_text(log_path, "[BRAVE] Skipped — no open objections to research")
        return []

    ledger.search_diag_live_retrieval_attempted = True
    all_evidence = []
    seen_urls = set()
    _brave_failures = 0
    _brave_attempts = 0

    for i, query in enumerate(queries):
        _log_text(log_path, f"[BRAVE] Query {i + 1}/{len(queries)}: {query}")
        _brave_attempts += 1
        results = _brave_search(query, log_path=log_path)
        if results is None:
            _brave_failures += 1
            _log_text(log_path, f"[BRAVE-ERROR] Query {i + 1} failed ({_brave_failures}/{_brave_attempts} failed)")
            continue
        _log_text(log_path, f"[BRAVE] Got {len(results)} results")

        obj = open_objections[i] if i < len(open_objections) else open_objections[0]
        for result in results:
            if result["url"] in seen_urls:
                continue
            seen_urls.add(result["url"])
            content_key = f"{result['title'][:80].strip().lower()}||{result['snippet'][:120].strip().lower()}"
            if content_key in ledger.evidence_content_hashes:
                continue

            # Relevance gate: reject results with no keyword overlap with the query/objection
            if not _is_relevant_result(result, query, obj.objection_text):
                _log_text(
                    log_path,
                    f"[BRAVE-REJECTED] Irrelevant result dropped: '{result.get('title', '')[:80]}' "
                    f"(no keyword overlap with query)",
                )
                continue

            # Topic-relevance gate (P1): reject off-domain evidence before ID assignment
            _temp_ev = Evidence(
                evidence_id="TEMP",
                topic=result["title"][:100],
                source_type="web_search",
                fact=result["snippet"][:200],
                confidence="MEDIUM",
                supports_claim_ids=[],
            )
            if not _is_evidence_relevant(_temp_ev, ledger.task, ledger, ledger.cycle_index + 1, "brave", log_path):
                continue

            ledger.evidence_counter += 1
            eid = f"E{ledger.evidence_counter:03d}"

            obj = open_objections[i] if i < len(open_objections) else open_objections[0]
            supports = [obj.claim_id] if obj.claim_id else []

            ev = Evidence(
                evidence_id=eid,
                topic=result["title"][:100],
                source_type="web_search",
                fact=f"{result['snippet'][:200]} (Source: {result['url']})",
                value="",
                units="",
                confidence="MEDIUM",
                supports_claim_ids=supports,
            )
            ledger.evidence_content_hashes[content_key] = eid
            ledger.evidence_seen_ids.add(eid)
            all_evidence.append(ev)
            _log_text(log_path, f"[EVIDENCE-ADMITTED] cycle={ledger.cycle_index + 1} source=brave id={eid}")

    # V5: Fail loudly if ALL Brave queries failed
    if _brave_attempts > 0 and _brave_failures == _brave_attempts:
        _log_text(log_path, f"[BRAVE-SEARCH-UNAVAILABLE] ALL {_brave_attempts} queries failed — search is broken, aborting")
        raise RuntimeError(
            f"Brave Search unavailable: all {_brave_attempts} queries failed. "
            "Cannot produce evidence-backed results without search. Aborting."
        )

    _log_text(log_path, f"[BRAVE] Total evidence items from retrieval: {len(all_evidence)}")
    return all_evidence


async def _sonar_deep_evidence(
    unresolved_blocking: list[Objection],
    ledger: RunLedger,
    log_path: Path,
    sonar_client,
) -> list[Evidence]:
    """Targeted Sonar Pro deep-dive on blocking objections that Brave couldn't resolve."""
    if ledger.search_mode in ("training_only", "minimal"):
        has_blocking = bool(unresolved_blocking)
        skip_reason = "policy_ceiling" if has_blocking else "no_retrieval_needed_and_mode_locked"
        blocking_ids = [o.objection_id for o in unresolved_blocking[:5]]
        if ledger.search_mode == "training_only" and has_blocking:
            ledger.search_diag_training_only_skips += 1
        _log_text(
            log_path,
            f"[SEARCH-MODE-LOCK] engine=sonar current_mode={ledger.search_mode} "
            f"retrieval_skipped=sonar_deep_evidence skip_reason={skip_reason} "
            f"unresolved_blocking_count={len(unresolved_blocking)} blocking_ids={blocking_ids} "
            f"policy_blocked={'yes' if has_blocking else 'no_need'}",
        )
        return []

    if not SONAR_DEEP_ENABLED or sonar_client is None:
        _log_text(log_path, "[SONAR-DEEP-UNAVAILABLE] Sonar Pro not enabled or client missing — skipping deep evidence")
        return []
    if not unresolved_blocking:
        _log_text(log_path, "[SONAR-DEEP] Skipped — no unresolved blocking objections")
        return []

    from autogen_core.models import UserMessage

    queries = []
    for obj in unresolved_blocking[:MAX_SONAR_DEEP_QUERIES]:
        if obj.requested_evidence:
            query_base = obj.requested_evidence[0][:150]
        else:
            query_base = obj.objection_text[:150]
        # Do NOT prepend recommendation names — same pollution fix as BRAVE query construction.
        query = query_base.strip()

        # Apply sanitizer BEFORE dedup check — same guards as BRAVE
        pre_sanitize = query
        query = _sanitize_brave_query(query, ledger, log_path)
        if query is None:
            continue
        if query != pre_sanitize:
            _log_text(log_path, f"[SONAR-SANITIZED] {pre_sanitize[:100]} → {query[:100]}")

        # Dedup against already-seen BRAVE queries (first 8 words match)
        query_words = query.lower().split()
        query_prefix = " ".join(query_words[:8])
        is_duplicate = any(
            " ".join(seen.split()[:8]) == query_prefix
            for seen in ledger.seen_brave_queries
        )
        if is_duplicate:
            _log_text(log_path, f"[SONAR-DEEP-DEDUP] Skipping duplicate of BRAVE query: {query[:100]}")
            continue

        queries.append((query, obj))

    all_evidence = []
    for i, (query, obj) in enumerate(queries):
        _log_text(log_path, f"[SONAR-DEEP] Query {i + 1}/{len(queries)}: {query[:100]}")
        prompt = (
            f"Search the web and provide factual, citation-backed answers for this query:\n\n{query}\n\n"
            "For each finding, provide:\n"
            "1. A clear factual statement with specific numbers/dates\n"
            "2. The source URL\n"
            "3. The title of the source\n\n"
            "Return 3-5 distinct findings. Be specific with numbers, dates, and sources."
        )
        try:
            messages = [UserMessage(content=prompt, source="user")]
            result = await asyncio.wait_for(sonar_client.create(messages), timeout=120)
            raw_text = str(result.content).strip()
            chunks = re.split(r"\n\s*\d+[\.\)]\s*", raw_text)
            count = 0
            for chunk in chunks:
                chunk = chunk.strip()
                if len(chunk) < 20:
                    continue
                url_match = re.search(r"https?://[^\s\)\]]+", chunk)
                url = url_match.group(0) if url_match else ""
                lines = chunk.split("\n")
                title = lines[0][:100].strip("*#- ")
                snippet = chunk[:300]

                content_key = f"{title[:80].strip().lower()}||{snippet[:120].strip().lower()}"
                if content_key in ledger.evidence_content_hashes:
                    continue

                # Topic-relevance gate (P1): reject off-domain evidence before ID assignment
                _temp_sonar_ev = Evidence(
                    evidence_id="TEMP",
                    topic=title,
                    source_type="web_search",
                    fact=snippet[:200],
                    confidence="MEDIUM",
                    supports_claim_ids=[],
                )
                if not _is_evidence_relevant(_temp_sonar_ev, ledger.task, ledger, ledger.cycle_index + 1, "sonar", log_path):
                    continue

                ledger.evidence_counter += 1
                eid = f"E{ledger.evidence_counter:03d}"
                supports = [obj.claim_id] if obj.claim_id else []
                source_suffix = f" (Source: {url})" if url else ""
                ev = Evidence(
                    evidence_id=eid,
                    topic=title,
                    source_type="web_search",
                    fact=f"{snippet[:200]}{source_suffix}",
                    value="",
                    units="",
                    confidence="MEDIUM",
                    supports_claim_ids=supports,
                )
                ledger.evidence_content_hashes[content_key] = eid
                ledger.evidence_seen_ids.add(eid)
                all_evidence.append(ev)
                _log_text(log_path, f"[EVIDENCE-ADMITTED] cycle={ledger.cycle_index + 1} source=sonar id={eid}")
                count += 1
            _log_text(log_path, f"[SONAR-DEEP] Got {count} results")
        except Exception as exc:
            _log_text(log_path, f"[SONAR-DEEP] Error: {exc}")

    _log_text(log_path, f"[SONAR-DEEP] Total deep evidence items: {len(all_evidence)}")
    return all_evidence


def _maybe_emit_live_evidence_candidate(
    ledger: "RunLedger",
    log_path: Path,
    cycle: int,
    open_objections: list["Objection"],
    audit: "AuditSnapshot | None",
) -> None:
    """Emit [LIVE-EVIDENCE-CANDIDATE] when training_only run shows evidence gaps.

    Observability only — does not change any chamber behavior or retrieval policy.
    Conservative trigger: only fires when Auditor explicitly surfaces missing evidence
    OR open objections have listed requested_evidence gaps.
    """
    if ledger.search_mode != "training_only":
        return

    # Gather signals from Auditor state
    missing_from_audit: list[str] = audit.missing_evidence[:5] if audit else []
    unresolved_from_audit: list[str] = audit.unresolved_objections[:5] if audit else []

    # Gather evidence gaps from open objections
    evidence_gap_objections: list[str] = [
        o.objection_id for o in open_objections if o.requested_evidence
    ]
    evidence_gaps_sample: list[str] = [
        gap for o in open_objections for gap in o.requested_evidence[:2]
    ][:6]

    # Only fire if there is a concrete evidence gap signal
    has_signal = bool(missing_from_audit or evidence_gap_objections)
    if not has_signal:
        return

    ledger.search_diag_live_evidence_candidates += 1
    _log_text(
        log_path,
        f"[LIVE-EVIDENCE-CANDIDATE] cycle={cycle + 1} current_mode=training_only "
        f"live_evidence_benefit_candidate=true "
        f"missing_evidence_from_auditor={missing_from_audit} "
        f"unresolved_objection_ids_from_auditor={unresolved_from_audit} "
        f"objections_with_evidence_gaps={evidence_gap_objections} "
        f"evidence_gaps_sample={evidence_gaps_sample} "
        f"retrieval_skipped_count_so_far={ledger.search_diag_training_only_skips}",
    )


def _maybe_escalate_search_mode(
    ledger: "RunLedger",
    log_path: "Path | None",
    cycle: int,
    open_objections: list["Objection"],
) -> None:
    """Mid-run escalation: training_only → minimal (one-time, one-way, conservative).

    Trigger conditions (ALL must be true):
    - Current search_mode is training_only
    - Not already escalated (search_mode_escalated is False)
    - cycle >= 1 (at least one full cycle has completed)
    - >= 2 open objections with evidence gaps (requested_evidence non-empty OR type == evidence_gap)
    - retrieval_skips >= 2 (search_diag_training_only_skips)

    Escalates to "minimal" only — never "full". Fires at most once per run.
    Logs [SEARCH-ESCALATION] marker.
    """
    if ledger.search_mode != "training_only":
        return
    if ledger.search_mode_escalated:
        return
    if cycle < 1:
        return
    if ledger.search_diag_training_only_skips < 2:
        return

    # Count objections with concrete evidence gaps
    evidence_gap_objections = [
        o for o in open_objections
        if o.requested_evidence or o.type == "evidence_gap"
    ]
    if len(evidence_gap_objections) < 2:
        return

    # All conditions met — escalate to minimal
    ledger.search_mode = "minimal"
    ledger.search_mode_escalated = True
    gap_ids = [o.objection_id for o in evidence_gap_objections[:5]]
    if log_path is not None:
        _log_text(
            log_path,
            f"[SEARCH-ESCALATION] training_only→minimal cycle={cycle + 1} "
            f"evidence_gap_objection_count={len(evidence_gap_objections)} "
            f"retrieval_skips={ledger.search_diag_training_only_skips} "
            f"gap_objection_ids={gap_ids} "
            f"note=one-time-escalation-never-to-full",
        )


def _emit_search_diagnostics(ledger: "RunLedger", log_path: Path) -> None:
    """Emit [SEARCH-DIAGNOSTICS] end-of-run summary for search-gate observability.

    Observability only — no behavior change. Designed to be grep-friendly for
    auditing which runs are candidates for future mid-run mode escalation.
    """
    upfront_mode = ledger.search_diag_upfront_mode or ledger.search_mode  # fallback for ledgers pre-dating this field
    final_mode = ledger.search_mode
    confidence = ledger.search_diag_router_confidence or "UNKNOWN"
    training_only_skips = ledger.search_diag_training_only_skips
    live_candidates = ledger.search_diag_live_evidence_candidates
    live_attempted = ledger.search_diag_live_retrieval_attempted

    # Ceiling and escalation status derived from upfront mode and actual escalation flag
    escalation_actually_triggered = getattr(ledger, "search_mode_escalated", False)
    escalation_candidate = (
        not escalation_actually_triggered
        and upfront_mode == "training_only"
        and training_only_skips > 0
        and live_candidates > 0
    )

    if escalation_actually_triggered:
        note = f"Escalation triggered: {upfront_mode}→{final_mode}"
    elif escalation_candidate:
        note = "Run is a credible candidate for future mid-run mode escalation review"
    else:
        note = "No escalation signal"

    _log_text(
        log_path,
        f"[SEARCH-DIAGNOSTICS] run_id={ledger.run_id} "
        f"upfront_selected_mode={upfront_mode} "
        f"final_mode={final_mode} "
        f"routing_confidence={confidence} "
        f"hard_live_retrieval_ceiling={upfront_mode == 'training_only'} "
        f"live_retrieval_ever_attempted={live_attempted} "
        f"training_only_retrieval_skips={training_only_skips} "
        f"live_evidence_candidate_events={live_candidates} "
        f"escalation_triggered={escalation_actually_triggered} "
        f"escalation_candidate={escalation_candidate} "
        f"note={note}",
    )


def _apply_evidence_ceiling(audit: AuditSnapshot, ledger: RunLedger, log_path: Path) -> AuditSnapshot:
    """If ALL evidence is training_knowledge, cap overall quality at MEDIUM.

    Skipped when search_mode is not 'full' — training-only and minimal runs are expected
    to have no web evidence and should not be penalized for it.
    """
    if ledger.search_mode != "full":
        _log_text(log_path, f"[EVIDENCE-CAP] Skipped — search_mode={ledger.search_mode}, no web-evidence penalty")
        return audit

    has_web_evidence = any(ev.source_type == "web_search" for ev in ledger.evidence_ledger)
    if has_web_evidence:
        return audit

    all_training = all(e.source_type == "training_knowledge" for e in ledger.evidence_ledger)
    if all_training and audit.overall_evidence_quality == "HIGH":
        _log_text(log_path, "[EVIDENCE-CAP] All evidence is training_knowledge -> capping quality at MEDIUM")
        audit.overall_evidence_quality = "MEDIUM"
    return audit


def _update_objection_states(
    latest_critic_pack: ObjectionPack,
    audit: AuditSnapshot,
    ledger: RunLedger,
    log_path: Path,
    dropped_claims: list[str] | None = None,
    cycle: int = 0,
) -> None:
    """Update objection states from EXPLICIT auditor findings, not from omission."""
    dropped_claims = dropped_claims or []
    is_degraded = cycle in ledger.degraded_cycles

    for obj in latest_critic_pack.objections:
        if obj.objection_id not in ledger.objection_ledger:
            ledger.objection_ledger[obj.objection_id] = "OPEN"
        obj.last_seen_cycle = cycle

    findings_map: dict[str, ObjectionFinding] = {}
    for finding in audit.objection_findings:
        findings_map[finding.objection_id] = finding

    # Liveness check: objections not restated by current Critic move to NOT_RESTATED
    current_critic_ids = {obj.objection_id for obj in latest_critic_pack.objections}
    for obj_id, current_status in list(ledger.objection_ledger.items()):
        if current_status in ("OPEN", "UPHELD") and obj_id not in current_critic_ids:
            if obj_id in findings_map:
                continue
            ledger.objection_ledger[obj_id] = "NOT_RESTATED"
            _log_text(log_path, f"[LIVENESS] {obj_id} -> NOT_RESTATED (not in current Critic output, no Auditor reaffirmation)")

    for obj_id, current_status in list(ledger.objection_ledger.items()):
        if current_status in ("RESOLVED", "WITHDRAWN", "DEFERRED", "DOWNGRADED_TO_RISK", "NOT_RESTATED"):
            continue

        obj_detail = None
        for obj in latest_critic_pack.objections:
            if obj.objection_id == obj_id:
                obj_detail = obj
                break
        if obj_detail is None:
            for oh in ledger.objection_history:
                for obj in oh.objections:
                    if obj.objection_id == obj_id:
                        obj_detail = obj
                        break
                if obj_detail:
                    break

        if obj_detail and obj_detail.claim_id in dropped_claims:
            ledger.objection_ledger[obj_id] = "WITHDRAWN"
            if obj_detail:
                obj_detail.disposition = "WITHDRAWN"
            _log_text(log_path, f"[OBJECTION] {obj_id} -> WITHDRAWN (claim dropped)")
            continue

        finding = findings_map.get(obj_id)
        if finding:
            new_disposition = finding.disposition
            # Cap: Auditor cannot RESOLVE an objection the Strategist never addressed
            if new_disposition == "RESOLVED" and obj_id not in ledger.strategist_addressed_ids:
                new_disposition = "DOWNGRADED_TO_RISK"
                _log_text(log_path, f"[RESOLVE-CAP] {obj_id} capped at DOWNGRADED_TO_RISK (Strategist never addressed this objection)")

            # Same-cycle downgrade guard: only EFFECTIVELY BLOCKING objections are held
            if new_disposition == "DOWNGRADED_TO_RISK" and current_status == "OPEN":
                is_effectively_blocking = False
                if obj_detail:
                    # BLOCKING-class objections are effectively blocking
                    if getattr(obj_detail, "blocking_class", None) == "BLOCKING":
                        is_effectively_blocking = True
                    # HIGH severity + ITEM scope = effectively blocking
                    if getattr(obj_detail, "severity", None) == "HIGH" and getattr(obj_detail, "scope", "ITEM") == "ITEM":
                        is_effectively_blocking = True
                    # Attached to WEAK/UNSUPPORTED claim = effectively blocking
                    if obj_detail.claim_id and audit.claim_scores:
                        for cs in audit.claim_scores:
                            if cs.claim_id == obj_detail.claim_id and cs.support_level in ("WEAK", "UNSUPPORTED"):
                                is_effectively_blocking = True
                                break
                    # RISK_ONLY and PORTFOLIO_ONLY classification always overrides — these
                    # are never effectively blocking regardless of severity or scope
                    if getattr(obj_detail, "blocking_class", None) in ("RISK_ONLY", "PORTFOLIO_ONLY"):
                        is_effectively_blocking = False
                # Check if first raised this cycle
                first_raised_this_cycle = getattr(obj_detail, 'raised_in_cycle', None) == cycle if obj_detail else False
                if not first_raised_this_cycle:
                    first_raised_this_cycle = obj_id not in {
                        o.objection_id for oh in ledger.objection_history[:-1] for o in oh.objections
                    } if ledger.objection_history else False

                if is_effectively_blocking and first_raised_this_cycle:
                    new_disposition = "UPHELD"
                    if obj_detail:
                        obj_detail.guard_held = True
                    _log_text(log_path, f"[GUARD] {obj_id} -> UPHELD (effectively blocking, cannot be downgraded in same cycle)")

            # Degraded-cycle guard: cannot resolve/downgrade objections when no new evidence was found
            if is_degraded and new_disposition in ("RESOLVED", "DOWNGRADED_TO_RISK"):
                if current_status in ("OPEN", "UPHELD"):
                    new_disposition = current_status
                    _log_text(log_path, f"[DEGRADED-GUARD] {obj_id} -> kept {current_status} (degraded cycle, no new evidence)")

            if new_disposition in ("RESOLVED", "WITHDRAWN", "DOWNGRADED_TO_RISK", "UPHELD"):
                ledger.objection_ledger[obj_id] = new_disposition
                if obj_detail:
                    obj_detail.disposition = new_disposition
                    obj_detail.controller_status = new_disposition
                if finding.upgrade_to_blocking and obj_detail:
                    obj_detail.blocking_class = "BLOCKING"
                    obj_detail.blocking = True
                    _log_text(log_path, f"[OBJECTION] {obj_id} -> UPGRADED to BLOCKING by Auditor: {finding.rationale[:100]}")
                _log_text(log_path, f"[OBJECTION] {obj_id} -> {new_disposition} (Auditor: {finding.rationale[:100]})")
            else:
                ledger.objection_ledger[obj_id] = "OPEN"
                if obj_detail:
                    obj_detail.disposition = "OPEN"
                    obj_detail.controller_status = "OPEN"
                _log_text(log_path, f"[OBJECTION] {obj_id} -> still OPEN (Auditor finding: {new_disposition})")
        else:
                _log_text(log_path, f"[OBJECTION] {obj_id} -> unchanged (no Auditor finding)")


def _backfill_missing_evidence(
    audit: AuditSnapshot,
    ledger: RunLedger,
    log_path: Path,
) -> AuditSnapshot:
    """Backfill missing_evidence for WEAK/UNSUPPORTED claims when Auditor left it empty.

    Sources: requested_evidence from active objections targeting that claim.
    """
    for cs in audit.claim_scores:
        if cs.support_level in ("WEAK", "UNSUPPORTED") and not cs.missing_evidence:
            # Collect requested_evidence from active objections on this claim
            backfill = []
            for oh in ledger.objection_history:
                for obj in oh.objections:
                    status = ledger.objection_ledger.get(obj.objection_id, "OPEN")
                    if status in ("OPEN", "UPHELD") and obj.claim_id == cs.claim_id:
                        for req in obj.requested_evidence:
                            if req not in backfill:
                                backfill.append(req)
            if backfill:
                cs.missing_evidence = backfill[:4]  # cap at 4 items
                _log_text(log_path, f"[BACKFILL] Claim {cs.claim_id} ({cs.support_level}): backfilled {len(cs.missing_evidence)} missing_evidence from objections")
    return audit


def _reconcile_decisions(
    audit: AuditSnapshot,
    ledger: RunLedger,
    latest_proposal: ProposalPack,
    log_path: Path,
) -> AuditSnapshot:
    """Enforce consistency between objection states and item decisions.

    Rule 1: If an item has an ITEM-scope OPEN/UPHELD BLOCKING objection, it cannot be PASS or PASS_WITH_RISK.
    Rule 2: If an objection only targets an already-FAIL item, it should not block Judge entry.
    """
    item_blockers: dict[str, list[str]] = {}
    for oh in ledger.objection_history:
        for obj in oh.objections:
            status = ledger.objection_ledger.get(obj.objection_id, "OPEN")
            if status in ("OPEN", "UPHELD") and obj.scope == "ITEM":
                if obj.blocking_class == "BLOCKING" or obj.guard_held:
                    target_items = []
                    for rec in latest_proposal.recommendations:
                        if obj.claim_id in rec.claim_ids:
                            target_items.append(rec.item_id)
                    for item_id in target_items:
                        item_blockers.setdefault(item_id, []).append(obj.objection_id)

    decisions_map = {rd.item_id: rd for rd in audit.recommendation_decisions}

    for item_id, blocker_ids in item_blockers.items():
        rd = decisions_map.get(item_id)
        if rd and rd.decision in ("PASS", "PASS_WITH_RISK"):
            rd.decision = "NEEDS_EVIDENCE"
            rd.reason = f"Demoted: active blocking objection(s) {blocker_ids}"
            _log_text(log_path, f"[RECONCILE] {item_id} demoted to NEEDS_EVIDENCE - active blockers: {blocker_ids}")

    # Rule 2: objections targeting only FAIL items — do not block Judge entry,
    # but ONLY downgrade to RISK_ONLY if they are NOT causal (i.e. not cited as failure reason)
    fail_items = {rd.item_id for rd in audit.recommendation_decisions if rd.decision == "FAIL"}
    # Build causal objection set: objections explicitly cited in any FAIL recommendation_decision reason
    causal_objection_ids: set[str] = set()
    for rd in audit.recommendation_decisions:
        if rd.decision == "FAIL" and rd.reason:
            for oh in ledger.objection_history:
                for obj in oh.objections:
                    if obj.objection_id in rd.reason or (obj.objection_text[:60] in rd.reason):
                        causal_objection_ids.add(obj.objection_id)
    for oh in ledger.objection_history:
        for obj in oh.objections:
            status = ledger.objection_ledger.get(obj.objection_id, "OPEN")
            if status in ("OPEN", "UPHELD"):
                target_items = []
                for rec in latest_proposal.recommendations:
                    if obj.claim_id in rec.claim_ids:
                        target_items.append(rec.item_id)
                if target_items and all(item_id in fail_items for item_id in target_items):
                    if obj.objection_id in causal_objection_ids:
                        # Causal: keep blocking force, just mark as non-gating for Judge
                        obj.non_gating = True
                        _log_text(log_path, f"[RECONCILE] {obj.objection_id} is causal for FAIL — kept blocking, marked non-gating")
                    else:
                        # Non-causal: safe to downgrade
                        obj.blocking_class = "RISK_ONLY"
                        _log_text(log_path, f"[RECONCILE] {obj.objection_id} downgraded to RISK_ONLY - non-causal, all target items FAIL")

    return audit


async def _call_agent(
    client: ChatCompletionClient,
    system_prompt: str,
    user_prompt: str,
    node_name: str,
    ledger: RunLedger,
    log_path: Path,
    trace_path: Path,
) -> str:
    """Call an LLM agent with explicit timeout, retry, and loud failure logging.

    Retry policy:
    - Up to 3 attempts for transient network/timeout errors
    - Exponential backoff: 15s, 30s between retries
    - Explicit asyncio timeout of 300s (5 min) per attempt to catch silent hangs
    - Every failure is logged loudly with [LLM-ERROR] tag
    - Non-transient errors raise immediately
    """
    # Per-agent timeout: 5 minutes should be enough for any single LLM call
    # including thinking time with 30K max_tokens
    CALL_TIMEOUT_SECONDS = 300

    messages = [SystemMessage(content=system_prompt), UserMessage(content=user_prompt, source="user")]
    last_exc: Exception | None = None
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            # Wrap the LLM call in an explicit async timeout to catch silent hangs
            result = await asyncio.wait_for(
                client.create(messages),
                timeout=CALL_TIMEOUT_SECONDS,
            )
            last_exc = None
            break
        except asyncio.TimeoutError:
            last_exc = asyncio.TimeoutError(
                f"{node_name} LLM call timed out after {CALL_TIMEOUT_SECONDS}s on attempt {attempt + 1}/{max_attempts}"
            )
            _log_text(
                log_path,
                f"[LLM-ERROR] {node_name} TIMEOUT after {CALL_TIMEOUT_SECONDS}s "
                f"(attempt {attempt + 1}/{max_attempts})",
            )
            if attempt < max_attempts - 1:
                wait = 15 * (2 ** attempt)  # 15s, 30s
                _log_text(log_path, f"[LLM-RETRY] {node_name} retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                _log_text(
                    log_path,
                    f"[LLM-ERROR] {node_name} ALL {max_attempts} ATTEMPTS FAILED (timeout). "
                    f"Run will terminate with system failure.",
                )
                raise last_exc
        except Exception as exc:
            exc_name = type(exc).__name__
            # Transient network errors — retry with backoff
            transient_errors = (
                "ReadError", "RemoteProtocolError", "ConnectError",
                "TimeoutException", "ConnectionError", "ConnectionResetError",
                "ServerDisconnectedError", "ClientPayloadError",
            )
            is_transient = (
                exc_name in transient_errors
                or "ReadError" in str(type(exc))
                or "timeout" in str(exc).lower()
                or "connection" in str(exc).lower()
            )
            if is_transient:
                last_exc = exc
                _log_text(
                    log_path,
                    f"[LLM-ERROR] {node_name} transient error on attempt {attempt + 1}/{max_attempts}: "
                    f"{exc_name}: {str(exc)[:200]}",
                )
                if attempt < max_attempts - 1:
                    wait = 15 * (2 ** attempt)
                    _log_text(log_path, f"[LLM-RETRY] {node_name} retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    _log_text(
                        log_path,
                        f"[LLM-ERROR] {node_name} ALL {max_attempts} ATTEMPTS FAILED ({exc_name}). "
                        f"Run will terminate with system failure.",
                    )
                    raise
            else:
                # Non-transient error — log loudly and raise immediately
                _log_text(
                    log_path,
                    f"[LLM-ERROR] {node_name} NON-TRANSIENT ERROR: {exc_name}: {str(exc)[:300]}. "
                    f"No retry — raising immediately.",
                )
                raise

    if last_exc is not None:
        raise last_exc

    _ = _normalize_finish_reason(getattr(result, "finish_reason", None))
    text = _strip_think_tags(str(result.content))
    _log_turn(log_path, node_name, text)
    _log_event(trace_path, "turn_complete", {"node": node_name, "cycle": ledger.cycle_index, "chars": len(text)})
    ledger.transcript.append({"source": node_name, "content": text})
    return text


async def _call_and_validate(
    client: ChatCompletionClient,
    system_prompt: str,
    user_prompt: str,
    schema_class: type[BaseModel],
    node_name: str,
    ledger: RunLedger,
    log_path: Path,
    trace_path: Path,
    max_retries: int = 2,
) -> BaseModel | None:
    original_prompt = user_prompt
    last_bad_output: str | None = None
    last_error = ""
    for attempt in range(max_retries + 1):
        if attempt > 0 and last_bad_output is not None:
            prompt = (
                f"{original_prompt}\n\n"
                f"[REPAIR ATTEMPT {attempt}]\n"
                f"Your previous output was invalid:\n```\n{last_bad_output[:2000]}\n```\n"
                f"Error: {last_error}\n"
                f"Return ONLY a valid JSON object matching the required schema. No markdown, no explanation."
            )
        else:
            prompt = user_prompt
        text = await _call_agent(client, system_prompt, prompt, node_name, ledger, log_path, trace_path)
        raw = _extract_json(text)
        if raw is None:
            last_bad_output = text[:2000]
            last_error = "JSON extraction failed — no valid JSON found in response"
            _log_text(log_path, f"[VALIDATE] {node_name}: JSON extraction failed (attempt {attempt + 1})")
            if attempt < max_retries:
                continue
            return None
        try:
            return schema_class.model_validate(raw)
        except ValidationError as exc:
            last_bad_output = text[:2000]
            last_error = str(exc)
            _log_text(log_path, f"[VALIDATE] {node_name}: Schema validation failed: {exc} (attempt {attempt + 1})")
            if attempt < max_retries:
                continue
            return None
    return None


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True)


INFEASIBLE_KEYWORDS = [
    "monte carlo",
    "simulation",
    "backtest",
    "live data",
    "real-time",
    "stress test scenario",
    "sensitivity analysis",
    "sharpe ratio calculation",
    "correlation matrix",
    "portfolio optimization",
    "var calculation",
    "forward projection model",
    "regression analysis",
]

NON_BLOCKING_TYPES = {"concentration", "overlap", "valuation", "regime_risk", "timing"}


def _stabilize_objection_ids(
    objection_pack: ObjectionPack,
    ledger: RunLedger,
    log_path: Path,
    cycle: int = 0,
) -> ObjectionPack:
    """Use semantic issue_key to detect same-issue vs different-issue objections."""
    import hashlib

    def _make_issue_key(obj: Objection) -> str:
        thesis_norm = obj.objection_text[:80].strip().lower()
        thesis_hash = hashlib.md5(thesis_norm.encode()).hexdigest()[:6]
        return f"{obj.claim_id}:{obj.scope}:{obj.type}:{thesis_hash}"

    known_keys: dict[str, str] = {}
    known_ids: dict[str, str] = {}
    for oh in ledger.objection_history:
        for obj in oh.objections:
            key = obj.issue_key if obj.issue_key else _make_issue_key(obj)
            if key not in known_keys:
                known_keys[key] = obj.objection_id
            if obj.objection_id not in known_ids:
                known_ids[obj.objection_id] = key

    max_num = 0
    for oh in ledger.objection_history:
        for obj in oh.objections:
            match = re.match(r"OBJ(\d+)", obj.objection_id)
            if match:
                max_num = max(max_num, int(match.group(1)))
    for obj in objection_pack.objections:
        match = re.match(r"OBJ(\d+)", obj.objection_id)
        if match:
            max_num = max(max_num, int(match.group(1)))

    for obj in objection_pack.objections:
        obj.issue_key = _make_issue_key(obj)
        obj.last_seen_cycle = cycle

        if obj.issue_key in known_keys and known_keys[obj.issue_key] != obj.objection_id:
            old_id = obj.objection_id
            obj.objection_id = known_keys[obj.issue_key]
            _log_text(log_path, f"[ID-STABILIZE] {old_id} is same issue as {obj.objection_id} (key match)")
            ledger.supersession_map[old_id] = obj.objection_id
            # Lineage: inherit raised_in_cycle from the original objection
            for oh in ledger.objection_history:
                for prev_obj in oh.objections:
                    if prev_obj.objection_id == obj.objection_id:
                        obj.raised_in_cycle = prev_obj.raised_in_cycle
                        break
                else:
                    continue
                break
        elif obj.objection_id in known_ids and known_ids[obj.objection_id] != obj.issue_key:
            max_num += 1
            old_id = obj.objection_id
            new_id = f"OBJ{max_num:03d}"
            obj.objection_id = new_id
            known_keys[obj.issue_key] = new_id
            _log_text(log_path, f"[ID-STABILIZE] {old_id} recycled for different issue -> {new_id}")
            # Lineage: this is a genuinely new issue, raised_in_cycle = current cycle
            obj.raised_in_cycle = cycle
        elif obj.issue_key not in known_keys:
            known_keys[obj.issue_key] = obj.objection_id

        if obj.raised_in_cycle == 0 and obj.objection_id not in {o.objection_id for oh in ledger.objection_history for o in oh.objections}:
            obj.raised_in_cycle = cycle

    # Auto-withdraw superseded objections: if a new objection has the same issue_key
    # as an existing one but got a new ID (restated), withdraw the old one
    current_ids = {obj.objection_id for obj in objection_pack.objections}
    for oh in ledger.objection_history:
        for old_obj in oh.objections:
            if old_obj.objection_id not in current_ids:
                old_key = old_obj.issue_key if old_obj.issue_key else _make_issue_key(old_obj)
                current_status = ledger.objection_ledger.get(old_obj.objection_id, "OPEN")
                if current_status in ("OPEN", "UPHELD"):
                    for new_obj in objection_pack.objections:
                        new_key = new_obj.issue_key if new_obj.issue_key else _make_issue_key(new_obj)
                        if (old_obj.claim_id == new_obj.claim_id and
                                old_obj.type == new_obj.type and
                                old_obj.objection_id != new_obj.objection_id):
                            # Keep a live blocking predecessor when the successor would be frozen by the round-3 objection freeze.
                            successor_will_be_deferred = (cycle >= 2 and new_obj.objection_id not in ledger.objection_ledger)
                            predecessor_is_blocking = (
                                getattr(old_obj, 'blocking_class', 'RISK_ONLY') == "BLOCKING"
                                or getattr(old_obj, 'guard_held', False)
                            )
                            if predecessor_is_blocking and successor_will_be_deferred:
                                _log_text(log_path, f"[SUPERSEDE-BLOCKED] {old_obj.objection_id} NOT withdrawn — successor {new_obj.objection_id} will be deferred, predecessor is blocking")
                            else:
                                ledger.objection_ledger[old_obj.objection_id] = "WITHDRAWN"
                                old_obj.disposition = "WITHDRAWN"
                                ledger.supersession_map[old_obj.objection_id] = new_obj.objection_id
                                if successor_will_be_deferred:
                                    _log_text(log_path, f"[SUPERSEDE] {old_obj.objection_id} withdrawn - superseded by {new_obj.objection_id} (non-blocking, successor deferred OK)")
                                else:
                                    _log_text(log_path, f"[SUPERSEDE] {old_obj.objection_id} withdrawn - superseded by {new_obj.objection_id} (same claim+type)")
                            break

    return objection_pack


def _classify_blocking(objection_pack: ObjectionPack, log_path: Path) -> ObjectionPack:
    """Set default blocking_class based on type. Auditor can override later."""
    for obj in objection_pack.objections:
        if obj.type in NON_BLOCKING_TYPES:
            obj.blocking_class = "RISK_ONLY"
            obj.blocking = False
            if obj.scope == "PORTFOLIO":
                obj.blocking_class = "PORTFOLIO_ONLY"
            if obj.severity == "HIGH":
                _log_text(
                    log_path,
                    f"[CLASSIFY] {obj.objection_id}: HIGH {obj.type} -> {obj.blocking_class} (default, Auditor may override)",
                )
        else:
            obj.blocking_class = "BLOCKING"
            obj.blocking = True
    return objection_pack


def _filter_infeasible_objections(
    objection_pack: ObjectionPack,
    log_path: Path,
) -> ObjectionPack:
    """Downgrade objections that demand evidence impossible without tools."""
    for obj in objection_pack.objections:
        infeasible_requests = []
        feasible_requests = []
        for req in obj.requested_evidence:
            req_lower = req.lower()
            if any(kw in req_lower for kw in INFEASIBLE_KEYWORDS):
                infeasible_requests.append(req)
            else:
                feasible_requests.append(req)

        if infeasible_requests:
            _log_text(
                log_path,
                f"[INFEASIBLE] {obj.objection_id}: filtered {len(infeasible_requests)} infeasible evidence requests",
            )
            obj.requested_evidence = feasible_requests
            if not feasible_requests and obj.severity == "HIGH":
                obj.severity = "MEDIUM"
                _log_text(log_path, f"[INFEASIBLE] {obj.objection_id}: downgraded HIGH -> MEDIUM (all requests infeasible)")

    return objection_pack


def _apply_successor_materiality_gate(
    objection_pack: ObjectionPack,
    ledger: RunLedger,
    log_path: Path,
    cycle: int,
    latest_audit: "AuditSnapshot | None",
) -> ObjectionPack:
    """Successor-objection materiality gate.

    Runs after ID-STABILIZE, before FREEZE. Evaluates late-cycle successor
    objections whose predecessors were already RESOLVED or DOWNGRADED_TO_RISK.
    Non-material refinements are downgraded to DOWNGRADED_TO_RISK so they do
    not drag confidence as live HIGH or high-severity DEFERRED items.
    """
    if cycle < 1 or latest_audit is None:
        return objection_pack

    SUPPORT_ORDER = {"UNSUPPORTED": 0, "WEAK": 1, "ADEQUATE": 2, "STRONG": 3}
    DECISION_ORDER = {"NEEDS_EVIDENCE": 0, "FAIL": 0, "PASS_WITH_RISK": 1, "PASS": 2}
    ADEQUATE_MIN = SUPPORT_ORDER["ADEQUATE"]
    APPROVABLE_MIN = DECISION_ORDER["PASS_WITH_RISK"]

    # Build lookup maps from latest (previous-cycle) audit
    claim_support: dict[str, str] = {
        cs.claim_id: cs.support_level for cs in latest_audit.claim_scores
    }
    rec_decisions: dict[str, str] = {
        rd.item_id: rd.decision for rd in latest_audit.recommendation_decisions
    }

    # Map claim_id -> recommendation IDs that cite it (from most-recent proposal)
    claim_to_recs: dict[str, list[str]] = {}
    if ledger.proposal_history:
        for rec in ledger.proposal_history[-1].recommendations:
            for cid in rec.claim_ids:
                claim_to_recs.setdefault(cid, []).append(rec.item_id)

    # Collect resolved/downgraded predecessors, keyed by objection_id and by (claim_id, type)
    id_predecessors: dict[str, Objection] = {}
    lineage_predecessors: dict[tuple[str, str], Objection] = {}
    for oh in ledger.objection_history:
        for obj in oh.objections:
            status = ledger.objection_ledger.get(obj.objection_id, "OPEN")
            if status in ("RESOLVED", "DOWNGRADED_TO_RISK"):
                id_predecessors[obj.objection_id] = obj
                lineage_predecessors[(obj.claim_id, obj.type)] = obj  # last one wins

    # Evidence known before current cycle's researcher ran
    boundary_idx = (
        ledger.evidence_cycle_boundaries[cycle]
        if cycle < len(ledger.evidence_cycle_boundaries)
        else len(ledger.evidence_ledger)
    )
    pre_cycle_eids: set[str] = {e.evidence_id for e in ledger.evidence_ledger[:boundary_idx]}

    _quant_re = re.compile(
        r"\b\d+(?:\.\d+)?(?:\s*%|\s*percent|\s*\$|\s*million|\s*billion|\s*x\b)",
        re.IGNORECASE,
    )

    for obj in objection_pack.objections:
        # --- Find predecessor ---
        predecessor: Objection | None = None
        if obj.objection_id in id_predecessors:
            predecessor = id_predecessors[obj.objection_id]
        else:
            predecessor = lineage_predecessors.get((obj.claim_id, obj.type))

        if predecessor is None:
            continue  # No resolved/downgraded predecessor → not a gatable successor

        predecessor_disposition = ledger.objection_ledger.get(predecessor.objection_id, "OPEN")
        claim_id = obj.claim_id
        claim_sup = claim_support.get(claim_id, "UNSUPPORTED")
        target_claim_adequate = SUPPORT_ORDER.get(claim_sup, 0) >= ADEQUATE_MIN

        dependent_recs = claim_to_recs.get(claim_id, [])
        all_recs_approvable = all(
            DECISION_ORDER.get(rec_decisions.get(rid, "FAIL"), 0) >= APPROVABLE_MIN
            for rid in dependent_recs
        ) if dependent_recs else True

        presumptively_non_material = target_claim_adequate and all_recs_approvable

        def _emit(materiality: str, reason: str, final: str) -> None:
            _log_text(
                log_path,
                f"[SUCCESSOR-GATE] {obj.objection_id} (predecessor: {predecessor.objection_id} {predecessor_disposition})"
                f" target={claim_id} claim_support={claim_sup} all_recs_approvable={all_recs_approvable}"
                f" materiality={materiality} reason=\"{reason}\" -> {final}",
            )

        # --- Condition 2 / 3: claim or recs not adequate → MATERIAL, keep HIGH ---
        if not presumptively_non_material:
            reasons = []
            if not target_claim_adequate:
                reasons.append(f"claim not adequate ({claim_sup})")
            if not all_recs_approvable:
                reasons.append("dependent rec not approvable")
            _emit("MATERIAL", "; ".join(reasons), "UPHELD")
            continue

        # --- Escape: type escalation to factual_contradiction ---
        if obj.type == "factual_contradiction" and predecessor.type != "factual_contradiction":
            _emit(
                "MATERIAL",
                f"introduces factual_contradiction type escalation from {predecessor.type}",
                "UPHELD",
            )
            continue

        # --- Escape: objection references evidence IDs added after predecessor was adjudicated ---
        all_refs = obj.objection_text + " " + " ".join(obj.requested_evidence)
        new_eids = [eid for eid in re.findall(r"\bE\d{3}\b", all_refs) if eid not in pre_cycle_eids]
        if new_eids:
            _emit("MATERIAL", f"references new evidence IDs not in pre-cycle ledger: {new_eids[:3]}", "UPHELD")
            continue

        # --- Escape: introduces novel quantitative figures absent from predecessor ---
        new_quants = _quant_re.findall(obj.objection_text)
        pred_quants = set(_quant_re.findall(predecessor.objection_text))
        novel_quants = [q for q in new_quants if q not in pred_quants]
        if novel_quants:
            _emit("MATERIAL", f"introduces novel quantitative figures: {novel_quants[:3]}", "UPHELD")
            continue

        # --- Escape: low keyword overlap → possible novel issue ---
        pred_kw = _relevance_keywords(predecessor.objection_text)
        new_kw = _relevance_keywords(obj.objection_text)
        if pred_kw and new_kw:
            overlap_ratio = len(pred_kw & new_kw) / max(len(pred_kw), len(new_kw))
            if overlap_ratio < 0.2:
                _emit(
                    "MATERIAL",
                    f"low keyword overlap ({overlap_ratio:.0%}) with predecessor — possible novel issue",
                    "UPHELD",
                )
                continue

        # --- All escape hatches missed → NON_MATERIAL: downgrade to DOWNGRADED_TO_RISK ---
        same_type_label = f"same type {obj.type}, " if obj.type == predecessor.type else ""
        reason = (
            f"predecessor {predecessor_disposition.lower()}, claim adequate ({claim_sup}), "
            f"all_recs_approvable, {same_type_label}refinement only"
        )
        _emit("NON_MATERIAL", reason, "DOWNGRADED_TO_RISK")

        obj.disposition = "DOWNGRADED_TO_RISK"
        obj.blocking_class = "RISK_ONLY"
        obj.blocking = False
        if obj.severity == "HIGH":
            obj.severity = "MEDIUM"
        ledger.objection_ledger[obj.objection_id] = "DOWNGRADED_TO_RISK"

    return objection_pack


def _researcher_prompt(task: str, ledger: RunLedger, latest_audit: AuditSnapshot | None) -> str:
    if ledger.cycle_index == 0 or latest_audit is None:
        base_prompt = f"Task: {task}\nThis is the first research pass. Gather evidence for the topic.\nMaximum 10 evidence items."
        # V4 (Cascade): When Brain augmentation is available, inject evidence gaps
        # as targeted research directives for the first cycle
        if ledger.brain_augmentation and ledger.cycle_index == 0:
            gaps = ledger.brain_augmentation.get("evidence_gaps", [])
            if gaps:
                gap_lines = "\n".join(
                    f"  - {g.get('gap_id', '?')}: {g.get('text', '')[:150]}"
                    for g in gaps[:8]
                )
                base_prompt += (
                    "\n\nPRIORITY EVIDENCE GAPS (from prior multi-model analysis):\n"
                    f"{gap_lines}\n"
                    "Address these gaps first, then fill remaining slots with broad evidence."
                )
            # Also inject position summary as context for targeted research
            positions = ledger.brain_augmentation.get("position_summary", [])
            if positions:
                pos_lines = "\n".join(
                    f"  - {p.get('model', '?')}: {p.get('kind', '?')} → {p.get('primary_option', '?')} "
                    f"(confidence={p.get('confidence', '?')})"
                    for p in positions[:6]
                )
                base_prompt += (
                    "\n\nPRIOR MODEL POSITIONS (for context — do NOT decide, only gather evidence):\n"
                    f"{pos_lines}"
                )
        return base_prompt

    open_obj_ids = {oid for oid, status in ledger.objection_ledger.items() if status == "OPEN"}
    latest_objections = ledger.objection_history[-1] if ledger.objection_history else None

    obj_details = []
    if latest_objections:
        for obj in latest_objections.objections:
            if obj.objection_id in open_obj_ids:
                obj_details.append(
                    {
                        "objection_id": obj.objection_id,
                        "claim_id": obj.claim_id,
                        "severity": obj.severity,
                        "text": obj.objection_text,
                        "requested_evidence": obj.requested_evidence,
                    }
                )

    return (
        f"Task: {task}\n"
        "TARGETED RESEARCH PASS - gather evidence ONLY for these open objections:\n"
        f"{_json_dump(obj_details)}\n\n"
        f"Missing evidence from Auditor: {_json_dump(latest_audit.missing_evidence)}\n"
        f"Prior evidence IDs already gathered: {_json_dump([e.evidence_id for e in ledger.evidence_ledger])}\n"
        "RULES:\n"
        "- Only fetch evidence that directly addresses an open objection\n"
        "- Do NOT do broad research - only targeted gap-filling\n"
        "- Maximum 10 evidence items\n"
        "- Set supports_claim_ids to the claim_ids the evidence supports"
    )


def _strategist_prompt(
    task: str,
    ledger: RunLedger,
    latest_objections: ObjectionPack | None,
    latest_audit: AuditSnapshot | None,
) -> str:
    if ledger.cycle_index == 0:
        parts = [
            f"Task: {task}",
            f"Evidence ledger: {_json_dump([e.model_dump() for e in ledger.evidence_ledger])}",
        ]
        # Explicit-option anchoring: require coverage of all brief-stated options
        if ledger.explicit_option_mode and ledger.brief_option_registry:
            option_block = "\n".join(
                f"  {o['id']}: {o['text'][:200]}" for o in ledger.brief_option_registry
            )
            parts.append(
                f"\n--- EXPLICIT OPTIONS FROM THE BRIEF ---\n"
                f"The brief presents these explicit alternatives that MUST each be evaluated:\n"
                f"{option_block}\n\n"
                f"REQUIREMENTS:\n"
                f"- You MUST produce a separate, standalone recommendation for EACH option listed above.\n"
                f"- Do NOT merge two brief options into a single recommendation.\n"
                f"- Do NOT omit any brief option, even if you believe it is a poor choice.\n"
                f"- If you think an option is weak, still include it as a recommendation — state its "
                f"weaknesses in known_risks and let the Critic and Auditor evaluate it.\n"
                f"- You MAY also propose additional hybrid or composite recommendations beyond the brief "
                f"options, but these are supplementary — they cannot replace the brief-native options.\n"
                f"- For each recommendation, indicate whether it is a brief-native option or a "
                f"Strategist-added composite in the role_in_portfolio field.\n"
                f"--- END EXPLICIT OPTIONS ---\n"
            )
        parts.append("Build your proposal using evidence IDs from the ledger. Every CORE claim must cite evidence.")
        # V4 (Cascade): Inject Brain's position summary and shared ground as context
        if ledger.brain_augmentation:
            positions = ledger.brain_augmentation.get("position_summary", [])
            if positions:
                pos_lines = "\n".join(
                    f"  - {p.get('model', '?')}: recommends {p.get('primary_option', '?')} "
                    f"({p.get('kind', '?')}, confidence={p.get('confidence', '?')})"
                    for p in positions[:6]
                )
                parts.append(
                    f"\n--- PRIOR MULTI-MODEL POSITIONS (context only — you decide independently) ---\n"
                    f"{pos_lines}"
                )
            shared = ledger.brain_augmentation.get("brain_shared_ground", [])
            if shared:
                parts.append(f"Shared ground across models: {', '.join(str(s) for s in shared)}")
            brain_outcome = ledger.brain_augmentation.get("brain_outcome")
            if brain_outcome:
                parts.append(f"Prior deliberation outcome: {brain_outcome}")
        return "\n".join(parts)

    boundary = ledger.evidence_cycle_boundaries[-1] if ledger.evidence_cycle_boundaries else 0
    new_evidence = ledger.evidence_ledger[boundary:]
    prior_evidence_ids = [e.evidence_id for e in ledger.evidence_ledger[:boundary]]

    parts = [
        f"Task: {task}",
        f"New evidence this cycle ({len(new_evidence)} items): {_json_dump([e.model_dump() for e in new_evidence])}",
        f"Prior evidence IDs (still valid): {_json_dump(prior_evidence_ids)}",
    ]
    if latest_objections is not None:
        open_objs = [o for o in latest_objections.objections if o.controller_status == "OPEN"]
        parts.append(f"Open objections ({len(open_objs)}): {_json_dump([o.model_dump() for o in open_objs])}")
    if latest_audit is not None:
        parts.append(
            f"Prior audit summary: quality={latest_audit.overall_evidence_quality}, "
            f"eligible={latest_audit.eligible_for_judgment}"
        )
        weak_claims = [cs for cs in latest_audit.claim_scores if cs.support_level in ("UNSUPPORTED", "WEAK")]
        if weak_claims:
            parts.append(f"Claims needing work: {_json_dump([cs.model_dump() for cs in weak_claims])}")
    if ledger.proposal_history:
        parts.append(f"Your prior proposal: {_json_dump(ledger.proposal_history[-1].model_dump())}")
    parts.append("Revise ONLY claims touched by objections or new evidence. Keep unchanged claims identical (same IDs, same text).")
    return "\n".join(parts)


def _strategist_patch_prompt(
    task: str,
    ledger: RunLedger,
    current_proposal: ProposalPack,
    latest_objections: ObjectionPack | None,
    latest_audit: AuditSnapshot | None,
) -> str:
    open_objs = []
    if latest_objections:
        open_objs = [
            o for o in latest_objections.objections if ledger.objection_ledger.get(o.objection_id, "OPEN") == "OPEN"
        ]

    parts = [
        f"Task: {task}",
        f"Current proposal: {_json_dump(current_proposal.model_dump())}",
        f"Open objections requiring your response ({len(open_objs)}): {_json_dump([o.model_dump() for o in open_objs])}",
    ]
    if latest_audit:
        parts.append(f"Audit: quality={latest_audit.overall_evidence_quality}")
        if latest_audit.recommendation_decisions:
            parts.append(
                f"Recommendation decisions: {_json_dump([rd.model_dump() for rd in latest_audit.recommendation_decisions])}"
            )
        weak = [cs for cs in latest_audit.claim_scores if cs.support_level in ("UNSUPPORTED", "WEAK")]
        if weak:
            parts.append(f"Weak claims: {_json_dump([cs.model_dump() for cs in weak])}")
    boundary = ledger.evidence_cycle_boundaries[-1] if ledger.evidence_cycle_boundaries else 0
    new_ev = ledger.evidence_ledger[boundary:]
    if new_ev:
        parts.append(f"New evidence this cycle: {_json_dump([e.model_dump() for e in new_ev])}")
    parts.append("Submit a PATCH addressing each open objection. Do NOT regenerate the full proposal.")
    return "\n".join(parts)


def _critic_prompt(
    latest_proposal: ProposalPack,
    ledger: RunLedger,
    latest_audit: AuditSnapshot | None,
) -> str:
    if ledger.cycle_index == 0:
        parts = [
            f"Latest proposal: {_json_dump(latest_proposal.model_dump())}",
            f"Evidence ledger: {_json_dump([e.model_dump() for e in ledger.evidence_ledger])}",
        ]
        # V4 (Cascade): Inject Brain's contested dimensions as explicit attack surfaces
        if ledger.brain_augmentation:
            contested = ledger.brain_augmentation.get("contested_dimensions", [])
            if contested:
                parts.append(
                    "\nKNOWN CONTESTED DIMENSIONS (from prior multi-model analysis):\n"
                    + "\n".join(f"  - {dim}" for dim in contested[:10])
                    + "\nThese dimensions had unresolved disagreement across multiple models. "
                    "Challenge the proposal specifically on these dimensions."
                )
            # Inject Brain outcome as context
            brain_outcome = ledger.brain_augmentation.get("brain_outcome")
            if brain_outcome:
                parts.append(
                    f"\nPrior analysis outcome: {brain_outcome}. "
                    f"Convergence: {ledger.brain_augmentation.get('brain_convergence', 'unknown')}."
                )
        return "\n".join(parts)

    parts = [
        f"Latest proposal: {_json_dump(latest_proposal.model_dump())}",
    ]
    boundary = ledger.evidence_cycle_boundaries[-1] if ledger.evidence_cycle_boundaries else 0
    new_evidence = ledger.evidence_ledger[boundary:]
    parts.append(f"New evidence this cycle: {_json_dump([e.model_dump() for e in new_evidence])}")
    if latest_audit is not None:
        parts.append(
            f"Prior audit: quality={latest_audit.overall_evidence_quality}, "
            f"unresolved={_json_dump(latest_audit.unresolved_objections)}"
        )
    parts.append("Focus on revised claims and unresolved objections only. Do not re-challenge resolved items.")
    return "\n".join(parts)


def _auditor_prompt(
    ledger: RunLedger,
    latest_proposal: ProposalPack,
    latest_objections: ObjectionPack,
    cycle: int = 0,
) -> str:
    if ledger.cycle_index == 0:
        parts = [
            f"Evidence ledger: {_json_dump([e.model_dump() for e in ledger.evidence_ledger])}",
            f"Latest proposal: {_json_dump(latest_proposal.model_dump())}",
            f"Latest objections: {_json_dump(latest_objections.model_dump())}",
        ]
        parts.append("Score each claim's evidence support and decide if judgment is eligible.")
        return "\n".join(parts)

    parts = [
        f"Latest proposal: {_json_dump(latest_proposal.model_dump())}",
    ]
    open_objs = [o for o in latest_objections.objections if o.controller_status in ("OPEN", "UPHELD")]
    parts.append(f"Open objections ({len(open_objs)}): {_json_dump([o.model_dump() for o in open_objs])}")
    obj_status = []
    for oh in ledger.objection_history:
        for obj in oh.objections:
            if ledger.objection_ledger.get(obj.objection_id, "OPEN") in ("OPEN", "UPHELD"):
                obj_status.append(
                    {
                        "objection_id": obj.objection_id,
                        "claim_id": obj.claim_id,
                        "type": obj.type,
                        "scope": obj.scope,
                        "blocking_class": obj.blocking_class,
                        "text": obj.objection_text[:150],
                    }
                )
    parts.append(f"Active objections requiring your finding ({len(obj_status)}): {_json_dump(obj_status)}")
    parts.append("You MUST provide an objection_finding for EVERY active objection listed above.")
    boundary = ledger.evidence_cycle_boundaries[-1] if ledger.evidence_cycle_boundaries else 0
    new_evidence = ledger.evidence_ledger[boundary:]
    parts.append(f"New evidence this cycle: {_json_dump([e.model_dump() for e in new_evidence])}")
    parts.append(f"Total evidence count: {len(ledger.evidence_ledger)}")
    if cycle in ledger.strategist_cited_evidence:
        cited = ledger.strategist_cited_evidence[cycle]
        parts.append(f"Strategist-cited evidence IDs this cycle: {_json_dump(cited)}")
        parts.append("RULE: Only Strategist-cited evidence can justify claim support UPGRADES or FAIL->PASS flips. Uncited evidence may keep objections alive or reduce confidence but cannot strengthen claims.")
    if ledger.audit_history:
        prev = ledger.audit_history[-1]
        parts.append(f"Prior audit: quality={prev.overall_evidence_quality}, eligible={prev.eligible_for_judgment}")
        parts.append(f"Prior claim scores: {_json_dump([cs.model_dump() for cs in prev.claim_scores])}")
    parts.append("Score each claim's evidence support and decide if judgment is eligible.")
    return "\n".join(parts)


def _judge_prompt(
    task: str,
    ledger: RunLedger,
    latest_proposal: ProposalPack,
    latest_audit: AuditSnapshot,
    latest_objections: ObjectionPack,
) -> str:
    open_objs = [
        o
        for oh in ledger.objection_history
        for o in oh.objections
        if ledger.objection_ledger.get(o.objection_id, "OPEN") == "OPEN"
    ]
    parts = [
        f"Task: {task}",
        f"Final proposal: {_json_dump(latest_proposal.model_dump())}",
        f"Final audit: {_json_dump(latest_audit.model_dump())}",
        f"Recommendation decisions: {_json_dump([rd.model_dump() for rd in latest_audit.recommendation_decisions])}",
        f"Open objections still unresolved ({len(open_objs)}): {_json_dump([o.model_dump() for o in open_objs])}",
        f"Objection ledger: {_json_dump(ledger.objection_ledger)}",
        "Issue your final verdict. Apply the confidence caps strictly.",
        "You are an AGGREGATOR. Respect Auditor decisions: FAIL items must be rejected.",
        "PASS_WITH_RISK items may be approved but risks must be noted.",
        "Keep rationale under 500 words.",
    ]
    deferred_objs = []
    for oid, status in ledger.objection_ledger.items():
        if status == "DEFERRED":
            obj_detail = ledger.deferred_objection_store.get(oid)
            if obj_detail:
                deferred_objs.append(
                    f'- {oid}: severity={obj_detail.severity}, type={obj_detail.type}, '
                    f'target={obj_detail.claim_id}, text="{obj_detail.objection_text[:150]}"'
                )
    if deferred_objs:
        parts.append("DEFERRED OBJECTIONS (not adjudicated — include in unresolved_points with actual content):")
        parts.extend(deferred_objs)
    return "\n".join(parts)


def _system_failure(reason: str) -> ConsensusVerdict:
    return ConsensusVerdict(
        status="SYSTEM_FAILURE",
        confidence=0.0,
        approved_items=[],
        rejected_items=[],
        unresolved_points=[],
        rationale=reason,
        next_action="Inspect logs and retry the run.",
    )


def _print_transcript(ledger: RunLedger) -> None:
    print("\n" + "=" * 60, flush=True)
    print("TRANSCRIPT", flush=True)
    for item in ledger.transcript:
        print(f"\n[{item['source']}]\n{item['content']}", flush=True)


def _print_verdict(verdict: ConsensusVerdict) -> None:
    print("\n" + "=" * 60, flush=True)
    print("VERDICT", flush=True)
    print(json.dumps(verdict.model_dump(), indent=2), flush=True)


async def run_chamber_v3(task: str, brain_augmentation: dict | None = None) -> ConsensusVerdict | None:
    """Run the Chamber V11 deliberation pipeline.

    Args:
        task: The brief/task text.
        brain_augmentation: Optional structured pre-work from Brain V3 (cascade mode).
            When provided, replaces LLM option extraction and enriches Researcher/Critic
            prompts with Brain's evidence gaps and contested dimensions.
            Keys: options, choice_mode, evidence_gaps, contested_dimensions,
                  position_summary, brain_outcome, brain_convergence, brain_shared_ground
    """
    def _pick_strategist(clients: dict[str, ChatCompletionClient], ledger: RunLedger) -> ChatCompletionClient:
        if ledger.cycle_index == 0:
            return clients["strategist_r1"]
        return clients["strategist_r2"]

    _load_dotenv_if_present()
    logging.getLogger("autogen_agentchat").setLevel(logging.DEBUG)

    reports_dir = (Path(__file__).parent / "reports").resolve()
    reports_dir.mkdir(exist_ok=True)
    timestamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    log_path = (reports_dir / f"chamber-v3-{timestamp}.log").resolve()
    trace_path = (reports_dir / f"chamber-v3-trace-{timestamp}.jsonl").resolve()
    log_path.write_text(f"Chamber v3 run started: {_dt.now().isoformat()}\nTask: {task}\n\n", encoding="utf-8")
    print(f"[Chamber] Live log: tail -f {log_path}", flush=True)

    clients = _build_clients()
    sonar_client = SonarProSearchClient() if SONAR_DEEP_ENABLED else None
    ledger = RunLedger(run_id=f"run-{uuid.uuid4().hex[:12]}", task=task)
    ledger.search_mode, ledger.search_diag_router_confidence = await _resolve_search_mode(
        task, clients["judge"], log_path
    )
    ledger.search_diag_upfront_mode = ledger.search_mode
    _log_event(trace_path, "run_started", {"run_id": ledger.run_id, "task": task, "search_mode": ledger.search_mode})

    # --- Explicit-option extraction ---
    # When brain_augmentation is provided, use Brain's pre-mapped options instead of LLM call.
    # Brain's options are already controller-owned structured data, not LLM prose.
    if brain_augmentation and brain_augmentation.get("options") and len(brain_augmentation["options"]) >= 2:
        brief_options = brain_augmentation["options"]
        detected_choice_mode = brain_augmentation.get("choice_mode", "portfolio")
        _log_text(log_path,
                  f"[BRAIN-AUGMENT] Using Brain's pre-mapped options: "
                  f"{len(brief_options)} options, choice_mode={detected_choice_mode}")
        _log_text(log_path,
                  f"[BRAIN-AUGMENT] Brain outcome={brain_augmentation.get('brain_outcome', '?')} "
                  f"convergence={brain_augmentation.get('brain_convergence', '?')} "
                  f"shared_ground={brain_augmentation.get('brain_shared_ground', [])}")
        _log_event(trace_path, "brain_augmentation_applied", {
            "source": brain_augmentation.get("source", "brain_v3"),
            "brain_run_id": brain_augmentation.get("brain_run_id", "?"),
            "option_count": len(brief_options),
            "evidence_gap_count": len(brain_augmentation.get("evidence_gaps", [])),
            "contested_count": len(brain_augmentation.get("contested_dimensions", [])),
        })
    else:
        # Standard path: LLM-based option extraction
        brief_options, detected_choice_mode = await _extract_explicit_options_llm(task, clients["strategist_r1"], log_path)

    if brief_options and len(brief_options) >= 2:
        ledger.explicit_option_mode = True
        ledger.brief_option_registry = brief_options
        ledger.choice_mode = detected_choice_mode
        _log_event(trace_path, "explicit_options_detected", {
            "count": len(brief_options),
            "option_ids": [o["id"] for o in brief_options],
            "choice_mode": detected_choice_mode,
        })
        _log_text(log_path, f"[CHOICE-MODE] {detected_choice_mode} — {'single selection required' if detected_choice_mode == 'exclusive' else 'portfolio of approved options allowed'}")
    else:
        ledger.explicit_option_mode = False
        ledger.choice_mode = "portfolio"

    # Store brain augmentation on ledger for prompt enrichment
    if brain_augmentation:
        ledger.brain_augmentation = brain_augmentation

    verdict: ConsensusVerdict | None = None
    latest_proposal: ProposalPack | None = None
    latest_objections: ObjectionPack | None = None
    latest_audit: AuditSnapshot | None = None

    try:
        for cycle in range(ledger.max_cycles):
            ledger.cycle_index = cycle
            _log_text(log_path, f"[CYCLE] Starting cycle {cycle + 1}/{ledger.max_cycles}")
            dropped_claim_ids = []

            prior_audit = ledger.audit_history[-1] if ledger.audit_history else None
            researcher_prompt = _researcher_prompt(task, ledger, prior_audit)
            # V4 observability: log what Brain augmentation was injected into Researcher prompt
            if ledger.brain_augmentation and cycle == 0:
                _aug = ledger.brain_augmentation
                _gaps = _aug.get("evidence_gaps", [])
                _positions = _aug.get("position_summary", [])
                if _gaps:
                    _gap_ids = ", ".join(g.get("gap_id", "?") for g in _gaps[:8])
                    _log_text(log_path, f"[BRAIN-AUGMENT-GAPS] count={len(_gaps)} ids=[{_gap_ids}] → Researcher prompt")
                if _positions:
                    _pos_labels = ", ".join(f"{p.get('model','?')}={p.get('primary_option','?')}" for p in _positions[:6])
                    _log_text(log_path, f"[BRAIN-AUGMENT-POSITIONS] count={len(_positions)} models=[{_pos_labels}] → Researcher prompt")
                if not _gaps and not _positions:
                    _log_text(log_path, "[BRAIN-AUGMENT-RESEARCHER] no gaps or positions to inject")
            elif not ledger.brain_augmentation and cycle == 0:
                _log_text(log_path, "[BRAIN-AUGMENT-ABSENT] no brain augmentation provided (non-cascade run)")
            researcher_pack = await _call_and_validate(
                clients["researcher"],
                _build_researcher_system(task),
                researcher_prompt,
                EvidencePack,
                "Researcher",
                ledger,
                log_path,
                trace_path,
                max_retries=ledger.max_repair_attempts,
            )
            if researcher_pack is None:
                verdict = _system_failure("Researcher failed to return valid structured evidence.")
                break
            ledger.evidence_cycle_boundaries.append(len(ledger.evidence_ledger))
            new_evidence = []
            for ev in researcher_pack.evidence:
                # Semantic dedup: check content similarity, not model-supplied ID
                content_key = f"{ev.topic.strip().lower()[:80]}||{ev.fact.strip().lower()[:120]}"
                if content_key in ledger.evidence_content_hashes:
                    _log_text(log_path, f"[EVIDENCE] Skipping semantic duplicate: {ev.evidence_id} (matches {ledger.evidence_content_hashes[content_key]})")
                    continue
                # Relevance gate — reject off-topic items before ID assignment (P1)
                if not _is_evidence_relevant(ev, task, ledger, cycle + 1, "researcher", log_path):
                    continue
                # Assign controller-canonical ID
                ledger.evidence_counter += 1
                canonical_id = f"E{ledger.evidence_counter:03d}"
                old_id = ev.evidence_id
                ev.evidence_id = canonical_id
                ledger.evidence_content_hashes[content_key] = canonical_id
                ledger.evidence_seen_ids.add(canonical_id)
                new_evidence.append(ev)
                if old_id != canonical_id:
                    _log_text(log_path, f"[EVIDENCE-ID] {old_id} -> {canonical_id} (controller-assigned)")
                _log_text(log_path, f"[EVIDENCE-ADMITTED] cycle={cycle + 1} source=researcher id={canonical_id}")
            MAX_EVIDENCE_PER_CYCLE = 10
            if len(new_evidence) > MAX_EVIDENCE_PER_CYCLE:
                _log_text(log_path, f"[EVIDENCE] Capping from {len(new_evidence)} to {MAX_EVIDENCE_PER_CYCLE} items")
                confidence_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
                new_evidence.sort(key=lambda e: confidence_order.get(e.confidence, 3))
                new_evidence = new_evidence[:MAX_EVIDENCE_PER_CYCLE]
            ledger.evidence_ledger.extend(new_evidence)
            _log_text(
                log_path,
                f"[EVIDENCE] Cycle {cycle + 1}: added {len(new_evidence)} new, "
                f"{len(researcher_pack.evidence) - len(new_evidence)} duplicates skipped, total {len(ledger.evidence_ledger)}",
            )
            # One-shot retry if Researcher returned nothing and active objections need evidence
            if cycle > 0 and len(new_evidence) == 0:
                active_obj_ids = [oid for oid, s in ledger.objection_ledger.items() if s in ("OPEN", "UPHELD")]
                if active_obj_ids:
                    # Build targeted nudge
                    active_obj_texts = []
                    for oh in ledger.objection_history:
                        for obj in oh.objections:
                            if obj.objection_id in active_obj_ids:
                                active_obj_texts.append(f"- {obj.objection_id}: {obj.objection_text[:120]}")
                    nudge = (
                        "You returned no new evidence in the previous response. "
                        "The following objections are still OPEN and need supporting or counter-evidence:\n"
                        + "\n".join(active_obj_texts[:5])
                        + "\n\nPlease search your training knowledge for specific facts, data points, "
                        "or studies that address these gaps. Return at least 1-3 concrete evidence items."
                    )
                    _log_text(log_path, f"[RESEARCHER-RETRY] Cycle {cycle + 1}: 0 new evidence with {len(active_obj_ids)} active objections — retrying once with nudge")
                    retry_pack = await _call_and_validate(
                        clients["researcher"],
                        _build_researcher_system(task),
                        nudge,
                        EvidencePack,
                        "Researcher",
                        ledger,
                        log_path,
                        trace_path,
                        max_retries=1,
                    )
                    if retry_pack is not None and retry_pack.evidence:
                        retry_new = []
                        for ev in retry_pack.evidence:
                            content_key = f"{ev.topic.strip().lower()[:80]}||{ev.fact.strip().lower()[:120]}"
                            if content_key in ledger.evidence_content_hashes:
                                _log_text(log_path, f"[EVIDENCE] Skipping semantic duplicate on retry: {ev.evidence_id}")
                                continue
                            # Relevance gate — reject off-topic items before ID assignment (P1)
                            if not _is_evidence_relevant(ev, task, ledger, cycle + 1, "researcher", log_path):
                                continue
                            ledger.evidence_counter += 1
                            canonical_id = f"E{ledger.evidence_counter:03d}"
                            ev.evidence_id = canonical_id
                            ledger.evidence_content_hashes[content_key] = canonical_id
                            ledger.evidence_seen_ids.add(canonical_id)
                            retry_new.append(ev)
                            _log_text(log_path, f"[EVIDENCE-ADMITTED] cycle={cycle + 1} source=researcher id={canonical_id}")
                        if retry_new:
                            ledger.evidence_ledger.extend(retry_new)
                            new_evidence = retry_new
                            _log_text(log_path, f"[RESEARCHER-RETRY] Got {len(retry_new)} new evidence items on retry")
                        else:
                            _log_text(log_path, "[RESEARCHER-RETRY] Retry returned only duplicates — proceeding to degraded")
                    else:
                        _log_text(log_path, "[RESEARCHER-RETRY] Retry also returned empty — cycle will be marked degraded")
            if cycle == 0:
                strategist_prompt = _strategist_prompt(task, ledger, None, None)
                # V4 observability: log what Brain augmentation was injected into Strategist prompt
                if ledger.brain_augmentation:
                    _aug = ledger.brain_augmentation
                    _positions = _aug.get("position_summary", [])
                    _shared = _aug.get("brain_shared_ground", [])
                    _outcome = _aug.get("brain_outcome")
                    if _positions:
                        _pos_labels = ", ".join(f"{p.get('model','?')}={p.get('primary_option','?')}" for p in _positions[:6])
                        _log_text(log_path, f"[BRAIN-AUGMENT-POSITIONS] count={len(_positions)} models=[{_pos_labels}] → Strategist prompt")
                    if _shared:
                        _log_text(log_path, f"[BRAIN-AUGMENT-SHARED] ground=[{', '.join(str(s) for s in _shared)}] → Strategist prompt")
                    if _outcome:
                        _log_text(log_path, f"[BRAIN-AUGMENT-CONTEXT] outcome={_outcome} → Strategist prompt")
                    if not _positions and not _shared and not _outcome:
                        _log_text(log_path, "[BRAIN-AUGMENT-STRATEGIST] no positions, shared ground, or outcome to inject")
                proposal_pack = await _call_and_validate(
                    _pick_strategist(clients, ledger),
                    STRATEGIST_SYSTEM,
                    strategist_prompt,
                    ProposalPack,
                    "Strategist",
                    ledger,
                    log_path,
                    trace_path,
                    max_retries=ledger.max_repair_attempts,
                )
                if proposal_pack is None:
                    verdict = _system_failure("Strategist failed to return a valid proposal.")
                    break
                latest_proposal = proposal_pack
                ledger.proposal_history.append(proposal_pack)
                cited = set()
                for claim in proposal_pack.claims:
                    cited.update(claim.evidence_ids)
                for rec in proposal_pack.recommendations:
                    cited.update(rec.evidence_ids)
                ledger.strategist_cited_evidence[cycle] = list(cited)
                _log_text(log_path, f"[EVIDENCE-ATTR] Cycle {cycle + 1}: Strategist cited {len(cited)} evidence IDs")

                # --- Explicit-option coverage validation ---
                if ledger.explicit_option_mode and ledger.brief_option_registry:
                    missing = _validate_option_coverage(proposal_pack, ledger.brief_option_registry, log_path)
                    if missing:
                        _log_text(
                            log_path,
                            f"[OPTION-COVERAGE-RETRY] Strategist omitted {len(missing)} brief options: "
                            f"{missing} — requesting retry with explicit coverage nudge",
                        )
                        # Build a retry prompt with the missing options highlighted
                        missing_opts = [o for o in ledger.brief_option_registry if o["id"] in missing]
                        nudge_lines = "\n".join(f"  - {o['id']}: {o['text'][:150]}" for o in missing_opts)
                        retry_prompt = (
                            f"{strategist_prompt}\n\n"
                            f"IMPORTANT: Your previous proposal did not include standalone recommendations for "
                            f"these brief-stated options:\n{nudge_lines}\n\n"
                            f"You MUST add a separate recommendation for each missing option listed above, "
                            f"even if you believe it is a poor choice. State weaknesses in known_risks."
                        )
                        retry_pack = await _call_and_validate(
                            _pick_strategist(clients, ledger),
                            STRATEGIST_SYSTEM,
                            retry_prompt,
                            ProposalPack,
                            "Strategist",
                            ledger,
                            log_path,
                            trace_path,
                            max_retries=1,
                        )
                        if retry_pack is not None:
                            # Re-validate coverage
                            still_missing = _validate_option_coverage(retry_pack, ledger.brief_option_registry, log_path)
                            if len(still_missing) < len(missing):
                                latest_proposal = retry_pack
                                ledger.proposal_history[-1] = retry_pack
                                _log_text(log_path, f"[OPTION-COVERAGE-RETRY] Retry improved coverage: {len(missing)} → {len(still_missing)} missing")
                            else:
                                _log_text(log_path, f"[OPTION-COVERAGE-RETRY] Retry did not improve coverage — keeping original proposal")
                        else:
                            _log_text(log_path, "[OPTION-COVERAGE-RETRY] Retry failed — keeping original proposal")
            else:
                # --- Pre-patch Brave retrieval (cycles 1+) ---
                if BRAVE_SEARCH_ENABLED:
                    pre_patch_objs = [
                        obj
                        for oh in ledger.objection_history
                        for obj in oh.objections
                        if ledger.objection_ledger.get(obj.objection_id) in ("OPEN", "UPHELD")
                    ]
                    if pre_patch_objs:
                        brave_evidence = _brave_retrieve_evidence(pre_patch_objs, ledger, log_path)
                        for ev in brave_evidence:
                            ledger.evidence_ledger.append(ev)
                        if brave_evidence:
                            _log_text(log_path, f"[BRAVE-PRE] Injected {len(brave_evidence)} pre-patch evidence items")
                            _log_event(trace_path, "brave_pre_patch", {"cycle": cycle, "items": len(brave_evidence)})
                patch_prompt = _strategist_patch_prompt(task, ledger, latest_proposal, latest_objections, latest_audit)
                patch = await _call_and_validate(
                    _pick_strategist(clients, ledger),
                    STRATEGIST_SYSTEM,
                    patch_prompt,
                    StrategistPatch,
                    "Strategist-Patch",
                    ledger,
                    log_path,
                    trace_path,
                    max_retries=ledger.max_repair_attempts,
                )
                if patch is None:
                    verdict = _system_failure("Strategist failed to return a valid patch.")
                    break
                latest_proposal = _apply_patch(latest_proposal, patch, ledger, log_path)
                retry_patch: StrategistPatch | None = None
                # Patch-coverage validation + enforcement
                if cycle > 0 and latest_objections is not None:
                    actual_open_ids = {
                        oid for oid, status in ledger.objection_ledger.items()
                        if status in ("OPEN", "UPHELD")
                    }
                    # Fix A: semantic rejection — empty objection_responses with live objections = force retry
                    _semantic_reject = bool(actual_open_ids and not patch.objection_responses)
                    if _semantic_reject:
                        _log_text(
                            log_path,
                            f"[PATCH-SEMANTIC-REJECT] Patch has 0 objection_responses but {len(actual_open_ids)} live "
                            f"objections — semantically incomplete, forcing retry immediately",
                        )
                    # Build objection lookup for semantic validation
                    _obj_lookup: dict[str, Objection] = {}
                    for _oh in ledger.objection_history:
                        for _obj in _oh.objections:
                            if _obj.objection_id not in _obj_lookup:
                                _obj_lookup[_obj.objection_id] = _obj
                    # P1 round-4: semantic validation — only credit ID if content also matches
                    if _semantic_reject or not (patch and patch.objection_responses):
                        responded_ids: set[str] = set()
                        _direct_count = _indirect_count = _mismatch_count = _unrepaired_count = 0
                        _not_addressed_ids: set[str] = set()
                        _unsupported_quant_count = 0
                    else:
                        responded_ids = set()
                        _direct_count = _indirect_count = _mismatch_count = _unrepaired_count = 0
                        _not_addressed_ids = set()
                        _resp_outcome_map: dict[str, str] = {}
                        for _resp in patch.objection_responses:
                            _obj_for_resp = _obj_lookup.get(_resp.objection_id)
                            if _obj_for_resp is None:
                                # Unknown ID — credit it (phantom detection handles later)
                                responded_ids.add(_resp.objection_id)
                                _direct_count += 1
                                _resp_outcome_map[_resp.objection_id] = PATCH_VALIDATED_DIRECT
                            else:
                                _outcome = _classify_patch_outcome(_resp, _obj_for_resp, log_path)
                                _resp_outcome_map[_resp.objection_id] = _outcome
                                if _outcome == PATCH_VALIDATED_DIRECT:
                                    responded_ids.add(_resp.objection_id)
                                    _direct_count += 1
                                elif _outcome == PATCH_VALIDATED_INDIRECT:
                                    responded_ids.add(_resp.objection_id)
                                    _indirect_count += 1
                                elif _outcome == PATCH_MISMATCH:
                                    _mismatch_count += 1
                                    _not_addressed_ids.add(_resp.objection_id)
                                else:  # PATCH_UNREPAIRED
                                    _unrepaired_count += 1
                                    _not_addressed_ids.add(_resp.objection_id)
                        # P1 round-6: unsupported-quantification guard — demote before coverage tally
                        _unsupported_quant_count = 0
                        if patch.revised_claims:
                            _invalid_quant_claims = _check_unsupported_quantification(patch, ledger, log_path)
                            if _invalid_quant_claims:
                                _invalid_quant_set = set(_invalid_quant_claims)
                                for _resp in patch.objection_responses:
                                    if _resp.objection_id not in responded_ids:
                                        continue  # already not credited
                                    _resp_combined = (_resp.response or "") + " " + (_resp.action or "")
                                    _resp_claim_ids = set(re.findall(r'\b[A-Z]\d{3}\b', _resp_combined))
                                    _demote_claims = _resp_claim_ids & _invalid_quant_set
                                    if _demote_claims:
                                        responded_ids.discard(_resp.objection_id)
                                        _not_addressed_ids.add(_resp.objection_id)
                                        _unrepaired_count += 1
                                        _prior_outcome = _resp_outcome_map.get(_resp.objection_id, "")
                                        if _prior_outcome == PATCH_VALIDATED_DIRECT:
                                            _direct_count -= 1
                                        elif _prior_outcome == PATCH_VALIDATED_INDIRECT:
                                            _indirect_count -= 1
                                        _unsupported_quant_count += 1
                                        for _cid in sorted(_demote_claims):
                                            _log_text(log_path, f"[PATCH-QUANT-INVALID] OBJ{_resp.objection_id} response demoted to UNREPAIRED — claim {_cid} introduced unsupported quantification")
                    # Expand responded_ids with supersession credit
                    forwarded_ids = set()
                    for rid in responded_ids:
                        live_id = ledger.supersession_map.get(rid)
                        if live_id and live_id != rid:
                            forwarded_ids.add(live_id)
                    if forwarded_ids:
                        responded_ids = responded_ids | forwarded_ids
                        _log_text(log_path, f"[PATCH-COVERAGE] Forwarded predecessor credit: {forwarded_ids}")
                    phantom_ids = responded_ids - actual_open_ids
                    missed_ids = actual_open_ids - responded_ids
                    if phantom_ids:
                        _log_text(log_path, f"[PATCH-COVERAGE] Phantom objection IDs in Strategist response: {phantom_ids}")
                    if missed_ids:
                        _log_text(log_path, f"[PATCH-COVERAGE] Open objections NOT addressed by Strategist: {missed_ids}")
                    coverage = len(responded_ids & actual_open_ids) / max(len(actual_open_ids), 1)
                    _covered_count = len(responded_ids & actual_open_ids)
                    _total_resp = len(patch.objection_responses) if (patch and patch.objection_responses) else 0
                    _log_text(log_path, f"[PATCH-SUMMARY] cycle={cycle + 1} total={_total_resp} direct={_direct_count} indirect={_indirect_count} mismatch={_mismatch_count} unrepaired={_unrepaired_count} unsupported_quant={_unsupported_quant_count} covered={_covered_count}/{len(actual_open_ids)}")
                    _not_addressed_open = _not_addressed_ids & actual_open_ids
                    _log_text(log_path, f"[PATCH-COVERAGE] Coverage: {coverage:.0%} ({_covered_count}/{len(actual_open_ids)}) — direct={_direct_count}, indirect={_indirect_count}, mismatch={_mismatch_count}, unrepaired={_unrepaired_count}")
                    if _not_addressed_open:
                        _log_text(log_path, f"[PATCH-COVERAGE] NOT addressed: {sorted(_not_addressed_open)}")
                    # Enforcement: if coverage < 50%, retry patch once with explicit missed IDs
                    if coverage < 0.5 and missed_ids:
                        missed_list = ", ".join(sorted(missed_ids))
                        _log_text(log_path, f"[PATCH-RETRY] Coverage below 50% — retrying with explicit missed objection IDs: {missed_list}")
                        retry_patch = await _call_and_validate(
                            _pick_strategist(clients, ledger),
                            STRATEGIST_SYSTEM,
                            _strategist_patch_prompt(task, ledger, latest_proposal, latest_objections, prior_audit)
                            + f"\n\nCRITICAL: You MUST address these objection IDs which you missed: {missed_list}"
                            + "\n\nREMINDER — QUANTIFICATION RULE: Do NOT introduce specific probabilities, percentages, or expected-value figures unless directly supported by an evidence item. Prefer qualitative dominance arguments over invented precision.",
                            StrategistPatch,
                            "Strategist",
                            ledger,
                            log_path,
                            trace_path,
                            max_retries=1,
                        )
                        if retry_patch is not None:
                            latest_proposal = _apply_patch(latest_proposal, retry_patch, ledger, log_path)
                            retry_responded: set[str] = set()
                            if retry_patch.objection_responses:
                                for _rresp in retry_patch.objection_responses:
                                    _robj = _obj_lookup.get(_rresp.objection_id)
                                    if _robj is None or _validate_response_semantic_match(_rresp, _robj, log_path):
                                        retry_responded.add(_rresp.objection_id)
                            newly_covered = retry_responded & missed_ids
                            _log_text(log_path, f"[PATCH-RETRY] Retry covered {len(newly_covered)}/{len(missed_ids)} previously missed objections")
                        else:
                            _log_text(log_path, "[PATCH-RETRY] Retry failed — proceeding with partial coverage")
                # Track which objections the Strategist has addressed
                # Forward credit from predecessor IDs to live successor IDs
                if patch and patch.objection_responses:
                    for resp in patch.objection_responses:
                        ledger.strategist_addressed_ids.add(resp.objection_id)
                        # Forward credit: if Strategist addressed a superseded ID, credit the live successor
                        live_id = ledger.supersession_map.get(resp.objection_id)
                        if live_id and live_id != resp.objection_id:
                            ledger.strategist_addressed_ids.add(live_id)
                            _log_text(log_path, f"[PATCH-FORWARD] {resp.objection_id} -> {live_id} (predecessor credit forwarded to live successor)")
                if retry_patch and retry_patch.objection_responses:
                    for resp in retry_patch.objection_responses:
                        ledger.strategist_addressed_ids.add(resp.objection_id)
                        live_id = ledger.supersession_map.get(resp.objection_id)
                        if live_id and live_id != resp.objection_id:
                            ledger.strategist_addressed_ids.add(live_id)
                            _log_text(log_path, f"[PATCH-FORWARD] {resp.objection_id} -> {live_id} (predecessor credit forwarded to live successor)")
                ledger.proposal_history.append(latest_proposal)
                cited = set()
                for claim in latest_proposal.claims:
                    cited.update(claim.evidence_ids)
                for rec in latest_proposal.recommendations:
                    cited.update(rec.evidence_ids)
                ledger.strategist_cited_evidence[cycle] = list(cited)
                _log_text(log_path, f"[EVIDENCE-ATTR] Cycle {cycle + 1}: Strategist cited {len(cited)} evidence IDs")
                dropped_claim_ids = list(patch.dropped_claim_ids)
                if retry_patch is not None and retry_patch.dropped_claim_ids:
                    dropped_claim_ids.extend(
                        claim_id for claim_id in retry_patch.dropped_claim_ids if claim_id not in dropped_claim_ids
                    )
            critic_prompt = _critic_prompt(latest_proposal, ledger, latest_audit)
            # V4 observability: log what Brain augmentation was injected into Critic prompt
            if ledger.brain_augmentation and cycle == 0:
                _aug = ledger.brain_augmentation
                _contested = _aug.get("contested_dimensions", [])
                _outcome = _aug.get("brain_outcome")
                if _contested:
                    _dim_labels = ", ".join(str(d)[:40] for d in _contested[:10])
                    _log_text(log_path, f"[BRAIN-AUGMENT-CONTESTED] count={len(_contested)} dims=[{_dim_labels}] → Critic prompt")
                if _outcome:
                    _log_text(log_path, f"[BRAIN-AUGMENT-CONTEXT] outcome={_outcome} convergence={_aug.get('brain_convergence', '?')} → Critic prompt")
                if not _contested and not _outcome:
                    _log_text(log_path, "[BRAIN-AUGMENT-CRITIC] no contested dims or outcome to inject")
            objection_pack = await _call_and_validate(
                clients["critic"],
                CRITIC_SYSTEM,
                critic_prompt,
                ObjectionPack,
                "Critic",
                ledger,
                log_path,
                trace_path,
                max_retries=ledger.max_repair_attempts,
            )
            if objection_pack is None:
                verdict = _system_failure("Critic failed to return valid objections.")
                break
            # Critic empty-output retry: if Critic returned 0 objections but live ones exist
            if len(objection_pack.objections) == 0:
                live_obj_ids = [oid for oid, s in ledger.objection_ledger.items() if s in ("OPEN", "UPHELD")]
                if live_obj_ids:
                    live_list = ", ".join(sorted(live_obj_ids))
                    _log_text(log_path, f"[CRITIC-RETRY] Empty Critic output with {len(live_obj_ids)} live objections — retrying with explicit IDs: {live_list}")
                    retry_critic = await _call_and_validate(
                        clients["critic"],
                        CRITIC_SYSTEM,
                        _critic_prompt(latest_proposal, ledger, latest_audit)
                        + f"\n\nCRITICAL: The following objections are still OPEN and must be explicitly restated or withdrawn: {live_list}",
                        ObjectionPack,
                        "Critic",
                        ledger,
                        log_path,
                        trace_path,
                        max_retries=1,
                    )
                    if retry_critic is not None and len(retry_critic.objections) > 0:
                        objection_pack = retry_critic
                        _log_text(log_path, f"[CRITIC-RETRY] Retry returned {len(objection_pack.objections)} objections")
                    else:
                        _log_text(log_path, f"[CRITIC-COLLAPSE] Critic returned empty even after retry — {len(live_obj_ids)} live objections orphaned")
                        # Apply confidence penalty for collapse
                        ledger.critic_collapse_penalty = getattr(ledger, "critic_collapse_penalty", 0.0) + 0.05
                        _log_text(log_path, f"[CRITIC-COLLAPSE] Confidence penalty: -{ledger.critic_collapse_penalty:.2f}")
            objection_pack = _stabilize_objection_ids(objection_pack, ledger, log_path, cycle=cycle)
            objection_pack = _apply_successor_materiality_gate(objection_pack, ledger, log_path, cycle=cycle, latest_audit=latest_audit)
            if cycle >= 2:
                known_ids = set(ledger.objection_ledger.keys())
                frozen_objs = []
                deferred_objs = []
                for obj in objection_pack.objections:
                    if obj.objection_id in known_ids:
                        frozen_objs.append(obj)
                    else:
                        obj.disposition = "DEFERRED"
                        obj.blocking_class = "RISK_ONLY"
                        obj.blocking = False
                        deferred_objs.append(obj)
                        ledger.objection_ledger[obj.objection_id] = "DEFERRED"
                        ledger.deferred_objection_store[obj.objection_id] = obj
                if deferred_objs:
                    _log_text(log_path, f"[FREEZE] Round {cycle + 1}: {len(deferred_objs)} new objections DEFERRED (freeze active)")
                    for d in deferred_objs:
                        _log_text(log_path, f"[DEFERRED] {d.objection_id}: {d.objection_text[:100]}")
                objection_pack = ObjectionPack(objections=frozen_objs)
            objection_pack = _filter_infeasible_objections(objection_pack, log_path)
            objection_pack = _classify_blocking(objection_pack, log_path)
            latest_objections = objection_pack
            ledger.objection_history.append(objection_pack)
            # Initialize new objections as OPEN so Brave can find them before Auditor runs
            for _obj in latest_objections.objections:
                if _obj.objection_id not in ledger.objection_ledger:
                    ledger.objection_ledger[_obj.objection_id] = "OPEN"
            # --- Controller-managed Brave retrieval ---
            if BRAVE_SEARCH_ENABLED:
                open_objs_for_search = [
                    obj
                    for oh in ledger.objection_history
                    for obj in oh.objections
                    if ledger.objection_ledger.get(obj.objection_id) in ("OPEN", "UPHELD")
                ]
                if open_objs_for_search:
                    brave_evidence = _brave_retrieve_evidence(open_objs_for_search, ledger, log_path)
                    for ev in brave_evidence:
                        ledger.evidence_ledger.append(ev)
                    if brave_evidence:
                        if cycle > 0:
                            for ev in brave_evidence:
                                ev.source_type = "web_search_next_cycle"
                            _log_text(log_path, f"[BRAVE-POST] Injected {len(brave_evidence)} post-Critic evidence (next-cycle attribution)")
                        else:
                            _log_text(log_path, f"[BRAVE] Injected {len(brave_evidence)} web evidence items into ledger")
                        _log_event(
                            trace_path,
                            "brave_retrieval",
                            {
                                "cycle": cycle,
                                "items_added": len(brave_evidence),
                                "timing": "post_critic",
                            },
                        )

            auditor_prompt = _auditor_prompt(ledger, latest_proposal, latest_objections, cycle=cycle)
            audit_snapshot = await _call_and_validate(
                clients["auditor"],
                AUDITOR_SYSTEM,
                auditor_prompt,
                AuditSnapshot,
                "Auditor",
                ledger,
                log_path,
                trace_path,
                max_retries=ledger.max_repair_attempts,
            )
            if audit_snapshot is None:
                verdict = _system_failure("Auditor failed to return a valid audit snapshot.")
                break
            audit_snapshot = _apply_evidence_ceiling(audit_snapshot, ledger, log_path)
            audit_snapshot = _backfill_missing_evidence(audit_snapshot, ledger, log_path)
            _update_objection_states(
                latest_objections,
                audit_snapshot,
                ledger,
                log_path,
                dropped_claims=dropped_claim_ids if cycle > 0 else None,
                cycle=cycle,
            )
            audit_snapshot = _reconcile_decisions(audit_snapshot, ledger, latest_proposal, log_path)
            # Surface DEFERRED objections in Auditor's unresolved accounting before gate checks.
            deferred_ids = [oid for oid, s in ledger.objection_ledger.items() if s == "DEFERRED"]
            if deferred_ids and audit_snapshot is not None:
                for did in deferred_ids:
                    if did not in audit_snapshot.unresolved_objections:
                        audit_snapshot.unresolved_objections.append(did)
                _log_text(log_path, f"[DEFERRED-UNRESOLVED] {len(deferred_ids)} deferred objections added to unresolved list: {deferred_ids}")
            # Degraded-cycle check: net-new usable evidence from ALL sources
            boundary_start = ledger.evidence_cycle_boundaries[-1] if ledger.evidence_cycle_boundaries else 0
            net_new_this_cycle = len(ledger.evidence_ledger) - boundary_start
            active_needing_evidence = [
                oid for oid, s in ledger.objection_ledger.items() if s in ("OPEN", "UPHELD")
            ]
            if active_needing_evidence and net_new_this_cycle == 0 and cycle > 0:
                ledger.degraded_cycles.append(cycle)
                _log_text(log_path, f"[DEGRADED] Cycle {cycle + 1}: {len(active_needing_evidence)} active objections but 0 net-new evidence from any source - cycle marked DEGRADED")
            elif active_needing_evidence and net_new_this_cycle > 0:
                _log_text(log_path, f"[EVIDENCE] Cycle {cycle + 1}: {net_new_this_cycle} net-new evidence items for {len(active_needing_evidence)} active objections")
            progress = _check_semantic_progress(ledger, audit_snapshot, log_path)
            latest_audit = audit_snapshot
            ledger.audit_history.append(audit_snapshot)

            # --- Sonar Pro deep-dive on unresolved blocking objections ---
            if SONAR_DEEP_ENABLED and sonar_client is not None and cycle < ledger.max_cycles - 1:
                unresolved_blocking = [
                    obj
                    for oh in ledger.objection_history
                    for obj in oh.objections
                    if ledger.objection_ledger.get(obj.objection_id) in ("OPEN", "UPHELD")
                    and getattr(obj, "blocking_class", "RISK_ONLY") == "BLOCKING"
                ]
                if unresolved_blocking:
                    sonar_evidence = await _sonar_deep_evidence(unresolved_blocking, ledger, log_path, sonar_client)
                    for ev in sonar_evidence:
                        ledger.evidence_ledger.append(ev)
                    if sonar_evidence:
                        _log_text(log_path, f"[SONAR-DEEP] Injected {len(sonar_evidence)} deep evidence items for next cycle")
                        _log_event(trace_path, "sonar_deep", {"cycle": cycle, "items": len(sonar_evidence)})
            # Search-gate observability: live evidence candidate detection (training_only only)
            _current_open_for_diag = [
                obj
                for oh in ledger.objection_history
                for obj in oh.objections
                if ledger.objection_ledger.get(obj.objection_id) in ("OPEN", "UPHELD")
            ]
            _maybe_emit_live_evidence_candidate(
                ledger, log_path, cycle, _current_open_for_diag, latest_audit
            )
            _maybe_escalate_search_mode(ledger, log_path, cycle, _current_open_for_diag)
            _log_event(trace_path, "progress_check", {"cycle": cycle, **progress})
            _log_text(
                log_path,
                f"[PROGRESS] Cycle {cycle + 1}: evidence={audit_snapshot.overall_evidence_quality}, "
                f"eligible={audit_snapshot.eligible_for_judgment}, progress={progress}",
            )

            no_open_blocking = not any(
                ledger.objection_ledger.get(o.objection_id, "OPEN") in ("OPEN", "UPHELD")
                for oh in ledger.objection_history
                for o in oh.objections
                if (o.blocking_class == "BLOCKING" or o.guard_held) and not o.non_gating
            )
            all_decided = audit_snapshot.recommendation_decisions and all(
                rd.decision != "NEEDS_EVIDENCE" for rd in audit_snapshot.recommendation_decisions
            )

            if no_open_blocking and all_decided:
                if cycle == 0 and len(ledger.objection_ledger) > 0:
                    _log_text(log_path, "[GATE] Cycle 0 raised objections — forcing one rebuttal cycle before Judge")
                elif (ledger.search_mode_escalated
                      and not ledger.search_diag_live_retrieval_attempted
                      and cycle < ledger.max_cycles - 1):
                    # Escalation triggered but retrieval hasn't happened yet — force one more cycle
                    # so the newly unlocked search mode can actually be used
                    _log_text(
                        log_path,
                        f"[GATE] Search escalation triggered but live retrieval not yet attempted "
                        f"— forcing post-escalation retrieval cycle before Judge"
                    )
                else:
                    _log_text(log_path, "[GATE] All blocking objections resolved, all recs decided -> Judge")
                    break

            if cycle >= 1 and not progress["progress"]:
                # Same protection: don't terminate on no-progress if escalation just fired unused
                if (ledger.search_mode_escalated
                    and not ledger.search_diag_live_retrieval_attempted
                    and cycle < ledger.max_cycles - 1):
                    _log_text(
                        log_path,
                        f"[GATE] No semantic progress but search escalation unused — "
                        f"forcing post-escalation retrieval cycle"
                    )
                else:
                    _log_text(log_path, f"[GATE] No semantic progress in cycle {cycle + 1} -> Judge")
                    break

            if cycle >= ledger.max_cycles - 1:
                _log_text(log_path, "[GATE] Max cycles reached -> Judge")
                break

            active_count = len([oid for oid, s in ledger.objection_ledger.items() if s in ("OPEN", "UPHELD")])
            _log_text(
                log_path,
                f"[GATE] Continuing - {active_count} active objections remain (OPEN + UPHELD)",
            )
            continue

        if verdict is None:
            if latest_proposal is None or latest_objections is None or latest_audit is None:
                verdict = _system_failure("Run ended without sufficient state to call Judge.")
            else:
                if latest_audit is not None and latest_audit.eligible_for_judgment:
                    open_objections = [
                        obj
                        for obj in latest_objections.objections
                        if ledger.objection_ledger.get(obj.objection_id, "OPEN") == "OPEN"
                    ]
                    if open_objections:
                        _log_text(
                            log_path,
                            f"[GATE] Critic confirmation: {len(open_objections)} open objections - running final Critic pass",
                        )
                        confirm_prompt = (
                            "FINAL CONFIRMATION PASS. Review ONLY these open objections against the latest proposal.\n"
                            f"Open objections: {_json_dump([o.model_dump() for o in open_objections])}\n"
                            f"Latest proposal: {_json_dump(latest_proposal.model_dump())}\n"
                            f"Evidence ledger: {_json_dump([e.model_dump() for e in ledger.evidence_ledger])}\n"
                            "If any HIGH severity objection is still valid and unaddressed, include it. "
                            "If resolved by evidence or proposal changes, do not include it."
                        )
                        confirm_pack = await _call_and_validate(
                            clients["critic"],
                            CRITIC_SYSTEM,
                            confirm_prompt,
                            ObjectionPack,
                            "Critic-Confirm",
                            ledger,
                            log_path,
                            trace_path,
                            max_retries=1,
                        )
                        if confirm_pack is not None:
                            confirm_pack = _filter_infeasible_objections(confirm_pack, log_path)
                            reopened_high = [o for o in confirm_pack.objections if o.severity == "HIGH"]
                            if reopened_high:
                                _log_text(
                                    log_path,
                                    f"[GATE] Critic reopened {len(reopened_high)} HIGH objections - demoting to PARTIAL_CONSENSUS ceiling",
                                )
                                latest_audit.eligible_for_judgment = True
                                if latest_audit.overall_evidence_quality == "HIGH":
                                    latest_audit.overall_evidence_quality = "MEDIUM"
                            else:
                                _log_text(log_path, "[GATE] Critic confirmation: no HIGH objections reopened - proceeding to Judge")
                    else:
                        _log_text(log_path, "[GATE] Critic confirmation: no open objections - proceeding to Judge")
                # Cardinality guard: enforce "top N" from task if specified
                import re as _re
                _top_n_match = _re.search(r'top\s+(\d+)', task.lower())
                if _top_n_match:
                    intended_n = int(_top_n_match.group(1))
                    active_recs = [r for r in latest_proposal.recommendations if r.rank is not None]
                    if len(active_recs) > intended_n:
                        # Sort by rank, keep only top N
                        active_recs.sort(key=lambda r: r.rank if r.rank is not None else 9999)
                        keep_ids = {r.item_id for r in active_recs[:intended_n]}
                        pruned = [r.item_id for r in latest_proposal.recommendations if r.item_id not in keep_ids]
                        latest_proposal.recommendations = [r for r in latest_proposal.recommendations if r.item_id in keep_ids]
                        _log_text(log_path, f"[CARDINALITY] Pruned {len(pruned)} excess recommendations to match 'top {intended_n}': {pruned}")
                    elif len(latest_proposal.recommendations) > intended_n:
                        # Some have rank=None (ghosts that survived) — prune those
                        ranked = [r for r in latest_proposal.recommendations if r.rank is not None]
                        unranked = [r for r in latest_proposal.recommendations if r.rank is None]
                        if unranked:
                            latest_proposal.recommendations = ranked
                            _log_text(log_path, f"[CARDINALITY] Removed {len(unranked)} unranked ghost recommendations: {[r.item_id for r in unranked]}")
                judge_prompt = _judge_prompt(task, ledger, latest_proposal, latest_audit, latest_objections)
                judge_verdict = await _call_and_validate(
                    clients["judge"],
                    JUDGE_SYSTEM,
                    judge_prompt,
                    ConsensusVerdict,
                    "Judge",
                    ledger,
                    log_path,
                    trace_path,
                    max_retries=ledger.max_repair_attempts,
                )
                if judge_verdict is None:
                    verdict = _system_failure("Judge failed to return a valid verdict.")
                else:
                    verdict = _build_final_verdict(judge_verdict, latest_audit, ledger, log_path, latest_proposal)
        _slp_trace: dict[str, Any] = {}
        if verdict is not None and verdict.highest_standalone_leverage:
            _slp_trace["slp_highlight_item"] = verdict.highest_standalone_leverage.get("item_id")
            _slp_trace["slp_highlight_confidence"] = verdict.highest_standalone_leverage.get("confidence")
            _slp_trace["slp_profile_count"] = len(verdict.standalone_leverage_profiles)
        _search_trace: dict[str, Any] = {
            "upfront_selected_mode": ledger.search_diag_upfront_mode or ledger.search_mode,
            "final_mode": ledger.search_mode,
            "search_mode_escalated": getattr(ledger, "search_mode_escalated", False),
            "live_retrieval_ever_attempted": ledger.search_diag_live_retrieval_attempted,
        }
        _choice_trace: dict[str, Any] = {
            "choice_mode": ledger.choice_mode,
        }
        if verdict and verdict.selected_option:
            _choice_trace["selected_option"] = verdict.selected_option.get("item_id")
            _choice_trace["selected_source_type"] = verdict.selected_option.get("source_type")
        _log_event(trace_path, "run_completed", {
            "run_id": ledger.run_id,
            "status": verdict.status if verdict else "NONE",
            **_slp_trace,
            **_search_trace,
            **_choice_trace,
        })
        _emit_search_diagnostics(ledger, log_path)
        if verdict is not None:
            _print_transcript(ledger)
            _print_verdict(verdict)
        return verdict
    finally:
        for client in clients.values():
            close_fn = getattr(client, "close", None)
            if close_fn is None:
                continue
            result = close_fn()
            if asyncio.iscoroutine(result):
                await result
        if sonar_client is not None:
            close_fn = getattr(sonar_client, "close", None)
            if close_fn is not None:
                result = close_fn()
                if asyncio.iscoroutine(result):
                    await result

if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "Default task"
    asyncio.run(run_chamber_v3(task))
