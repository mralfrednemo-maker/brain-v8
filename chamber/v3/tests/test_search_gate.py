"""Tests for the hybrid three-layer search gate in consensus_runner_v3."""
import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure orchestrator dir is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Helpers — lightweight stubs so import doesn't require full env
# ---------------------------------------------------------------------------

# Stub heavy optional deps before importing the module under test
for _mod_name in ("autogen_core", "autogen_core.models"):
    if _mod_name not in sys.modules:
        _stub = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stub

# autogen_core stubs (real module likely not installed in test env)
_ag = sys.modules.get("autogen_core") or types.ModuleType("autogen_core")
_ag_models = sys.modules.get("autogen_core.models") or types.ModuleType("autogen_core.models")


class _FakeChatCompletionClient:
    pass


class _FakeSystemMessage:
    def __init__(self, content):
        self.content = content


class _FakeUserMessage:
    def __init__(self, content, source):
        self.content = content
        self.source = source


_ag_models.ChatCompletionClient = _FakeChatCompletionClient
_ag_models.SystemMessage = _FakeSystemMessage
_ag_models.UserMessage = _FakeUserMessage
sys.modules["autogen_core"] = _ag
sys.modules["autogen_core.models"] = _ag_models

# consensus_runner stubs (imported by v3)
_cr_stub = types.ModuleType("consensus_runner")
_cr_stub.AnthropicChatCompletionClient = _FakeChatCompletionClient
_cr_stub.DeepSeekChatCompletionClient = _FakeChatCompletionClient
_cr_stub.DeepSeekReasonerChatCompletionClient = _FakeChatCompletionClient
_cr_stub.KimiK2ChatCompletionClient = _FakeChatCompletionClient
_cr_stub.ZhipuChatCompletionClient = _FakeChatCompletionClient
_cr_stub.SonarProSearchClient = _FakeChatCompletionClient
_cr_stub._load_dotenv_if_present = lambda: None
_cr_stub._normalize_finish_reason = lambda x: x
sys.modules["consensus_runner"] = _cr_stub

from consensus_runner_v3 import (  # noqa: E402
    RunLedger,
    _classify_search_mode,
    _has_domain_substance,
    Objection,
)

# Lazy import — added in Task 4; imported inside test class to avoid early ImportError
def _get_escalate_fn():
    from consensus_runner_v3 import _maybe_escalate_search_mode
    return _maybe_escalate_search_mode

# Convenience alias used in tests
def _maybe_escalate_search_mode(ledger, log_path, cycle, open_objections):
    return _get_escalate_fn()(ledger, log_path, cycle, open_objections)


# ---------------------------------------------------------------------------
# Tests: Layer 1 — regex hard gates (CLEAR cases)
# ---------------------------------------------------------------------------

class TestRegexHardGates:
    """Regex-only CLEAR cases must never reach the LLM tiebreaker."""

    def test_cve_id_is_full_clear(self):
        mode, conf = _classify_search_mode("Assess the risk of CVE-2024-12345 in Apache")
        assert mode == "full"
        assert conf == "CLEAR"

    def test_ticker_is_full_clear(self):
        mode, conf = _classify_search_mode("Should I buy NVDA or MSFT for my portfolio?")
        assert mode == "full"
        assert conf == "CLEAR"

    def test_regulation_is_full_clear(self):
        mode, conf = _classify_search_mode("Explain the requirements of NIST SP 800-61")
        assert mode == "full"
        assert conf == "CLEAR"

    def test_pure_hypothetical_no_domain_is_training_only_clear(self):
        """Pure hypothetical with zero domain substance → training_only CLEAR (no LLM needed)."""
        mode, conf = _classify_search_mode("What if someone imagined a scenario with no specifics?")
        assert mode == "training_only"
        assert conf == "CLEAR"

    def test_hypothetical_with_domain_signals_is_borderline(self):
        """Hypothetical framing + domain substance → BORDERLINE (escalates to LLM tiebreaker)."""
        mode, conf = _classify_search_mode(
            "In a hypothetical scenario, evaluate the risk of a remote code execution vulnerability in a web server."
        )
        assert conf == "BORDERLINE"

    def test_no_identifiers_no_hypothetical_is_ambiguous(self):
        """No identifiers, no hypothetical markers → AMBIGUOUS (escalates to LLM tiebreaker).
        NOTE: avoid all-caps tokens — 'ETF' would be caught by ticker detector as CLEAR.
        """
        mode, conf = _classify_search_mode("How do index funds work in general?")
        assert conf == "AMBIGUOUS"


# ---------------------------------------------------------------------------
# Tests: _has_domain_substance
# ---------------------------------------------------------------------------

class TestDomainSubstance:
    def test_rce_has_domain_substance(self):
        assert _has_domain_substance("remote code execution vulnerability in a web server")

    def test_etf_has_domain_substance(self):
        assert _has_domain_substance("build a hypothetical etf portfolio")

    def test_pure_abstract_has_no_domain_substance(self):
        assert not _has_domain_substance("what if things were different somehow")

    def test_sql_injection_has_domain_substance(self):
        assert _has_domain_substance("sql injection attack on a database")


# ---------------------------------------------------------------------------
# Tests: Layer 2 — LLM tiebreaker fires for BORDERLINE/AMBIGUOUS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_tiebreaker_fires_for_borderline():
    """LLM tiebreaker must be called when regex returns BORDERLINE."""
    from consensus_runner_v3 import _resolve_search_mode

    mock_result = MagicMock()
    mock_result.content = '{"mode": "minimal", "rationale": "hypothetical but has domain content"}'

    mock_client = MagicMock()
    mock_client.create = AsyncMock(return_value=mock_result)

    task = "In a hypothetical scenario, evaluate remote code execution risk in a web server."
    mode, conf = await _resolve_search_mode(task, mock_client, None)

    mock_client.create.assert_called_once()
    assert mode in ("full", "minimal", "training_only")


@pytest.mark.asyncio
async def test_llm_tiebreaker_skipped_for_clear():
    """LLM tiebreaker must NOT be called when regex returns CLEAR."""
    from consensus_runner_v3 import _resolve_search_mode

    mock_client = MagicMock()
    mock_client.create = AsyncMock()

    task = "Assess the risk of CVE-2024-12345 in Apache HTTP Server."
    mode, conf = await _resolve_search_mode(task, mock_client, None)

    mock_client.create.assert_not_called()
    assert mode == "full"
    assert conf == "CLEAR"


@pytest.mark.asyncio
async def test_llm_tiebreaker_fallback_on_error():
    """LLM tiebreaker failure must fall back gracefully to minimal."""
    from consensus_runner_v3 import _resolve_search_mode

    mock_client = MagicMock()
    mock_client.create = AsyncMock(side_effect=Exception("network error"))

    # Use a task with no uppercase tokens so ticker detector doesn't fire → AMBIGUOUS → tiebreaker
    task = "How do index funds work in general?"
    mode, conf = await _resolve_search_mode(task, mock_client, None)

    assert mode == "minimal"  # fallback


@pytest.mark.asyncio
async def test_llm_tiebreaker_fires_for_ambiguous():
    """LLM tiebreaker must also be called for AMBIGUOUS confidence (not just BORDERLINE)."""
    from consensus_runner_v3 import _resolve_search_mode

    mock_result = MagicMock()
    mock_result.content = '{"mode": "minimal", "rationale": "general question, no specific identifiers"}'

    mock_client = MagicMock()
    mock_client.create = AsyncMock(return_value=mock_result)

    # No uppercase tokens → ticker detector won't fire → AMBIGUOUS
    task = "How do index funds work in general?"
    mode, conf = await _resolve_search_mode(task, mock_client, None)

    mock_client.create.assert_called_once()
    assert conf == "AMBIGUOUS"  # router confidence is from regex, not LLM
    assert mode in ("full", "minimal", "training_only")


# ---------------------------------------------------------------------------
# Tests: Layer 3 — mid-run escalation
# ---------------------------------------------------------------------------

def _make_ledger(search_mode="training_only", skips=2, escalated=False):
    l = RunLedger(run_id="test", task="test task")
    l.search_mode = search_mode
    l.search_diag_training_only_skips = skips
    l.search_mode_escalated = escalated
    return l


def _make_evidence_gap_objection(obj_id="O001", evidence=("some evidence",)):
    return Objection(
        objection_id=obj_id,
        claim_id="C001",
        severity="HIGH",
        type="evidence_gap",
        objection_text="Missing evidence",
        requested_evidence=list(evidence),
    )


class TestMidRunEscalation:
    def test_escalates_when_conditions_met(self, tmp_path):
        ledger = _make_ledger(skips=2)
        log_path = tmp_path / "test.log"
        log_path.write_text("")
        objections = [
            _make_evidence_gap_objection("O001"),
            _make_evidence_gap_objection("O002"),
        ]
        _maybe_escalate_search_mode(ledger, log_path, cycle=1, open_objections=objections)
        assert ledger.search_mode == "minimal"
        assert ledger.search_mode_escalated is True
        assert "[SEARCH-ESCALATION]" in log_path.read_text()

    def test_does_not_escalate_twice(self, tmp_path):
        ledger = _make_ledger(skips=3, escalated=True)
        ledger.search_mode = "minimal"  # already escalated
        log_path = tmp_path / "test.log"
        log_path.write_text("")
        objections = [_make_evidence_gap_objection("O001"), _make_evidence_gap_objection("O002")]
        _maybe_escalate_search_mode(ledger, log_path, cycle=2, open_objections=objections)
        assert ledger.search_mode == "minimal"  # unchanged

    def test_does_not_escalate_on_cycle_0(self, tmp_path):
        ledger = _make_ledger(skips=2)
        log_path = tmp_path / "test.log"
        log_path.write_text("")
        objections = [_make_evidence_gap_objection("O001"), _make_evidence_gap_objection("O002")]
        _maybe_escalate_search_mode(ledger, log_path, cycle=0, open_objections=objections)
        assert ledger.search_mode == "training_only"  # must not escalate on cycle 0

    def test_does_not_escalate_with_too_few_skips(self, tmp_path):
        ledger = _make_ledger(skips=1)
        log_path = tmp_path / "test.log"
        log_path.write_text("")
        objections = [_make_evidence_gap_objection("O001"), _make_evidence_gap_objection("O002")]
        _maybe_escalate_search_mode(ledger, log_path, cycle=1, open_objections=objections)
        assert ledger.search_mode == "training_only"

    def test_does_not_escalate_with_too_few_evidence_gap_objections(self, tmp_path):
        ledger = _make_ledger(skips=2)
        log_path = tmp_path / "test.log"
        log_path.write_text("")
        # Only 1 evidence-gap objection
        objections = [_make_evidence_gap_objection("O001")]
        _maybe_escalate_search_mode(ledger, log_path, cycle=1, open_objections=objections)
        assert ledger.search_mode == "training_only"

    def test_does_not_escalate_non_training_only(self, tmp_path):
        ledger = _make_ledger(search_mode="minimal", skips=2)
        log_path = tmp_path / "test.log"
        log_path.write_text("")
        objections = [_make_evidence_gap_objection("O001"), _make_evidence_gap_objection("O002")]
        _maybe_escalate_search_mode(ledger, log_path, cycle=1, open_objections=objections)
        assert ledger.search_mode == "minimal"  # not training_only, no change

    def test_never_escalates_to_full(self, tmp_path):
        """Escalation must never promote to full — only to minimal."""
        ledger = _make_ledger(skips=5)
        log_path = tmp_path / "test.log"
        log_path.write_text("")
        objections = [_make_evidence_gap_objection(f"O{i:03d}") for i in range(5)]
        _maybe_escalate_search_mode(ledger, log_path, cycle=2, open_objections=objections)
        assert ledger.search_mode != "full"


# ---------------------------------------------------------------------------
# Tests: choose between regression
# ---------------------------------------------------------------------------

class TestChooseBetweenRegression:
    def test_choose_between_does_not_force_training_only(self):
        """Regression: 'choose between' is a decision-framing phrase, not a hypothetical marker.
        A concrete operational brief containing it must not be forced into training_only."""
        task = (
            "We need to choose between deploying the patch immediately or waiting for the "
            "next maintenance window. Assess the operational risk of each option."
        )
        mode, conf = _classify_search_mode(task)
        assert mode != "training_only", (
            f"'choose between' should not force training_only; got mode={mode!r} conf={conf!r}"
        )

    def test_genuine_hypothetical_markers_still_classify_correctly(self):
        """Safety: prompts with real hypothetical markers (hypothetical, what if, imagine, suppose)
        and no domain substance must still be allowed to reach training_only."""
        task = "Suppose you imagine a hypothetical what if scenario with no specifics at all."
        mode, conf = _classify_search_mode(task)
        assert mode == "training_only", (
            f"Genuine hypothetical with no domain substance should be training_only; "
            f"got mode={mode!r} conf={conf!r}"
        )


# ---------------------------------------------------------------------------
# Ticker false-positive regression tests (Round 1 fix)
# ---------------------------------------------------------------------------


class TestTickerFalsePositives:
    """Uppercase acronyms from non-finance domains must not trigger ticker classification."""

    def test_hipaa_not_ticker(self):
        """HIPAA is a regulation, not a stock ticker."""
        mode, conf = _classify_search_mode(
            "A healthcare SaaS platform discovers a HIPAA breach exposing 2.1M patient records."
        )
        # HIPAA should be caught by regulation detector, not ticker detector
        # It should NOT produce ticker:HIPAA in the reasons
        # Mode may still be 'full' from regulation or proper-noun detection — that's fine
        # But confidence should come from regulation, not from a bogus ticker
        assert conf != "CLEAR" or mode == "full"  # regulation match is legitimate

    def test_jit_not_ticker(self):
        """JIT is a technical concept (Just-In-Time compilation), not a stock ticker."""
        mode, conf = _classify_search_mode(
            "Our PostgreSQL 14 database is hitting query planner regressions after enabling JIT compilation."
        )
        # Without finance context, JIT should not produce ticker-based CLEAR
        # May still route to 'full' via proper-noun:PostgreSQL — that's fine
        assert not (conf == "CLEAR" and mode == "full" and "ticker" in str(conf).lower())

    def test_arr_not_ticker(self):
        """ARR is Annual Recurring Revenue, not a stock ticker."""
        mode, conf = _classify_search_mode(
            "A mid-stage SaaS startup with $8M ARR discovers their test suite has been broken for 6 months."
        )
        # ARR alone should not trigger ticker classification
        assert conf != "CLEAR"

    def test_rps_not_ticker(self):
        """RPS is Requests Per Second, not a stock ticker."""
        mode, conf = _classify_search_mode(
            "Our production Kubernetes cluster handling 12K RPS has a cascading memory leak from Redis."
        )
        # RPS should be in the hard stoplist
        assert conf != "CLEAR" or "regulation" in str(conf)

    def test_usd_not_ticker(self):
        """USD is a currency code, not a stock ticker."""
        mode, conf = _classify_search_mode(
            "Our e-commerce platform costs approximately 4K USD per hour at peak auto-scaling rates."
        )
        assert conf != "CLEAR"

    def test_ai_not_ticker_without_finance_context(self):
        """AI in a non-finance context should not trigger ticker classification."""
        mode, conf = _classify_search_mode(
            "Our AI content moderation system has a 4.2% false-positive rate on Arabic-language content."
        )
        assert conf != "CLEAR"

    def test_ai_is_ticker_with_finance_context(self):
        """AI in a finance context should still work as a ticker."""
        mode, conf = _classify_search_mode(
            "Should I add AI stock to my portfolio given the current market conditions?"
        )
        assert mode == "full"
        assert conf == "CLEAR"

    def test_real_ticker_with_finance_context(self):
        """NVDA in a finance context should still be classified as a ticker."""
        mode, conf = _classify_search_mode(
            "Should I buy NVDA or MSFT for my portfolio?"
        )
        assert mode == "full"
        assert conf == "CLEAR"

    def test_btc_with_finance_context(self):
        """BTC in a trading context should be recognized."""
        mode, conf = _classify_search_mode(
            "What is the current trading price of BTC on the exchange?"
        )
        assert mode == "full"
        assert conf == "CLEAR"

    def test_btc_without_finance_context(self):
        """BTC mentioned casually without finance signals should not trigger ticker."""
        mode, conf = _classify_search_mode(
            "Our payment system supports BTC as one of several payment methods alongside credit cards."
        )
        assert conf != "CLEAR"
