"""Tests for the Position Tracker."""
import pytest

from thinker.tools.position import PositionTracker
from thinker.types import Position, Confidence


class TestPositionExtraction:
    async def test_extracts_positions(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "r1: O4 [HIGH] — advocates full shutdown due to active RCE\n"
            "reasoner: O3 [MEDIUM] — prefers controlled isolation first\n"
            "glm5: O4 [HIGH] — agrees with full shutdown\n"
            "kimi: O4 [HIGH] — supports immediate shutdown\n"
        ))
        tracker = PositionTracker(mock_llm)
        positions = await tracker.extract_positions(
            round_num=1,
            model_outputs={"r1": "...", "reasoner": "...", "glm5": "...", "kimi": "..."},
        )
        assert len(positions) == 4
        assert positions["r1"].primary_option == "O4"
        assert positions["reasoner"].primary_option == "O3"


class TestConvergenceCheck:
    def test_full_consensus(self):
        tracker = PositionTracker(None)
        tracker.positions_by_round[3] = {
            "r1": Position("r1", 3, "O4", confidence=Confidence.HIGH),
            "reasoner": Position("reasoner", 3, "O4", confidence=Confidence.HIGH),
        }
        ratio = tracker.agreement_ratio(3)
        assert ratio == 1.0

    def test_split_positions(self):
        tracker = PositionTracker(None)
        tracker.positions_by_round[1] = {
            "r1": Position("r1", 1, "O3"),
            "reasoner": Position("reasoner", 1, "O3"),
            "glm5": Position("glm5", 1, "O4"),
            "kimi": Position("kimi", 1, "O4"),
        }
        ratio = tracker.agreement_ratio(1)
        assert ratio == 0.5

    def test_position_changes_tracked(self):
        tracker = PositionTracker(None)
        tracker.positions_by_round[1] = {"r1": Position("r1", 1, "O3")}
        tracker.positions_by_round[2] = {"r1": Position("r1", 2, "O4")}
        changes = tracker.get_position_changes(1, 2)
        assert len(changes) == 1
        assert changes[0]["from_position"] == "O3"
        assert changes[0]["to_position"] == "O4"
