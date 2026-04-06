#!/usr/bin/env python3
"""Bundle integrity validator for chamber v3 runs.

Validates that a chamber run bundle is internally consistent before sealing.
Designed to be called as the final step of bundle creation — if validation
fails, the bundle must not be emitted.

Usage:
    python validate_bundle.py <log_path> <trace_path> [--archive-label <label>] [--manifest-brief <text>]

Or as a library:
    from validate_bundle import validate_bundle, derive_manifest_from_trace
    errors = validate_bundle(log_path, trace_path, archive_label=..., manifest_brief=...)
    manifest = derive_manifest_from_trace(trace_path, log_path)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _normalize_brief(text: str) -> str:
    """Normalize brief text for identity comparison.

    Strips whitespace, collapses multiple spaces, removes trailing punctuation,
    and lowercases.  This prevents false failures from harmless formatting
    differences while still catching true cross-brief mismatches.
    """
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.rstrip('.')
    text = text.lower()
    # Remove common prefixes that may differ between sources
    text = re.sub(r'^task:\s*', '', text)
    return text


def _extract_log_task(log_path: Path) -> str | None:
    """Extract the Task: header from the raw chamber log."""
    with log_path.open('r', encoding='utf-8') as fh:
        for i, line in enumerate(fh):
            if line.startswith('Task:'):
                return line[len('Task:'):].strip()
            # Task is always in the first few lines
            if i > 10:
                break
    return None


def _extract_trace_fields(trace_path: Path) -> dict:
    """Extract summary fields from the JSONL trace.

    Reads run_started (first event) and run_completed (last event) to derive
    all manifest summary fields from the actual executed run.
    """
    fields: dict = {}
    first_event = None
    last_event = None

    with trace_path.open('r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if first_event is None:
                first_event = event
            last_event = event

    if first_event and first_event.get('event') == 'run_started':
        fields['run_id'] = first_event.get('run_id', '')
        fields['task'] = first_event.get('task', '')
        fields['search_mode'] = first_event.get('search_mode', '')

    if last_event and last_event.get('event') == 'run_completed':
        fields['final_status'] = last_event.get('status', '')
        fields['slp_highlight_item'] = last_event.get('slp_highlight_item')
        fields['slp_highlight_confidence'] = last_event.get('slp_highlight_confidence', '')
        fields['slp_profile_count'] = last_event.get('slp_profile_count', 0)
        # Search-mode escalation fields (from run_completed trace event)
        if 'upfront_selected_mode' in last_event:
            fields['trace_upfront_mode'] = last_event['upfront_selected_mode']
        if 'final_mode' in last_event:
            fields['trace_final_mode'] = last_event['final_mode']
        if 'search_mode_escalated' in last_event:
            fields['trace_escalated'] = last_event['search_mode_escalated']
        if 'live_retrieval_ever_attempted' in last_event:
            fields['trace_live_retrieval'] = last_event['live_retrieval_ever_attempted']
        # Choice-mode fields
        if 'choice_mode' in last_event:
            fields['choice_mode'] = last_event['choice_mode']
        if 'selected_option' in last_event:
            fields['selected_option'] = last_event['selected_option']
        if 'selected_source_type' in last_event:
            fields['selected_source_type'] = last_event['selected_source_type']

    return fields


def derive_manifest_from_trace(trace_path: Path, log_path: Path) -> dict:
    """Derive all manifest summary fields from the actual run artifacts.

    This is the single source of truth for manifest generation.
    Returns a dict suitable for writing into a manifest file.
    """
    trace_fields = _extract_trace_fields(trace_path)
    log_task = _extract_log_task(log_path)

    # Extract additional fields from the log that aren't in the trace
    search_diagnostics = ''
    final_norm_line = ''
    confidence = None
    approved = []
    rejected = []

    # Search-mode escalation fields
    # Primary source: trace run_completed event (if new code produced it)
    # Fallback: parsed from SEARCH-DIAGNOSTICS log line
    upfront_selected_mode = trace_fields.get('trace_upfront_mode', '') or trace_fields.get('search_mode', '')
    final_mode = trace_fields.get('trace_final_mode', '') or upfront_selected_mode
    search_mode_escalated = trace_fields.get('trace_escalated', False)
    live_retrieval_ever_attempted = trace_fields.get('trace_live_retrieval', False)

    with log_path.open('r', encoding='utf-8') as fh:
        for line in fh:
            if '[SEARCH-DIAGNOSTICS]' in line:
                search_diagnostics = line.strip()
                # Fallback: parse from log line if trace didn't carry these fields
                if not upfront_selected_mode:
                    _upfront_match = re.search(r'upfront_selected_mode=(\S+)', line)
                    if _upfront_match:
                        upfront_selected_mode = _upfront_match.group(1)
                if final_mode == upfront_selected_mode:
                    # Check if log shows a different final mode (escalation)
                    _final_match = re.search(r'final_mode=(\S+)', line)
                    if _final_match:
                        final_mode = _final_match.group(1)
                if not search_mode_escalated:
                    _escalated_match = re.search(r'escalation_triggered=(True|False)', line)
                    if _escalated_match:
                        search_mode_escalated = _escalated_match.group(1) == 'True'
                    elif upfront_selected_mode != final_mode:
                        search_mode_escalated = True  # infer from mode difference
                if not live_retrieval_ever_attempted:
                    _live_match = re.search(r'live_retrieval_ever_attempted=(True|False)', line)
                    if _live_match:
                        live_retrieval_ever_attempted = _live_match.group(1) == 'True'
            if '[FINAL-NORM] Step D: verdict finalized' in line:
                final_norm_line = line.strip()
                # Extract confidence
                conf_match = re.search(r'confidence=([0-9.]+)', line)
                if conf_match:
                    confidence = float(conf_match.group(1))
                # Extract approved/rejected
                app_match = re.search(r"approved=\[([^\]]*)\]", line)
                if app_match:
                    approved = [x.strip().strip("'\"") for x in app_match.group(1).split(',') if x.strip()]
                rej_match = re.search(r"rejected=\[([^\]]*)\]", line)
                if rej_match:
                    rejected = [x.strip().strip("'\"") for x in rej_match.group(1).split(',') if x.strip()]
            if '[SLP-FINAL]' in line:
                trace_fields['slp_final_line'] = line.strip()

    manifest = {
        'run_id': trace_fields.get('run_id', ''),
        'task': log_task or trace_fields.get('task', ''),
        'upfront_selected_mode': upfront_selected_mode,
        'final_mode': final_mode,
        'search_mode_escalated': search_mode_escalated,
        'live_retrieval_ever_attempted': live_retrieval_ever_attempted,
        'final_status': trace_fields.get('final_status', ''),
        'confidence': confidence,
        'approved': approved,
        'rejected': rejected,
        'search_diagnostics': search_diagnostics,
        'final_norm': final_norm_line,
        'slp_highlight_item': trace_fields.get('slp_highlight_item'),
        'slp_highlight_confidence': trace_fields.get('slp_highlight_confidence', ''),
        'slp_profile_count': trace_fields.get('slp_profile_count', 0),
        'choice_mode': trace_fields.get('choice_mode', 'portfolio'),
        'selected_option': trace_fields.get('selected_option'),
        'selected_source_type': trace_fields.get('selected_source_type'),
    }
    return manifest


def validate_bundle(
    log_path: Path,
    trace_path: Path,
    archive_label: str | None = None,
    manifest_brief: str | None = None,
) -> list[str]:
    """Validate bundle integrity. Returns a list of error strings (empty = valid).

    Checks:
    1. Log Task: header exists and is non-empty
    2. Trace run_started event exists and contains a task
    3. Log task and trace task are consistent (normalized comparison)
    4. If archive_label is provided, it must be consistent with the log task
    5. If manifest_brief is provided, it must be consistent with the log task
    6. Trace run_completed event exists
    7. Search mode in trace matches what the log recorded
    """
    errors: list[str] = []

    # --- Check log ---
    if not log_path.exists():
        errors.append(f"Log file does not exist: {log_path}")
        return errors

    log_task = _extract_log_task(log_path)
    if not log_task:
        errors.append("Log file does not contain a Task: header in the first 5000 bytes")
        return errors

    # --- Check trace ---
    if not trace_path.exists():
        errors.append(f"Trace file does not exist: {trace_path}")
        return errors

    trace_fields = _extract_trace_fields(trace_path)
    trace_task = trace_fields.get('task', '')

    if not trace_task:
        errors.append("Trace file does not contain a run_started event with a task field")
    elif _normalize_brief(log_task) != _normalize_brief(trace_task):
        errors.append(
            f"BRIEF MISMATCH: log Task: header does not match trace run_started task.\n"
            f"  Log:   {log_task[:120]}\n"
            f"  Trace: {trace_task[:120]}"
        )

    # --- Check run_completed ---
    if not trace_fields.get('final_status'):
        errors.append("Trace file does not contain a run_completed event with a status field")

    # --- Check archive label if provided ---
    if archive_label:
        # Extract meaningful domain keywords from archive label, ignoring boilerplate
        _label_boilerplate = {"chamber", "bundle", "brief", "run", "report", "test", "trace", "log"}
        label_terms = set(re.findall(r'[a-z]{3,}', archive_label.lower()))
        label_terms -= _label_boilerplate
        # Remove version/date-like tokens (v82, v83, 20260323, etc.)
        label_terms = {t for t in label_terms if not re.match(r'^v?\d+$', t)}
        task_normalized = _normalize_brief(log_task)
        if label_terms:
            matching_terms = [t for t in label_terms if t in task_normalized]
            # At least 1 meaningful domain term from the label should appear in the task
            if len(matching_terms) == 0:
                errors.append(
                    f"BRIEF MISMATCH: archive label does not match log task.\n"
                    f"  Label: {archive_label}\n"
                    f"  Task:  {log_task[:120]}\n"
                    f"  Domain terms from label: {sorted(label_terms)}\n"
                    f"  Matching terms in task: none"
                )

    # --- Check manifest brief if provided ---
    if manifest_brief:
        norm_manifest = _normalize_brief(manifest_brief)
        norm_log = _normalize_brief(log_task)
        # Use prefix comparison — manifest brief may be truncated
        min_len = min(len(norm_manifest), len(norm_log), 100)
        if min_len > 0 and norm_manifest[:min_len] != norm_log[:min_len]:
            errors.append(
                f"BRIEF MISMATCH: manifest brief does not match log task.\n"
                f"  Manifest: {manifest_brief[:120]}\n"
                f"  Log:      {log_task[:120]}"
            )

    # --- Check search mode consistency ---
    # The trace run_started carries the upfront mode. The log may show a different
    # final mode if mid-run escalation occurred. Both are valid — the check ensures
    # the trace's upfront mode appears in the log's early routing output.
    trace_mode = trace_fields.get('search_mode', '')
    if trace_mode:
        # Verify the log recorded this mode as the initial routing result
        log_has_mode = False
        with log_path.open('r', encoding='utf-8') as fh:
            for i, line in enumerate(fh):
                if f'selected_mode={trace_mode}' in line or f"Classified as: {trace_mode}" in line:
                    log_has_mode = True
                    break
                # Also accept tiebreaker override to this mode
                if f'llm_mode={trace_mode}' in line or f'tiebreaker_override' in line and trace_mode in line:
                    log_has_mode = True
                    break
                if i > 50:  # Only check early in the log
                    break
        if not log_has_mode:
            errors.append(
                f"SEARCH MODE MISMATCH: trace says search_mode={trace_mode} "
                f"but log does not confirm this mode in its routing output"
            )

    return errors


def main() -> int:
    """CLI entry point. Returns 0 on success, 1 on validation failure."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate chamber run bundle integrity")
    parser.add_argument("log_path", type=Path, help="Path to the chamber run log file")
    parser.add_argument("trace_path", type=Path, help="Path to the JSONL trace file")
    parser.add_argument("--archive-label", type=str, default=None,
                        help="Archive filename/label to check against brief identity")
    parser.add_argument("--manifest-brief", type=str, default=None,
                        help="Manifest brief text to check against log task")
    parser.add_argument("--derive-manifest", action="store_true",
                        help="Print derived manifest fields as JSON and exit")

    args = parser.parse_args()

    if args.derive_manifest:
        manifest = derive_manifest_from_trace(args.trace_path, args.log_path)
        print(json.dumps(manifest, indent=2))
        return 0

    errors = validate_bundle(
        args.log_path,
        args.trace_path,
        archive_label=args.archive_label,
        manifest_brief=args.manifest_brief,
    )

    if errors:
        print(f"BUNDLE VALIDATION FAILED — {len(errors)} error(s):", file=sys.stderr)
        for i, err in enumerate(errors, 1):
            print(f"  [{i}] {err}", file=sys.stderr)
        return 1

    print("Bundle validation PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
