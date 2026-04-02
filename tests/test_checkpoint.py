"""Tests for checkpoint system."""
import json
from pathlib import Path

import pytest

from thinker.checkpoint import PipelineState, STAGE_ORDER, should_stop, CHECKPOINT_VERSION


class TestCheckpointVersion:

    def test_default_version_set(self):
        state = PipelineState()
        assert state.checkpoint_version == CHECKPOINT_VERSION

    def test_version_saved_to_json(self, tmp_path):
        state = PipelineState(run_id="test-001", brief="test brief")
        path = tmp_path / "checkpoint.json"
        state.save(path)
        data = json.loads(path.read_text())
        assert data["checkpoint_version"] == CHECKPOINT_VERSION

    def test_version_mismatch_raises(self, tmp_path):
        path = tmp_path / "checkpoint.json"
        state = PipelineState(run_id="test-mismatch")
        state.save(path)
        # Tamper with the version
        data = json.loads(path.read_text())
        data["checkpoint_version"] = "0.0"
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="Checkpoint version mismatch"):
            PipelineState.load(path)

    def test_compatible_version_loads(self, tmp_path):
        state = PipelineState(run_id="test-002", brief="test")
        path = tmp_path / "checkpoint.json"
        state.save(path)
        loaded = PipelineState.load(path)
        assert loaded.run_id == "test-002"
        assert loaded.checkpoint_version == CHECKPOINT_VERSION


class TestCheckpointSaveLoad:

    def test_round_trip(self, tmp_path):
        state = PipelineState(
            run_id="test-003", brief="A test brief",
            current_stage="r1", completed_stages=["gate1", "r1"],
        )
        path = tmp_path / "checkpoint.json"
        state.save(path)
        loaded = PipelineState.load(path)
        assert loaded.run_id == "test-003"
        assert loaded.completed_stages == ["gate1", "r1"]

    def test_unknown_fields_ignored_on_load(self, tmp_path):
        path = tmp_path / "checkpoint.json"
        state = PipelineState(run_id="test-004")
        state.save(path)
        data = json.loads(path.read_text())
        data["future_field"] = "something"
        path.write_text(json.dumps(data))
        loaded = PipelineState.load(path)
        assert loaded.run_id == "test-004"


class TestShouldStop:

    def test_stop_when_matches(self):
        assert should_stop("gate1", "gate1") is True

    def test_no_stop_when_different(self):
        assert should_stop("gate1", "r1") is False

    def test_no_stop_when_none(self):
        assert should_stop("gate1", None) is False


class TestPositionComponentsRoundTrip:

    def test_full_components_saved_and_restored(self, tmp_path):
        """B3: Position components must survive checkpoint round-trip, not collapse to [option]."""
        from thinker.types import Confidence, Position
        from thinker.tools.position import PositionTracker
        from thinker.argument_tracker import ArgumentTracker
        from thinker.evidence import EvidenceLedger
        from conftest import MockLLMClient

        state = PipelineState(run_id="test-b3")
        state.positions_by_round["1"] = {
            "r1": {
                "option": "GDPR:reportable + SOC_2:documentation-required",
                "confidence": "HIGH",
                "qualifier": "72h notify; depends on BAA",
                "components": ["GDPR:reportable", "SOC_2:documentation-required"],
                "kind": "sequence",
            },
        }
        path = tmp_path / "checkpoint.json"
        state.save(path)
        loaded = PipelineState.load(path)

        # Simulate restore
        mock_llm = MockLLMClient()
        position_tracker = PositionTracker(mock_llm)
        argument_tracker = ArgumentTracker(mock_llm)
        evidence = EvidenceLedger()

        from thinker.brain import Brain
        from thinker.config import BrainConfig
        brain = Brain(config=BrainConfig(), llm_client=mock_llm, resume_state=loaded)
        brain._restore_trackers(argument_tracker, position_tracker, evidence)

        restored = position_tracker.positions_by_round[1]["r1"]
        assert restored.components == ["GDPR:reportable", "SOC_2:documentation-required"]
        assert restored.kind == "sequence"

    def test_single_position_components_preserved(self, tmp_path):
        """Single-dimension positions should also preserve components."""
        from thinker.types import Confidence, Position
        from thinker.tools.position import PositionTracker
        from thinker.argument_tracker import ArgumentTracker
        from thinker.evidence import EvidenceLedger
        from conftest import MockLLMClient

        state = PipelineState(run_id="test-b3-single")
        state.positions_by_round["1"] = {
            "r1": {
                "option": "O3",
                "confidence": "HIGH",
                "qualifier": "strong preference",
                "components": ["O3"],
                "kind": "single",
            },
        }
        path = tmp_path / "checkpoint.json"
        state.save(path)
        loaded = PipelineState.load(path)

        mock_llm = MockLLMClient()
        position_tracker = PositionTracker(mock_llm)
        argument_tracker = ArgumentTracker(mock_llm)
        evidence = EvidenceLedger()

        from thinker.brain import Brain
        from thinker.config import BrainConfig
        brain = Brain(config=BrainConfig(), llm_client=mock_llm, resume_state=loaded)
        brain._restore_trackers(argument_tracker, position_tracker, evidence)

        restored = position_tracker.positions_by_round[1]["r1"]
        assert restored.components == ["O3"]
        assert restored.kind == "single"


class TestStageOrder:

    def test_all_stages_present(self):
        expected = [
            "preflight", "dimensions",
            "r1", "track1", "perspective_cards", "framing_pass",
            "ungrounded_r1", "search1",
            "r2", "track2", "frame_survival_r2",
            "ungrounded_r2", "search2",
            "r3", "track3", "frame_survival_r3",
            "r4", "track4",
            "semantic_contradiction", "synthesis_packet",
            "synthesis", "stability", "gate2",
        ]
        assert STAGE_ORDER == expected
