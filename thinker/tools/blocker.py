"""Blocker Lifecycle — tracks evidence gaps, contradictions, and disagreements."""
from __future__ import annotations

from thinker.types import Blocker, BlockerKind, BlockerStatus


class BlockerLedger:
    def __init__(self):
        self.blockers: list[Blocker] = []
        self._counter = 0

    def add(self, kind: BlockerKind, source: str, detected_round: int,
            detail: str = "", models: list[str] | None = None,
            severity: str = "MEDIUM") -> Blocker:
        self._counter += 1
        blocker = Blocker(
            blocker_id=f"BLK{self._counter:03d}",
            kind=kind,
            source=source,
            detected_round=detected_round,
            severity=severity,
            detail=detail,
            models_involved=models or [],
            status_history=[{"status": "OPEN", "round": detected_round, "trigger": "detected"}],
        )
        self.blockers.append(blocker)
        return blocker

    def resolve(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.RESOLVED, round_num, trigger, note)

    def defer(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.DEFERRED, round_num, trigger, note)

    def drop(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.DEFERRED, round_num, trigger, note)

    def open_blockers(self) -> list[Blocker]:
        return [b for b in self.blockers if b.status == BlockerStatus.OPEN]

    def summary(self) -> dict:
        by_status = {}
        by_kind = {}
        for b in self.blockers:
            by_status[b.status.value] = by_status.get(b.status.value, 0) + 1
            by_kind[b.kind.value] = by_kind.get(b.kind.value, 0) + 1
        return {
            "total_blockers": len(self.blockers),
            "by_status": by_status,
            "by_kind": by_kind,
            "open_at_end": len(self.open_blockers()),
        }

    def _update_status(self, blocker_id: str, new_status: BlockerStatus,
                       round_num: int, trigger: str, note: str):
        for b in self.blockers:
            if b.blocker_id == blocker_id:
                b.status = new_status
                b.resolution_note = note
                b.status_history.append({
                    "status": new_status.value, "round": round_num, "trigger": trigger,
                })
                return
