"""Tests for DELTA-5: SHORT_CIRCUIT 5-invariant reasoning contract."""


def test_all_five_invariants_present():
    from brain.brain import _validate_short_circuit_invariants
    response = (
        "PREMISE CHECK: assumes X is always true. "
        "CONFIDENCE BASIS: based on 2 sources. "
        "KNOWN UNKNOWNS: we don't know the trend. "
        "COUNTER-CONSIDERATION: one could argue Y. "
        "COMPRESSION REASON: short_circuit applied."
    )
    ok, missing = _validate_short_circuit_invariants(response)
    assert ok is True
    assert missing == []


def test_missing_counter_consideration():
    from brain.brain import _validate_short_circuit_invariants
    response = (
        "PREMISE CHECK: assumes X. "
        "CONFIDENCE BASIS: based on sources. "
        "KNOWN UNKNOWNS: uncertain. "
        "COMPRESSION REASON: trivial question."
    )
    ok, missing = _validate_short_circuit_invariants(response)
    assert ok is False
    assert "counter_consideration" in missing


def test_all_missing():
    from brain.brain import _validate_short_circuit_invariants
    ok, missing = _validate_short_circuit_invariants("Just a quick answer: X is correct.")
    assert ok is False
    assert len(missing) == 5


def test_reasoning_contract_proof_field():
    from brain.proof import ProofBuilder
    pb = ProofBuilder(run_id="t", brief="t", rounds_requested=4)
    pb.set_reasoning_contract({"short_circuit_run": True, "all_invariants_present": True, "missing": []})
    result = pb.build()
    assert result.get("reasoning_contract", {}).get("all_invariants_present") is True
