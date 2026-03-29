"""Pipeline stage registry — self-documenting architecture.

Decorators declare metadata for each pipeline stage. The HTML diagram
generator reads this registry at runtime — no hardcoded descriptions.

Usage:
    @pipeline_stage(
        name="Gate 1",
        description="Is the brief complete?",
        stage_type="gate",
        order=1,
        provider="sonnet",
        inputs=["brief"],
        outputs=["passed", "questions", "reasoning"],
        prompt=GATE1_PROMPT,
        logic="PASS if specific. NEED_MORE if vague. Fail open on error.",
    )
    async def run_gate1(client, brief):
        ...

    # Generate diagram from registry:
    from thinker.pipeline import STAGE_REGISTRY, generate_architecture_html
    generate_architecture_html(Path("architecture.html"))
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class StageInfo:
    """Metadata for a single pipeline stage."""
    id: str                          # unique key, e.g. "gate1", "r1", "search"
    name: str                        # display name
    description: str                 # what it does
    stage_type: str                  # "gate", "round", "track", "search", "synthesis", "deterministic"
    order: int                       # pipeline order (for diagram layout)
    provider: str = ""               # "sonnet", "4_models", "deterministic", etc.
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    prompt: str = ""                 # prompt template (if LLM-based)
    logic: str = ""                  # decision logic description
    thresholds: dict = field(default_factory=dict)  # e.g. {"agreement": 0.75}
    failure_mode: str = ""           # what happens on failure
    cost: str = ""                   # cost info


# Global registry — populated by decorators at import time
STAGE_REGISTRY: dict[str, StageInfo] = {}
_order_counter = 0


def pipeline_stage(
    name: str,
    description: str,
    stage_type: str,
    order: int,
    provider: str = "",
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    prompt: str = "",
    logic: str = "",
    thresholds: dict | None = None,
    failure_mode: str = "",
    cost: str = "",
    stage_id: str = "",
):
    """Decorator that registers a function as a pipeline stage."""
    global _order_counter

    def decorator(func):
        nonlocal stage_id
        _id = stage_id or func.__name__

        info = StageInfo(
            id=_id,
            name=name,
            description=description,
            stage_type=stage_type,
            order=order,
            provider=provider,
            inputs=inputs or [],
            outputs=outputs or [],
            prompt=prompt,
            logic=logic,
            thresholds=thresholds or {},
            failure_mode=failure_mode,
            cost=cost,
        )
        STAGE_REGISTRY[_id] = info

        # Attach metadata to function for introspection
        func._stage_info = info
        return func

    return decorator


# --- Colors for stage types ---
_TYPE_COLORS = {
    "gate": ("#f97316", "#000"),      # orange
    "round": ("#1d4ed8", "#fff"),     # blue
    "track": ("#be185d", "#fff"),     # pink
    "search": ("#a855f7", "#fff"),    # purple
    "synthesis": ("#06b6d4", "#000"), # cyan
    "deterministic": ("#22c55e", "#000"),  # green
}


def generate_architecture_html(path: Path, run_events: list | None = None, proof: dict | None = None, report: str = ""):
    """Generate the interactive architecture diagram from the stage registry.

    If run_events and proof are provided, the diagram is auto-populated
    with actual run data alongside the architecture reference.
    """
    stages = sorted(STAGE_REGISTRY.values(), key=lambda s: s.order)

    # Build run data index if available
    run_data = {}
    if run_events:
        for e in run_events:
            run_data[e.get("stage", "")] = e

    # Pipeline bar — shows actual execution flow, not just stage types
    # The real flow repeats stages across rounds:
    # Gate1 → R1 → Track → Search → R2 → Track → Search → R3 → Track → Synthesis → Gate2
    _FLOW = [
        ("gate1", "Gate 1"),
        ("round", "R1 (4)"),
        ("argument_tracker", "Args"),
        ("position_tracker", "Pos"),
        ("search", "Search"),
        ("page_fetch", "Fetch"),
        ("evidence_extractor", "Extract"),
        ("round", "R2 (3)"),
        ("argument_tracker", "Args"),
        ("position_tracker", "Pos"),
        ("search", "Search"),
        ("page_fetch", "Fetch"),
        ("evidence_extractor", "Extract"),
        ("round", "R3 (2)"),
        ("argument_tracker", "Args"),
        ("position_tracker", "Pos"),
        ("round", "R4 (2)"),
        ("argument_tracker", "Args"),
        ("position_tracker", "Pos"),
        ("synthesis", "Synthesis"),
        ("gate2", "Gate 2"),
        ("invariant_validator", "Invariants"),
        ("residue_verification", "Residue"),
    ]
    pipeline_nodes = []
    for stage_id, label in _FLOW:
        s = STAGE_REGISTRY.get(stage_id)
        if s:
            bg, fg = _TYPE_COLORS.get(s.stage_type, ("#64748b", "#fff"))
        else:
            bg, fg = "#64748b", "#fff"
        pipeline_nodes.append(
            f'<div class="pipe-node" style="background:{bg};color:{fg}" '
            f'onclick="show(\'{stage_id}\')">{label}</div>'
        )
    pipeline_html = '<span class="pipe-arrow">→</span>'.join(pipeline_nodes)

    # Detail panels
    panels_html = ""
    for s in stages:
        bg, fg = _TYPE_COLORS.get(s.stage_type, ("#64748b", "#fff"))
        tag_label = s.stage_type.upper()
        if s.provider:
            tag_label += f" | {s.provider}"

        # Build sections
        sections = ""

        # Description
        sections += _detail("Purpose", f"<p>{s.description}</p>")

        # Inputs/Outputs
        if s.inputs or s.outputs:
            io_html = "<table><tr><th>Inputs</th><th>Outputs</th></tr><tr>"
            io_html += f"<td>{'<br>'.join(s.inputs) or 'none'}</td>"
            io_html += f"<td>{'<br>'.join(s.outputs) or 'none'}</td>"
            io_html += "</tr></table>"
            sections += _detail("Inputs / Outputs", io_html)

        # Logic
        if s.logic:
            sections += _detail("Decision Logic", f"<pre class='logic'>{_esc(s.logic)}</pre>")

        # Thresholds
        if s.thresholds:
            rows = "".join(f"<tr><td><code>{k}</code></td><td>{v}</td></tr>" for k, v in s.thresholds.items())
            sections += _detail("Thresholds", f"<table><tr><th>Parameter</th><th>Value</th></tr>{rows}</table>")

        # Prompt
        if s.prompt:
            prompt_preview = s.prompt[:2000] + ("..." if len(s.prompt) > 2000 else "")
            sections += _detail("Prompt Template", f"<pre class='logic'>{_esc(prompt_preview)}</pre>")

        # Failure mode
        if s.failure_mode:
            sections += _detail("Failure Handling", f"<p>{_esc(s.failure_mode)}</p>")

        # Cost
        if s.cost:
            sections += _detail("Cost", f"<p>{s.cost}</p>")

        # Run data (if available)
        run_event = run_data.get(s.id)
        if run_event:
            rd = run_event.get("data", {})
            elapsed = run_event.get("elapsed_s", 0)
            run_html = f"<p><strong>Elapsed:</strong> {elapsed:.1f}s</p>"
            # Show data as formatted JSON
            import json
            run_html += f"<pre class='logic'>{_esc(json.dumps(rd, indent=2, default=str)[:3000])}</pre>"
            sections += _detail("Run Data (this run)", run_html, open_default=True)

        panels_html += f"""
<div class="panel" id="panel-{s.id}">
  <div class="panel-header" style="background:{bg};color:{fg}">
    <h2>{s.name}</h2>
    <span class="tag">{tag_label}</span>
  </div>
  <hr class="sep">
  {sections}
  <div style="height:12px"></div>
</div>"""

    # Run summary banner (if proof available)
    banner = ""
    if proof:
        oc = proof.get("controller_outcome", {})
        banner = f"""
<div class="banner">
  <span class="val">{oc.get('verdict','N/A')}</span> |
  <span class="val">{oc.get('outcome_class','N/A')}</span> |
  agreement: {oc.get('agreement_ratio','N/A')} |
  evidence: {proof.get('evidence_items',0)} |
  rounds: {len(proof.get('rounds',{}))}
</div>"""

    # Report section
    report_section = ""
    if report:
        report_section = f"""
<div class="panel visible" id="panel-report">
  <div class="panel-header" style="background: var(--surface2);">
    <h2>Synthesis Report</h2>
  </div>
  <hr class="sep">
  <details><summary>Full Report</summary>
  <div class="detail-body"><pre class="logic">{_esc(report)}</pre></div>
  </details>
  <div style="height:12px"></div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>Thinker V8 — Architecture & Run Report</title>
<style>
  :root {{ --bg: #0f172a; --surface: #1e293b; --surface2: #334155; --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6; --green: #22c55e; --red: #ef4444; --orange: #f97316; --yellow: #eab308; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; line-height: 1.6; max-width: 1200px; margin: 0 auto; }}
  h1 {{ text-align: center; color: var(--accent); margin-bottom: 4px; font-size: 1.6em; }}
  h2 {{ font-size: 1.1em; }}
  .subtitle {{ text-align: center; color: var(--muted); margin-bottom: 20px; font-size: 0.9em; }}
  .banner {{ background: var(--surface); border-radius: 10px; padding: 14px 20px; margin: 16px 0; border-left: 4px solid var(--accent); font-size: 1.1em; }}
  .banner .val {{ font-weight: 700; color: var(--green); }}
  .pipeline {{ display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 6px; margin: 16px 0 24px; }}
  .pipe-node {{ padding: 8px 14px; border-radius: 6px; font-weight: 600; font-size: 0.82em; cursor: pointer; transition: all 0.2s; border: 2px solid transparent; }}
  .pipe-node:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.4); }}
  .pipe-node.active {{ border-color: #fff; }}
  .pipe-arrow {{ color: var(--muted); font-size: 1.2em; }}
  .panel {{ background: var(--surface); border-radius: 10px; margin-bottom: 12px; overflow: hidden; border: 1px solid var(--surface2); display: none; }}
  .panel.visible {{ display: block; animation: fadeIn 0.25s ease; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .panel-header {{ padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; }}
  .tag {{ font-size: 0.7em; padding: 3px 10px; border-radius: 20px; font-weight: 600; background: rgba(255,255,255,0.2); }}
  .sep {{ border: none; border-top: 1px solid var(--surface2); margin: 0 16px; }}
  details {{ margin: 6px 16px; background: var(--bg); border: 1px solid var(--surface2); border-radius: 6px; }}
  details[open] {{ border-color: var(--accent); }}
  summary {{ padding: 8px 12px; cursor: pointer; font-weight: 600; font-size: 0.9em; color: var(--accent); list-style: none; }}
  summary::before {{ content: '▸ '; }} details[open] summary::before {{ content: '▾ '; }}
  summary::-webkit-details-marker {{ display: none; }}
  .detail-body {{ padding: 0 12px 12px; font-size: 0.88em; }}
  .logic {{ background: var(--surface2); border-radius: 4px; padding: 10px; font-family: 'Cascadia Code','Fira Code',monospace; font-size: 0.85em; white-space: pre-wrap; max-height: 500px; overflow-y: auto; }}
  table {{ width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 0.88em; }}
  th {{ background: var(--surface2); text-align: left; padding: 6px 8px; color: var(--accent); }}
  td {{ padding: 6px 8px; border-bottom: 1px solid var(--surface2); }}
  code {{ background: var(--surface2); padding: 1px 5px; border-radius: 3px; font-size: 0.86em; }}
  p {{ margin: 4px 0; }}
</style>
</head><body>
<h1>Thinker V8 Brain Engine</h1>
<p class="subtitle">Auto-generated from code + run data. Click any stage to explore.</p>
{banner}
<div class="pipeline">{pipeline_html}</div>
<div class="panels">{panels_html}{report_section}</div>
<script>
function show(id) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('visible'));
  document.querySelectorAll('.pipe-node').forEach(n => n.classList.remove('active'));
  const panel = document.getElementById('panel-' + id);
  if (panel) {{ panel.classList.add('visible'); panel.scrollIntoView({{ behavior: 'smooth', block: 'start' }}); }}
  if (event && event.target) event.target.classList.add('active');
}}
</script>
</body></html>"""

    path.write_text(html, encoding="utf-8")


def _detail(title: str, content: str, open_default: bool = False) -> str:
    """Build a collapsible detail section."""
    open_attr = " open" if open_default else ""
    return f"""<details{open_attr}><summary>{title}</summary><div class="detail-body">{content}</div></details>"""


def _esc(text: str) -> str:
    """Escape HTML entities."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
