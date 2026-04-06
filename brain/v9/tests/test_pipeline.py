"""Tests for pipeline stage registry."""
from brain.pipeline import STAGE_REGISTRY, pipeline_stage, StageInfo


class TestStageRegistry:

    def test_registry_has_stages(self):
        # Import all modules to populate registry
        import brain.gate1, thinker.rounds, thinker.argument_tracker  # noqa
        import brain.tools.position, thinker.search, thinker.synthesis, thinker.gate2  # noqa
        assert len(STAGE_REGISTRY) > 0

    def test_stage_info_fields(self):
        import brain.gate1  # noqa
        if "gate1" in STAGE_REGISTRY:
            info = STAGE_REGISTRY["gate1"]
            assert isinstance(info, StageInfo)
            assert info.name
            assert info.description
            assert info.stage_type

    def test_pipeline_stage_decorator(self):
        @pipeline_stage(
            name="test stage", description="for testing",
            stage_type="test", order=99, stage_id="test_stage_99",
        )
        def dummy():
            pass
        assert "test_stage_99" in STAGE_REGISTRY
        assert STAGE_REGISTRY["test_stage_99"].name == "test stage"
        # Cleanup
        del STAGE_REGISTRY["test_stage_99"]

    def test_decorator_attaches_metadata(self):
        @pipeline_stage(
            name="meta test", description="test metadata",
            stage_type="test", order=98, stage_id="test_stage_98",
        )
        def meta_fn():
            pass
        assert hasattr(meta_fn, "_stage_info")
        assert meta_fn._stage_info.name == "meta test"
        del STAGE_REGISTRY["test_stage_98"]
