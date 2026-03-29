"""Tests for blocker lifecycle."""
from thinker.tools.blocker import BlockerLedger
from thinker.types import BlockerKind, BlockerStatus


class TestBlockerLedger:

    def test_add_blocker(self):
        ledger = BlockerLedger()
        b = ledger.add(BlockerKind.EVIDENCE_GAP, "test", 1, detail="missing data")
        assert b.blocker_id == "BLK001"
        assert b.status == BlockerStatus.OPEN
        assert len(ledger.blockers) == 1

    def test_sequential_ids(self):
        ledger = BlockerLedger()
        b1 = ledger.add(BlockerKind.EVIDENCE_GAP, "a", 1)
        b2 = ledger.add(BlockerKind.CONTRADICTION, "b", 2)
        assert b1.blocker_id == "BLK001"
        assert b2.blocker_id == "BLK002"

    def test_resolve(self):
        ledger = BlockerLedger()
        b = ledger.add(BlockerKind.EVIDENCE_GAP, "test", 1)
        ledger.resolve(b.blocker_id, 2, "evidence found", "resolved by E003")
        assert b.status == BlockerStatus.RESOLVED
        assert b.resolution_note == "resolved by E003"
        assert len(b.status_history) == 2

    def test_defer(self):
        ledger = BlockerLedger()
        b = ledger.add(BlockerKind.UNRESOLVED_DISAGREEMENT, "test", 1)
        ledger.defer(b.blocker_id, 3, "too complex")
        assert b.status == BlockerStatus.DEFERRED

    def test_drop(self):
        ledger = BlockerLedger()
        b = ledger.add(BlockerKind.CONTESTED_POSITION, "test", 1)
        ledger.drop(b.blocker_id, 2, "false positive")
        assert b.status == BlockerStatus.DROPPED

    def test_open_blockers(self):
        ledger = BlockerLedger()
        b1 = ledger.add(BlockerKind.EVIDENCE_GAP, "a", 1)
        b2 = ledger.add(BlockerKind.CONTRADICTION, "b", 1)
        ledger.resolve(b1.blocker_id, 2, "found")
        assert len(ledger.open_blockers()) == 1
        assert ledger.open_blockers()[0].blocker_id == "BLK002"

    def test_summary(self):
        ledger = BlockerLedger()
        ledger.add(BlockerKind.EVIDENCE_GAP, "a", 1)
        ledger.add(BlockerKind.CONTRADICTION, "b", 1)
        s = ledger.summary()
        assert s["total_blockers"] == 2
        assert s["open_at_end"] == 2
        assert s["by_kind"]["EVIDENCE_GAP"] == 1
        assert s["by_kind"]["CONTRADICTION"] == 1

    def test_status_history_tracks_changes(self):
        ledger = BlockerLedger()
        b = ledger.add(BlockerKind.EVIDENCE_GAP, "test", 1)
        assert b.status_history[0]["status"] == "OPEN"
        ledger.resolve(b.blocker_id, 2, "fixed")
        assert b.status_history[1]["status"] == "RESOLVED"
        assert b.status_history[1]["round"] == 2

    def test_models_involved(self):
        ledger = BlockerLedger()
        b = ledger.add(BlockerKind.UNRESOLVED_DISAGREEMENT, "test", 1, models=["r1", "glm5"])
        assert b.models_involved == ["r1", "glm5"]
