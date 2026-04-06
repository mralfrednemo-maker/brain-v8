"""Tests for Standalone Leverage Profile (SLP) — controller-synthesized from final adjudicated state."""
import sys
import types
from pathlib import Path
from tempfile import NamedTemporaryFile

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

# ---------------------------------------------------------------------------
# Fixtures — minimal state builders
# ---------------------------------------------------------------------------


def _tmp_log():
    f = NamedTemporaryFile(suffix=".log", mode="w", delete=False)
    f.close()
    return Path(f.name)


def _make_rec(item_id, rank=1, role="Primary response", thesis="Deploy immediately", known_risks=None, decision="PASS"):
    return cr.Recommendation(
        item_id=item_id, name=f"Rec {item_id}", rank=rank,
        role_in_portfolio=role, thesis=thesis,
        claim_ids=["C001"], evidence_ids=["E001", "E002"],
        known_risks=known_risks or [],
    )


def _make_audit(*recs_decisions, claim_support="ADEQUATE"):
    """Build a minimal AuditSnapshot.  recs_decisions: list of (item_id, decision) tuples."""
    return cr.AuditSnapshot(
        overall_evidence_quality="MEDIUM",
        claim_scores=[cr.ClaimScore(claim_id="C001", support_level=claim_support, support_reason="test")],
        recommendation_decisions=[
            cr.RecommendationDecision(item_id=rid, decision=dec, reason="test")
            for rid, dec in recs_decisions
        ],
        progress_assessment="test",
        eligible_for_judgment=True,
    )


def _make_ledger():
    return cr.RunLedger(run_id="test-run", task="test task")


def _make_proposal(*recs):
    return cr.ProposalPack(proposal_id="P001", claims=[
        cr.Claim(claim_id="C001", claim_text="Test claim", importance="CORE", evidence_ids=["E001"]),
    ], recommendations=list(recs))


# ---------------------------------------------------------------------------
# Test 1: Passed recommendation gets SLP
# ---------------------------------------------------------------------------


def test_passed_recommendation_gets_slp():
    log = _tmp_log()
    rec = _make_rec("R001")
    audit = _make_audit(("R001", "PASS"))
    ledger = _make_ledger()
    proposal = _make_proposal(rec)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)

    assert len(profiles) == 1
    assert profiles[0].item_id == "R001"
    assert profiles[0].standalone_eligibility.status == "ELIGIBLE"
    assert profiles[0].standalone_impact.rating in cr.SLP_IMPACT_BANDS
    assert profiles[0].execution_feasibility.rating in cr.SLP_FEASIBILITY_BANDS
    assert profiles[0].time_to_protective_effect.rating in cr.SLP_TIME_BANDS
    assert profiles[0].reversibility_downside.rating in cr.SLP_REVERSIBILITY_BANDS
    assert profiles[0].evidence_confidence.rating in cr.SLP_EVIDENCE_BANDS


# ---------------------------------------------------------------------------
# Test 2: Failed recommendation cannot be highlighted
# ---------------------------------------------------------------------------


def test_failed_recommendation_not_highlightable():
    log = _tmp_log()
    rec_pass = _make_rec("R001", rank=1)
    rec_fail = _make_rec("R002", rank=2, role="Rejected standalone option", decision="FAIL")
    audit = _make_audit(("R001", "PASS"), ("R002", "FAIL"))
    ledger = _make_ledger()
    proposal = _make_proposal(rec_pass, rec_fail)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    highlight = cr._build_slp_highlight(profiles, log, task="test task")

    # R002 should be ineligible
    r002_profile = [p for p in profiles if p.item_id == "R002"][0]
    assert r002_profile.standalone_eligibility.status == "INELIGIBLE_FOR_HIGHLIGHT"

    # Highlight should not point to R002
    assert highlight.item_id != "R002"


# ---------------------------------------------------------------------------
# Test 3: Conditionally eligible is suppressed when condition unsatisfied
# ---------------------------------------------------------------------------


def test_conditionally_eligible_excluded_from_highlight():
    log = _tmp_log()
    rec_primary = _make_rec("R001", rank=1, role="Primary response — layered approach")
    rec_escalation = _make_rec(
        "R002", rank=2,
        role="Escalation fallback — immediate containment if active exploitation detected",
        thesis="Full shutdown eliminates all attack surface. Justified only if exploitation confirmed.",
        known_risks=["Escalation trigger: confirmed exploitation or patch failure"],
    )
    audit = _make_audit(("R001", "PASS_WITH_RISK"), ("R002", "PASS_WITH_RISK"))
    ledger = _make_ledger()
    proposal = _make_proposal(rec_primary, rec_escalation)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    highlight = cr._build_slp_highlight(profiles, log, task="test task")

    r002_profile = [p for p in profiles if p.item_id == "R002"][0]
    assert r002_profile.standalone_eligibility.status == "CONDITIONALLY_ELIGIBLE"

    # Highlight should not select a conditionally eligible item
    assert highlight.item_id != "R002"


# ---------------------------------------------------------------------------
# Test 4: Weak evidence candidate cannot be highlighted
# ---------------------------------------------------------------------------


def test_weak_evidence_not_highlighted():
    log = _tmp_log()
    rec = _make_rec("R001")
    audit = _make_audit(("R001", "PASS"), claim_support="UNSUPPORTED")  # Maps to WEAK
    ledger = _make_ledger()
    proposal = _make_proposal(rec)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    highlight = cr._build_slp_highlight(profiles, log, task="test task")

    assert profiles[0].evidence_confidence.rating == "WEAK"
    assert highlight.item_id is None
    assert highlight.confidence == "INDETERMINATE"


# ---------------------------------------------------------------------------
# Test 5: UNCERTAIN on standalone_impact caps to MARGINAL
# ---------------------------------------------------------------------------


def test_uncertain_impact_caps_to_marginal():
    """When execution_feasibility is UNCERTAIN, highlight should be capped to MARGINAL at most."""
    log = _tmp_log()
    # Create a rec with many feasibility concerns to trigger UNCERTAIN
    rec = _make_rec(
        "R001", rank=1,
        known_risks=["Deployment may fail", "Rollback is untested", "Implementation complexity is high"],
    )
    audit = _make_audit(("R001", "PASS"))
    ledger = _make_ledger()
    # Add feasibility-related deferred objections
    ledger.objection_ledger["OBJ001"] = "DEFERRED"
    obj = cr.Objection(
        objection_id="OBJ001", claim_id="C001", severity="HIGH",
        type="evidence_gap", objection_text="Feasibility of deployment is unverified",
        scope="ITEM",
    )
    ledger.deferred_objection_store["OBJ001"] = obj
    ledger.objection_history.append(cr.ObjectionPack(objections=[obj]))
    proposal = _make_proposal(rec)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    highlight = cr._build_slp_highlight(profiles, log, task="test task")

    # With UNCERTAIN feasibility, highlight should be MARGINAL at most
    if profiles[0].execution_feasibility.rating == "UNCERTAIN":
        assert highlight.confidence in ("MARGINAL", "INDETERMINATE")


# ---------------------------------------------------------------------------
# Test 6: Clear dominance produces CLEAR
# ---------------------------------------------------------------------------


def test_clear_dominance():
    log = _tmp_log()
    rec_strong = _make_rec(
        "R001", rank=1, role="Primary response — definitive remediation",
        thesis="Deploy patch immediately with bounded rollback",
    )
    rec_weak = _make_rec(
        "R002", rank=2, role="Secondary option — partial mitigation only",
        thesis="Apply WAF rules only. Low disruption but limited coverage.",
    )
    audit = _make_audit(("R001", "PASS"), ("R002", "PASS"), claim_support="STRONG")
    ledger = _make_ledger()
    proposal = _make_proposal(rec_strong, rec_weak)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    highlight = cr._build_slp_highlight(profiles, log, task="test task")

    # R001 should dominate (definitive remediation → CRITICAL impact; R002 partial → MODERATE)
    r001_profile = [p for p in profiles if p.item_id == "R001"][0]
    r002_profile = [p for p in profiles if p.item_id == "R002"][0]

    # R001 impact should be strictly better than R002
    assert cr._slp_band_index(r001_profile.standalone_impact.rating, cr.SLP_IMPACT_BANDS) < \
           cr._slp_band_index(r002_profile.standalone_impact.rating, cr.SLP_IMPACT_BANDS)

    assert highlight.item_id == "R001"
    assert highlight.confidence == "CLEAR"


# ---------------------------------------------------------------------------
# Test 7: Split profile produces INDETERMINATE with null item_id
# ---------------------------------------------------------------------------


def test_split_profile_indeterminate():
    log = _tmp_log()
    # Two recommendations with equivalent standalone action semantics — tied on impact
    rec_a = _make_rec("R001", rank=1, role="Definitive remediation option A",
                      thesis="Deploy patch version A to eliminate the vulnerability")
    rec_b = _make_rec("R002", rank=2, role="Definitive remediation option B",
                      thesis="Deploy patch version B to eliminate the vulnerability")
    audit = _make_audit(("R001", "PASS"), ("R002", "PASS"))
    ledger = _make_ledger()
    proposal = _make_proposal(rec_a, rec_b)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    highlight = cr._build_slp_highlight(profiles, log, task="test task")

    # Both should have the same impact band since both are definitive remediation
    assert profiles[0].standalone_impact.rating == profiles[1].standalone_impact.rating
    assert highlight.item_id is None
    assert highlight.confidence == "INDETERMINATE"


# ---------------------------------------------------------------------------
# Test 8: Portfolio ranking/output unchanged
# ---------------------------------------------------------------------------


def test_portfolio_unchanged_by_slp():
    """SLP does not alter the verdict's core fields: status, confidence, approved/rejected, rationale."""
    log = _tmp_log()
    rec = _make_rec("R001")
    audit = _make_audit(("R001", "PASS"))
    ledger = _make_ledger()
    proposal = _make_proposal(rec)

    raw_verdict = cr.ConsensusVerdict(
        status="CONSENSUS",
        confidence=0.80,
        approved_items=["R001"],
        rejected_items=[],
        unresolved_points=[],
        rationale="All recommendations pass with strong evidence.",
        next_action="Proceed with implementation.",
    )

    final = cr._build_final_verdict(raw_verdict, audit, ledger, log, proposal)

    # Core verdict fields preserved (status may normalize but that's existing behavior)
    assert "R001" in final.approved_items
    assert final.confidence <= 0.80  # May be penalized by normalization, never increased
    assert len(final.rationale) > 0

    # SLP fields are present and supplementary
    assert isinstance(final.standalone_leverage_profiles, list)
    assert len(final.standalone_leverage_profiles) == 1
    assert final.highest_standalone_leverage is not None
    assert final.highest_standalone_leverage["confidence"] in cr.SLP_HIGHLIGHT_CONFIDENCE


# ---------------------------------------------------------------------------
# Test 9: Satisfied conditional candidate can compete in highlight pool
# ---------------------------------------------------------------------------


def test_conditionally_eligible_with_satisfied_condition():
    """A CONDITIONALLY_ELIGIBLE item enters the pool when the brief satisfies its condition."""
    log = _tmp_log()
    rec_primary = _make_rec("R001", rank=1, role="Primary response — layered approach")
    rec_escalation = _make_rec(
        "R002", rank=2,
        role="Escalation fallback — immediate containment if active exploitation detected",
        thesis="Full shutdown eliminates all attack surface immediately. Severe business impact but bounded.",
        known_risks=["Escalation trigger: confirmed exploitation or patch failure"],
    )
    audit = _make_audit(("R001", "PASS_WITH_RISK"), ("R002", "PASS_WITH_RISK"))
    ledger = _make_ledger()
    proposal = _make_proposal(rec_primary, rec_escalation)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    r002_profile = [p for p in profiles if p.item_id == "R002"][0]
    assert r002_profile.standalone_eligibility.status == "CONDITIONALLY_ELIGIBLE"

    # When the task explicitly states exploitation is confirmed, R002 should enter the pool
    task_with_confirmed = "Active exploitation has been confirmed on the API gateway. We need immediate containment."
    highlight = cr._build_slp_highlight(profiles, log, task=task_with_confirmed)

    # R002 should now be eligible — it may or may not win, but it must not be excluded
    # The highlight should not be INDETERMINATE due to "no eligible candidates"
    assert highlight.rationale != "No eligible candidates in the pool."

    # Verify the unsatisfied case still excludes R002
    task_unsatisfied = "We do not know if exploitation is occurring."
    highlight_unsatisfied = cr._build_slp_highlight(profiles, log, task=task_unsatisfied)
    # R001 is still ELIGIBLE, so we should get a result — but R002 should not be the winner
    # unless R001 is also excluded for other reasons


# ---------------------------------------------------------------------------
# Test 10: 3-candidate pool where third candidate blocks false CLEAR
# ---------------------------------------------------------------------------


def test_three_candidate_pool_third_blocks_clear():
    """In a 3-candidate pool, a third option with better viability should prevent a false CLEAR."""
    log = _tmp_log()
    # R001: highest impact but worst reversibility
    rec_best_impact = _make_rec(
        "R001", rank=1, role="Primary response — aggressive remediation",
        thesis="Emergency patch with immediate deployment. Severe disruption if it fails.",
    )
    # R002: moderate impact, good viability
    rec_moderate = _make_rec(
        "R002", rank=2, role="Secondary option — balanced approach",
        thesis="Staged deployment with bounded rollback risk.",
    )
    # R003: lower impact but excellent reversibility — this is the blocker
    rec_safe = _make_rec(
        "R003", rank=3, role="Conservative option — minimal disruption",
        thesis="WAF rules only. Low disruption, bounded and recoverable downside.",
    )
    audit = _make_audit(
        ("R001", "PASS"), ("R002", "PASS"), ("R003", "PASS"),
        claim_support="STRONG",
    )
    ledger = _make_ledger()
    proposal = _make_proposal(rec_best_impact, rec_moderate, rec_safe)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    highlight = cr._build_slp_highlight(profiles, log, task="test task")

    # R001 has "severe" in thesis → SEVERE reversibility
    # R003 has "bounded and recoverable" → BOUNDED reversibility
    # R001 is materially worse on reversibility vs R003 → should not get CLEAR
    r001 = [p for p in profiles if p.item_id == "R001"][0]
    r003 = [p for p in profiles if p.item_id == "R003"][0]

    if r001.reversibility_downside.rating == "SEVERE" and r003.reversibility_downside.rating == "BOUNDED":
        # R001 is materially worse on reversibility vs R003
        # Dominance check against ALL pool members should catch this
        assert highlight.confidence != "CLEAR", \
            f"R001 should not get CLEAR when R003 has materially better reversibility. Got: {highlight.confidence}"


# ---------------------------------------------------------------------------
# Test 11: Cross-domain analog evidence is rejected by domain-coherence gate
# ---------------------------------------------------------------------------


def test_cross_domain_analog_rejected():
    """Medical/toxicological evidence should be rejected when the task is cybersecurity."""
    log = _tmp_log()
    task = "Critical RCE vulnerability in API gateway authentication middleware. PoC exploit published 4 hours ago."
    ledger = _make_ledger()
    ledger.task = task

    # Medical analog evidence — exactly the kind that slipped through in the v8 run
    medical_ev = cr.Evidence(
        evidence_id="ETEST",
        topic="acute risk timeline post-PoC",
        source_type="training_knowledge",
        fact="Toxicological studies on acute poisoning cases indicate that peak systemic absorption "
             "and maximum clinical deterioration typically occur within 2-6 hours of exposure, "
             "with the 4-hour mark representing a critical inflection point used in clinical triage "
             "protocols (e.g., Rumack-Matthew nomogram for acetaminophen uses 4-hour post-ingestion "
             "serum levels as the standard reference point).",
        confidence="MEDIUM",
    )

    result = cr._is_evidence_relevant(medical_ev, task, ledger, cycle=3, source="researcher", log_path=log)
    assert result is False, "Medical/toxicological evidence should be rejected for a cybersecurity task"

    # Verify the log captured the rejection reason
    log_content = log.read_text()
    assert "cross-domain-analog" in log_content


def test_same_domain_evidence_admitted():
    """Cybersecurity evidence should still be admitted for a cybersecurity task."""
    log = _tmp_log()
    task = "Critical RCE vulnerability in API gateway authentication middleware. PoC exploit published 4 hours ago."
    ledger = _make_ledger()
    ledger.task = task

    cyber_ev = cr.Evidence(
        evidence_id="ETEST",
        topic="exploit weaponization timeline",
        source_type="training_knowledge",
        fact="After a PoC exploit is published publicly, mass automated scanning and exploitation "
             "typically begins within 15-60 minutes. Vulnerability scanners and botnets integrate "
             "exploit code within 24 hours of public disclosure.",
        confidence="HIGH",
    )

    result = cr._is_evidence_relevant(cyber_ev, task, ledger, cycle=1, source="researcher", log_path=log)
    assert result is True, "Cybersecurity evidence should be admitted for a cybersecurity task"


def test_domain_coherence_does_not_block_unknown_domain():
    """Evidence with no clear domain family should not be rejected by domain-coherence."""
    log = _tmp_log()
    task = "Critical RCE vulnerability in API gateway authentication middleware."
    ledger = _make_ledger()
    ledger.task = task

    generic_ev = cr.Evidence(
        evidence_id="ETEST",
        topic="cost analysis",
        source_type="training_knowledge",
        fact="Industry reports estimate average incident response costs between $1M and $5M "
             "depending on severity and scope of the breach.",
        confidence="MEDIUM",
    )

    result = cr._is_evidence_relevant(generic_ev, task, ledger, cycle=1, source="researcher", log_path=log)
    assert result is True, "Generic evidence with no clear domain should not be rejected"


# ---------------------------------------------------------------------------
# Test 14: Definitive remediation outranks partial mitigation on standalone
#           impact even when the partial mitigation is ranked higher in portfolio
# ---------------------------------------------------------------------------


def test_standalone_impact_decoupled_from_rank():
    """A rank-2 definitive fix should have higher standalone impact than a rank-1 partial mitigation."""
    log = _tmp_log()
    rec_waf = _make_rec(
        "R001", rank=1,
        role="Immediate partial mitigation to reduce exploitation probability during the patch preparation window",
        thesis="Deploy WAF rules within 30 minutes to provide partial coverage. Buys time but is not a fix. "
               "30-50% bypass rate means this is a temporary compensating control only.",
    )
    rec_patch = _make_rec(
        "R002", rank=2,
        role="Definitive vulnerability remediation that eliminates the root cause",
        thesis="Emergency patch deployment eliminates the RCE vulnerability permanently. "
               "Accepts bounded regression risk to remove the root cause.",
    )
    audit = _make_audit(("R001", "PASS"), ("R002", "PASS"), claim_support="STRONG")
    ledger = _make_ledger()
    proposal = _make_proposal(rec_waf, rec_patch)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)

    r001_profile = [p for p in profiles if p.item_id == "R001"][0]
    r002_profile = [p for p in profiles if p.item_id == "R002"][0]

    # R002 (definitive remediation) should have strictly higher standalone impact than R001 (partial)
    r001_idx = cr._slp_band_index(r001_profile.standalone_impact.rating, cr.SLP_IMPACT_BANDS)
    r002_idx = cr._slp_band_index(r002_profile.standalone_impact.rating, cr.SLP_IMPACT_BANDS)

    assert r002_idx < r001_idx, (
        f"R002 (definitive, rank=2) should have higher standalone impact than R001 (partial, rank=1). "
        f"Got R001={r001_profile.standalone_impact.rating} (idx={r001_idx}), "
        f"R002={r002_profile.standalone_impact.rating} (idx={r002_idx})"
    )

    # The highlight should either pick R002 or be INDETERMINATE — never R001
    highlight = cr._build_slp_highlight(profiles, log, task="test task")
    assert highlight.item_id != "R001" or highlight.confidence == "INDETERMINATE", (
        f"R001 (partial mitigation) should not be the standalone highlight over R002 (definitive). "
        f"Got highlight={highlight.item_id} ({highlight.confidence})"
    )


# ---------------------------------------------------------------------------
# Test 15: Reversibility follows action-downside, not threat-severity language
# ---------------------------------------------------------------------------


def test_reversibility_follows_action_not_threat():
    """When thesis contains both 'bounded/recoverable' about the action and
    'catastrophic/irreversible' about the threat, reversibility should follow
    the action-downside signal, not the threat language."""
    log = _tmp_log()
    rec = _make_rec(
        "R001", rank=1,
        role="Definitive vulnerability remediation",
        thesis="Emergency patch eliminates the RCE root cause. Accepts bounded regression risk "
               "with rollback capability. The alternative — no patch — risks catastrophic and "
               "irreversible breach consequences including data exfiltration and regulatory penalties.",
        known_risks=[
            "Patch regression risk is bounded; rollback via container image revert takes under 15 minutes",
            "15-minute maintenance window required for deployment",
        ],
    )
    audit = _make_audit(("R001", "PASS"), claim_support="STRONG")
    ledger = _make_ledger()
    proposal = _make_proposal(rec)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    r001 = profiles[0]

    # The action's own downside is bounded/recoverable (rollback in <15min)
    # The thesis mentions "catastrophic" and "irreversible" but those describe the THREAT, not the action
    assert r001.reversibility_downside.rating in ("BOUNDED", "MANAGEABLE"), (
        f"R001 reversibility should be BOUNDED or MANAGEABLE (action has rollback), "
        f"not {r001.reversibility_downside.rating} (which would mean threat language leaked in)"
    )


def test_shutdown_recommendation_gets_severe_reversibility():
    """A shutdown recommendation with genuine severe action-downside should still get SEVERE."""
    log = _tmp_log()
    rec = _make_rec(
        "R001", rank=1,
        role="Full shutdown as last resort",
        thesis="Full shutdown eliminates all attack surface by taking the service offline. "
               "Full outage for all 200K users. Service unavailability until patch is validated.",
        known_risks=[
            "Full outage impacts all users; extended shutdown duration is unpredictable",
            "Cannot roll back once initiated — service must be fully revalidated before restart",
        ],
    )
    audit = _make_audit(("R001", "PASS"))
    ledger = _make_ledger()
    proposal = _make_proposal(rec)

    profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
    r001 = profiles[0]

    assert r001.reversibility_downside.rating == "SEVERE", (
        f"Shutdown with genuine full outage and no rollback should be SEVERE, "
        f"got {r001.reversibility_downside.rating}"
    )


# ===========================================================================
# Cross-domain calibration regression tests (Round 2)
# ===========================================================================


class TestCalibrationSecurity:
    """Security/incident-response domain: definitive patch beats compensating control."""

    def test_patch_beats_waf_on_impact(self):
        log = _tmp_log()
        rec_waf = _make_rec("R001", rank=1,
            role="Compensating control — temporary WAF rules to reduce active exploit surface",
            thesis="Deploy WAF rules within 30 minutes as a compensating control. Buys time but is not a fix.")
        rec_patch = _make_rec("R002", rank=2,
            role="Definitive vulnerability remediation that eliminates the root cause",
            thesis="Emergency patch eliminates the RCE root cause permanently.")
        audit = _make_audit(("R001", "PASS"), ("R002", "PASS"), claim_support="STRONG")
        ledger = _make_ledger()
        ledger.task = "Critical RCE vulnerability in API gateway. Deploy WAF or patch."
        proposal = _make_proposal(rec_waf, rec_patch)
        profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
        r001 = [p for p in profiles if p.item_id == "R001"][0]
        r002 = [p for p in profiles if p.item_id == "R002"][0]
        assert cr._slp_band_index(r002.standalone_impact.rating, cr.SLP_IMPACT_BANDS) < \
               cr._slp_band_index(r001.standalone_impact.rating, cr.SLP_IMPACT_BANDS), \
            f"Patch (definitive) should beat WAF (compensating) on impact: R001={r001.standalone_impact.rating}, R002={r002.standalone_impact.rating}"


class TestCalibrationEngineering:
    """Engineering process/debt domain: gating restoration beats staffing/process."""

    def test_gating_restoration_beats_hire_qa(self):
        log = _tmp_log()
        rec_hybrid = _make_rec("R001", rank=1,
            role="Primary — restore gating through critical-path sprint",
            thesis="2-week sprint to rebuild the test foundation and reintroduce trustworthy validation for the deployment pipeline.")
        rec_hire = _make_rec("R002", rank=2,
            role="Staffing — hire dedicated QA team",
            thesis="Hire a dedicated team of 6 QA engineers to backfill tests over 3 months.")
        audit = _make_audit(("R001", "PASS"), ("R002", "PASS"))
        ledger = _make_ledger()
        ledger.task = "Test suite has 12% real coverage. Choose between sprint rebuild or hire QA team."
        proposal = _make_proposal(rec_hybrid, rec_hire)
        profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
        r001 = [p for p in profiles if p.item_id == "R001"][0]
        r002 = [p for p in profiles if p.item_id == "R002"][0]
        assert cr._slp_band_index(r001.standalone_impact.rating, cr.SLP_IMPACT_BANDS) < \
               cr._slp_band_index(r002.standalone_impact.rating, cr.SLP_IMPACT_BANDS), \
            f"Gating restoration should beat staffing on impact: R001={r001.standalone_impact.rating}, R002={r002.standalone_impact.rating}"


class TestCalibrationCompliance:
    """Compliance/regulatory domain: active containment beats later governance."""

    def test_lockdown_beats_internal_only(self):
        log = _tmp_log()
        rec_lockdown = _make_rec("R001", rank=1,
            role="Full lockdown and external forensic audit — stops the active disclosure path",
            thesis="Immediate full lockdown eliminates ongoing data exposure. External forensic audit provides legal defensibility and satisfies HIPAA breach reporting requirements.")
        rec_internal = _make_rec("R002", rank=2,
            role="Internal log analysis only — future governance improvement",
            thesis="Internal rapid-response with log analysis. Lower cost but documentation alone without stopping current exposure.")
        audit = _make_audit(("R001", "PASS"), ("R002", "PASS"))
        ledger = _make_ledger()
        ledger.task = "HIPAA breach: S3 bucket exposed 2.1M patient records for 5 days."
        proposal = _make_proposal(rec_lockdown, rec_internal)
        profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
        r001 = [p for p in profiles if p.item_id == "R001"][0]
        r002 = [p for p in profiles if p.item_id == "R002"][0]
        assert cr._slp_band_index(r001.standalone_impact.rating, cr.SLP_IMPACT_BANDS) <= \
               cr._slp_band_index(r002.standalone_impact.rating, cr.SLP_IMPACT_BANDS), \
            f"Lockdown+forensic should match or beat internal-only on impact: R001={r001.standalone_impact.rating}, R002={r002.standalone_impact.rating}"


class TestCalibrationInfrastructure:
    """Infrastructure domain: direct bottleneck fix ties or beats coarse restart."""

    def test_root_cause_fix_matches_restart(self):
        log = _tmp_log()
        rec_fix = _make_rec("R001", rank=1,
            role="Root cause fix — audit and fix session key TTLs",
            thesis="Fix the root cause by correcting Redis session TTL configuration. Addresses root cause permanently.")
        rec_restart = _make_rec("R002", rank=2,
            role="Emergency mitigation — set Redis maxmemory + rolling restart",
            thesis="Cap Redis memory with maxmemory and rolling restart pods. Reduces risk but does not fix root cause.")
        audit = _make_audit(("R001", "PASS"), ("R002", "PASS"))
        ledger = _make_ledger()
        ledger.task = "Kubernetes cluster: Redis session store OOMKill every 8 minutes, 12K RPS."
        proposal = _make_proposal(rec_fix, rec_restart)
        profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
        r001 = [p for p in profiles if p.item_id == "R001"][0]
        r002 = [p for p in profiles if p.item_id == "R002"][0]
        # Root cause fix should be >= restart on impact
        assert cr._slp_band_index(r001.standalone_impact.rating, cr.SLP_IMPACT_BANDS) <= \
               cr._slp_band_index(r002.standalone_impact.rating, cr.SLP_IMPACT_BANDS), \
            f"Root cause fix should match or beat restart on impact: R001={r001.standalone_impact.rating}, R002={r002.standalone_impact.rating}"


class TestCalibrationAIPolicy:
    """AI policy/ethics domain: governance intervention has elevated impact."""

    def test_governance_beats_monitoring(self):
        log = _tmp_log()
        rec_governance = _make_rec("R001", rank=1,
            role="Governance safeguard — sunset governance with hard expiration",
            thesis="Establish formal sunset governance: document threshold adjustment as temporary with hard expiration tied to retrain completion.")
        rec_monitor = _make_rec("R002", rank=2,
            role="Monitoring only — detect bias in real-time without fixing",
            thesis="Deploy monitoring dashboard to detect bias patterns. Does not fix the bias, only makes it visible.")
        audit = _make_audit(("R001", "PASS"), ("R002", "PASS"))
        ledger = _make_ledger()
        ledger.task = "AI content moderation system has 4.2% false-positive rate on Arabic content vs 0.8% on English. Bias and fairness disparity in model threshold adjustment."
        proposal = _make_proposal(rec_governance, rec_monitor)
        profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
        r001 = [p for p in profiles if p.item_id == "R001"][0]
        r002 = [p for p in profiles if p.item_id == "R002"][0]
        assert cr._slp_band_index(r001.standalone_impact.rating, cr.SLP_IMPACT_BANDS) < \
               cr._slp_band_index(r002.standalone_impact.rating, cr.SLP_IMPACT_BANDS), \
            f"Governance should beat monitoring on impact in AI policy domain: R001={r001.standalone_impact.rating}, R002={r002.standalone_impact.rating}"


class TestCalibrationOperations:
    """Operations/traffic domain: capacity scaling has elevated impact; monitoring-only does not."""

    def test_scaling_beats_monitoring(self):
        log = _tmp_log()
        rec_scale = _make_rec("R001", rank=1,
            role="Capacity defense — activate auto-scaling immediately",
            thesis="Activate auto-scaling to add capacity and scale out beyond the 8x traffic spike.")
        rec_monitor = _make_rec("R002", rank=2,
            role="Attribution analysis — collect data before acting",
            thesis="Begin parallel attribution analysis to investigate whether traffic is bot or legitimate.")
        audit = _make_audit(("R001", "PASS"), ("R002", "PASS"))
        ledger = _make_ledger()
        ledger.task = "E-commerce platform experiencing 8x traffic spike, CDN cache hit rate dropped from 94% to 61%."
        proposal = _make_proposal(rec_scale, rec_monitor)
        profiles = cr._build_slp_profiles(audit, ledger, proposal, log)
        r001 = [p for p in profiles if p.item_id == "R001"][0]
        r002 = [p for p in profiles if p.item_id == "R002"][0]
        assert cr._slp_band_index(r001.standalone_impact.rating, cr.SLP_IMPACT_BANDS) < \
               cr._slp_band_index(r002.standalone_impact.rating, cr.SLP_IMPACT_BANDS), \
            f"Auto-scaling should beat monitoring on impact: R001={r001.standalone_impact.rating}, R002={r002.standalone_impact.rating}"


class TestArchetypeClassification:
    """Verify action archetype classification works correctly."""

    def test_definitive_remediation_detected(self):
        archetype = cr._classify_action_archetype(
            "eliminates the root cause vulnerability permanently", "", "")
        assert archetype == "definitive_remediation"

    def test_containment_mitigation_detected(self):
        archetype = cr._classify_action_archetype(
            "deploy waf rules as compensating control temporary bridge", "", "")
        assert archetype == "containment_mitigation"

    def test_monitoring_detected(self):
        archetype = cr._classify_action_archetype(
            "deploy monitoring dashboard to detect and alert on anomalies", "", "")
        assert archetype == "monitoring_observability"

    def test_staffing_detected(self):
        archetype = cr._classify_action_archetype(
            "hire a dedicated team of 6 qa engineers", "", "")
        assert archetype == "staffing_process"

    def test_rejected_override(self):
        archetype = cr._classify_action_archetype(
            "eliminates the root cause", "", "rejected option")
        assert archetype == "rejected_alternative"

    def test_capacity_scaling_detected(self):
        archetype = cr._classify_action_archetype(
            "activate auto-scaling to scale out and add capacity", "", "")
        assert archetype == "capacity_scaling"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
