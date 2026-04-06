"""Tests for ADDITION-7: Anti-groupthink search helpers."""


def test_triggers_on_high_agreement_open_question():
    from brain.brain import _should_trigger_anti_groupthink
    from brain.types import QuestionClass, StakesClass
    assert _should_trigger_anti_groupthink(0.85, QuestionClass.OPEN, StakesClass.STANDARD) is True


def test_triggers_on_high_stakes():
    from brain.brain import _should_trigger_anti_groupthink
    from brain.types import QuestionClass, StakesClass
    assert _should_trigger_anti_groupthink(0.85, QuestionClass.WELL_ESTABLISHED, StakesClass.HIGH) is True


def test_does_not_trigger_below_threshold():
    from brain.brain import _should_trigger_anti_groupthink
    from brain.types import QuestionClass, StakesClass
    assert _should_trigger_anti_groupthink(0.75, QuestionClass.OPEN, StakesClass.STANDARD) is False


def test_does_not_trigger_low_stakes_established():
    from brain.brain import _should_trigger_anti_groupthink
    from brain.types import QuestionClass, StakesClass
    assert _should_trigger_anti_groupthink(0.90, QuestionClass.WELL_ESTABLISHED, StakesClass.LOW) is False


def test_anti_groupthink_proof_field():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_anti_groupthink_search({"triggered": True, "query": "counterarguments to X"})
    result = pb.build()
    assert result.get("anti_groupthink_search", {}).get("triggered") is True
