#!/usr/bin/env python3
"""Ein Design Ledger — state tracking for the design synthesis pipeline.

Design pipeline phases (in order):
  draft    — each engine independently produces a full design document
  cross_1  — 1st cross-pollination: each engine revises after seeing the other two drafts
  cross_2  — 2nd cross-pollination: same, using revised documents
  cross_3  — 3rd cross-pollination (optional, if convergence insufficient after cross_2)
  final    — ChatGPT produces the final master document using 2/3 majority on remaining disputes
"""

import json, sys, hashlib, argparse
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION  = "design-2.0"
DESIGN_PHASES   = ["draft", "cross_1", "cross_2", "cross_3", "final"]
ENGINES         = ["chatgpt", "gemini", "claude"]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _save(ledger: dict, path: Path) -> None:
    path = Path(path)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "saved", "path": str(path)}))


def _empty_ledger(question: str, context: str, brief: dict | None = None) -> dict:
    return {
        "schema_version":   SCHEMA_VERSION,
        "question":         question,
        "context":          context,
        "brief":            brief or {},
        "created_at":       _now(),
        "phases":           {},
        "conversation_registry": {},
    }


def _verify_provenance(phase_data: dict, phase_name: str) -> None:
    for engine, r in phase_data.get("responses", {}).items():
        stored_hash = r.get("response_hash")
        text        = r.get("response", "")
        if stored_hash and _hash(text) != stored_hash:
            print(
                f"FATAL: provenance mismatch in {phase_name}/{engine} "
                f"(expected {stored_hash}, got {_hash(text)})",
                file=sys.stderr,
            )
            sys.exit(1)


# ── Public API ────────────────────────────────────────────────────────────────

def create_ledger(question: str, context: str, path: str | Path,
                  brief: dict | None = None) -> dict:
    ledger = _empty_ledger(question, context, brief)
    _save(ledger, path)
    return ledger


def append_phase(ledger: dict, phase_name: str, phase_data: dict,
                 assignments: dict | None = None) -> None:
    if phase_name not in DESIGN_PHASES:
        print(f"FATAL: unknown phase '{phase_name}'. Must be one of {DESIGN_PHASES}",
              file=sys.stderr)
        sys.exit(1)

    if phase_name in ledger.get("phases", {}):
        print(f"FATAL: phase '{phase_name}' already exists in ledger. "
              "Zero-tolerance: never overwrite.", file=sys.stderr)
        sys.exit(1)

    results = phase_data.get("results", {})
    failed  = [e for e, r in results.items() if not r.get("success")]

    if failed:
        print(f"FATAL: {phase_name} failed for engines: {failed}. "
              "Zero-tolerance policy.", file=sys.stderr)
        sys.exit(1)

    responses = {}
    for engine, r in results.items():
        text = r.get("response", "")
        responses[engine] = {
            "response":        text,
            "response_hash":   _hash(text),
            "model_used":      r.get("model_used", ""),
            "elapsed_seconds": r.get("elapsed_seconds", 0),
            "source":          r.get("source", "inline"),
            "success":         r.get("success", True),
            "error":           r.get("error"),
        }

    ledger.setdefault("phases", {})[phase_name] = {
        "phase":             phase_name,
        "timestamp":         _now(),
        "engine_count":      len(responses),
        "action":            phase_data.get("action", phase_name),
        "total_elapsed":     phase_data.get("total_elapsed_seconds", 0),
        "responses":         responses,
        "assignments":       assignments or {},
    }


def set_conversation_registry(ledger: dict, registry: dict) -> None:
    ledger["conversation_registry"] = registry


def get_other_two(ledger: dict, source_phase: str, engine_name: str) -> list:
    """Return the other two engines' responses from a given phase.

    Returns: [(engine_name_a, response_text_a), (engine_name_b, response_text_b)]
    """
    phase_data = ledger.get("phases", {}).get(source_phase, {})
    _verify_provenance(phase_data, source_phase)
    responses = phase_data.get("responses", {})

    others = []
    for eng in ENGINES:
        if eng != engine_name and eng in responses:
            others.append((eng, responses[eng].get("response", "")))
    return others


def get_latest_cross_phase(ledger: dict) -> str | None:
    """Return the name of the most recent completed cross phase."""
    phases = ledger.get("phases", {})
    for p in reversed(["cross_1", "cross_2", "cross_3"]):
        if p in phases:
            return p
    return None


def source_phase_for(target_phase: str, ledger: dict) -> str:
    """Determine which phase to read OTHER engines' responses from.

    cross_1 reads from: draft
    cross_2 reads from: cross_1
    cross_3 reads from: cross_2
    final   reads from: latest cross phase
    """
    mapping = {
        "cross_1": "draft",
        "cross_2": "cross_1",
        "cross_3": "cross_2",
    }
    if target_phase == "final":
        return get_latest_cross_phase(ledger) or "draft"
    return mapping.get(target_phase, "draft")


def status(ledger: dict) -> dict:
    completed = list(ledger.get("phases", {}).keys())
    remaining = [p for p in DESIGN_PHASES if p not in completed]
    return {
        "question":            ledger.get("question", ""),
        "schema_version":      ledger.get("schema_version", ""),
        "completed_phases":    completed,
        "next_phase":          remaining[0] if remaining else "done",
        "remaining":           remaining,
        "conversation_registry": ledger.get("conversation_registry", {}),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ein Design Ledger CLI")
    parser.add_argument("--ledger", type=str, help="Path to ledger JSON file")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create")
    p_create.add_argument("question", type=str)
    p_create.add_argument("context",  type=str)
    p_create.add_argument("path",     type=str)

    sub.add_parser("status")
    sub.add_parser("registry")

    args = parser.parse_args()

    if args.command == "create":
        brief = {}
        ledger = create_ledger(args.question, args.context, Path(args.path), brief or None)
        print(json.dumps({"status": "created", "path": args.path}))
    elif args.command == "status":
        ledger = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
        print(json.dumps(status(ledger), indent=2))
    elif args.command == "registry":
        ledger = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
        print(json.dumps(ledger.get("conversation_registry", {}), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
