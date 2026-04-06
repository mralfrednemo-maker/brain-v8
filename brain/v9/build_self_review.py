"""Build a self-review brief by bundling source code + DoD."""
from pathlib import Path

brief_parts = []
brief_parts.append("# Self-Review: Thinker V8 Brain — Gap Analysis\n")
brief_parts.append("## Task\n")
brief_parts.append("Perform a gap analysis on the V8 Brain engine. Review the source code and the Definition of Done document below. Identify:\n")
brief_parts.append("1. Any DoD items marked DONE that the code does not fully implement\n")
brief_parts.append("2. Any code that contradicts the design constraints\n")
brief_parts.append("3. Any architectural weaknesses, missing error handling, or edge cases\n")
brief_parts.append("4. Any discrepancies between what the code does and what the DoD claims\n\n")
brief_parts.append("This is a closed code review — all source code and documentation is provided below. No external information is needed.\n\n")
brief_parts.append("---\n\n")

# Add V8-DOD.md
brief_parts.append("## V8-DOD.md\n\n")
brief_parts.append("```markdown\n")
brief_parts.append(Path("V8-DOD.md").read_text(encoding="utf-8"))
brief_parts.append("\n```\n\n---\n\n")

# Add source files
brief_parts.append("## Source Code\n\n")
src_files = [
    "thinker/types.py",
    "thinker/brain.py",
    "thinker/gate1.py",
    "thinker/gate2.py",
    "thinker/rounds.py",
    "thinker/synthesis.py",
    "thinker/search.py",
    "thinker/evidence.py",
    "thinker/evidence_extractor.py",
    "thinker/page_fetch.py",
    "thinker/invariant.py",
    "thinker/residue.py",
    "thinker/proof.py",
    "thinker/checkpoint.py",
    "thinker/argument_tracker.py",
    "thinker/config.py",
    "thinker/tools/position.py",
    "thinker/tools/blocker.py",
    "thinker/tools/contradiction.py",
    "thinker/tools/cross_domain.py",
    "thinker/bing_search.py",
]

for f in src_files:
    p = Path(f)
    if p.exists():
        content = p.read_text(encoding="utf-8")
        brief_parts.append(f"### {f}\n\n")
        brief_parts.append(f"```python\n{content}\n```\n\n")

full_brief = "\n".join(brief_parts)
out = Path("tests/fixtures/briefs/self-review.md")
out.write_text(full_brief, encoding="utf-8")
print(f"Brief size: {len(full_brief)} chars ({len(full_brief)//1000}k)")
print(f"Written to: {out}")
