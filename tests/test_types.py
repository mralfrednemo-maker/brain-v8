"""Tests for core types."""
from thinker.types import (
    Argument, ArgumentStatus, BrainResult, Blocker, BlockerKind,
    BlockerStatus, Confidence, Contradiction, EvidenceItem, Gate1Result,
    Gate2Assessment, ModelResponse, Outcome, Position, RoundResult, SearchResult,
    ResolutionStatus, PreflightResult, PremiseFlag, PremiseFlagType,
    PremiseFlagSeverity, PremiseFlagRouting, DimensionSeedResult, DimensionItem,
    StabilityResult, FrameInfo, FrameType, FrameSurvivalStatus,
    AssumptionVerifiability, CriticalAssumption, AnalysisDebug, AnalysisMap,
    ResidueVerification, SynthesisPacket, UngroundedStatItem, UngroundedStatResult,
)
from thinker.config import ROUND_TOPOLOGY, MODEL_REGISTRY, BrainConfig


def test_outcome_has_all_values():
    assert set(o.value for o in Outcome) == {
        "DECIDE", "ESCALATE", "NO_CONSENSUS", "ANALYSIS", "ERROR", "NEED_MORE"
    }


def test_outcome_values():
    assert Outcome.DECIDE.value == "DECIDE"
    assert Outcome.ESCALATE.value == "ESCALATE"
    assert Outcome.NEED_MORE.value == "NEED_MORE"


def test_round_topology_narrows():
    assert len(ROUND_TOPOLOGY[1]) == 4
    assert len(ROUND_TOPOLOGY[2]) == 3
    assert len(ROUND_TOPOLOGY[3]) == 2
    assert len(ROUND_TOPOLOGY[4]) == 2


def test_all_topology_models_in_registry():
    for round_num, models in ROUND_TOPOLOGY.items():
        for model_name in models:
            assert model_name in MODEL_REGISTRY, f"{model_name} missing from registry"


def test_round_result_responded():
    rr = RoundResult(round_num=1, responses={
        "r1": ModelResponse(model="r1", ok=True, text="analysis", elapsed_s=10.0),
        "glm5": ModelResponse(model="glm5", ok=False, text="", elapsed_s=5.0, error="timeout"),
    })
    assert rr.responded == ["r1"]
    assert rr.texts == {"r1": "analysis"}


def test_round_result_texts_excludes_failures():
    rr = RoundResult(round_num=1, responses={
        "r1": ModelResponse(model="r1", ok=True, text="yes", elapsed_s=1.0),
        "kimi": ModelResponse(model="kimi", ok=True, text="no", elapsed_s=2.0),
    })
    assert len(rr.texts) == 2


def test_brain_config_defaults():
    cfg = BrainConfig()
    assert cfg.rounds == 4
    assert cfg.max_evidence_items == 10


def test_evidence_item_creation():
    ev = EvidenceItem(
        evidence_id="E001", topic="JWT bypass", fact="CVE-2026-1234",
        url="https://nvd.nist.gov/...", confidence=Confidence.HIGH,
    )
    assert ev.evidence_id == "E001"
    assert ev.confidence == Confidence.HIGH


def test_argument_defaults():
    arg = Argument(argument_id="ARG-1", round_num=1, model="r1", text="The breach is severe")
    assert arg.status == ArgumentStatus.IGNORED
    assert arg.addressed_in_round is None


def test_blocker_lifecycle():
    b = Blocker(
        blocker_id="BLK001", kind=BlockerKind.CONTESTED_POSITION,
        source="position:O3", detected_round=1,
    )
    assert b.status == BlockerStatus.OPEN
    b.status = BlockerStatus.RESOLVED
    b.resolution_note = "All models converged"
    assert b.status == BlockerStatus.RESOLVED


# --- V9 Type Tests ---


def test_preflight_result_critical_flags():
    pf = PreflightResult(
        premise_flags=[
            PremiseFlag(
                flag_id="PFLAG-1", flag_type=PremiseFlagType.INTERNAL_CONTRADICTION,
                severity=PremiseFlagSeverity.CRITICAL, summary="test",
                routing=PremiseFlagRouting.MANAGEABLE_UNKNOWN,
            ),
        ],
    )
    assert pf.has_critical_flags is True
    assert len(pf.unresolved_critical_flags) == 1


def test_preflight_result_resolved_critical_not_blocking():
    pf = PreflightResult(
        premise_flags=[
            PremiseFlag(
                flag_id="PFLAG-1", flag_type=PremiseFlagType.INTERNAL_CONTRADICTION,
                severity=PremiseFlagSeverity.CRITICAL, summary="test",
                routing=PremiseFlagRouting.MANAGEABLE_UNKNOWN,
                resolved=True, resolved_stage="r2",
            ),
        ],
    )
    assert pf.has_critical_flags is False


def test_dimension_seed_result_to_dict():
    ds = DimensionSeedResult(
        items=[DimensionItem(dimension_id="DIM-1", name="Legal")],
        dimension_count=1,
    )
    d = ds.to_dict()
    assert d["seeded"] is True
    assert len(d["items"]) == 1


def test_stability_result_defaults():
    sr = StabilityResult()
    assert sr.conclusion_stable is True
    assert sr.groupthink_warning is False


def test_frame_info_to_dict():
    f = FrameInfo(frame_id="FRAME-1", text="test", frame_type=FrameType.INVERSION)
    d = f.to_dict()
    assert d["frame_type"] == "INVERSION"
    assert d["survival_status"] == "ACTIVE"


def test_evidence_item_has_two_tier_fields():
    e = EvidenceItem(
        evidence_id="E001", topic="test", fact="test fact",
        url="https://example.com", confidence=Confidence.HIGH,
    )
    assert e.is_active is True
    assert e.is_archived is False
    assert e.authority_tier == "STANDARD"


def test_argument_has_resolution_status():
    a = Argument(argument_id="R1-ARG-1", round_num=1, model="r1", text="test")
    assert a.resolution_status == ResolutionStatus.ORIGINAL
    assert a.refines is None
    assert a.superseded_by is None
    assert a.open is True


def test_preflight_fatal_assumptions():
    pf = PreflightResult(
        critical_assumptions=[
            CriticalAssumption(
                assumption_id="CA-1", text="Data is real-time",
                verifiability=AssumptionVerifiability.UNVERIFIABLE, material=True,
            ),
        ],
    )
    assert pf.has_fatal_assumptions is True


def test_preflight_to_dict_roundtrip():
    pf = PreflightResult()
    d = pf.to_dict()
    assert d["answerability"] == "ANSWERABLE"
    assert d["executed"] is True
    assert isinstance(d["premise_flags"], list)


def test_blocker_new_kinds():
    b1 = Blocker(
        blocker_id="BLK-COV", kind=BlockerKind.COVERAGE_GAP,
        source="dimension:DIM-1", detected_round=2,
    )
    b2 = Blocker(
        blocker_id="BLK-UNV", kind=BlockerKind.UNVERIFIED_CLAIM,
        source="claim:C-1", detected_round=3,
    )
    assert b1.kind == BlockerKind.COVERAGE_GAP
    assert b2.kind == BlockerKind.UNVERIFIED_CLAIM


def test_contradiction_new_fields():
    c = Contradiction(
        ctr_id="CTR-1", evidence_ids=["E1", "E2"],
        topic="test", severity="HIGH", detection_mode="SEMANTIC",
        justification="Conflicting data", linked_claim_ids=["C-1"],
    )
    assert c.detection_mode == "SEMANTIC"
    assert len(c.linked_claim_ids) == 1
    assert c.ctr_id == "CTR-1"
    assert c.contradiction_id == "CTR-1"


def test_gate2_assessment_rule_trace():
    g = Gate2Assessment(
        outcome=Outcome.DECIDE, convergence_ok=True,
        evidence_credible=True, dissent_addressed=True,
        enough_data=True, report_honest=True,
        modality="DECIDE", rule_trace=[{"rule": "D1", "matched": True}],
    )
    assert g.modality == "DECIDE"
    assert len(g.rule_trace) == 1


def test_missing_schema_dataclasses_exist():
    assert UngroundedStatItem(claim_id="UG-1", text="42%").to_dict()["claim_id"] == "UG-1"
    assert UngroundedStatResult(items=[UngroundedStatItem(claim_id="UG-1", text="42%")]).to_dict()["flagged_claims"][0]["claim_id"] == "UG-1"
    assert SynthesisPacket(packet_complete=True).to_dict()["packet_complete"] is True
    assert ResidueVerification().to_dict()["coverage_pass"] is True
    assert AnalysisMap().to_dict()["header"] == "EXPLORATORY MAP — NOT A DECISION"
    assert AnalysisDebug(debug_mode=True).to_dict()["debug_mode"] is True


def test_brain_error_defaults_to_fatal_integrity_error_class():
    from thinker.types import BrainError

    err = BrainError("stage", "boom")
    assert err.error_class == "FATAL_INTEGRITY"


def test_ungrounded_stats_items_alias_maps_to_flagged_claims():
    result = UngroundedStatResult(items=[UngroundedStatItem(claim_id="UG-1", text="42%")])
    assert result.flagged_claims[0].claim_id == "UG-1"
    assert result.items[0].claim_id == "UG-1"


def test_argument_to_dict_uses_dod_field_names():
    payload = Argument(argument_id="ARG-1", round_num=1, model="r1", text="claim").to_dict()
    assert payload["round_origin"] == 1
    assert payload["model_id"] == "r1"
    assert "refines" in payload
    assert "round_num" not in payload
    assert "model" not in payload


def test_evidence_to_dict_uses_source_url():
    payload = EvidenceItem("E001", "topic", "fact", "https://example.com", Confidence.HIGH).to_dict()
    assert payload["source_url"] == "https://example.com"
    assert "url" not in payload


def test_blocker_to_dict_uses_dod_field_names():
    payload = Blocker("BLK-1", BlockerKind.EVIDENCE_GAP, "dimension:DIM-1", 1).to_dict()
    assert payload["type"] == "EVIDENCE_GAP"
    assert payload["linked_ids"] == []
    assert "kind" not in payload
