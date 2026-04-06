"""Position Tracker — tracks model positions per round and measures convergence."""
from __future__ import annotations

import re
from collections import Counter

from brain.config import MODEL_REGISTRY
from brain.pipeline import pipeline_stage
from brain.types import Confidence, Position

# Known model names for validation — only accept these as position sources
_KNOWN_MODELS = set(MODEL_REGISTRY.keys())

POSITION_EXTRACT_PROMPT = """Extract each model's position from these round {round_num} outputs.

Model outputs:
{outputs}

For each model, identify:
- Their primary option/position (O1, O2, O3, O4, or a short label)
- Their confidence (HIGH, MEDIUM, LOW)
- Brief qualifier (one sentence summary of their stance)

IMPORTANT: If a model gives a compound position covering multiple frameworks, standards, or
dimensions (e.g., "GDPR-reportable + SOC 2-reportable + HIPAA-not-reportable"), break it into
separate per-framework lines. This lets us detect partial agreement (e.g., all models agree on
GDPR but split on SOC 2).

Format for single-dimension positions:
model_name: OPTION [CONFIDENCE] — qualifier

Format for multi-framework positions (one line per framework):
model_name/FRAMEWORK: POSITION [CONFIDENCE] — qualifier

Example:
r1/GDPR: reportable [HIGH] — 72-hour notification required
r1/SOC_2: documentation-required [MEDIUM] — depends on BAA scope
r1/HIPAA: not-reportable [HIGH] — no PHI exposed"""


def _normalize_position(option: str) -> str:
    """Normalize a position label for agreement comparison.

    Strips parenthetical qualifiers, trailing whitespace, and lowercases.
    Also normalizes option variants: 'O3-modified', 'Enhanced Option 3',
    'Modified/Accelerated Option 3' all become 'o3'.

    'GDPR-reportable + SOC 2-reportable + HIPAA-not-reportable (BAA review required)'
    becomes 'gdpr-reportable + soc 2-reportable + hipaa-not-reportable'
    """
    # Remove parenthetical qualifiers
    normalized = re.sub(r"\s*\([^)]*\)", "", option)
    normalized = normalized.strip().lower()

    # Normalize option variants: extract core option number
    # Matches: "o3", "o3-modified", "option 3", "enhanced option 3",
    # "modified/accelerated option 3", "option 3 (enhanced)", etc.
    core_match = re.search(r"(?:option\s*|o)(\d+)", normalized)
    if core_match:
        return f"o{core_match.group(1)}"

    return normalized


def _is_frame_drop_position(option: str) -> bool:
    normalized = _normalize_position(option)
    return normalized in {"dropped", "drop", "frame_dropped", "frame-dropped"}


class PositionTracker:
    def __init__(self, llm_client):
        self._llm = llm_client
        self.positions_by_round: dict[int, dict[str, Position]] = {}
        self.last_raw_response: str = ""  # For debug logging

    async def extract_positions(
        self, round_num: int, model_outputs: dict[str, str],
    ) -> dict[str, Position]:
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        resp = await self._llm.call(
            "sonnet",
            POSITION_EXTRACT_PROMPT.format(round_num=round_num, outputs=combined),
        )
        if not resp.ok:
            from brain.types import BrainError
            raise BrainError(f"track{round_num}", f"Position extraction failed: {resp.error}",
                             detail="Sonnet could not extract positions from round outputs.")
        self.last_raw_response = resp.text

        positions = self._parse_positions(resp.text, round_num)
        if not positions:
            from brain.types import BrainError
            raise BrainError(f"track{round_num}",
                             f"Position extraction returned 0 positions (expected {len(model_outputs)})",
                             detail=f"Raw response:\n{resp.text[:500]}")
        self.positions_by_round[round_num] = positions
        return positions

    def agreement_ratio(self, round_num: int) -> float:
        """What fraction of models agree on the core position?

        For single-dimension positions: majority count / total models.
        For per-framework positions: average agreement across frameworks.
        Normalizes positions before comparison.
        """
        positions = self.positions_by_round.get(round_num, {})
        if not positions:
            return 0.0

        # Check if any positions are per-framework (kind="sequence")
        has_frameworks = any(p.kind == "sequence" for p in positions.values())

        if has_frameworks:
            return self._framework_agreement_ratio(positions)

        options = [
            _normalize_position(p.primary_option)
            for p in positions.values()
            if not _is_frame_drop_position(p.primary_option)
        ]
        if not options:
            return 0.0
        counts = Counter(options)
        majority_count = counts.most_common(1)[0][1]
        return majority_count / len(options)

    def _framework_agreement_ratio(self, positions: dict[str, Position]) -> float:
        """Compute agreement across per-framework components.

        For each framework, compute what fraction of models agree.
        Return the average across all frameworks.
        """
        # Collect {framework: [position_label, ...]} across all models
        framework_positions: dict[str, list[str]] = {}
        for p in positions.values():
            if p.kind == "sequence" and p.components:
                for comp in p.components:
                    if ":" in comp:
                        fw, label = comp.split(":", 1)
                        normalized_label = _normalize_position(label.strip())
                        if _is_frame_drop_position(normalized_label):
                            continue
                        framework_positions.setdefault(fw.strip(), []).append(
                            normalized_label
                        )
                    else:
                        normalized_label = _normalize_position(comp.strip())
                        if _is_frame_drop_position(normalized_label):
                            continue
                        framework_positions.setdefault("default", []).append(
                            normalized_label
                        )
            else:
                normalized = _normalize_position(p.primary_option)
                if _is_frame_drop_position(normalized):
                    continue
                framework_positions.setdefault("default", []).append(normalized)

        if not framework_positions:
            return 0.0

        ratios = []
        for fw, labels in framework_positions.items():
            if not labels:
                continue
            counts = Counter(labels)
            majority = counts.most_common(1)[0][1]
            ratios.append(majority / len(labels))
        if not ratios:
            return 0.0
        return sum(ratios) / len(ratios)

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
        # Collect per-framework components: {model: [(framework, option, conf, qualifier)]}
        framework_components: dict[str, list[tuple[str, str, Confidence, str]]] = {}

        # Track current model from ### headers (for table-per-model format)
        current_model = ""

        for line in text.strip().split("\n"):
            line = line.strip()

            # Track model headers: ### r1, ### reasoner, etc.
            header_match = re.match(r"#{1,4}\s+[*`]*(\w+)[*`]*\s*$", line)
            if header_match:
                candidate = header_match.group(1).lower()
                if candidate in _KNOWN_MODELS:
                    current_model = candidate
                continue

            # Table row with framework as first column (model from header):
            # | GDPR | **not-reportable** | MEDIUM | qualifier |
            # | Framework | Position | Confidence | Qualifier | (skip header)
            if current_model and "|" in line:
                fw_row = re.search(
                    r"\|\s*[*`]*(\w[\w\s]*\w|\w+)[*`]*\s*\|\s*[*`]*(.+?)[*`]*\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|",
                    line,
                )
                if fw_row:
                    framework = fw_row.group(1).strip().upper().replace(" ", "_")
                    option = fw_row.group(2).strip().strip("*`").strip()
                    conf_text = fw_row.group(3).strip()
                    qualifier = fw_row.group(4).strip()
                    # Skip header rows and separator rows
                    if (framework not in ("FRAMEWORK", "---", "MODEL")
                            and not option.startswith("---")
                            and not option.lower().startswith("position")
                            and conf_text.upper() in ("HIGH", "MEDIUM", "LOW")):
                        conf = self._parse_confidence(conf_text)
                        framework_components.setdefault(current_model, []).append(
                            (framework, option, conf, qualifier)
                        )
                        continue

            # Try markdown table row with model/framework
            # Handles: | `r1/PCI_DSS` | position | HIGH | qualifier |
            # Also: | **r1/GDPR** | position | MEDIUM | qualifier |
            # Also: | 1 | `r1/PCI_DSS` | position | HIGH | qualifier | (leading column)
            table_match = re.search(
                r"\|\s*[*`]*(\w+)/(\w+)[*`]*\s*\|\s*(.+?)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|",
                line,
            )
            if table_match:
                model = table_match.group(1).lower()
                framework = table_match.group(2).upper()
                option = table_match.group(3).strip().strip("*`").strip()
                conf = self._parse_confidence(table_match.group(4))
                qualifier = table_match.group(5).strip()
                if model in _KNOWN_MODELS and not option.startswith("---"):
                    framework_components.setdefault(model, []).append(
                        (framework, option, conf, qualifier)
                    )
                continue

            # Also handle: | `model` | position | HIGH | qualifier | (no framework)
            # Also: | **model** | position | HIGH | qualifier |
            table_simple = re.search(
                r"\|\s*[*`]*(\w+)[*`]*\s*\|\s*(.+?)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|",
                line,
            )
            if table_simple:
                model = table_simple.group(1).lower()
                option = table_simple.group(2).strip().strip("*`").strip()
                if model in _KNOWN_MODELS and not option.startswith("---"):
                    conf = self._parse_confidence(table_simple.group(3))
                    qualifier = table_simple.group(4).strip()
                    positions[model] = Position(
                        model=model, round_num=round_num, primary_option=option,
                        components=[option], confidence=conf, qualifier=qualifier,
                    )
                continue

            # Try per-framework format: model/FRAMEWORK: POSITION [CONFIDENCE] — qualifier
            fw_match = re.match(
                r"[*`]*(\w+)/(\w+)[*`]*:?\s*"   # model/framework
                r"(.+?)\s*"                      # option
                r"\[([^\]]+)\]\s*"               # confidence bracket
                r"(?:[—-]\s*(.+))?",             # optional qualifier
                line,
            )
            if fw_match:
                model = fw_match.group(1).lower()
                if model not in _KNOWN_MODELS:
                    continue
                framework = fw_match.group(2).upper()
                option = fw_match.group(3).strip().strip("*`").strip()
                conf = self._parse_confidence(fw_match.group(4))
                qualifier = (fw_match.group(5) or "").strip()
                framework_components.setdefault(model, []).append(
                    (framework, option, conf, qualifier)
                )
                continue

            # Standard format: model: OPTION [CONFIDENCE] — qualifier
            match = re.match(
                r"[*`]*(\w+)[*`]*:?\s*"         # model name (with optional markdown + colon)
                r"(.+?)\s*"                      # option (lazy until confidence bracket)
                r"\[([^\]]+)\]\s*"               # confidence bracket
                r"(?:[—-]\s*(.+))?",             # optional qualifier
                line,
            )
            if match:
                model = match.group(1).lower()
                if model not in _KNOWN_MODELS:
                    continue
                option = match.group(2).strip().strip("*`").strip()
                conf = self._parse_confidence(match.group(3))
                qualifier = (match.group(4) or "").strip()
                positions[model] = Position(
                    model=model, round_num=round_num, primary_option=option,
                    components=[option], confidence=conf, qualifier=qualifier,
                )

        # Merge per-framework components into composite positions
        for model, components in framework_components.items():
            if model not in _KNOWN_MODELS:
                continue
            comp_labels = [f"{fw}:{opt}" for fw, opt, _, _ in components]
            primary = " + ".join(comp_labels)
            # Use the lowest confidence across frameworks
            confs = [c for _, _, c, _ in components]
            min_conf = min(confs, key=lambda c: {"HIGH": 2, "MEDIUM": 1, "LOW": 0}[c.value])
            qualifiers = [q for _, _, _, q in components if q]
            positions[model] = Position(
                model=model, round_num=round_num, primary_option=primary,
                components=comp_labels, confidence=min_conf,
                qualifier="; ".join(qualifiers),
                kind="sequence",
            )

        return positions

    @staticmethod
    def _parse_confidence(conf_text: str) -> Confidence:
        conf_text = conf_text.upper()
        if "HIGH" in conf_text:
            return Confidence.HIGH
        elif "MEDIUM" in conf_text:
            return Confidence.MEDIUM
        elif "LOW" in conf_text:
            return Confidence.LOW
        return Confidence.MEDIUM


@pipeline_stage(
    name="Position Tracker",
    description="Extracts each model's position label and confidence from round outputs. Tracks position changes across rounds. Computes agreement_ratio for Gate 2.",
    stage_type="track",
    order=4,
    provider="sonnet (1 call per round)",
    inputs=["model_outputs (dict[model, text])"],
    outputs=["positions (dict[model, Position])", "agreement_ratio (float)", "position_changes (list)"],
    prompt=POSITION_EXTRACT_PROMPT,
    logic="""Sonnet extracts: model: POSITION [CONFIDENCE] — qualifier.
Parser handles bold (**model:**), multi-word options, compound positions.
Agreement ratio = count(majority_option) / total_models.""",
    failure_mode="Extraction fails: empty positions, agreement=0.0.",
    cost="1 Sonnet call per round ($0 on Max subscription)",
    stage_id="position_tracker",
)
def _register_position_tracker(): pass
