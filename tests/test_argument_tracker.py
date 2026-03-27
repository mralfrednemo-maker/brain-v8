"""Tests for the Argument Tracker."""
import pytest

from thinker.argument_tracker import ArgumentTracker, parse_arguments, parse_comparison
from thinker.types import Argument, ArgumentStatus


class TestArgumentExtraction:
    async def test_extracts_arguments_from_outputs(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "ARG-1: [r1] The JWT bypass affects all multi-tenant configurations\n"
            "ARG-2: [r1] Rollback to v2.7.9 is the safest immediate action\n"
            "ARG-3: [glm5] The 847 requests suggest automated exploitation, not manual\n"
            "ARG-4: [kimi] GDPR notification is required within 72 hours\n"
        ))
        tracker = ArgumentTracker(mock_llm)
        args = await tracker.extract_arguments(
            round_num=1,
            model_outputs={"r1": "JWT bypass analysis...", "glm5": "Automated attack...", "kimi": "GDPR..."},
        )
        assert len(args) == 4
        assert args[0].argument_id == "ARG-1"
        assert args[0].model == "r1"
        assert args[2].model == "glm5"

    async def test_prompt_includes_all_model_outputs(self, mock_llm):
        mock_llm.add_response("sonnet", "ARG-1: [r1] Some argument\n")
        tracker = ArgumentTracker(mock_llm)
        await tracker.extract_arguments(
            round_num=1,
            model_outputs={"r1": "R1 view here", "kimi": "Kimi view here"},
        )
        prompt = mock_llm.last_prompt_for("sonnet")
        assert "R1 view here" in prompt
        assert "Kimi view here" in prompt


class TestArgumentComparison:
    async def test_identifies_addressed_arguments(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "ARG-1: ADDRESSED\n"
            "ARG-2: IGNORED\n"
            "ARG-3: MENTIONED\n"
        ))
        tracker = ArgumentTracker(mock_llm)
        tracker.arguments_by_round[1] = [
            Argument("ARG-1", 1, "r1", "JWT affects multi-tenant"),
            Argument("ARG-2", 1, "glm5", "Automated exploitation"),
            Argument("ARG-3", 1, "kimi", "GDPR 72 hours"),
        ]
        unaddressed = await tracker.compare_with_round(
            prev_round=1,
            curr_outputs={"r1": "Agreed on multi-tenant issue...", "reasoner": "..."},
        )
        assert len(unaddressed) >= 1
        ignored_ids = {a.argument_id for a in unaddressed if a.status == ArgumentStatus.IGNORED}
        assert "ARG-2" in ignored_ids

    async def test_no_unaddressed_when_all_addressed(self, mock_llm):
        mock_llm.add_response("sonnet", "ARG-1: ADDRESSED\nARG-2: ADDRESSED\n")
        tracker = ArgumentTracker(mock_llm)
        tracker.arguments_by_round[1] = [
            Argument("ARG-1", 1, "r1", "Point A"),
            Argument("ARG-2", 1, "glm5", "Point B"),
        ]
        unaddressed = await tracker.compare_with_round(prev_round=1, curr_outputs={"r1": "..."})
        ignored = [a for a in unaddressed if a.status == ArgumentStatus.IGNORED]
        assert len(ignored) == 0


class TestReinjectionFormatting:
    def test_format_reinjection(self):
        tracker = ArgumentTracker(None)
        args = [
            Argument("ARG-2", 1, "glm5", "Automated exploitation pattern", status=ArgumentStatus.IGNORED),
            Argument("ARG-5", 2, "r1", "Insider threat possibility", status=ArgumentStatus.IGNORED),
        ]
        text = tracker.format_reinjection(args)
        assert "ARG-2" in text
        assert "ARG-5" in text
        assert "Automated exploitation" in text
        assert "MUST engage" in text

    def test_empty_reinjection(self):
        tracker = ArgumentTracker(None)
        text = tracker.format_reinjection([])
        assert text == ""


class TestArgumentParsing:
    def test_parse_arguments(self):
        text = (
            "ARG-1: [r1] First argument\n"
            "ARG-2: [glm5] Second argument\n"
        )
        args = parse_arguments(text, round_num=1)
        assert len(args) == 2
        assert args[0].model == "r1"
        assert args[1].text == "Second argument"

    def test_parse_comparison(self):
        text = "ARG-1: ADDRESSED\nARG-2: IGNORED\nARG-3: MENTIONED\n"
        statuses = parse_comparison(text)
        assert statuses["ARG-1"] == ArgumentStatus.ADDRESSED
        assert statuses["ARG-2"] == ArgumentStatus.IGNORED
        assert statuses["ARG-3"] == ArgumentStatus.MENTIONED
