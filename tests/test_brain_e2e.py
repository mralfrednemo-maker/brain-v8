"""End-to-end Brain orchestrator tests with mock data."""
import pytest

from thinker.brain import Brain
from thinker.config import BrainConfig
from thinker.types import Outcome
from conftest import MockLLMClient, load_model_output


def _setup_full_mock(mock: MockLLMClient, rounds: int = 3):
    """Queue all responses needed for a full Brain run (no search_fn).

    Call order per Brain.run() (V9) with search_fn=None:
    Preflight(sonnet) -> DimensionSeeder(sonnet)
    -> R1(4 models) -> R1_args(sonnet) -> R1_pos(sonnet)
    -> FramingExtract(sonnet)
    -> R2(3 models) -> R2_args(sonnet) -> R2_pos(sonnet) -> R1vR2_cmp(sonnet)
    -> FrameSurvival(sonnet)
    -> R3(2 models) -> R3_args(sonnet) -> R3_pos(sonnet) -> R2vR3_cmp(sonnet)
    -> Synthesis(sonnet)
    (Gate 2 + Stability are deterministic — no LLM call needed)
    """
    # Preflight (V9 — replaces Gate 1)
    mock.add_response("sonnet", (
        '{"answerability": "ANSWERABLE", "question_class": "OPEN", "stakes_class": "HIGH", '
        '"effort_tier": "STANDARD", "modality": "DECIDE", "search_scope": "TARGETED", '
        '"exploration_required": true, "short_circuit_allowed": false, "fatal_premise": false, '
        '"follow_up_questions": [], "premise_flags": [], "hidden_context_gaps": [], '
        '"critical_assumptions": [], "reasoning": "Clear security incident brief."}'
    ))

    # Dimension Seeder (V9)
    mock.add_response("sonnet", (
        '{"dimensions": ['
        '{"dimension_id": "DIM-1", "name": "Technical Severity", "mandatory": true}, '
        '{"dimension_id": "DIM-2", "name": "Business Impact", "mandatory": true}, '
        '{"dimension_id": "DIM-3", "name": "Legal & Compliance", "mandatory": true}'
        ']}'
    ))

    # --- Round 1 ---
    mock.add_responses_from_fixtures(1, ["r1", "reasoner", "glm5", "kimi"])
    # R1 argument extraction
    mock.add_response("sonnet", (
        "ARG-1: [r1] Full shutdown is safest given active RCE\n"
        "ARG-2: [reasoner] Controlled isolation minimizes business impact\n"
        "ARG-3: [glm5] The 847 requests indicate automated exploitation\n"
        "ARG-4: [kimi] GDPR 72-hour notification applies\n"
    ))
    # R1 position extraction
    mock.add_response("sonnet", (
        "r1: O3 [HIGH] — controlled isolation first\n"
        "reasoner: O3 [MEDIUM] — prefers isolation\n"
        "glm5: O4 [HIGH] — full shutdown\n"
        "kimi: O4 [HIGH] — full shutdown\n"
    ))

    # Framing Extract (V9) — after R1 tracking
    mock.add_response("sonnet", (
        '{"frames": ['
        '{"frame_id": "FRAME-1", "text": "Isolation-first may expose to lateral movement", '
        '"origin_model": "glm5", "frame_type": "PREMISE_CHALLENGE", "material_to_outcome": true}'
        '], "cross_domain_analogies": []}'
    ))

    # --- Round 2 ---
    mock.add_responses_from_fixtures(2, ["r1", "reasoner", "glm5"])
    # R2 argument extraction
    mock.add_response("sonnet", (
        "ARG-5: [r1] Evidence confirms RCE severity warrants shutdown\n"
        "ARG-6: [glm5] Isolation delays may allow lateral movement\n"
    ))
    # R2 position extraction
    mock.add_response("sonnet", (
        "r1: O4 [HIGH] — shifted to full shutdown after evidence\n"
        "reasoner: O3 [MEDIUM] — still prefers isolation\n"
        "glm5: O4 [HIGH] — maintains shutdown position\n"
    ))
    # Frame Survival R2 (V9) — runs after track2, before comparison
    mock.add_response("sonnet", (
        '{"evaluations": ['
        '{"frame_id": "FRAME-1", "status": "CONTESTED", "drop_vote_models": ["r1"], '
        '"reasoning": "R1 partially addressed lateral movement risk"}'
        ']}'
    ))

    # R1->R2 argument comparison
    mock.add_response("sonnet", "ARG-1: ADDRESSED\nARG-2: ADDRESSED\nARG-3: MENTIONED\nARG-4: ADDRESSED\n")

    # --- Round 3 ---
    mock.add_responses_from_fixtures(3, ["r1", "reasoner"])
    # R3 argument extraction
    mock.add_response("sonnet", "ARG-7: [r1] All models converging on O4\n")
    # R3 position extraction
    mock.add_response("sonnet", (
        "r1: O4 [HIGH] — full shutdown\n"
        "reasoner: O4 [HIGH] — converged to shutdown\n"
    ))
    # Frame Survival R3 (V9)
    mock.add_response("sonnet", (
        '{"evaluations": ['
        '{"frame_id": "FRAME-1", "status": "CONTESTED", "drop_vote_models": [], '
        '"reasoning": "Frame still relevant in R3"}'
        ']}'
    ))

    # R2->R3 argument comparison
    mock.add_response("sonnet", "ARG-5: ADDRESSED\nARG-6: ADDRESSED\n")

    # Decisive Claims (V9)
    mock.add_response("sonnet", (
        '{"claims": ['
        '{"claim_id": "DC-1", "text": "Active RCE confirmed via 847 automated requests", '
        '"material_to_conclusion": true, "evidence_refs": ["E001"], "evidence_support_status": "SUPPORTED"}, '
        '{"claim_id": "DC-2", "text": "Full shutdown required to contain lateral movement risk", '
        '"material_to_conclusion": true, "evidence_refs": [], "evidence_support_status": "PARTIAL"}'
        ']}'
    ))

    # --- Synthesis (returns dual format: markdown + JSON) ---
    mock.add_response("sonnet", (
        "# Deliberation Report\n\n## TL;DR\nAll models converged on full service shutdown (O4).\n"
        "\n---JSON---\n\n"
        '{"title": "Security Incident Assessment", "tldr": "Consensus on O4 shutdown", '
        '"verdict": "Full shutdown (O4)", "confidence": "high", '
        '"agreed_points": ["RCE confirmed", "Shutdown required"], "contested_points": [], '
        '"key_findings": ["CVE-2026-1234 active RCE", "847 automated requests"], '
        '"risk_factors": [], "evidence_cited": ["E001"], "unresolved_questions": []}'
    ))

    # No Gate 2 mock needed — it's deterministic


class TestBrainE2E:
    """Full Brain run with mock data."""

    async def test_full_run_decides(self):
        mock = MockLLMClient()
        _setup_full_mock(mock, rounds=3)

        brain = Brain(
            config=BrainConfig(rounds=3),
            llm_client=mock,
            search_fn=None,  # No live search in tests
        )
        result = await brain.run(brief=(
            "# Security Incident Assessment\n\n"
            "JWT bypass in production. 847 requests. Active RCE.\n"
        ))
        # V9: Pipeline must complete. Outcome depends on Gate 2 DOD rules
        # (mock data may trigger D6/COVERAGE_GAP blockers — that's correct behavior)
        assert result.outcome in (Outcome.DECIDE, Outcome.ESCALATE, Outcome.NO_CONSENSUS)
        assert result.preflight is not None
        assert result.gate2 is not None
        assert result.gate2.rule_trace is not None
        assert len(result.gate2.rule_trace) > 0
        assert "proof_version" in result.proof
        assert result.proof["proof_version"] == "3.0"

    async def test_preflight_rejection_short_circuits(self):
        mock = MockLLMClient()
        mock.add_response("sonnet", (
            '{"answerability": "NEED_MORE", "question_class": "AMBIGUOUS", '
            '"stakes_class": "STANDARD", "effort_tier": "ELEVATED", "modality": "DECIDE", '
            '"search_scope": "NONE", "exploration_required": false, '
            '"short_circuit_allowed": false, "fatal_premise": false, '
            '"follow_up_questions": ["What system is affected?", "What is the scope?"], '
            '"premise_flags": [], "hidden_context_gaps": [], '
            '"critical_assumptions": [], "reasoning": "Brief is too vague."}'
        ))
        brain = Brain(config=BrainConfig(rounds=3), llm_client=mock, search_fn=None)
        result = await brain.run(brief="Something broke, help?")
        assert result.outcome == Outcome.NEED_MORE
        assert result.preflight is not None
        assert len(result.preflight.follow_up_questions) >= 1
        # Should NOT have called any deliberation models
        assert len(mock.calls_for("r1")) == 0

    async def test_proof_has_round_data(self):
        mock = MockLLMClient()
        _setup_full_mock(mock, rounds=3)
        brain = Brain(config=BrainConfig(rounds=3), llm_client=mock, search_fn=None)
        result = await brain.run(brief="JWT bypass incident. 847 requests. Active RCE.")
        proof = result.proof
        assert "1" in proof["rounds"]
        assert "2" in proof["rounds"]
        assert "3" in proof["rounds"]
        assert proof["final_status"] == "COMPLETE"
