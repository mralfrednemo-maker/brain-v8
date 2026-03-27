"""Position Tracker — tracks model positions per round and measures convergence."""
from __future__ import annotations

import re
from collections import Counter

from thinker.types import Confidence, Position

POSITION_EXTRACT_PROMPT = """Extract each model's position from these round {round_num} outputs.

Model outputs:
{outputs}

For each model, identify:
- Their primary option/position (O1, O2, O3, O4, or a short label)
- Their confidence (HIGH, MEDIUM, LOW)
- Brief qualifier (one sentence summary of their stance)

Format:
model_name: OPTION [CONFIDENCE] — qualifier"""


class PositionTracker:
    def __init__(self, llm_client):
        self._llm = llm_client
        self.positions_by_round: dict[int, dict[str, Position]] = {}

    async def extract_positions(
        self, round_num: int, model_outputs: dict[str, str],
    ) -> dict[str, Position]:
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        resp = await self._llm.call(
            "sonnet",
            POSITION_EXTRACT_PROMPT.format(round_num=round_num, outputs=combined),
        )
        if not resp.ok:
            return {}

        positions = self._parse_positions(resp.text, round_num)
        self.positions_by_round[round_num] = positions
        return positions

    def agreement_ratio(self, round_num: int) -> float:
        positions = self.positions_by_round.get(round_num, {})
        if not positions:
            return 0.0
        options = [p.primary_option for p in positions.values()]
        counts = Counter(options)
        majority_count = counts.most_common(1)[0][1]
        return majority_count / len(options)

    def get_position_changes(self, from_round: int, to_round: int) -> list[dict]:
        from_pos = self.positions_by_round.get(from_round, {})
        to_pos = self.positions_by_round.get(to_round, {})
        changes = []
        for model in set(from_pos) & set(to_pos):
            if from_pos[model].primary_option != to_pos[model].primary_option:
                changes.append({
                    "model": model,
                    "from_round": from_round,
                    "to_round": to_round,
                    "from_position": from_pos[model].primary_option,
                    "to_position": to_pos[model].primary_option,
                })
        return changes

    def _parse_positions(self, text: str, round_num: int) -> dict[str, Position]:
        positions = {}
        for line in text.strip().split("\n"):
            line = line.strip()
            match = re.match(
                r"(\w+):\s+(O\d+|[\w_]+)\s+\[(HIGH|MEDIUM|LOW)\]\s*(?:—\s*(.+))?", line,
            )
            if match:
                model = match.group(1)
                option = match.group(2)
                conf = Confidence[match.group(3)]
                qualifier = (match.group(4) or "").strip()
                positions[model] = Position(
                    model=model, round_num=round_num, primary_option=option,
                    components=[option], confidence=conf, qualifier=qualifier,
                )
        return positions
