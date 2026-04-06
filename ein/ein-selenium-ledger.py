#!/usr/bin/env python3
"""ein-ledger.py — Deterministic ledger management for Ein deliberations.

Enforces phase ordering, schema validation, append-only writes,
continuity checks, and structured extraction. Stores data as JSON
(machine-readable) and renders to Markdown (human-readable).

Usage:
    python ein-ledger.py create --question "..." --context "..."
    python ein-ledger.py append --phase phase1 --responses-json results.json
    python ein-ledger.py append --phase phase1_5 --responses-json results.json --assignments assignments.json
    python ein-ledger.py status
    python ein-ledger.py validate
    python ein-ledger.py summary [--phase phase1]
    python ein-ledger.py fulltext --phase phase1
    python ein-ledger.py continuity-check --phase phase3 --log-json actions.json
    python ein-ledger.py render-md
    python ein-ledger.py extract-for-prompt --phase phase2
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHASE_ORDER = ["phase1", "phase1_5", "phase2", "phase3", "phase4", "synthesis"]
DEBATE_WINDOW_PHASES = {"phase3", "phase4"}  # require continuity checks
LLM_LABELS = {"claude": "Opus", "chatgpt": "ChatGPT", "gemini": "Gemini"}
ANON_MAP_PHASE1 = {"claude": "A", "chatgpt": "B", "gemini": "C"}
ANON_MAP_PHASE1_5 = {"claude": "D", "chatgpt": "E", "gemini": "F"}
# In exploration window (phase1, phase1_5) -> R1-A..C, R2-D..F
# In debate window (phase2+) -> anonymized Participant labels

REQUIRED_RESPONSE_FIELDS = {"success", "response", "llm", "elapsed_seconds"}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Ledger data structure
# ---------------------------------------------------------------------------

PHASE4_REQUIRED_HEADERS = [
    "## POSITION",
    "## STRONGEST EVIDENCE",
    "## BIGGEST CONCESSION",
    "## REMAINING UNCERTAINTY",
    "## VERDICT",
]


def _empty_ledger(question: str, context: str,
                  brief: dict | None = None) -> dict:
    ledger = {
        "version": 2,
        "created": _now_iso(),
        "question": question,
        "context": context,
        "phases": {},
        "continuity_checks": {},
        "integrity_hashes": {},
    }
    if brief:
        ledger["brief"] = brief
    return ledger


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_response(resp: dict) -> list[str]:
    """Return list of validation errors for a single LLM response."""
    errors = []
    missing = REQUIRED_RESPONSE_FIELDS - set(resp.keys())
    if missing:
        errors.append(f"Missing fields: {missing}")
    if not resp.get("success"):
        errors.append(f"Response marked as failed for {resp.get('llm', '?')}")
    if not resp.get("response", "").strip():
        errors.append(f"Empty response text for {resp.get('llm', '?')}")
    return errors


def validate_phase_order(ledger: dict, phase: str) -> list[str]:
    """Ensure phases are appended in order, no skips."""
    errors = []
    idx = PHASE_ORDER.index(phase)

    # All prior phases must exist
    for prior in PHASE_ORDER[:idx]:
        if prior not in ledger["phases"]:
            errors.append(f"Cannot append {phase}: prior phase {prior} missing")

    # This phase must not already exist (append-only, no overwrites)
    if phase in ledger["phases"]:
        errors.append(f"Phase {phase} already exists in ledger (append-only)")

    return errors


def validate_responses_set(responses: dict, phase: str) -> list[str]:
    """Validate that we have exactly 3 successful LLM responses.

    Zero-tolerance: all 3 engines must be present and successful.
    """
    errors = []
    expected = {"claude", "chatgpt", "gemini"}
    got = set(responses.keys())

    missing = expected - got
    if missing:
        errors.append(f"Phase {phase}: missing engines: {missing}")

    for llm, resp in responses.items():
        for e in validate_response(resp):
            errors.append(f"Phase {phase}/{llm}: {e}")

    return errors


def validate_phase4_headers(responses: dict) -> list[str]:
    """Check Phase 4 responses for required Markdown section headers.

    Warning-only — returns list of warnings but does NOT block the append.
    Required headers: ## POSITION, ## STRONGEST EVIDENCE,
    ## BIGGEST CONCESSION, ## REMAINING UNCERTAINTY, ## VERDICT
    """
    import re
    warnings = []
    for llm_name, resp in responses.items():
        text = resp.get("response", "")
        for header in PHASE4_REQUIRED_HEADERS:
            # Case-insensitive check for the header (with or without colon)
            pattern = re.escape(header).replace(r"\#\#", "##")
            if not re.search(rf"(?i)^{pattern}\b", text, re.MULTILINE):
                short = header.replace("## ", "")
                warnings.append(
                    f"Phase 4/{llm_name}: missing section '{short}'")
    return warnings


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def create_ledger(question: str, context: str, path: Path,
                  brief: dict | None = None) -> dict:
    """Create a new ledger file. Fails if file already exists.

    brief (optional): structured brief with keys:
        decision_type: "decision" or "analysis"
        success_criteria: what counts as a good outcome
        constraints: known constraints or limitations
        out_of_scope: what is explicitly excluded
    """
    if path.exists():
        print(f"ERROR: Ledger already exists at {path}", file=sys.stderr)
        sys.exit(1)

    ledger = _empty_ledger(question, context, brief)
    _save(ledger, path)
    print(json.dumps({"status": "created", "path": str(path)}))
    return ledger


def append_phase(ledger: dict, phase: str, ein_output: dict,
                 assignments: dict | None = None) -> dict:
    """Append a phase to the ledger with full validation."""
    # Phase order validation
    errors = validate_phase_order(ledger, phase)
    if errors:
        print(f"PHASE ORDER ERRORS: {errors}", file=sys.stderr)
        sys.exit(1)

    # Extract responses from ein-parallel output
    results = ein_output.get("results", {})
    responses = {}
    for llm_name, data in results.items():
        resp_text = data.get("response", "")
        # Provenance metadata: source label, phase, content hash
        if phase == "phase1":
            source_label = f"R1-{ANON_MAP_PHASE1.get(llm_name, '?')}"
        elif phase == "phase1_5":
            source_label = f"R2-{ANON_MAP_PHASE1_5.get(llm_name, '?')}"
        else:
            source_label = f"Participant-{llm_name}"

        responses[llm_name] = {
            "success": data.get("success", False),
            "response": resp_text,
            "llm": llm_name,
            "elapsed_seconds": data.get("elapsed_seconds", 0),
            "model_used": data.get("model_used", "unknown"),
            # Provenance fields (Optimization 5)
            "source_label": source_label,
            "source_phase": phase,
            "response_hash": _hash(resp_text),
        }

    # Response validation
    errors = validate_responses_set(responses, phase)
    if errors:
        # Hard errors stop the run
        hard = [e for e in errors if "fewer than 2" in e or "Missing fields" in e]
        if hard:
            print(f"VALIDATION ERRORS: {hard}", file=sys.stderr)
            sys.exit(1)
        # Soft warnings are logged
        for e in errors:
            print(f"WARNING: {e}", file=sys.stderr)

    # Zero-tolerance: all 3 engines must succeed. No degraded mode.
    engine_count = sum(1 for r in responses.values() if r.get("success"))
    if engine_count < 3:
        failed = [llm for llm, r in responses.items() if not r.get("success")]
        print(f"FATAL: Phase {phase}: engines failed: {', '.join(failed)}. "
              f"Zero-tolerance policy: all 3 engines must succeed. "
              f"Refusing to append.", file=sys.stderr)
        sys.exit(1)
    degraded = False  # impossible under zero-tolerance

    # Phase 4 header validation (warning-only, does not block append)
    header_warnings = []
    if phase == "phase4":
        header_warnings = validate_phase4_headers(responses)
        for w in header_warnings:
            print(f"HEADER WARNING: {w}", file=sys.stderr)

    entry = {
        "phase": phase,
        "timestamp": _now_iso(),
        "engine_count": engine_count,
        "degraded": degraded,
        "action": ein_output.get("action", "unknown"),
        "total_elapsed": ein_output.get("total_elapsed_seconds", 0),
        "responses": responses,
    }

    if assignments and phase == "phase1_5":
        entry["contrarian_assignments"] = assignments

    if header_warnings:
        entry["header_warnings"] = header_warnings

    # Build per-response ledger summaries
    entry["summaries"] = _build_summaries(phase, responses, assignments)

    # Content hash for integrity
    content_hash = _hash(json.dumps(entry, sort_keys=True))
    entry["content_hash"] = content_hash

    ledger["phases"][phase] = entry
    ledger["integrity_hashes"][phase] = content_hash

    return ledger


def continuity_check(ledger: dict, phase: str, ein_output: dict) -> dict:
    """Verify thread continuity for debate-window phases."""
    if phase not in DEBATE_WINDOW_PHASES:
        return {"phase": phase, "required": False}

    results = ein_output.get("results", {})
    check = {
        "phase": phase,
        "timestamp": _now_iso(),
        "required": True,
        "results": {},
        "passed": True,
    }

    for llm_name, data in results.items():
        # In ask_continue mode, new_chat should NOT have been called
        new_chat_called = "new_chat" in data and data["new_chat"].get("success")
        continued = not new_chat_called
        check["results"][llm_name] = {
            "same_chat": continued,
            "status": "OK" if continued else "BROKEN",
        }
        if not continued:
            check["passed"] = False

    if not check["passed"]:
        print("FATAL: CONTINUITY CHECK FAILED. Run is DEAD.", file=sys.stderr)
        print(json.dumps(check, indent=2), file=sys.stderr)
        sys.exit(1)

    ledger["continuity_checks"][phase] = check
    return check


def get_status(ledger: dict) -> dict:
    """Return current deliberation status."""
    completed = [p for p in PHASE_ORDER if p in ledger["phases"]]
    remaining = [p for p in PHASE_ORDER if p not in ledger["phases"]]
    current = remaining[0] if remaining else "complete"

    degraded_phases = [
        p for p, data in ledger["phases"].items()
        if data.get("degraded")
    ]

    return {
        "question": ledger["question"],
        "completed_phases": completed,
        "next_phase": current,
        "remaining": remaining,
        "degraded_phases": degraded_phases,
        "total_phases": len(PHASE_ORDER),
        "progress": f"{len(completed)}/{len(PHASE_ORDER)}",
    }


def build_ledger_summary(ledger: dict) -> str:
    """Build the summary block used in prompts.

    Regenerates summaries from the actual response texts (using
    _extract_first_substantive) rather than relying on stored summaries,
    which may have been generated with an older/weaker extractor.
    """
    lines = []
    phase1 = ledger["phases"].get("phase1")
    phase1_5 = ledger["phases"].get("phase1_5")

    if phase1:
        lines.append("**Opening Positions (Phase 1):**")
        for llm_name in ("claude", "chatgpt", "gemini"):
            resp = phase1["responses"].get(llm_name, {})
            text = resp.get("response", "")
            summary = _extract_first_substantive(text)
            label = f"R1-{ANON_MAP_PHASE1[llm_name]}"
            lines.append(f"- **{label}**: {summary}")
        lines.append("")

    if phase1_5:
        lines.append("**Contrarian Challenges (Phase 1.5):**")
        assignments = phase1_5.get("assignments", {})
        for llm_name in ("claude", "chatgpt", "gemini"):
            resp = phase1_5["responses"].get(llm_name, {})
            text = resp.get("response", "")
            summary = _extract_first_substantive(text)
            label = f"R2-{ANON_MAP_PHASE1_5[llm_name]}"
            target_info = ""
            if llm_name in assignments:
                a = assignments[llm_name]
                target_info = (f" [{a.get('lens', '?')} targeting "
                               f"{a.get('target', '?')}]")
            lines.append(f"- **{label}**{target_info}: {summary}")

    return "\n".join(lines)


def get_full_texts(ledger: dict, phase_name: str,
                   clean: bool = True) -> dict[str, str]:
    """Extract full response texts for a phase, keyed by anonymized label.

    If clean=True (default), strips preamble noise and boilerplate from
    each response before returning.
    """
    phase = ledger["phases"].get(phase_name)
    if not phase:
        return {}

    texts = {}
    for llm_name, resp in phase["responses"].items():
        if phase_name == "phase1":
            label = f"R1-{ANON_MAP_PHASE1[llm_name]}"
        elif phase_name == "phase1_5":
            label = f"R2-{ANON_MAP_PHASE1_5[llm_name]}"
        else:
            label = f"Participant-{llm_name}"
        text = resp["response"]
        if clean:
            text = _clean_response_text(text)
        texts[label] = text
    return texts


def _verify_provenance(phase_data: dict, phase_name: str):
    """Verify response_hash matches stored response text. Fail-closed."""
    for llm_name, resp in phase_data.get("responses", {}).items():
        stored_hash = resp.get("response_hash")
        if not stored_hash:
            continue  # legacy ledgers without provenance
        actual_hash = _hash(resp.get("response", ""))
        if stored_hash != actual_hash:
            print(f"FATAL: Provenance integrity failure — "
                  f"{phase_name}/{llm_name}: stored hash {stored_hash} "
                  f"!= computed hash {actual_hash}. "
                  f"Response text has been tampered with or corrupted.",
                  file=sys.stderr)
            sys.exit(1)


def extract_for_prompt(ledger: dict, target_phase: str) -> dict:
    """Build the context needed for a specific phase's prompt.

    Returns a dict with a 'document' key containing a self-explanatory
    Markdown string ready to be submitted as context to a model, plus
    structured data for programmatic use.

    Verifies provenance hashes before routing any response text (fail-closed).
    """
    question = ledger["question"]
    context = ledger["context"]

    if target_phase == "phase2":
        # Verify provenance before routing (fail-closed)
        _verify_provenance(ledger["phases"].get("phase1", {}), "phase1")
        _verify_provenance(ledger["phases"].get("phase1_5", {}), "phase1_5")

        # Needs: question, context, 6-entry summary, all 6 full texts
        summary = build_ledger_summary(ledger)
        p1_texts = get_full_texts(ledger, "phase1")
        p15_texts = get_full_texts(ledger, "phase1_5")

        # Build self-contained document
        doc_lines = [
            "# Deliberation Context -- For Phase 2 (Cross-Examination)",
            "",
            f"**Question:** {question}",
            "",
            f"**Context:** {context}",
            "",
        ]

        # Include structured brief if present
        brief = ledger.get("brief")
        if brief:
            doc_lines.append("## Brief")
            doc_lines.append("")
            if brief.get("decision_type"):
                doc_lines.append(f"**Type:** {brief['decision_type']}")
            if brief.get("success_criteria"):
                doc_lines.append(f"**Success criteria:** "
                                 f"{brief['success_criteria']}")
            if brief.get("constraints"):
                doc_lines.append(f"**Constraints:** {brief['constraints']}")
            if brief.get("out_of_scope"):
                doc_lines.append(f"**Out of scope:** "
                                 f"{brief['out_of_scope']}")
            doc_lines.append("")

        doc_lines.extend([
            "## What You Are Reading",
            "",
            "Below are 6 responses from an exploration round of a "
            "three-way deliberation. Three AI models each gave an "
            "opening position (labeled R1-A, R1-B, R1-C), then each "
            "was assigned to challenge a different model's opening "
            "from a fresh thread (labeled R2-D, R2-E, R2-F).",
            "",
            "You have not seen these before. Treat them as input "
            "to evaluate, not positions to defend.",
            "",
            "## Summary of All 6 Positions",
            "",
            summary,
            "",
            "## Full Responses -- Opening Statements (Phase 1)",
            "",
        ])
        for label in sorted(p1_texts.keys()):
            doc_lines.append(f"### {label}")
            doc_lines.append("")
            doc_lines.append(p1_texts[label])
            doc_lines.append("")

        doc_lines.append("## Full Responses -- Contrarian Challenges "
                         "(Phase 1.5)")
        doc_lines.append("")
        for label in sorted(p15_texts.keys()):
            doc_lines.append(f"### {label}")
            doc_lines.append("")
            doc_lines.append(p15_texts[label])
            doc_lines.append("")

        return {
            "document": "\n".join(doc_lines),
            "question": question,
            "context": context,
            "ledger_summary": summary,
            "opening_texts": p1_texts,
            "contrarian_texts": p15_texts,
        }

    elif target_phase in ("phase3", "phase4"):
        # Verify provenance before routing (fail-closed)
        prev_phase = "phase2" if target_phase == "phase3" else "phase3"
        _verify_provenance(ledger["phases"].get(prev_phase, {}), prev_phase)

        # Needs: previous phase responses for cross-routing
        # Each model gets the OTHER TWO's responses, so we return
        # all three and the caller selects which two to include
        prev = ledger["phases"].get(prev_phase, {})
        responses = {}
        for llm_name, resp in prev.get("responses", {}).items():
            responses[llm_name] = _clean_response_text(resp["response"])

        phase_label = "3" if target_phase == "phase3" else "4"
        prev_label = "2" if target_phase == "phase3" else "3"

        # Build per-model documents (each model sees the other two)
        per_model_docs = {}
        for target_llm in responses:
            others = {k: v for k, v in responses.items() if k != target_llm}
            other_names = list(others.keys())

            doc_lines = [
                f"# Deliberation Context -- For Phase {phase_label}",
                "",
                f"**Question:** {question}",
                "",
                "## What You Are Reading",
                "",
                f"Below are the other two participants' Phase "
                f"{prev_label} responses. These are the models you "
                f"are deliberating with. They have seen the same "
                f"6 exploration-round perspectives you saw.",
                "",
            ]
            for i, (llm, text) in enumerate(others.items()):
                label = chr(ord('X') + i)  # X, Y
                doc_lines.append(f"### Participant {label}")
                doc_lines.append("")
                doc_lines.append(text)
                doc_lines.append("")

            per_model_docs[target_llm] = "\n".join(doc_lines)

        return {
            "per_model_documents": per_model_docs,
            "question": question,
            "previous_phase": prev_phase,
            "responses": responses,
        }

    elif target_phase == "synthesis":
        # Build complete record for synthesis
        doc_lines = [
            "# Complete Deliberation Record -- For Synthesis",
            "",
            f"**Question:** {question}",
            "",
            f"**Context:** {context}",
            "",
            "## What You Are Reading",
            "",
            "This is the complete record of a three-way deliberation "
            "between Opus (Claude), ChatGPT, and Gemini. It contains "
            "all responses from all phases. The facilitator must now "
            "apply mechanical 2/3 logic to produce a synthesis.",
            "",
        ]

        for pname in PHASE_ORDER:
            phase = ledger["phases"].get(pname)
            if not phase or pname == "synthesis":
                continue
            title, desc = PHASE_DESCRIPTIONS[pname]
            doc_lines.append(f"## {title}")
            doc_lines.append("")
            doc_lines.append(f"*{desc}*")
            doc_lines.append("")
            for llm, resp in phase["responses"].items():
                label = LLM_LABELS.get(llm, llm)
                doc_lines.append(f"### {label}")
                doc_lines.append("")
                doc_lines.append(_clean_response_text(resp["response"]))
                doc_lines.append("")

        return {
            "document": "\n".join(doc_lines),
            "question": question,
            "context": context,
            "all_phases": {
                name: {
                    llm: _clean_response_text(resp["response"])
                    for llm, resp in phase["responses"].items()
                }
                for name, phase in ledger["phases"].items()
            },
        }

    return {}


# ---------------------------------------------------------------------------
# Summary builders
# ---------------------------------------------------------------------------

def _build_summaries(phase: str, responses: dict,
                     assignments: dict | None) -> dict[str, str]:
    """Build one-line summaries for each response in a phase.

    For phase1 and phase1_5, these become the ledger summary entries.
    For later phases, they're stored but the full text is authoritative.
    """
    summaries = {}

    for llm_name, resp in responses.items():
        text = resp.get("response", "")
        # Extract first substantive sentence as summary (heuristic)
        first_line = _extract_first_substantive(text)

        if phase == "phase1":
            label = f"R1-{ANON_MAP_PHASE1[llm_name]}"
            summaries[label] = first_line
        elif phase == "phase1_5":
            label = f"R2-{ANON_MAP_PHASE1_5[llm_name]}"
            target_info = ""
            if assignments and llm_name in assignments:
                a = assignments[llm_name]
                target_info = f" (Contrarian: {a.get('lens', '?')} targeting {a.get('target', '?')})"
            summaries[label] = first_line + target_info
        else:
            summaries[llm_name] = first_line

    return summaries


def generate_assignments(ledger: dict) -> dict:
    """Deterministic round-robin contrarian assignments from Phase 1.

    Uses a content-hash-seeded rotation so assignments are reproducible
    but vary per deliberation. No facilitator judgment involved.
    """
    phase1 = ledger["phases"].get("phase1")
    if not phase1:
        print("ERROR: Phase 1 not found — cannot generate assignments", file=sys.stderr)
        sys.exit(1)

    lenses = ["Opposite conclusion", "Missing stakeholder/risk", "Pre-mortem"]
    models = ["claude", "chatgpt", "gemini"]
    labels = {"claude": "R1-A (Opus opening)", "chatgpt": "R1-B (ChatGPT opening)",
              "gemini": "R1-C (Gemini opening)"}

    # Seed rotation from content hash of phase1 for reproducibility
    seed = int(phase1.get("content_hash", "0")[:8], 16)
    rotation = seed % 3

    assignments = {}
    for i, model in enumerate(models):
        lens_idx = (i + rotation) % 3
        # Target: next model in cycle (never self)
        target_idx = (i + 1) % 3
        target_model = models[target_idx]
        assignments[model] = {
            "lens": lenses[lens_idx],
            "target": labels[target_model],
        }

    return assignments


def build_prompt(ledger: dict, target_phase: str, model: str = None) -> dict:
    """Build the exact prompt text for a phase, ready to pass to ein-parallel.

    Returns dict with 'prompt' (str), 'action' (ask/ask_continue),
    'upload' (file path or None), and optionally 'per_model' (dict of model->prompt).
    """
    question = ledger["question"]
    context = ledger["context"]

    if target_phase == "phase1":
        prompt = (
            f'You are participating in a structured three-way deliberation. '
            f'The question is:\n\n'
            f'"{question}"\n\n'
            f'Context: {context}\n\n'
            f'The attached file (three-way-deliberation.md) is the full Ein '
            f'protocol specification including phase structure, facilitator '
            f'constraints, ledger enforcement, thread architecture, and '
            f'execution commands.\n\n'
            f'Give your opening position in 4-6 paragraphs. Be specific and '
            f'take a clear stance. Identify your own dimensions of comparison '
            f'-- you are not restricted to any pre-defined axes.\n\n'
            f'IMPORTANT: Do you have enough context from the provided documents '
            f'and briefing to give a well-informed response? If not, tell me '
            f'what additional information you need before proceeding.'
        )
        return {"prompt": prompt, "action": "ask",
                "upload": "three-way-deliberation.md"}

    elif target_phase == "phase1_5":
        # Need Phase 1 texts and assignments
        phase1 = ledger["phases"].get("phase1")
        if not phase1:
            print("ERROR: Phase 1 not found", file=sys.stderr)
            sys.exit(1)

        # Get or generate assignments
        assignments = generate_assignments(ledger)

        # Get full texts (cleaned of preamble/boilerplate noise)
        texts = {}
        for llm in ("claude", "chatgpt", "gemini"):
            texts[llm] = _clean_response_text(phase1["responses"][llm]["response"])

        lens_prompts = {
            "Opposite conclusion":
                "What is the strongest case that {TARGET}'s core position is wrong?",
            "Missing stakeholder/risk":
                "What critical stakeholder, risk, or second-order effect did "
                "{TARGET}'s position ignore?",
            "Pre-mortem":
                "Assume we followed {TARGET}'s direction and it failed "
                "catastrophically in 12 months. What went wrong?",
        }

        per_model = {}
        for llm in ("claude", "chatgpt", "gemini"):
            a = assignments[llm]
            lens = a["lens"]
            target_label = a["target"]
            # Extract the letter (A/B/C) from target label
            target_letter = target_label.split("(")[0].strip().split("-")[1]

            lens_instruction = lens_prompts[lens].replace(
                "{TARGET}", f"Perspective {target_letter}")

            prompt = (
                f'You are on a fresh thread. You have NOT seen this material before.\n\n'
                f'Here are three opening positions on "{question}":\n\n'
                f'PERSPECTIVE A:\n{texts["claude"]}\n\n'
                f'PERSPECTIVE B:\n{texts["chatgpt"]}\n\n'
                f'PERSPECTIVE C:\n{texts["gemini"]}\n\n'
                f'YOUR CONTRARIAN TASK -- {lens}, targeted at PERSPECTIVE {target_letter}:\n\n'
                f'{lens_instruction}\n\n'
                f'Focus your critique SPECIFICALLY on Perspective {target_letter}\'s argument. '
                f'You may reference the other perspectives for contrast, but your '
                f'primary target is Perspective {target_letter}.\n\n'
                f'Do NOT just disagree for the sake of it. Instead: what is the strongest, '
                f'most inconvenient truth that undermines this position? What would a smart '
                f'skeptic say that would make this participant uncomfortable?\n\n'
                f'Be specific. Take a clear stance. 4-6 paragraphs.\n\n'
                f'IMPORTANT: Do you have enough context from the provided documents '
                f'and briefing to give a well-informed response? If not, tell me '
                f'what additional information you need before proceeding.'
            )
            per_model[llm] = prompt

        return {"per_model": per_model, "action": "ask",
                "upload": "three-way-deliberation.md",
                "assignments": assignments}

    elif target_phase == "phase2":
        # Extract context document from ledger (already contains question + context)
        ctx = extract_for_prompt(ledger, "phase2")
        document = ctx.get("document", "")

        prompt = (
            f'{document}\n\n'
            f'--- YOUR TASK ---\n\n'
            f'1. Which of these 6 perspectives has the STRONGEST argument and why?\n'
            f'2. Which has the WEAKEST and why?\n'
            f'3. Where do perspectives contradict each other in ways that cannot '
            f'both be true? Identify the real fault lines.\n'
            f'4. What is YOUR position on this question, informed by all 6 views? '
            f'Take a clear stance. Do not hedge.\n'
            f'5. What is the single most important thing that ALL 6 perspectives '
            f'either missed or underweighted?\n'
            f'6. HALLUCINATION CHECK: Identify any factual premise or core assumption '
            f'that multiple perspectives agreed upon, but for which NO ONE provided '
            f'concrete evidence. Challenge the weakest shared assumption.\n\n'
            f'IMPORTANT: Do you have enough context from the provided documents '
            f'and briefing to give a well-informed response? If not, tell me '
            f'what additional information you need before proceeding.'
        )
        return {"prompt": prompt, "action": "ask",
                "upload": "three-way-deliberation.md"}

    elif target_phase in ("phase3", "phase4"):
        prev_phase = "phase2" if target_phase == "phase3" else "phase3"
        prev = ledger["phases"].get(prev_phase)
        if not prev:
            print(f"ERROR: {prev_phase} not found", file=sys.stderr)
            sys.exit(1)

        responses = {llm: _clean_response_text(resp["response"])
                     for llm, resp in prev["responses"].items()}

        if target_phase == "phase3":
            task_block = (
                "Respond directly:\n\n"
                "1. Where do you AGREE with their analysis? Be specific -- which of "
                "their judgments do you share?\n"
                "2. Where do you DISAGREE? What did they get wrong?\n"
                "3. They identified fault lines and gaps. Are those the RIGHT fault "
                "lines? Or did they miss the real ones?\n"
                "4. Has your position shifted after seeing their analysis? If yes, "
                "what moved you? If no, why not?"
            )
        else:  # phase4
            task_block = (
                "Do NOT repeat arguments already made. State your FINAL position:\n\n"
                "1. POSITION: Your stance in 2-3 sentences.\n"
                "2. STRONGEST EVIDENCE: The single most compelling argument from the "
                "entire debate (any phase, any participant) that supports your position.\n"
                "3. BIGGEST CONCESSION: The strongest point AGAINST your position "
                "that you cannot fully rebut.\n"
                "4. REMAINING UNCERTAINTY: What would you need to know to be more "
                "confident?\n"
                "5. VERDICT: For decision questions -- a direct, actionable answer. "
                "For analysis questions -- your recommended framework, prioritized "
                "considerations, or key takeaways."
            )

        header = ("Here are the other two participants' analyses:\n\n"
                  if target_phase == "phase3" else
                  "Final round. Here are the other two participants' latest responses:\n\n")

        per_model = {}
        for target_llm in responses:
            others = {k: v for k, v in responses.items() if k != target_llm}
            other_items = list(others.items())

            prompt = (
                f'{header}'
                f'PARTICIPANT X:\n{other_items[0][1]}\n\n'
                f'PARTICIPANT Y:\n{other_items[1][1]}\n\n'
                f'{task_block}\n\n'
                f'IMPORTANT: Do you have enough context from the provided documents '
                f'and briefing to give a well-informed response? If not, tell me '
                f'what additional information you need before proceeding.'
            )
            per_model[target_llm] = prompt

        return {"per_model": per_model, "action": "ask_continue", "upload": None}

    return {}


def _extract_first_substantive(text: str) -> str:
    """Extract the first substantive sentence from a response.

    Skips timestamps, 'Yes I have enough context' preambles, filename echoes,
    and other non-substantive lines.
    """
    import re
    skip_prefixes = (
        "yes", "i have", "2026", "saturday", "sunday", "monday",
        "tuesday", "wednesday", "thursday", "friday",
        "here is", "here are",
        "not completely", "the provided", "sufficient", "important:",
        "no additional information",
        "context check:",
    )
    # Patterns that are never substantive content
    skip_patterns = [
        r"^\[?\d{4}-\d{2}-\d{2}",           # timestamps [2026-04-04...] or bare
        r"^\[?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",  # [Saturday, April 4...]
        r"^three-way-deliberation",           # filename echo
        r"^ein[\s-]",                         # protocol name echo
        r"^\*?\*?note:?\*?\*?",               # "Note:" preambles
    ]
    lines = text.strip().split("\n")
    for line in lines:
        cleaned = line.strip().rstrip(".")
        if not cleaned:
            continue
        lower = cleaned.lower()
        if any(lower.startswith(p) for p in skip_prefixes):
            continue
        if any(re.match(pat, lower) for pat in skip_patterns):
            continue
        if len(cleaned) < 30:
            continue
        # Truncate to ~200 chars
        if len(cleaned) > 200:
            cleaned = cleaned[:197] + "..."
        return cleaned
    return "(no summary extracted)"


def _clean_response_text(text: str) -> str:
    """Strip preamble noise from a full response text for prompt inclusion.

    Removes leading timestamps, 'I have enough context' declarations,
    filename echoes, and trailing 'IMPORTANT: do you have enough context'
    boilerplate. Preserves all substantive content.
    """
    import re

    lines = text.strip().split("\n")

    # Strip leading noise lines
    skip_prefixes = (
        "yes", "i have", "2026", "saturday", "sunday", "monday",
        "tuesday", "wednesday", "thursday", "friday",
        "here is", "here are",
        "not completely", "the provided", "sufficient",
        "no additional information",
        "context check:",
    )
    skip_patterns = [
        r"^\[?\d{4}-\d{2}-\d{2}",
        r"^\[?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        r"^three-way-deliberation$",
    ]

    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if any(lower.startswith(p) for p in skip_prefixes):
            start = i + 1
            continue
        if any(re.match(pat, lower) for pat in skip_patterns):
            start = i + 1
            continue
        break

    # Strip trailing boilerplate
    end = len(lines)
    for i in range(len(lines) - 1, max(start - 1, -1), -1):
        stripped = lines[i].strip().lower()
        if not stripped:
            end = i
            continue
        if "do you have enough context" in stripped or \
           "important: i have" in stripped or \
           stripped.startswith("important: do you") or \
           stripped.startswith("important: no additional") or \
           "no additional information" in stripped or \
           stripped.startswith("context check:") or \
           stripped == "three-way-deliberation":
            end = i
            continue
        break

    result = "\n".join(lines[start:end]).strip()
    # Remove any remaining standalone "three-way-deliberation" lines mid-text
    result = re.sub(r"\n\s*three-way-deliberation\s*\n", "\n\n", result,
                    flags=re.IGNORECASE)
    return result


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

PHASE_DESCRIPTIONS = {
    "phase1": (
        "Phase 1 -- Opening Statements",
        "All three participants received the question and context files "
        "simultaneously on fresh chat threads. Each gave an independent "
        "opening position without seeing the others."
    ),
    "phase1_5": (
        "Phase 1.5 -- Contrarian Round",
        "Each participant was given all three openings on a FRESH thread "
        "(to prevent self-anchoring) and assigned a specific contrarian "
        "lens targeting a specific other participant's opening. The goal "
        "is to stress-test the emerging consensus from different angles."
    ),
    "phase2": (
        "Phase 2 -- Cross-Examination Round 1",
        "All three participants received all 6 prior responses (3 openings "
        "+ 3 contrarian challenges) on FRESH threads. Each was asked to "
        "identify the strongest and weakest arguments, real fault lines, "
        "take their own position, flag what everyone missed, and perform "
        "a hallucination check on shared assumptions."
    ),
    "phase3": (
        "Phase 3 -- Cross-Examination Round 2",
        "Each participant received the other two's Phase 2 analyses on "
        "the SAME thread as Phase 2 (preserving debate continuity). Each "
        "responded with agreements, disagreements, and whether their "
        "position shifted."
    ),
    "phase4": (
        "Phase 4 -- Final Positions",
        "Each participant received the other two's Phase 3 responses on "
        "the SAME thread. Each stated a final position, strongest evidence, "
        "biggest concession, remaining uncertainty, and verdict."
    ),
    "synthesis": (
        "Phase 5 -- Synthesis",
        "The facilitator (not a participant) applied mechanical 2/3 logic "
        "to the three final positions. CONSENSUS = 3/3 agree. MAJORITY = "
        "2/3 agree (dissent noted). DISPUTE = all differ (user decides)."
    ),
}


def render_markdown(ledger: dict) -> str:
    """Render the full ledger as a self-contained Markdown document.

    Designed to be read cold by someone (or a model) who has never seen
    the deliberation before. Every section is self-explanatory.
    """
    completed = [p for p in PHASE_ORDER if p in ledger["phases"]]
    degraded = [p for p in completed if ledger["phases"][p].get("degraded")]

    lines = [
        "# Ein Deliberation Ledger",
        "",
        "## How to Read This Document",
        "",
        "This is the complete record of a structured three-way deliberation "
        "between three AI models: **Opus** (Claude), **ChatGPT**, and "
        "**Gemini**. A fourth AI (Claude Code) acted as **facilitator** -- "
        "it orchestrated the process but contributed zero opinions of its own.",
        "",
        "The deliberation followed a fixed protocol with up to 6 phases. "
        "Each phase builds on the previous ones. The document is organized "
        "chronologically -- read top to bottom.",
        "",
        "### Participant Labels",
        "",
        "To prevent brand-bias (models deferring to or attacking based on "
        "identity), responses are labeled with anonymous codes:",
        "",
        "| Label | Meaning |",
        "|-------|---------|",
        "| **R1-A, R1-B, R1-C** | The three Phase 1 opening positions |",
        "| **R2-D, R2-E, R2-F** | The three Phase 1.5 contrarian challenges |",
        "| **Participant X, Y** | Anonymous labels used when routing "
        "responses in later phases |",
        "",
        "### Phase Structure",
        "",
        "| Phase | What Happens | Thread |",
        "|-------|-------------|--------|",
        "| 1. Opening Statements | Each model gives independent position | "
        "Fresh |",
        "| 1.5 Contrarian Round | Each attacks a different model's opening | "
        "Fresh |",
        "| 2. Cross-Exam R1 | Each evaluates all 6 prior responses | "
        "Fresh |",
        "| 3. Cross-Exam R2 | Each responds to the other two's Phase 2 | "
        "Same as Phase 2 |",
        "| 4. Final Positions | Each states closing position | "
        "Same as Phase 2 |",
        "| 5. Synthesis | Facilitator applies 2/3 vote (no opinions) | "
        "N/A |",
        "",
        "### Decision Logic",
        "",
        "- **CONSENSUS** (3/3): All three models agree.",
        "- **MAJORITY** (2/3): Two agree, one dissents. "
        "Majority conclusion adopted, dissent recorded.",
        "- **DISPUTE** (all differ): No majority. "
        "All three positions presented; user decides.",
        "",
        "---",
        "",
        "## Deliberation Details",
        "",
        f"**Question:** {ledger['question']}",
        "",
        f"**Context:** {ledger['context']}",
        "",
        f"**Date:** {ledger['created']}",
        "",
        f"**Phases completed:** {len(completed)}/{len(PHASE_ORDER)}"
        + (f" | Degraded phases: {', '.join(degraded)}" if degraded else ""),
        "",
        "---",
    ]

    for phase_name in PHASE_ORDER:
        phase = ledger["phases"].get(phase_name)
        if not phase:
            continue

        title, description = PHASE_DESCRIPTIONS[phase_name]

        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"*{description}*")
        lines.append("")

        # Metadata line
        meta_parts = [
            f"Engines: {phase['engine_count']}/3"
            + (" **(DEGRADED)**" if phase.get("degraded") else ""),
            f"Elapsed: {phase['total_elapsed']:.1f}s",
        ]
        lines.append(" | ".join(meta_parts))

        # Contrarian assignments (Phase 1.5 only)
        if phase.get("contrarian_assignments"):
            lines.append("")
            lines.append("**Contrarian Assignments** (who attacks whom, "
                         "and through which lens):")
            lines.append("")
            for llm, a in phase["contrarian_assignments"].items():
                label = LLM_LABELS.get(llm, llm)
                lines.append(f"- **{label}** was assigned the "
                             f"**{a.get('lens', '?')}** lens, "
                             f"targeting **{a.get('target', '?')}**")

        # Continuity check (Phases 3, 4 only)
        cc = ledger["continuity_checks"].get(phase_name)
        if cc:
            lines.append("")
            status = "PASSED" if cc["passed"] else "**FAILED -- RUN IS DEAD**"
            lines.append(f"**Thread Continuity Check:** {status}")
            for llm, result in cc["results"].items():
                mark = "same chat" if result["same_chat"] else "**BROKEN**"
                lines.append(f"- {LLM_LABELS.get(llm, llm)}: {mark}")

        # Full responses -- the authoritative content
        lines.append("")
        for llm_name, resp in phase["responses"].items():
            label = LLM_LABELS.get(llm_name, llm_name)
            model = resp.get("model_used", "unknown")
            elapsed = resp.get("elapsed_seconds", 0)

            # Build the response header with context
            if phase_name == "phase1":
                anon = f"R1-{ANON_MAP_PHASE1.get(llm_name, '?')}"
                header = f"### {anon} -- {label} ({model}, {elapsed:.1f}s)"
            elif phase_name == "phase1_5":
                anon = f"R2-{ANON_MAP_PHASE1_5.get(llm_name, '?')}"
                assignment_note = ""
                if phase.get("contrarian_assignments", {}).get(llm_name):
                    a = phase["contrarian_assignments"][llm_name]
                    assignment_note = (f" -- {a.get('lens', '?')} lens "
                                       f"targeting {a.get('target', '?')}")
                header = (f"### {anon} -- {label} "
                          f"({model}, {elapsed:.1f}s){assignment_note}")
            else:
                header = f"### {label} ({model}, {elapsed:.1f}s)"

            lines.append(header)
            lines.append("")
            lines.append(resp["response"])
            lines.append("")

        lines.append("---")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validate full ledger
# ---------------------------------------------------------------------------

def validate_ledger(ledger: dict) -> list[str]:
    """Run all validation checks on a ledger. Returns list of issues."""
    issues = []

    if not ledger.get("question"):
        issues.append("Missing question")

    # Check integrity hashes
    for phase_name, phase in ledger.get("phases", {}).items():
        stored_hash = phase.get("content_hash", "")
        # Recompute hash (exclude the hash field itself)
        check = dict(phase)
        check.pop("content_hash", None)
        computed = _hash(json.dumps(check, sort_keys=True))
        # Note: hash won't match after append because we include it in the entry
        # Instead, check against the integrity_hashes registry
        registry_hash = ledger.get("integrity_hashes", {}).get(phase_name)
        if registry_hash and registry_hash != stored_hash:
            issues.append(f"Hash mismatch for {phase_name}: "
                          f"registry={registry_hash}, stored={stored_hash}")

    # Check phase ordering (no gaps)
    completed = [p for p in PHASE_ORDER if p in ledger.get("phases", {})]
    for i, phase in enumerate(completed):
        expected_idx = PHASE_ORDER.index(phase)
        if i > 0:
            prev_expected = PHASE_ORDER.index(completed[i - 1])
            if expected_idx != prev_expected + 1:
                issues.append(f"Phase gap: {completed[i-1]} -> {phase}")

    # Check continuity for debate-window phases
    for phase in DEBATE_WINDOW_PHASES:
        if phase in ledger.get("phases", {}):
            cc = ledger.get("continuity_checks", {}).get(phase)
            if not cc:
                issues.append(f"Missing continuity check for {phase}")
            elif not cc.get("passed"):
                issues.append(f"FAILED continuity check for {phase}")

    # Check for degraded phases
    for phase_name, phase in ledger.get("phases", {}).items():
        if phase.get("degraded"):
            issues.append(f"DEGRADED: {phase_name} ran with {phase['engine_count']} engines")

    return issues


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def _ledger_path(explicit: str | None = None) -> Path:
    """Find the current ledger file."""
    if explicit:
        return Path(explicit)
    # Look for most recent ledger in current directory
    candidates = sorted(Path(".").glob("deliberation-ledger-*.json"), reverse=True)
    if candidates:
        return candidates[0]
    return Path(f"deliberation-ledger-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(ledger: dict, path: Path):
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False),
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ein ledger management")
    parser.add_argument("--ledger", type=str, help="Explicit ledger path")
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create")
    p_create.add_argument("--question", required=True)
    p_create.add_argument("--context", required=True)
    p_create.add_argument("--decision-type", choices=["decision", "analysis"],
                          help="Is this a decision or analysis question?")
    p_create.add_argument("--success-criteria",
                          help="What counts as a good outcome")
    p_create.add_argument("--constraints",
                          help="Known constraints or limitations")
    p_create.add_argument("--out-of-scope",
                          help="What is explicitly excluded")

    # append
    p_append = sub.add_parser("append")
    p_append.add_argument("--phase", required=True, choices=PHASE_ORDER)
    p_append.add_argument("--responses-json", required=True,
                          help="Path to ein-parallel JSON output")
    p_append.add_argument("--assignments-json",
                          help="Path to contrarian assignments JSON (phase1_5 only)")

    # status
    sub.add_parser("status")

    # validate
    sub.add_parser("validate")

    # summary
    sub.add_parser("summary")

    # fulltext
    p_ft = sub.add_parser("fulltext")
    p_ft.add_argument("--phase", required=True)

    # continuity-check
    p_cc = sub.add_parser("continuity-check")
    p_cc.add_argument("--phase", required=True)
    p_cc.add_argument("--responses-json", required=True)

    # render-md
    sub.add_parser("render-md")

    # extract-for-prompt
    p_efp = sub.add_parser("extract-for-prompt")
    p_efp.add_argument("--phase", required=True)

    # generate-assignments (deterministic contrarian routing)
    sub.add_parser("generate-assignments")

    # build-prompt (generate exact prompt for a phase)
    p_bp = sub.add_parser("build-prompt")
    p_bp.add_argument("--phase", required=True)
    p_bp.add_argument("--model", help="Model name (for per-model phases)")
    p_bp.add_argument("--save-dir", default=".",
                      help="Directory to save prompt files")

    # run-phase (one-shot: build prompt, call ein-parallel, validate, append)
    p_rp = sub.add_parser("run-phase")
    p_rp.add_argument("--phase", required=True)
    p_rp.add_argument("--timeout", type=int, default=600)

    args = parser.parse_args()
    ledger_path = _ledger_path(args.ledger)

    if args.command == "create":
        brief = None
        dt = getattr(args, "decision_type", None)
        sc = getattr(args, "success_criteria", None)
        co = getattr(args, "constraints", None)
        os_ = getattr(args, "out_of_scope", None)
        if any([dt, sc, co, os_]):
            brief = {}
            if dt:  brief["decision_type"] = dt
            if sc:  brief["success_criteria"] = sc
            if co:  brief["constraints"] = co
            if os_: brief["out_of_scope"] = os_
        create_ledger(args.question, args.context, ledger_path, brief)
        return

    # All other commands need an existing ledger
    if not ledger_path.exists():
        print(f"ERROR: No ledger found at {ledger_path}", file=sys.stderr)
        sys.exit(1)

    ledger = _load(ledger_path)

    if args.command == "append":
        responses = json.loads(Path(args.responses_json).read_text(encoding="utf-8"))
        assignments = None
        if args.assignments_json:
            assignments = json.loads(
                Path(args.assignments_json).read_text(encoding="utf-8"))
        ledger = append_phase(ledger, args.phase, responses, assignments)
        _save(ledger, ledger_path)
        status = get_status(ledger)
        print(json.dumps({"status": "appended", "phase": args.phase,
                           "progress": status["progress"]}))

    elif args.command == "status":
        print(json.dumps(get_status(ledger), indent=2))

    elif args.command == "validate":
        issues = validate_ledger(ledger)
        result = {"valid": len(issues) == 0, "issues": issues}
        print(json.dumps(result, indent=2))
        if issues:
            sys.exit(1)

    elif args.command == "summary":
        print(build_ledger_summary(ledger))

    elif args.command == "fulltext":
        texts = get_full_texts(ledger, args.phase)
        print(json.dumps(texts, indent=2, ensure_ascii=False))

    elif args.command == "continuity_check" or args.command == "continuity-check":
        responses = json.loads(Path(args.responses_json).read_text(encoding="utf-8"))
        check = continuity_check(ledger, args.phase, responses)
        _save(ledger, ledger_path)
        print(json.dumps(check, indent=2))

    elif args.command == "render-md":
        md = render_markdown(ledger)
        # Write alongside JSON
        md_path = ledger_path.with_suffix(".md")
        md_path.write_text(md, encoding="utf-8")
        print(json.dumps({"rendered": str(md_path)}))

    elif args.command == "extract-for-prompt":
        data = extract_for_prompt(ledger, args.phase)
        print(json.dumps(data, indent=2, ensure_ascii=False))

    elif args.command == "generate-assignments":
        assignments = generate_assignments(ledger)
        print(json.dumps(assignments, indent=2))

    elif args.command == "build-prompt":
        data = build_prompt(ledger, args.phase, args.model)
        # If per_model, save each prompt to a file for piping
        if "per_model" in data:
            save_dir = Path(args.save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            for llm, prompt_text in data["per_model"].items():
                p = save_dir / f"prompt-{args.phase}-{llm}.txt"
                p.write_text(prompt_text, encoding="utf-8")
            info = {
                "action": data["action"],
                "upload": data.get("upload"),
                "models": list(data["per_model"].keys()),
                "files": {llm: str(save_dir / f"prompt-{args.phase}-{llm}.txt")
                          for llm in data["per_model"]},
            }
            if data.get("assignments"):
                assignments_path = save_dir / f"assignments-{args.phase}.json"
                assignments_path.write_text(
                    json.dumps(data["assignments"], indent=2), encoding="utf-8")
                info["assignments_file"] = str(assignments_path)
            print(json.dumps(info, indent=2))
        else:
            # Single prompt for all models
            save_dir = Path(args.save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            p = save_dir / f"prompt-{args.phase}.txt"
            p.write_text(data["prompt"], encoding="utf-8")
            print(json.dumps({
                "action": data["action"],
                "upload": data.get("upload"),
                "prompt_file": str(p),
            }, indent=2))

    elif args.command == "run-phase":
        import subprocess

        phase = args.phase
        timeout = args.timeout
        expected_engines = {"claude", "chatgpt", "gemini"}

        # --- PREFLIGHT: verify ledger is ready for this phase ---
        order_errors = validate_phase_order(ledger, phase)
        if order_errors:
            print(f"PREFLIGHT FAIL: {order_errors}", file=sys.stderr)
            sys.exit(1)

        # --- PREFLIGHT: verify upload file exists if needed ---
        data = build_prompt(ledger, phase)
        if data.get("upload"):
            upload_path = Path(data["upload"])
            if not upload_path.exists():
                print(f"PREFLIGHT FAIL: upload file not found: {data['upload']}",
                      file=sys.stderr)
                sys.exit(1)

        # --- PREFLIGHT: verify all 3 bridges are up and logged in ---
        print("PREFLIGHT: checking all 3 engines...", file=sys.stderr)
        status_cmd = ["python", "ein-parallel.py", "--action", "status"]
        status_proc = subprocess.run(status_cmd, capture_output=True, timeout=60)
        if status_proc.returncode != 0:
            print("PREFLIGHT FAIL: cannot reach engines", file=sys.stderr)
            sys.exit(1)
        status_result = json.loads(status_proc.stdout.decode())
        for engine in expected_engines:
            r = status_result.get("results", {}).get(engine, {})
            if not r.get("success"):
                print(f"PREFLIGHT FAIL: {engine} bridge unreachable: {r.get('error', '?')}",
                      file=sys.stderr)
                sys.exit(1)
            if not r.get("logged_in"):
                print(f"PREFLIGHT FAIL: {engine} not logged in", file=sys.stderr)
                sys.exit(1)
        print("PREFLIGHT: all 3 engines OK", file=sys.stderr)

        # --- DISPATCH ---
        def _run_parallel(action, prompt, upload, targets, timeout_s):
            """Run ein-parallel and return parsed result. Dies on any failure."""
            cmd = ["python", "ein-parallel.py",
                   "--action", action,
                   "--prompt", prompt,
                   "--timeout", str(timeout_s)]
            if upload:
                cmd += ["--upload", upload]
            if targets:
                cmd += ["--only", ",".join(targets)]
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout_s + 60)
            if proc.returncode != 0:
                stderr_tail = proc.stderr.decode()[-500:]
                print(f"FATAL: ein-parallel exited {proc.returncode}\n{stderr_tail}",
                      file=sys.stderr)
                sys.exit(1)
            result = json.loads(proc.stdout.decode())
            # In-flight zero-tolerance
            for llm, r in result.get("results", {}).items():
                if not r.get("success"):
                    print(f"FATAL: {llm} failed: {r.get('error', '?')}",
                          file=sys.stderr)
                    sys.exit(1)
            return result

        if "per_model" in data:
            # Per-model prompts (phase1_5, phase3, phase4) — run each engine
            all_results = {"action": data["action"], "results": {},
                           "total_elapsed_seconds": 0}
            for llm, prompt_text in data["per_model"].items():
                result = _run_parallel(
                    data["action"], prompt_text, data.get("upload"),
                    [llm], timeout)
                if llm in result.get("results", {}):
                    all_results["results"][llm] = result["results"][llm]
                all_results["total_elapsed_seconds"] += result.get(
                    "total_elapsed_seconds", 0)

            # POST-FLIGHT: verify we got all 3 engines
            got = set(all_results["results"].keys())
            missing = expected_engines - got
            if missing:
                print(f"FATAL: missing engine results: {missing}", file=sys.stderr)
                sys.exit(1)

            # Save combined results
            results_path = Path(f"{phase}-results.json")
            results_path.write_text(
                json.dumps(all_results, indent=2, ensure_ascii=False),
                encoding="utf-8")

            # Append with assignments if phase1_5
            assignments = data.get("assignments")
            ledger = append_phase(ledger, phase, all_results, assignments)
            _save(ledger, ledger_path)

            # Continuity check for debate-window phases
            if phase in DEBATE_WINDOW_PHASES:
                continuity_check(ledger, phase, all_results)
                _save(ledger, ledger_path)

        else:
            # Single prompt for all models (phase1, phase2)
            result = _run_parallel(
                data["action"], data["prompt"], data.get("upload"),
                None, timeout)

            # POST-FLIGHT: verify we got all 3 engines
            got = set(result.get("results", {}).keys())
            missing = expected_engines - got
            if missing:
                print(f"FATAL: missing engine results: {missing}", file=sys.stderr)
                sys.exit(1)

            # Save results
            results_path = Path(f"{phase}-results.json")
            results_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8")

            # Append
            ledger = append_phase(ledger, phase, result)
            _save(ledger, ledger_path)

        # POST-FLIGHT: validate the ledger after append
        issues = validate_ledger(ledger)
        if issues:
            print(f"POST-FLIGHT WARNING: ledger issues: {issues}",
                  file=sys.stderr)

        status = get_status(ledger)
        print(json.dumps({"status": "completed", "phase": phase,
                           "progress": status["progress"],
                           "results_file": str(results_path)}, indent=2))


if __name__ == "__main__":
    main()
