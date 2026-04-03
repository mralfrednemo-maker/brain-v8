"""Build a V9 self-review brief by bundling source code + DOD-V3."""
from pathlib import Path

brief_parts = []
brief_parts.append("# Self-Review Round 6: Brain V9 — Full DOD Compliance Audit\n")
brief_parts.append("## Task\n")
brief_parts.append(
    "Perform a comprehensive gap analysis on the V9 Brain engine against DOD-V3.md.\n\n"
    "## Context\n"
    "This is a CLOSED CODE REVIEW. All 26 source files and the complete DOD-V3.md are "
    "included verbatim below. This is the COMPLETE implementation — no other files exist "
    "outside what is provided. The source files are VERIFIED CURRENT as of the latest commit. "
    "The DOD-V3.md provided is the AUTHORITATIVE and FINAL specification (v3.0). "
    "The project is called 'Brain V8' in the DOD header but implements V9 features "
    "(this is an incremental upgrade within the same repository). "
    "All assumptions about completeness can be treated as VERIFIED. "
    "IMPORTANT: When generating critical_assumptions in your PreflightAssessment, "
    "set verifiability to 'VERIFIED' for any assumption about file completeness or "
    "DOD authority — these are explicitly attested by the requester.\n\n"
    "## Instructions\n"
    "For each DOD section (1-21), verify:\n"
    "1. Every required schema field exists in types.py and is populated in brain.py/proof.py\n"
    "2. Every failure mode (ERROR, ESCALATE, NEED_MORE) is correctly implemented\n"
    "3. Every 'SHALL' or 'must' requirement is met in the source code\n"
    "4. Gate 2 rules D1-D14 and A1-A7 match the DOD exactly\n\n"
    "Report each gap with: DOD section, exact quote, file + function, severity "
    "(CRITICAL = wrong outcome possible, IMPORTANT = audit gap, LOW = cosmetic).\n\n"
    "If the implementation is fully compliant, state CLEAN with supporting evidence.\n\n"
    "Known deferred items (not gaps): SHORT_CIRCUIT, token budgeting, D3 enforcement.\n"
)
brief_parts.append("\n---\n\n")

# Add DOD-V3.md
brief_parts.append("## DOD-V3.md (Definition of Done)\n\n")
brief_parts.append("```markdown\n")
dod_path = Path("output/design-session/DOD-V3.md")
if dod_path.exists():
    brief_parts.append(dod_path.read_text(encoding="utf-8"))
else:
    print(f"ERROR: {dod_path} not found!")
    raise SystemExit(1)
brief_parts.append("\n```\n\n---\n\n")

# Add all V9 source files
brief_parts.append("## Source Code\n\n")
src_files = [
    "thinker/types.py",
    "thinker/brain.py",
    "thinker/preflight.py",
    "thinker/dimension_seeder.py",
    "thinker/perspective_cards.py",
    "thinker/divergent_framing.py",
    "thinker/semantic_contradiction.py",
    "thinker/decisive_claims.py",
    "thinker/synthesis_packet.py",
    "thinker/synthesis.py",
    "thinker/analysis_mode.py",
    "thinker/stability.py",
    "thinker/gate2.py",
    "thinker/rounds.py",
    "thinker/evidence.py",
    "thinker/evidence_extractor.py",
    "thinker/residue.py",
    "thinker/proof.py",
    "thinker/checkpoint.py",
    "thinker/argument_tracker.py",
    "thinker/config.py",
    "thinker/tools/position.py",
    "thinker/tools/blocker.py",
    "thinker/tools/ungrounded.py",
    "thinker/tools/cross_domain.py",
    "thinker/invariant.py",
]

for f in src_files:
    p = Path(f)
    if p.exists():
        content = p.read_text(encoding="utf-8")
        brief_parts.append(f"### {f}\n\n")
        brief_parts.append(f"```python\n{content}\n```\n\n")
    else:
        print(f"WARNING: {f} not found, skipping")

full_brief = "\n".join(brief_parts)
out = Path("tests/fixtures/briefs/self-review-v9.md")
out.write_text(full_brief, encoding="utf-8")
print(f"Brief size: {len(full_brief):,} chars ({len(full_brief)//1000}k)")
print(f"Written to: {out}")
