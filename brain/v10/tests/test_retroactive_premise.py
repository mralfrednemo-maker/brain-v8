"""Tests for ADDITION-4: Retroactive premise escalation helpers."""


def test_retroactive_premise_result_dataclass():
    from brain.types import RetroactivePremiseResult
    r = RetroactivePremiseResult(
        executed=True, triggered=True,
        matched_premise="The market is growing",
        model_ids=["r1", "reasoner"],
        rerun_outcome="NEED_MORE",
    )
    assert r.triggered is True
    assert len(r.model_ids) == 2


def test_argument_has_argument_type_field():
    from brain.types import Argument
    a = Argument(argument_id="A001", round_num=1, model="r1", text="test", argument_type="premise_challenge")
    assert a.argument_type == "premise_challenge"


def test_argument_type_defaults_to_none():
    from brain.types import Argument
    a = Argument(argument_id="A001", round_num=1, model="r1", text="test")
    assert a.argument_type is None


def test_retroactive_scan_not_triggered_below_threshold():
    from brain.brain import _should_trigger_retroactive_premise
    premise_findings = [
        {"model": "r1", "premise": "market is growing", "type": "premise_challenge"},
    ]
    assert _should_trigger_retroactive_premise(premise_findings) is False


def test_retroactive_scan_triggered_at_threshold():
    from brain.brain import _should_trigger_retroactive_premise
    premise_findings = [
        {"model": "r1", "premise": "market is growing", "type": "premise_challenge"},
        {"model": "reasoner", "premise": "the market is growing", "type": "premise_challenge"},
    ]
    assert _should_trigger_retroactive_premise(premise_findings) is True


def test_one_shot_cap_field_in_pipeline_state():
    from brain.checkpoint import PipelineState
    state = PipelineState()
    state.retroactive_escalation_consumed = True
    assert state.retroactive_escalation_consumed is True
