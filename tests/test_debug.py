"""Tests for debug/logging infrastructure."""
import json
from pathlib import Path

from thinker.debug import RunLog, StageEvent


class TestRunLog:

    def test_verbose_mode(self, capsys):
        log = RunLog(verbose=True)
        log._print("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_silent_mode(self, capsys):
        log = RunLog(verbose=False)
        log._print("test message")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_lines_accumulated(self):
        log = RunLog(verbose=False)
        log._print("line 1")
        log._print("line 2")
        assert len(log._lines) == 2

    def test_save_log(self, tmp_path):
        log = RunLog()
        log._print("line 1")
        log._print("line 2")
        path = tmp_path / "debug.log"
        log.save_log(path)
        assert path.exists()
        text = path.read_text()
        assert "line 1" in text
        assert "line 2" in text

    def test_save_events_json(self, tmp_path):
        log = RunLog()
        log.events.append(StageEvent(stage="gate1", label="Gate 1", timestamp=0, elapsed_s=1.5))
        path = tmp_path / "events.json"
        log.save_events_json(path)
        data = json.loads(path.read_text())
        assert len(data) == 1
        assert data[0]["stage"] == "gate1"
        assert data[0]["elapsed_s"] == 1.5

    def test_gate1_event_recorded(self):
        log = RunLog()
        log.gate1_start(100)
        log.gate1_result(True, "looks good", [], 1.0)
        assert len(log.events) == 1
        assert log.events[0].data["passed"] is True

    def test_round_event_recorded(self):
        log = RunLog()
        log.round_start(1, ["r1", "glm5"], False)
        log.round_result(1, ["r1", "glm5"], [], {"r1": "output 1", "glm5": "output 2"}, 5.0)
        assert len(log.events) == 1
        assert log.events[0].data["responded"] == ["r1", "glm5"]


class TestStageEvent:

    def test_default_status(self):
        e = StageEvent(stage="test", label="Test", timestamp=0)
        assert e.status == "ok"

    def test_data_default_empty(self):
        e = StageEvent(stage="test", label="Test", timestamp=0)
        assert e.data == {}
