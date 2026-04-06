"""Tests for ADDITION-6: Breadth-Recovery Pulse."""


def test_triggers_above_threshold():
    from brain.brain import _should_trigger_breadth_recovery
    assert _should_trigger_breadth_recovery(r1_arg_count=10, ignored_count=5) is True


def test_does_not_trigger_at_threshold():
    from brain.brain import _should_trigger_breadth_recovery
    assert _should_trigger_breadth_recovery(r1_arg_count=10, ignored_count=4) is False


def test_zero_args_does_not_crash():
    from brain.brain import _should_trigger_breadth_recovery
    assert _should_trigger_breadth_recovery(r1_arg_count=0, ignored_count=0) is False


def test_proof_field_stored():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_breadth_recovery({"triggered": True, "ignored_ratio": 0.5})
    result = pb.build()
    assert result.get("breadth_recovery", {}).get("triggered") is True
