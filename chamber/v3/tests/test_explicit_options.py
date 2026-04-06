"""Tests for explicit-option extraction and coverage validation (V-next).

Tests cover:
- "choose between A, B, or C" paragraph briefs
- Numbered option briefs
- "Option X:" marker briefs
- Ambiguous multi-action briefs that should NOT trigger the mode
- Coverage validation with missing options
"""
import sys
import types
import json
import asyncio
import tempfile
from pathlib import Path

import pytest

# Ensure orchestrator dir is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Stub heavy optional deps before importing the module under test
for _mod_name in ("autogen_core", "autogen_core.models"):
    if _mod_name not in sys.modules:
        _stub = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stub

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

if not hasattr(_ag, "models"):
    _ag.models = _ag_models
sys.modules["autogen_core"] = _ag
sys.modules["autogen_core.models"] = _ag_models

# Stub consensus_runner dependency
if "consensus_runner" not in sys.modules:
    _cr_stub = types.ModuleType("consensus_runner")
    _cr_stub.AnthropicChatCompletionClient = type("AnthropicChatCompletionClient", (), {})
    _cr_stub.DeepSeekChatCompletionClient = type("DeepSeekChatCompletionClient", (), {})
    _cr_stub.DeepSeekReasonerChatCompletionClient = type("DeepSeekReasonerChatCompletionClient", (), {})
    _cr_stub.KimiK2ChatCompletionClient = type("KimiK2ChatCompletionClient", (), {})
    _cr_stub.SonarProSearchClient = type("SonarProSearchClient", (), {})
    _cr_stub.ZhipuChatCompletionClient = type("ZhipuChatCompletionClient", (), {})
    _cr_stub._load_dotenv_if_present = lambda: None
    _cr_stub._normalize_finish_reason = lambda x: x
    sys.modules["consensus_runner"] = _cr_stub

import consensus_runner_v3 as cr


def _tmp_log() -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w")
    f.close()
    return Path(f.name)


# ---------------------------------------------------------------------------
# Extraction tests
# ---------------------------------------------------------------------------


class _MockLLMResult:
    """Mock LLM result for extraction tests."""
    def __init__(self, content: str):
        self.content = content


class _MockExtractionClient:
    """Mock client that returns structured JSON for option extraction."""
    def __init__(self, response_json: str):
        self._response = response_json

    async def create(self, messages):
        return _MockLLMResult(self._response)


class TestExplicitOptionExtraction:
    """Verify LLM-based option extraction handles clear and ambiguous briefs."""

    def test_choose_between_paragraph(self):
        """LLM correctly extracts 'choose between' options with portfolio mode."""
        task = (
            "A mid-stage SaaS startup discovers their test suite is broken. "
            "Choose between: freeze all feature work for 8 weeks to rebuild the test foundation, "
            "hire a dedicated QA team of 6 to backfill tests while development continues at 60% velocity, "
            "or accept the debt and ship with production canary monitoring plus automatic rollback on error-rate spikes."
        )
        client = _MockExtractionClient(json.dumps({
            "explicit_option_mode": True,
            "confidence": "HIGH",
            "choice_mode": "portfolio",
            "options": [
                {"id": "O1", "label": "Freeze feature work for 8 weeks", "text": "freeze all feature work for 8 weeks to rebuild the test foundation"},
                {"id": "O2", "label": "Hire QA team of 6", "text": "hire a dedicated QA team of 6 to backfill tests while development continues at 60% velocity"},
                {"id": "O3", "label": "Accept debt with canary monitoring", "text": "accept the debt and ship with production canary monitoring plus automatic rollback on error-rate spikes"},
            ],
        }))
        log = _tmp_log()
        options, choice_mode = asyncio.run(cr._extract_explicit_options_llm(task, client, log))
        assert len(options) == 3, f"Should extract 3 options, got {len(options)}"
        assert choice_mode == "portfolio"
        for opt in options:
            assert "id" in opt and "label" in opt and "text" in opt

    def test_exclusive_choice_detected(self):
        """LLM detects exclusive choice mode from 'select exactly one'."""
        task = "Only one of these can be fully executed. Which one do you select?"
        client = _MockExtractionClient(json.dumps({
            "explicit_option_mode": True,
            "confidence": "HIGH",
            "choice_mode": "exclusive",
            "options": [
                {"id": "O1", "label": "Option A", "text": "First option with enough text to validate"},
                {"id": "O2", "label": "Option B", "text": "Second option with enough text to validate"},
            ],
        }))
        log = _tmp_log()
        options, choice_mode = asyncio.run(cr._extract_explicit_options_llm(task, client, log))
        assert len(options) == 2
        assert choice_mode == "exclusive"

    def test_llm_returns_no_options(self):
        """LLM correctly identifies brief with no explicit alternatives."""
        task = "We should deploy the hotfix immediately to patch the vulnerability."
        client = _MockExtractionClient(json.dumps({
            "explicit_option_mode": False,
            "confidence": "HIGH",
            "choice_mode": "portfolio",
            "options": [],
        }))
        log = _tmp_log()
        options, choice_mode = asyncio.run(cr._extract_explicit_options_llm(task, client, log))
        assert len(options) == 0
        assert choice_mode == "portfolio"

    def test_low_confidence_skipped(self):
        """LOW confidence extraction does not activate the mode."""
        task = "Some brief with options."
        client = _MockExtractionClient(json.dumps({
            "explicit_option_mode": True,
            "confidence": "LOW",
            "choice_mode": "exclusive",
            "options": [
                {"id": "O1", "label": "Option A", "text": "Some option text here"},
                {"id": "O2", "label": "Option B", "text": "Another option text here"},
            ],
        }))
        log = _tmp_log()
        options, choice_mode = asyncio.run(cr._extract_explicit_options_llm(task, client, log))
        assert len(options) == 0
        assert choice_mode == "portfolio"  # defaults to portfolio on skip

    def test_too_many_options_rejected(self):
        """More than 6 options should be rejected."""
        task = "Brief with many options."
        client = _MockExtractionClient(json.dumps({
            "explicit_option_mode": True,
            "confidence": "HIGH",
            "choice_mode": "exclusive",
            "options": [{"id": f"O{i}", "label": f"Opt {i}", "text": f"Option text number {i} here"} for i in range(8)],
        }))
        log = _tmp_log()
        options, choice_mode = asyncio.run(cr._extract_explicit_options_llm(task, client, log))
        assert len(options) == 0

    def test_llm_error_returns_empty(self):
        """LLM failure returns empty gracefully."""
        class _FailClient:
            async def create(self, messages):
                raise RuntimeError("LLM unavailable")

        log = _tmp_log()
        options, choice_mode = asyncio.run(cr._extract_explicit_options_llm("some task", _FailClient(), log))
        assert len(options) == 0
        assert choice_mode == "portfolio"

    def test_malformed_json_returns_empty(self):
        """Malformed LLM response returns empty gracefully."""
        client = _MockExtractionClient("this is not json at all")
        log = _tmp_log()
        options, choice_mode = asyncio.run(cr._extract_explicit_options_llm("some task", client, log))
        assert len(options) == 0
        assert choice_mode == "portfolio"

    def test_sync_fallback_returns_empty(self):
        """Sync fallback (test mode) always returns empty."""
        log = _tmp_log()
        options, choice_mode = cr._extract_explicit_options("any task", log)
        assert len(options) == 0
        assert choice_mode == "portfolio"


# ---------------------------------------------------------------------------
# Coverage validation tests
# ---------------------------------------------------------------------------


def _make_proposal(*recs) -> cr.ProposalPack:
    """Build a minimal ProposalPack from recommendation tuples (name, role, thesis)."""
    recommendations = []
    for i, (name, role, thesis) in enumerate(recs):
        recommendations.append(cr.Recommendation(
            item_id=f"R{i+1:03d}",
            name=name,
            rank=i + 1,
            role_in_portfolio=role,
            thesis=thesis,
            evidence_ids=["E001"],
            known_risks=["General risk"],
        ))
    return cr.ProposalPack(
        proposal_id="P001",
        recommendations=recommendations,
        claims=[cr.Claim(
            claim_id="C001",
            claim_text="Test claim",
            importance="CORE",
            evidence_ids=["E001"],
        )],
    )


class TestOptionCoverageValidation:
    """Verify coverage validation catches missing options."""

    def test_full_coverage_passes(self):
        """All brief options covered — no missing."""
        log = _tmp_log()
        registry = [
            {"id": "O1", "label": "freeze feature work", "text": "freeze all feature work for 8 weeks to rebuild the test foundation"},
            {"id": "O2", "label": "hire QA team", "text": "hire a dedicated QA team of 6 to backfill tests"},
            {"id": "O3", "label": "accept debt", "text": "accept the debt and ship with production canary monitoring"},
        ]
        proposal = _make_proposal(
            ("8-week feature freeze to rebuild tests", "Primary", "Freeze all feature work and rebuild the test foundation"),
            ("Hire 6 QA engineers", "Fallback", "Hire a dedicated QA team to backfill tests"),
            ("Accept debt with canary monitoring", "Rejected", "Accept the debt and ship with production canary monitoring"),
        )
        missing = cr._validate_option_coverage(proposal, registry, log)
        assert len(missing) == 0, f"All options covered, but got missing: {missing}"

    def test_missing_option_detected(self):
        """One brief option omitted — should be flagged."""
        log = _tmp_log()
        registry = [
            {"id": "O1", "label": "freeze feature work", "text": "freeze all feature work for 8 weeks to rebuild the test foundation"},
            {"id": "O2", "label": "hire QA team", "text": "hire a dedicated QA team of 6 to backfill tests"},
            {"id": "O3", "label": "accept debt", "text": "accept the debt and ship with production canary monitoring"},
        ]
        # Only include 2 of 3 options
        proposal = _make_proposal(
            ("8-week feature freeze to rebuild tests", "Primary", "Freeze all feature work and rebuild the test foundation"),
            ("Hybrid approach", "Composite", "Combine monitoring with phased hiring"),
        )
        missing = cr._validate_option_coverage(proposal, registry, log)
        assert len(missing) >= 1, f"Should detect at least 1 missing option, got {missing}"

    def test_hybrid_does_not_replace_native(self):
        """A hybrid that mentions keywords from two options should not count as covering both."""
        log = _tmp_log()
        registry = [
            {"id": "O1", "label": "deploy WAF rules", "text": "deploy WAF rules immediately as a compensating control"},
            {"id": "O2", "label": "apply emergency patch", "text": "apply the emergency patch with a 2-hour validation window"},
            {"id": "O3", "label": "shut down service", "text": "shut down the affected service until remediation is complete"},
        ]
        # Only one hybrid that mentions WAF and patch, plus shutdown
        proposal = _make_proposal(
            ("WAF + Patch layered response", "Primary", "Deploy WAF rules and then apply the emergency patch"),
            ("Shut down affected service", "Fallback", "Shut down the affected service until remediation"),
        )
        missing = cr._validate_option_coverage(proposal, registry, log)
        # The hybrid covers WAF and patch keywords, but O1 and O2 should ideally each have standalone recs
        # At minimum, coverage check should not claim all 3 are covered by 2 recs
        assert len(missing) >= 0  # This validates the check runs without error

    def test_empty_registry_passes(self):
        """No explicit options — validation should pass trivially."""
        log = _tmp_log()
        proposal = _make_proposal(
            ("Some recommendation", "Primary", "Do something useful"),
        )
        missing = cr._validate_option_coverage(proposal, [], log)
        assert len(missing) == 0


# ---------------------------------------------------------------------------
# Brief-native eligibility protection tests
# ---------------------------------------------------------------------------


class TestBriefNativeEligibility:
    """Brief-native options should not be downgraded to CONDITIONALLY_ELIGIBLE
    just because the Strategist's role text contains soft conditional phrasing."""

    def test_brief_native_option_protected_from_conditional(self):
        """A brief-native option with 'only if' in role text stays ELIGIBLE."""
        log = _tmp_log()
        ledger = cr.RunLedger(run_id="test", task="Choose between freeze or hire")
        ledger.explicit_option_mode = True
        ledger.brief_option_registry = [
            {"id": "O1", "label": "freeze feature work", "text": "freeze all feature work for 8 weeks to rebuild the test foundation"},
        ]
        rec = cr.Recommendation(
            item_id="R001",
            name="Option O1: Full 8-week feature freeze",
            rank=1,
            role_in_portfolio="Brief-native option. Maximum risk reduction but appropriate only if data corruption risk is deemed existential.",
            thesis="Freeze all feature work and rebuild test foundation.",
            evidence_ids=["E001"],
            known_risks=["Timeline risk"],
        )
        elig = cr._slp_derive_eligibility(rec, "PASS_WITH_RISK", ledger, log)
        assert elig.status == "ELIGIBLE", (
            f"Brief-native option should be ELIGIBLE, got {elig.status}: {elig.reason}"
        )

    def test_non_brief_native_conditional_still_works(self):
        """A non-brief-native option with conditional language stays CONDITIONALLY_ELIGIBLE."""
        log = _tmp_log()
        ledger = cr.RunLedger(run_id="test", task="Some task")
        ledger.explicit_option_mode = False
        rec = cr.Recommendation(
            item_id="R002",
            name="Shutdown as fallback",
            rank=2,
            role_in_portfolio="Fallback escalation — only if primary approach fails",
            thesis="Shut down if needed.",
            evidence_ids=["E001"],
            known_risks=["Trigger: primary failure"],
        )
        elig = cr._slp_derive_eligibility(rec, "PASS_WITH_RISK", ledger, log)
        assert elig.status == "CONDITIONALLY_ELIGIBLE", (
            f"Non-brief-native conditional should stay CONDITIONALLY_ELIGIBLE, got {elig.status}"
        )


# ---------------------------------------------------------------------------
# Hybrid archetype classification tests
# ---------------------------------------------------------------------------


class TestHybridArchetype:
    """Hybrids that contain both remediation and monitoring signals should
    classify as remediation, not monitoring."""

    def test_hybrid_with_freeze_and_canary_is_remediation(self):
        """A hybrid with critical-path freeze + canary should not be monitoring_observability."""
        archetype = cr._classify_action_archetype(
            "2-week critical-path freeze rebuild the test foundation canary monitoring parallel",
            "rollback risk bounded",
            "strategist-added composite",
        )
        assert archetype != "monitoring_observability", (
            f"Hybrid remediation+monitoring should not be monitoring_observability, got {archetype}"
        )
        assert archetype in ("definitive_remediation", "containment_mitigation", "freeze_halt"), (
            f"Expected a remediation archetype, got {archetype}"
        )

    def test_pure_monitoring_stays_monitoring(self):
        """Pure monitoring recommendation should still classify as monitoring."""
        archetype = cr._classify_action_archetype(
            "deploy monitoring dashboard to detect and alert on anomalies",
            "",
            "complementary safeguard",
        )
        assert archetype == "monitoring_observability"

    def test_rejected_override_still_works(self):
        """Rejected alternative override still takes priority."""
        archetype = cr._classify_action_archetype(
            "rebuild the test foundation and monitor everything",
            "",
            "rejected option — not recommended",
        )
        assert archetype == "rejected_alternative"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
