"""ANALYSIS mode — modified prompts and contracts for exploration modality (DESIGN-V3.md Section 4).

~80% pipeline reuse. What changes:
- Round prompts: exploration, not convergence
- Frame survival: EXPLORED/NOTED/UNEXPLORED (no dropping)
- Synthesis: analysis map per dimension, not verdict
- Gate 2: A1-A7 rules (in gate2.py)

Deployed with debug_mode per Section 4.6: rules log without enforcing initially.
"""
from __future__ import annotations


# V3.1 ADDITION-10: 8-section synthesis structure for ANALYSIS runs
ANALYSIS_SYNTHESIS_SECTIONS = [
    "framing",           # How the question is framed
    "aspect_map",        # Exploration by dimension
    "competing_lenses",  # Alternative hypotheses or interpretive frames
    "evidence_for",      # Evidence supporting each lens
    "evidence_against",  # Evidence against each lens
    "uncertainties",     # Unresolved unknowns
    "information_gaps",  # What data would most change the map
    "boundary_summary",  # Known / Inferred / Unknown classification
]


def get_analysis_round_preamble() -> str:
    """Get the ANALYSIS-mode preamble prepended to round prompts."""
    return (
        "## Mode: EXPLORATORY ANALYSIS\n"
        "Your task is to EXPLORE and MAP this question by dimension — identify:\n"
        "- **Knowns** (evidence-backed facts)\n"
        "- **Inferred** (model-supported but unverified)\n"
        "- **Unknowns** (gaps in knowledge)\n\n"
        "Do NOT seek agreement or converge on a verdict. Deepen exploration.\n"
        "Do NOT propose recommendations — map the territory.\n\n"
    )


def get_analysis_synthesis_contract() -> str:
    """Get the modified synthesis contract for ANALYSIS mode."""
    return (
        "\n## ANALYSIS Mode Synthesis Contract\n"
        "You are producing an EXPLORATORY MAP, NOT a decision.\n"
        "Header: 'EXPLORATORY MAP — NOT A DECISION'\n\n"
        "Required output structure:\n"
        "1. Framing of the question\n"
        "2. Aspect map (by dimension)\n"
        "3. Competing hypotheses or lenses\n"
        "4. Evidence for and against each\n"
        "5. Unresolved uncertainties\n"
        "6. What information would most change the map\n\n"
        "Do NOT provide a verdict, recommendation, or conclusion.\n"
    )
