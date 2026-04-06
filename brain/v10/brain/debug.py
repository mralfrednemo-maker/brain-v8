"""Debug infrastructure for the Brain pipeline.

Three modes:
  --verbose    : Full logging to console + log file (no pausing)
  --step       : Pause at each stage, show data, wait for Enter to continue
  (default)    : Silent, only final output

All modes emit structured events to RunLog. After the run, RunLog can
generate the interactive HTML diagram auto-populated with real data.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class StageEvent:
    """A single event in the pipeline."""
    stage: str           # e.g. "gate1", "r1", "search_r1", "arg_extract_r1"
    label: str           # Human-readable label
    timestamp: float     # time.monotonic()
    elapsed_s: float = 0.0
    data: dict = field(default_factory=dict)
    status: str = "ok"   # "ok", "fail", "skip"


class RunLog:
    """Structured event log for a Brain run.

    Captures every stage's inputs, outputs, and timing.
    Can generate debug HTML and JSON log after the run.
    """

    def __init__(self, verbose: bool = False, step: bool = False):
        self.verbose = verbose or step
        self.step = step
        self.events: list[StageEvent] = []
        self._start_time = time.monotonic()
        self._lines: list[str] = []  # full text log

    def _print(self, msg: str):
        """Print if verbose mode."""
        self._lines.append(msg)
        if self.verbose:
            print(msg)

    def _pause(self, stage: str):
        """Pause for user input if step mode."""
        if self.step:
            try:
                input(f"\n  [STEP] Press Enter to continue past {stage}... ")
            except EOFError:
                pass

    # --- Stage logging methods ---

    def gate1_start(self, brief_len: int):
        self._print(f"\n{'='*60}")
        self._print(f"  GATE 1 — Brief quality check ({brief_len} chars)")
        self._print(f"{'='*60}")

    def gate1_result(self, passed: bool, reasoning: str, questions: list[str], elapsed: float):
        status = "PASS" if passed else "NEED_MORE"
        self._print(f"  Result: {status} ({elapsed:.1f}s)")
        self._print(f"  Reasoning: {reasoning[:200]}...")
        if questions:
            for q in questions:
                self._print(f"    - {q}")
        event = StageEvent(
            stage="gate1", label="Gate 1", timestamp=time.monotonic(),
            elapsed_s=elapsed, status="ok" if passed else "blocked",
            data={"passed": passed, "reasoning": reasoning, "questions": questions},
        )
        self.events.append(event)
        self._pause("gate1")

    def round_start(self, round_num: int, models: list[str], is_last: bool):
        self._print(f"\n{'='*60}")
        self._print(f"  ROUND {round_num} — {len(models)} models: {', '.join(models)}")
        if is_last:
            self._print(f"  (final round — no search after this)")
        self._print(f"{'='*60}")

    def round_result(self, round_num: int, responded: list[str], failed: list[str],
                     texts: dict[str, str], elapsed: float):
        self._print(f"  Responded: {responded} ({elapsed:.1f}s)")
        if failed:
            self._print(f"  Failed: {failed}")
        # Show truncated outputs
        for model, text in texts.items():
            first_line = text.strip().split('\n')[0][:120]
            self._print(f"    {model}: {first_line}...")
            # Show search requests if present
            if "SEARCH_REQUESTS:" in text or "SEARCH REQUESTS:" in text:
                in_section = False
                for line in text.split('\n'):
                    if 'SEARCH_REQUESTS:' in line or 'SEARCH REQUESTS:' in line:
                        in_section = True
                        continue
                    if in_section:
                        line = line.strip()
                        if line and line.upper() != 'NONE':
                            self._print(f"      [SEARCH REQ] {line}")
                        if not line or line.upper() == 'NONE':
                            break
        event = StageEvent(
            stage=f"r{round_num}", label=f"Round {round_num}",
            timestamp=time.monotonic(), elapsed_s=elapsed,
            data={
                "responded": responded, "failed": failed,
                "output_lengths": {m: len(t) for m, t in texts.items()},
                "outputs": {m: t[:500] + "..." for m, t in texts.items()},
            },
        )
        self.events.append(event)
        self._pause(f"r{round_num}")

    def arg_extract(self, round_num: int, args: list, elapsed: float, raw_response: str = ""):
        self._print(f"\n  --- Argument Extraction (R{round_num}) ---")
        self._print(f"  {len(args)} arguments extracted ({elapsed:.1f}s)")
        if len(args) == 0 and raw_response:
            self._print(f"  [RAW RESPONSE - 0 args parsed]:")
            for line in raw_response[:500].split('\n'):
                self._print(f"    | {line}")
        for a in args[:6]:
            self._print(f"    {a.argument_id}: [{a.model}] {a.text[:80]}...")
        if len(args) > 6:
            self._print(f"    ... and {len(args)-6} more")
        self.events.append(StageEvent(
            stage=f"arg_extract_r{round_num}", label=f"Arg Extract R{round_num}",
            timestamp=time.monotonic(), elapsed_s=elapsed,
            data={"count": len(args), "raw_response": raw_response[:2000],
                  "args": [
                {"id": a.argument_id, "model": a.model, "text": a.text[:200]}
                for a in args
            ]},
        ))

    def pos_extract(self, round_num: int, positions: dict, elapsed: float, raw_response: str = ""):
        self._print(f"\n  --- Position Extraction (R{round_num}) ---")
        self._print(f"  {len(positions)} positions extracted ({elapsed:.1f}s)")
        if len(positions) == 0 and raw_response:
            self._print(f"  [RAW RESPONSE - 0 positions parsed]:")
            for line in raw_response[:500].split('\n'):
                self._print(f"    | {line}")
        for model, pos in positions.items():
            self._print(f"    {model}: {pos.primary_option} [{pos.confidence.value}]")
        self.events.append(StageEvent(
            stage=f"pos_extract_r{round_num}", label=f"Pos Extract R{round_num}",
            timestamp=time.monotonic(), elapsed_s=elapsed,
            data={"raw_response": raw_response[:2000],
                  "positions": {
                m: {"option": p.primary_option, "confidence": p.confidence.value, "qualifier": p.qualifier}
                for m, p in positions.items()
            }},
        ))
        self._pause(f"positions_r{round_num}")

    def arg_compare(self, prev_round: int, addressed: int, mentioned: int,
                    ignored: int, elapsed: float, unaddressed_args: list):
        curr = prev_round + 1
        self._print(f"\n  --- Argument Comparison (R{prev_round} vs R{curr}) ---")
        self._print(f"  ADDRESSED: {addressed} | MENTIONED: {mentioned} | IGNORED: {ignored} ({elapsed:.1f}s)")
        for a in unaddressed_args[:5]:
            self._print(f"    [{a.status.value}] {a.argument_id}: [{a.model}] {a.text[:60]}...")
        self.events.append(StageEvent(
            stage=f"arg_compare_r{prev_round}_r{curr}", label=f"Arg Compare R{prev_round}→R{curr}",
            timestamp=time.monotonic(), elapsed_s=elapsed,
            data={"addressed": addressed, "mentioned": mentioned, "ignored": ignored,
                  "unaddressed": [{"id": a.argument_id, "model": a.model, "status": a.status.value,
                                   "text": a.text[:200]} for a in unaddressed_args]},
        ))
        self._pause(f"arg_compare_r{prev_round}")

    def pos_changes(self, round_from: int, round_to: int, changes: list[dict]):
        if changes:
            self._print(f"\n  --- Position Changes (R{round_from}→R{round_to}) ---")
            for c in changes:
                self._print(f"    {c['model']}: {c['from_position']} → {c['to_position']}")
        self.events.append(StageEvent(
            stage=f"pos_changes_r{round_from}_r{round_to}",
            label=f"Pos Changes R{round_from}→R{round_to}",
            timestamp=time.monotonic(),
            data={"changes": changes},
        ))

    def search_start(self, phase: str, model_requests: list[str], proactive: list[str]):
        all_queries = model_requests + proactive
        self._print(f"\n  --- Search Phase ({phase}) ---")
        self._print(f"  Model-requested: {len(model_requests)} | Proactive: {len(proactive)}")
        for q in model_requests[:5]:
            self._print(f"    [MODEL] {q}")
        for q in proactive[:5]:
            self._print(f"    [PROACTIVE] {q}")

    def search_result(self, phase: str, queries_total: int, admitted: int, elapsed: float):
        self._print(f"  Queries executed: {queries_total} | Evidence admitted: {admitted} ({elapsed:.1f}s)")
        self.events.append(StageEvent(
            stage=f"search_{phase}", label=f"Search {phase}",
            timestamp=time.monotonic(), elapsed_s=elapsed,
            data={"queries_total": queries_total, "evidence_admitted": admitted},
        ))
        self._pause(f"search_{phase}")

    def synthesis_result(self, report_len: int, has_json: bool, elapsed: float):
        self._print(f"\n{'='*60}")
        self._print(f"  SYNTHESIS GATE ({elapsed:.1f}s)")
        self._print(f"{'='*60}")
        self._print(f"  Report: {report_len} chars | JSON section: {'yes' if has_json else 'no'}")
        self.events.append(StageEvent(
            stage="synthesis", label="Synthesis Gate",
            timestamp=time.monotonic(), elapsed_s=elapsed,
            data={"report_length": report_len, "has_json": has_json},
        ))
        self._pause("synthesis")

    def gate2_result(self, outcome: str, agreement: float, outcome_class: str,
                     ignored: int, evidence: int, contradictions: int, blockers: int):
        self._print(f"\n{'='*60}")
        self._print(f"  GATE 2 — DETERMINISTIC")
        self._print(f"{'='*60}")
        self._print(f"  Outcome:     {outcome}")
        self._print(f"  Class:       {outcome_class}")
        self._print(f"  Agreement:   {agreement:.2f}")
        self._print(f"  Ignored:     {ignored}")
        self._print(f"  Evidence:    {evidence}")
        self._print(f"  Contradict:  {contradictions}")
        self._print(f"  Blockers:    {blockers}")
        self.events.append(StageEvent(
            stage="gate2", label="Gate 2",
            timestamp=time.monotonic(),
            data={
                "outcome": outcome, "outcome_class": outcome_class,
                "agreement_ratio": agreement, "ignored_arguments": ignored,
                "evidence_count": evidence, "contradictions": contradictions,
                "open_blockers": blockers,
            },
        ))
        self._pause("gate2")

    def run_complete(self, outcome: str, outcome_class: str):
        total = time.monotonic() - self._start_time
        self._print(f"\n{'='*60}")
        self._print(f"  RUN COMPLETE — {outcome} / {outcome_class} ({total:.1f}s total)")
        self._print(f"{'='*60}")

    # --- Output methods ---

    def save_log(self, path: Path):
        """Save full text log to file."""
        path.write_text("\n".join(self._lines), encoding="utf-8")

    def save_events_json(self, path: Path):
        """Save structured events to JSON."""
        data = []
        for e in self.events:
            data.append({
                "stage": e.stage, "label": e.label,
                "elapsed_s": round(e.elapsed_s, 2),
                "status": e.status, "data": e.data,
            })
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def generate_html(self, path: Path, proof: dict, report: str):
        """Generate auto-populated interactive HTML diagram from run data."""
        events_by_stage = {e.stage: e for e in self.events}

        # Extract data for each stage
        gate1 = events_by_stage.get("gate1", StageEvent("gate1", "", 0))
        rounds_data = []
        for i in range(1, 5):
            r = events_by_stage.get(f"r{i}")
            if r:
                rounds_data.append(r)

        positions_html = ""
        for rnd, pos_data in proof.get("model_positions_by_round", {}).items():
            if pos_data:
                positions_html += f"<h4>Round {rnd}</h4><table><tr><th>Model</th><th>Position</th><th>Confidence</th></tr>"
                for m, d in pos_data.items():
                    positions_html += f"<tr><td>{m}</td><td>{d['primary_option']}</td><td>{d['confidence']}</td></tr>"
                positions_html += "</table>"

        changes_html = ""
        for c in proof.get("position_changes", []):
            changes_html += f"<li>{c['model']}: R{c['from_round']}→R{c['to_round']} <code>{c['from_position']}</code> → <code>{c['to_position']}</code></li>"
        if not changes_html:
            changes_html = "<li>(no position changes)</li>"

        # Build argument tracking sections
        arg_sections = ""
        for e in self.events:
            if e.stage.startswith("arg_extract_"):
                rnd = e.stage.split("_")[-1]
                args_list = "".join(f"<li><code>{a['id']}</code> [{a['model']}] {a['text'][:120]}</li>"
                                    for a in e.data.get("args", []))
                arg_sections += f"""<details><summary>R{rnd} Arguments ({e.data.get('count', 0)} extracted, {e.elapsed_s:.1f}s)</summary>
                <div class="detail-body"><ul>{args_list}</ul></div></details>"""
            if e.stage.startswith("arg_compare_"):
                d = e.data
                unaddr = "".join(f"<li>[{a['status']}] <code>{a['id']}</code> [{a['model']}] {a['text'][:120]}</li>"
                                 for a in d.get("unaddressed", []))
                arg_sections += f"""<details><summary>Compare: ADDR={d.get('addressed',0)} MENT={d.get('mentioned',0)} IGN={d.get('ignored',0)} ({e.elapsed_s:.1f}s)</summary>
                <div class="detail-body"><ul>{unaddr if unaddr else '<li>All addressed</li>'}</ul></div></details>"""

        # Search sections
        search_sections = ""
        for e in self.events:
            if e.stage.startswith("search_"):
                d = e.data
                search_sections += f"<p>Phase {e.label}: {d.get('queries_total',0)} queries, {d.get('evidence_admitted',0)} evidence admitted ({e.elapsed_s:.1f}s)</p>"
        if not search_sections:
            search_sections = "<p>(search disabled for this run)</p>"

        # Round outputs
        round_outputs_html = ""
        for e in self.events:
            if e.stage.startswith("r") and e.stage[1:].isdigit():
                rnd = e.stage[1:]
                outputs = e.data.get("outputs", {})
                output_details = "".join(
                    f"<details><summary>{m} ({e.data.get('output_lengths',{}).get(m,0)} chars)</summary>"
                    f"<div class='detail-body'><pre>{txt}</pre></div></details>"
                    for m, txt in outputs.items()
                )
                round_outputs_html += f"<h4>Round {rnd} ({e.elapsed_s:.1f}s)</h4>{output_details}"

        # Gate 2
        g2 = events_by_stage.get("gate2", StageEvent("gate2", "", 0))
        g2d = g2.data

        # Synthesis
        syn = events_by_stage.get("synthesis", StageEvent("synthesis", "", 0))

        outcome = proof.get("controller_outcome", {})

        html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Thinker V8 — Run {proof.get('run_id','')}</title>
<style>
  :root {{ --bg: #0f172a; --surface: #1e293b; --surface2: #334155; --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6; --green: #22c55e; --red: #ef4444; --orange: #f97316; --yellow: #eab308; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; line-height: 1.6; max-width: 1100px; margin: 0 auto; }}
  h1 {{ color: var(--accent); margin-bottom: 4px; }} h2 {{ color: var(--accent); margin: 20px 0 8px; border-bottom: 1px solid var(--surface2); padding-bottom: 6px; }}
  h3 {{ color: var(--orange); margin: 14px 0 6px; }} h4 {{ color: var(--muted); margin: 10px 0 4px; }}
  .banner {{ background: var(--surface); border-radius: 10px; padding: 16px 20px; margin: 16px 0; border-left: 4px solid var(--accent); }}
  .banner .val {{ font-size: 1.4em; font-weight: 700; }} .banner .lbl {{ color: var(--muted); font-size: 0.85em; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 12px 0; }}
  .card {{ background: var(--surface); border-radius: 8px; padding: 14px; text-align: center; }}
  .card .val {{ font-size: 1.6em; font-weight: 700; }} .card .lbl {{ color: var(--muted); font-size: 0.8em; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 0.9em; }}
  th {{ background: var(--surface2); text-align: left; padding: 8px; color: var(--accent); }}
  td {{ padding: 8px; border-bottom: 1px solid var(--surface2); }}
  details {{ background: var(--surface); border: 1px solid var(--surface2); border-radius: 8px; margin: 6px 0; }}
  details[open] {{ border-color: var(--accent); }}
  summary {{ padding: 10px 14px; cursor: pointer; font-weight: 600; color: var(--accent); list-style: none; }}
  summary::before {{ content: '▸ '; }} details[open] summary::before {{ content: '▾ '; }}
  summary::-webkit-details-marker {{ display: none; }}
  .detail-body {{ padding: 0 14px 14px; }}
  pre {{ background: var(--bg); padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 0.82em; white-space: pre-wrap; max-height: 400px; overflow-y: auto; }}
  code {{ background: var(--surface2); padding: 2px 6px; border-radius: 4px; font-size: 0.88em; }}
  ul {{ padding-left: 20px; }} li {{ margin: 3px 0; font-size: 0.9em; }}
  .ok {{ color: var(--green); }} .fail {{ color: var(--red); }} .warn {{ color: var(--yellow); }}
  .section {{ background: var(--surface); border-radius: 10px; padding: 16px 20px; margin: 16px 0; }}
</style>
</head><body>
<h1>Thinker V8 — Run Report</h1>
<p style="color: var(--muted)">Run ID: {proof.get('run_id','')} | {proof.get('timestamp','')}</p>

<div class="banner">
  <span class="val {'ok' if outcome.get('verdict')=='DECIDE' else 'warn'}">{outcome.get('verdict','N/A')}</span>
  <span class="lbl"> | </span>
  <span class="val">{outcome.get('outcome_class','N/A')}</span>
  <span class="lbl"> | agreement: {outcome.get('agreement_ratio','N/A')}</span>
</div>

<div class="grid">
  <div class="card"><div class="val">{len(proof.get('rounds',{}))}</div><div class="lbl">Rounds</div></div>
  <div class="card"><div class="val">{proof.get('evidence_items',0)}</div><div class="lbl">Evidence</div></div>
  <div class="card"><div class="val">{proof.get('blocker_summary',{}).get('total_blockers',0)}</div><div class="lbl">Blockers</div></div>
  <div class="card"><div class="val">{len(self.events)}</div><div class="lbl">Pipeline Events</div></div>
</div>

<h2>Gate 1</h2>
<div class="section">
  <p>Status: <span class="{'ok' if gate1.data.get('passed') else 'fail'}">{('PASS' if gate1.data.get('passed') else 'NEED_MORE')}</span> ({gate1.elapsed_s:.1f}s)</p>
  <details><summary>Reasoning</summary><div class="detail-body"><p>{gate1.data.get('reasoning','N/A')}</p></div></details>
</div>

<h2>Round Outputs</h2>
<div class="section">{round_outputs_html}</div>

<h2>Positions</h2>
<div class="section">{positions_html if positions_html else '<p>(no positions extracted)</p>'}</div>

<h2>Position Changes</h2>
<div class="section"><ul>{changes_html}</ul></div>

<h2>Argument Tracking</h2>
<div class="section">{arg_sections if arg_sections else '<p>(no argument data)</p>'}</div>

<h2>Search</h2>
<div class="section">{search_sections}</div>

<h2>Gate 2 (Deterministic)</h2>
<div class="section">
  <div class="grid">
    <div class="card"><div class="val {'ok' if g2d.get('outcome')=='DECIDE' else 'warn'}">{g2d.get('outcome','N/A')}</div><div class="lbl">Outcome</div></div>
    <div class="card"><div class="val">{g2d.get('outcome_class','N/A')}</div><div class="lbl">Classification</div></div>
    <div class="card"><div class="val">{g2d.get('agreement_ratio','N/A')}</div><div class="lbl">Agreement</div></div>
    <div class="card"><div class="val">{g2d.get('ignored_arguments','N/A')}</div><div class="lbl">Ignored Args</div></div>
  </div>
</div>

<h2>Synthesis Report</h2>
<div class="section">
  <p>Length: {syn.data.get('report_length',0)} chars | JSON: {'yes' if syn.data.get('has_json') else 'no'} ({syn.elapsed_s:.1f}s)</p>
  <details><summary>Full Report</summary><div class="detail-body"><pre>{report}</pre></div></details>
</div>

</body></html>"""

        path.write_text(html, encoding="utf-8")
