# Self-Review: Thinker V8 Brain — Gap Analysis

## Task

Perform a gap analysis on the V8 Brain engine. Review the source code and the Definition of Done document below. Identify:

1. Any DoD items marked DONE that the code does not fully implement

2. Any code that contradicts the design constraints

3. Any architectural weaknesses, missing error handling, or edge cases

4. Any discrepancies between what the code does and what the DoD claims


This is a closed code review — all source code and documentation is provided below. No external information is needed.


---


## V8-DOD.md


```markdown

# Thinker V8 Brain — Definition of Done

**Date:** 2026-03-29
**Scope:** Brain engine only (Chamber and Mission Controller come later)
**Parent DoD:** `_audit_thinker/THINKER-DOD-AND-PLAN.md`
**Philosophy:** Zero tolerance. No budgets. Works fully or ERROR.

---

## V8 DoD Checklist

Mapped from parent DoD (D1-D11, P1-P10) to V8 Brain scope.

### DONE (verified this session)

| # | Criterion | Status | How |
|---|-----------|--------|-----|
| D1 | No secrets in source code | DONE | All keys in `.env`, gitignored |
| D3 | Contradiction detection no false positives | DONE | Keyword threshold + stopword filter in `contradiction.py` |
| D4 | Argument tracking across rounds | DONE | Argument Tracker (extract → compare → re-inject). Replaces minority archive. Cumulative `all_unaddressed`. Round-prefixed IDs (R1-ARG-1). |
| D9 | proof.json always populated | DONE | Proof written on every complete run |
| D11 | All E2E tests pass | DONE | 211 tests pass (was 103) |
| -- | Zero-tolerance error handling | DONE | `BrainError` on any LLM/extraction failure. Pipeline halts. |
| -- | Search working (Bing free + Brave fallback + Sonar repeat) | DONE | Bing via curl_cffi primary ($0), Brave fallback, Sonar for repeats |
| -- | Per-framework position extraction | DONE | model/FRAMEWORK: POSITION [CONF] format, framework-level agreement |
| -- | Position validation against known models | DONE | Only MODEL_REGISTRY names accepted, no spurious positions |
| -- | Checkpoint/resume system | DONE | Full state save/restore, stage-level granularity |
| -- | Step-by-step default mode | DONE | `--full-run` to override, TTY check for non-interactive |

### DONE — Features (completed 2026-03-29)

| # | Criterion | How | Parent DoD |
|---|-----------|-----|------------|
| V8-F1 | Post-synthesis residue verification | `thinker/residue.py` — scans report for BLK/CTR/ARG IDs, flags >30% omission threshold. `synthesis_residue_omissions` added to proof.json. 8 tests. | D7 |
| V8-F2 | acceptance_status in proof | `AcceptanceStatus` enum in types.py. `compute_acceptance_status()` on ProofBuilder. ACCEPTED (clean) or ACCEPTED_WITH_WARNINGS. 5 tests. | D10 |
| V8-F3 | Evidence priority scoring | `score_evidence()` in evidence.py — keyword overlap + authority domain scoring. Under cap pressure, lowest-scored item evicted. FIFO preserved within same score. 7 tests. | D2 |
| V8-F4 | Full page content fetch | `thinker/page_fetch.py` — httpx fetch, HTML stripping, 50k char truncation. Populates `SearchResult.full_content`. 11 tests. | Spec §6 |
| V8-F5 | LLM-based evidence extraction | `thinker/evidence_extractor.py` — Sonnet call per page, parses FACT-N structured output. 11 tests. | Spec §6 |
| V8-F6 | Invariant validator | `thinker/invariant.py` — checks positions/rounds/evidence IDs/orphaned BLK+CTR refs. Returns violations with WARN/ERROR severity. 7 tests. | Spec §4 |

### DONE — Bug Fixes (completed 2026-03-29)

| # | Issue | Fix |
|---|-------|-----|
| V8-B1 | Bing search returns URLs without titles/snippets | Fixed by V8-F4 — page fetch provides content. Title auto-filled from page text when missing. |
| V8-B2 | Checkpoint schema not versioned | `CHECKPOINT_VERSION = "1.0"` constant. `PipelineState.load()` raises `ValueError` on mismatch. 4 tests. |
| V8-B3 | Position components lost on resume | Checkpoint now stores `components` list and `kind` field. Restore uses full components instead of `[option]`. 2 tests. |
| V8-B4 | 9 modules with zero test coverage | Added tests for: checkpoint (12), debug (9), pipeline (4), blocker (9), cross_domain (13), bing_search (5), brave_search (3), sonar_search (2). Total: 211 tests (was 103). |

### NOT APPLICABLE to V8 Brain (deferred to Chamber/Mission Controller)

| # | Criterion | Why |
|---|-----------|-----|
| D5 | Controller/synthesis mismatch ERROR | No Mission Controller yet |
| D6 | Mission inspects Brain invariants | No Mission Controller yet |
| D8 | Chamber proof artifact | Chamber not built yet |
| P1 | Mission controller test coverage | Not built yet |
| P4 | Chamber search parity | Chamber not built yet |

---

## Design Constraints (non-negotiable)

1. **Zero tolerance.** Any failure → BrainError → pipeline stops. No degraded mode.
2. **No budgets.** No wall clock limits, no token limits. Generous timeouts for all models.
3. **Thinking models get 30k tokens and 720s.** R1, Reasoner. Don't touch.
4. **Non-thinking models get 8k-16k tokens.** GLM-5, Kimi, Sonnet. Don't touch.
5. **Evidence FIFO cap.** Trust search engine ranking. No re-ranking. (V8-F3 would add eviction scoring but keep insertion order.)
6. **Gate 2 is deterministic.** No LLM call. Pure threshold computation. (Note: V8 spec §4 originally said LLM judgment — we chose deterministic. This is a deliberate simplification for V8.)
7. **Step-by-step is default.** `--full-run` to override.


```

---


## Source Code


### thinker/types.py


```python
"""Core types for the Thinker V8 Brain engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BrainError(Exception):
    """Fatal pipeline error — zero tolerance for silent failures.

    Raised when a critical component fails: LLM call, position extraction,
    argument tracking, synthesis. The pipeline must stop immediately.
    """
    def __init__(self, stage: str, message: str, detail: str = ""):
        self.stage = stage
        self.message = message
        self.detail = detail
        super().__init__(f"[{stage}] {message}")


class Outcome(Enum):
    """The three possible outcomes of a Brain deliberation."""
    DECIDE = "DECIDE"
    ESCALATE = "ESCALATE"
    NEED_MORE = "NEED_MORE"


class Confidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class BlockerKind(Enum):
    EVIDENCE_GAP = "EVIDENCE_GAP"
    CONTRADICTION = "CONTRADICTION"
    UNRESOLVED_DISAGREEMENT = "UNRESOLVED_DISAGREEMENT"
    CONTESTED_POSITION = "CONTESTED_POSITION"


class BlockerStatus(Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"
    DROPPED = "DROPPED"


class ArgumentStatus(Enum):
    ADDRESSED = "ADDRESSED"
    MENTIONED = "MENTIONED"
    IGNORED = "IGNORED"


class AcceptanceStatus(Enum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_WARNINGS = "ACCEPTED_WITH_WARNINGS"


@dataclass
class ModelResponse:
    """Raw response from a single LLM call."""
    model: str
    ok: bool
    text: str
    elapsed_s: float
    error: Optional[str] = None


@dataclass
class EvidenceItem:
    """A single piece of verified evidence."""
    evidence_id: str
    topic: str
    fact: str
    url: str
    confidence: Confidence
    content_hash: str = ""
    score: float = 0.0


@dataclass
class Argument:
    """A distinct argument extracted from model output."""
    argument_id: str
    round_num: int
    model: str
    text: str
    status: ArgumentStatus = ArgumentStatus.IGNORED
    addressed_in_round: Optional[int] = None


@dataclass
class Position:
    """A model's position in a given round."""
    model: str
    round_num: int
    primary_option: str
    components: list[str] = field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    qualifier: str = ""
    kind: str = "single"  # "single" or "sequence"


@dataclass
class Blocker:
    """A tracked blocker (evidence gap, contradiction, disagreement)."""
    blocker_id: str
    kind: BlockerKind
    source: str
    detected_round: int
    status: BlockerStatus = BlockerStatus.OPEN
    status_history: list[dict] = field(default_factory=list)
    models_involved: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    detail: str = ""
    resolution_note: str = ""


@dataclass
class Contradiction:
    """A detected contradiction between evidence items."""
    contradiction_id: str
    evidence_ids: list[str]
    topic: str
    severity: str  # "HIGH" or "MEDIUM"
    status: str = "UNRESOLVED"


@dataclass
class SearchResult:
    """A single search result (URL + content)."""
    url: str
    title: str
    snippet: str
    full_content: Optional[str] = None


@dataclass
class Gate1Result:
    """Result of Gate 1 assessment."""
    passed: bool
    outcome: Outcome
    questions: list[str] = field(default_factory=list)
    reasoning: str = ""
    search_recommended: bool = True  # Default to YES (conservative)
    search_reasoning: str = ""


@dataclass
class Gate2Assessment:
    """Result of Gate 2 trust assessment."""
    outcome: Outcome
    convergence_ok: bool
    evidence_credible: bool
    dissent_addressed: bool
    enough_data: bool
    report_honest: bool
    reasoning: str = ""


@dataclass
class RoundResult:
    """Result of a single deliberation round."""
    round_num: int
    responses: dict[str, ModelResponse] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)

    @property
    def responded(self) -> list[str]:
        return [m for m, r in self.responses.items() if r.ok]

    @property
    def texts(self) -> dict[str, str]:
        return {m: r.text for m, r in self.responses.items() if r.ok}


@dataclass
class BrainResult:
    """Final result of a complete Brain deliberation."""
    outcome: Outcome
    proof: dict
    report: str
    gate1: Gate1Result
    gate2: Optional[Gate2Assessment] = None

```


### thinker/brain.py


```python
"""Brain Orchestrator — wires the full V8 deliberation pipeline.

Flow:
  Gate 1 -> R1 -> Search(R1) -> R2 -> Search(R2) -> R3 -> Synthesis Gate -> Deterministic Gate 2

Debug modes:
  --verbose          : Full logging at each stage
  --stop-after STAGE : Run up to STAGE, save checkpoint, exit
  --resume FILE      : Resume from a checkpoint file

Stage IDs: gate1, r1, track1, search1, r2, track2, search2, r3, track3, synthesis, gate2
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Awaitable, Optional

from thinker.argument_tracker import ArgumentTracker
from thinker.config import BrainConfig, ROUND_TOPOLOGY
from thinker.debug import RunLog
from thinker.evidence import EvidenceLedger
from thinker.evidence_extractor import extract_evidence_from_page
from thinker.gate1 import run_gate1
from thinker.gate2 import run_gate2_deterministic, classify_outcome
from thinker.invariant import validate_invariants
from thinker.page_fetch import fetch_pages_for_results
from thinker.proof import ProofBuilder
from thinker.residue import check_synthesis_residue
from thinker.rounds import execute_round
from thinker.search import SearchOrchestrator, SearchPhase
from thinker.synthesis import run_synthesis
from thinker.tools.blocker import BlockerLedger
from thinker.tools.position import PositionTracker
from thinker.checkpoint import PipelineState, should_stop
from thinker.types import ArgumentStatus, BrainError, BrainResult, Confidence, EvidenceItem, Gate1Result, Outcome, Position, SearchResult


class Brain:
    """The V8 Brain deliberation engine."""

    def __init__(
        self,
        config: BrainConfig,
        llm_client,
        search_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        sonar_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        verbose: bool = False,
        stop_after: Optional[str] = None,
        outdir: str = "./output",
        resume_state: Optional[PipelineState] = None,
        debug_step: bool = False,
        search_override: Optional[bool] = None,
    ):
        self._config = config
        self._llm = llm_client
        self._search_fn = search_fn
        self._sonar_fn = sonar_fn
        self._stop_after = stop_after
        self._outdir = outdir
        self._debug_step = debug_step
        self._search_override = search_override  # None=gate1 decides, True=force on, False=force off
        self.log = RunLog(verbose=verbose)
        self.state = resume_state if resume_state else PipelineState()

    def _checkpoint(self, stage_id: str):
        """Save checkpoint and check if we should stop."""
        import os
        self.state.current_stage = stage_id
        self.state.completed_stages.append(stage_id)
        os.makedirs(self._outdir, exist_ok=True)
        self.state.save(Path(self._outdir) / "checkpoint.json")
        if should_stop(stage_id, self._stop_after):
            self.log._print(f"\n  [CHECKPOINT] Stopped after {stage_id}. Resume with --resume {self._outdir}/checkpoint.json")
            return True
        if self._debug_step:
            self._debug_pause(stage_id)
        return False

    def _debug_pause(self, stage_id: str):
        """Print stage analysis and wait for user confirmation."""
        st = self.state
        self.log._print(f"\n{'='*60}")
        self.log._print(f"  [DEBUG-STEP] Completed: {stage_id}")
        self.log._print(f"  Pipeline so far: {' → '.join(st.completed_stages)}")

        # Stage-specific analysis
        if stage_id == "gate1":
            self.log._print(f"  Gate 1: {'PASS' if st.gate1_passed else 'FAIL'}")
            if st.gate1_questions:
                self.log._print(f"  Questions: {st.gate1_questions}")

        elif stage_id.startswith("r"):
            rnd = stage_id[1:]
            texts = st.round_texts.get(rnd, {})
            responded = st.round_responded.get(rnd, [])
            failed = st.round_failed.get(rnd, [])
            self.log._print(f"  Round {rnd}: {len(responded)} responded, {len(failed)} failed")
            for m in responded:
                chars = len(texts.get(m, ""))
                self.log._print(f"    {m}: {chars} chars")
            if failed:
                self.log._print(f"    FAILED: {', '.join(failed)}")

        elif stage_id.startswith("track"):
            rnd = stage_id[5:]
            positions = st.positions_by_round.get(rnd, {})
            args = st.arguments_by_round.get(rnd, [])
            self.log._print(f"  Track R{rnd}: {len(positions)} positions, {len(args)} arguments")
            for m, p in positions.items():
                self.log._print(f"    {m}: {p.get('option','')} [{p.get('confidence','')}]")

        elif stage_id.startswith("search"):
            rnd = stage_id[6:]
            phase = "R1_R2" if rnd == "1" else f"R{rnd}_R{int(rnd)+1}"
            results = st.search_results.get(phase, 0)
            queries = st.search_queries.get(phase, [])
            self.log._print(f"  Search R{rnd}: {len(queries)} queries → {results} evidence items")
            self.log._print(f"  Total evidence: {st.evidence_count}")

        elif stage_id == "synthesis":
            self.log._print(f"  Synthesis complete")

        elif stage_id == "gate2":
            self.log._print(f"  Outcome: {st.outcome}")
            self.log._print(f"  Class: {st.outcome_class}")
            self.log._print(f"  Agreement: {st.agreement_ratio:.2f}")

        self.log._print(f"  Checkpoint: {self._outdir}/checkpoint.json")
        self.log._print(f"{'='*60}")
        import sys
        if not sys.stdin.isatty():
            self.log._print("  [DEBUG-STEP] Non-interactive mode (no TTY) — skipping pause. Use --full-run for cron/CI.")
            return
        try:
            resp = input("  Press Enter to continue, 'q' to stop → ").strip().lower()
        except EOFError:
            resp = ""
        if resp == "q":
            self.log._print("  [DEBUG-STEP] Stopped by user.")
            raise SystemExit(0)

    def _stage_done(self, stage_id: str) -> bool:
        """Check if a stage was already completed (for resume)."""
        return stage_id in self.state.completed_stages

    def _restore_trackers(self, argument_tracker: ArgumentTracker,
                          position_tracker: PositionTracker,
                          evidence: EvidenceLedger) -> tuple[dict[str, str], str]:
        """Restore tracker state from checkpoint. Returns (prior_views, unaddressed_text)."""
        from thinker.types import Argument, Confidence, Position
        st = self.state

        # Restore arguments by round
        for rnd_str, args_data in st.arguments_by_round.items():
            rnd = int(rnd_str)
            argument_tracker.arguments_by_round[rnd] = [
                Argument(
                    argument_id=a["id"], round_num=rnd,
                    model=a["model"], text=a["text"],
                )
                for a in args_data
            ]

        # Restore positions by round
        for rnd_str, pos_data in st.positions_by_round.items():
            rnd = int(rnd_str)
            positions = {}
            for model, p in pos_data.items():
                conf = Confidence[p.get("confidence", "MEDIUM")]
                option = p.get("option", "")
                components = p.get("components", [option])
                kind = p.get("kind", "single")
                positions[model] = Position(
                    model=model, round_num=rnd,
                    primary_option=option,
                    components=components,
                    confidence=conf,
                    qualifier=p.get("qualifier", ""),
                    kind=kind,
                )
            position_tracker.positions_by_round[rnd] = positions

        # Restore evidence items
        for ev_data in st.evidence_items:
            item = EvidenceItem(
                evidence_id=ev_data.get("evidence_id", ""),
                topic=ev_data.get("topic", ""),
                fact=ev_data.get("fact", ""),
                url=ev_data.get("url", ""),
                confidence=Confidence.MEDIUM,
            )
            evidence.add(item)

        # Find the last completed round to restore prior_views
        prior_views: dict[str, str] = {}
        last_round = 0
        for rnd_str in st.round_texts:
            rnd = int(rnd_str)
            if rnd > last_round:
                last_round = rnd
        if last_round > 0:
            prior_views = st.round_texts.get(str(last_round), {})

        unaddressed_text = st.unaddressed_text
        return prior_views, unaddressed_text

    async def run(self, brief: str) -> BrainResult:
        """Execute a full Brain deliberation."""
        log = self.log
        st = self.state
        resuming = len(st.completed_stages) > 0
        run_id = st.run_id if resuming else f"brain-{int(time.time())}"
        st.brief = brief
        st.rounds = self._config.rounds
        st.run_id = run_id

        if resuming:
            log._print(f"\n  [RESUME] Resuming from stage: {st.current_stage}")
            log._print(f"  [RESUME] Completed stages: {' → '.join(st.completed_stages)}")

        proof = ProofBuilder(run_id, brief, self._config.rounds)
        brief_keywords = {w.lower() for w in brief.split() if len(w) >= 4}
        evidence = EvidenceLedger(
            max_items=self._config.max_evidence_items,
            brief_keywords=brief_keywords,
        )
        argument_tracker = ArgumentTracker(self._llm)
        position_tracker = PositionTracker(self._llm)
        blocker_ledger = BlockerLedger()
        # Search decision deferred until after Gate 1 (needs recommendation)
        search_enabled = False
        search_orch = None
        proof.set_blocker_ledger(blocker_ledger)

        # Restore tracker state if resuming
        if resuming:
            prior_views, unaddressed_text = self._restore_trackers(
                argument_tracker, position_tracker, evidence,
            )
        else:
            prior_views = {}
            unaddressed_text = ""

        # --- Gate 1 ---
        if self._stage_done("gate1"):
            log._print("  [RESUME] Skipping gate1 (already completed)")
            gate1 = Gate1Result(
                passed=st.gate1_passed,
                outcome=Outcome.DECIDE if st.gate1_passed else Outcome.NEED_MORE,
                questions=st.gate1_questions,
                reasoning=st.gate1_reasoning,
                search_recommended=st.gate1_search_recommended,
                search_reasoning=st.gate1_search_reasoning,
            )
        else:
            log.gate1_start(len(brief))
            t0 = time.monotonic()
            gate1 = await run_gate1(self._llm, brief)
            log.gate1_result(gate1.passed, gate1.reasoning, gate1.questions, time.monotonic() - t0)
            st.gate1_passed = gate1.passed
            st.gate1_reasoning = gate1.reasoning
            st.gate1_questions = gate1.questions
            st.gate1_search_recommended = gate1.search_recommended
            st.gate1_search_reasoning = gate1.search_reasoning

            if not gate1.passed:
                proof.set_final_status("GATE1_REJECTED")
                return BrainResult(
                    outcome=gate1.outcome, proof=proof.build(),
                    report="", gate1=gate1,
                )
            if self._checkpoint("gate1"):
                return BrainResult(outcome=Outcome.NEED_MORE, proof=proof.build(), report="[STOPPED AT GATE1]", gate1=gate1)

        # --- Search Decision ---
        # CLI override > Gate 1 recommendation > default (on if provider available)
        has_search_provider = self._search_fn is not None
        if self._search_override is not None:
            # CLI override
            search_enabled = self._search_override and has_search_provider
            source = "cli_override"
            if self._search_override:
                override_reasoning = "Forced on via --search"
            else:
                override_reasoning = "Forced off via --no-search"
            proof.set_search_decision(
                source=source, value=search_enabled,
                reasoning=override_reasoning,
                gate1_recommended=gate1.search_recommended,
                gate1_search_reasoning=gate1.search_reasoning,
            )
            log._print(f"  [SEARCH DECISION] {source}: {'ON' if search_enabled else 'OFF'} "
                        f"(Gate 1 recommended: {'YES' if gate1.search_recommended else 'NO'} — {gate1.search_reasoning})")
        else:
            # Gate 1 decides
            search_enabled = gate1.search_recommended and has_search_provider
            proof.set_search_decision(
                source="gate1", value=search_enabled,
                reasoning=gate1.search_reasoning,
            )
            log._print(f"  [SEARCH DECISION] gate1: {'ON' if search_enabled else 'OFF'} — {gate1.search_reasoning}")

        if search_enabled:
            search_orch = SearchOrchestrator(
                self._llm, search_fn=self._search_fn,
                sonar_fn=self._sonar_fn,
            )

        # --- Deliberation Rounds ---
        if not resuming:
            prior_views = {}
            unaddressed_text = ""

        for round_num in range(1, self._config.rounds + 1):
            is_last_round = round_num == self._config.rounds
            models = ROUND_TOPOLOGY[round_num]

            # --- Skip completed round stages on resume ---
            round_stage = f"r{round_num}"
            track_stage = f"track{round_num}"
            search_stage = f"search{round_num}"

            # Determine if this round's search phase exists (search runs after R1 and R2, not last round)
            has_search_phase = (round_num <= self._config.search_after_rounds
                                and not is_last_round and search_orch)

            if self._stage_done(search_stage):
                # Round + tracking + search all done — fully skip
                log._print(f"  [RESUME] Skipping round {round_num} (already completed)")
                # Repopulate proof from checkpoint so skipped rounds appear in proof.json
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                proof.record_round(round_num, saved_responded, saved_failed)
                if str(round_num) in st.positions_by_round:
                    _pos = {}
                    for _m, _p in st.positions_by_round[str(round_num)].items():
                        _pos[_m] = Position(
                            model=_m, round_num=round_num,
                            primary_option=_p.get("option", ""),
                            components=_p.get("components", [_p.get("option", "")]),
                            confidence=Confidence[_p.get("confidence", "MEDIUM")],
                            qualifier=_p.get("qualifier", ""),
                            kind=_p.get("kind", "single"),
                        )
                    proof.record_positions(round_num, _pos)
                continue

            if self._stage_done(track_stage) and not has_search_phase:
                # Track done, no search phase for this round — fully skip
                log._print(f"  [RESUME] Skipping round {round_num} (already completed)")
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                proof.record_round(round_num, saved_responded, saved_failed)
                if str(round_num) in st.positions_by_round:
                    _pos = {}
                    for _m, _p in st.positions_by_round[str(round_num)].items():
                        _pos[_m] = Position(
                            model=_m, round_num=round_num,
                            primary_option=_p.get("option", ""),
                            components=_p.get("components", [_p.get("option", "")]),
                            confidence=Confidence[_p.get("confidence", "MEDIUM")],
                            qualifier=_p.get("qualifier", ""),
                            kind=_p.get("kind", "single"),
                        )
                    proof.record_positions(round_num, _pos)
                continue

            # Need to reconstruct RoundResult if round execution is done
            round_result = None
            if self._stage_done(round_stage) or self._stage_done(track_stage):
                # Round executed — reconstruct from checkpoint for search/compare
                skip_msg = "resuming at search" if self._stage_done(track_stage) else "resuming at tracking"
                log._print(f"  [RESUME] Skipping round {round_num} execution ({skip_msg})")
                from thinker.types import ModelResponse, RoundResult
                saved_texts = st.round_texts.get(str(round_num), {})
                saved_responded = st.round_responded.get(str(round_num), [])
                saved_failed = st.round_failed.get(str(round_num), [])
                responses = {}
                for m in saved_responded:
                    responses[m] = ModelResponse(model=m, ok=True, text=saved_texts.get(m, ""), elapsed_s=0.0)
                for m in saved_failed:
                    responses[m] = ModelResponse(model=m, ok=False, text="", elapsed_s=0.0, error="failed in prior run")
                round_result = RoundResult(round_num=round_num, responses=responses, failed=saved_failed)
            else:
                # Execute round normally
                log.round_start(round_num, models, is_last_round)

                t0 = time.monotonic()
                round_result = await execute_round(
                    self._llm, round_num=round_num, brief=brief,
                    prior_views=prior_views if round_num > 1 else None,
                    evidence_text=evidence.format_for_prompt() if round_num > 1 else "",
                    unaddressed_arguments=unaddressed_text if round_num > 1 else "",
                    is_last_round=is_last_round,
                )
                log.round_result(round_num, round_result.responded, round_result.failed,
                                 round_result.texts, time.monotonic() - t0)
                proof.record_round(round_num, round_result.responded, round_result.failed)
                # Store full text for resume — truncation loses SEARCH_REQUESTS appendix
                st.round_texts[str(round_num)] = round_result.texts
                st.round_responded[str(round_num)] = round_result.responded
                st.round_failed[str(round_num)] = round_result.failed

                if not round_result.responded:
                    proof.set_final_status("FAILED_NO_RESPONSES")
                    proof.add_violation("BV1", "FATAL", f"No models responded in round {round_num}")
                    return BrainResult(
                        outcome=Outcome.ESCALATE, proof=proof.build(),
                        report="", gate1=gate1,
                    )

                if self._checkpoint(f"r{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT R{round_num}]", gate1=gate1)

            # --- Tracking phase (skip if already done on resume) ---
            if not self._stage_done(track_stage):
                # Extract arguments
                t0 = time.monotonic()
                args = await argument_tracker.extract_arguments(round_num, round_result.texts)
                log.arg_extract(round_num, args, time.monotonic() - t0, argument_tracker.last_raw_response)
                st.arguments_by_round[str(round_num)] = [
                    {"id": a.argument_id, "model": a.model, "text": a.text} for a in args
                ]

                # Extract positions
                t0 = time.monotonic()
                positions = await position_tracker.extract_positions(round_num, round_result.texts)
                log.pos_extract(round_num, positions, time.monotonic() - t0, position_tracker.last_raw_response)
                proof.record_positions(round_num, positions)
                st.positions_by_round[str(round_num)] = {
                    m: {
                        "option": p.primary_option,
                        "confidence": p.confidence.value,
                        "qualifier": p.qualifier,
                        "components": p.components,
                        "kind": p.kind,
                    }
                    for m, p in positions.items()
                }

                # Track position changes
                if round_num > 1:
                    changes = position_tracker.get_position_changes(round_num - 1, round_num)
                    log.pos_changes(round_num - 1, round_num, changes)
                    proof.record_position_changes(changes)
                    st.position_changes.extend(changes)

                if self._checkpoint(f"track{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT TRACK{round_num}]", gate1=gate1)
            else:
                log._print(f"  [RESUME] Skipping track{round_num} (already completed)")

            # Search phase — after R1 and R2 only
            if has_search_phase:
                phase = SearchPhase.R1_R2 if round_num == 1 else SearchPhase.R2_R3
                t0 = time.monotonic()

                model_requests = search_orch.collect_model_requests(round_result.texts)
                proactive = await search_orch.generate_proactive_queries(
                    round_result.texts, already_queued=model_requests,
                )
                queries = search_orch.deduplicate(model_requests + proactive)
                log.search_start(phase.value, model_requests, proactive)
                st.search_queries[phase.value] = queries

                total_admitted = 0
                search_errors = 0
                all_search_results: list[SearchResult] = []
                for query in queries[:self._config.max_search_queries_per_phase]:
                    try:
                        results = await search_orch.execute_query(query, phase)
                    except Exception as e:
                        log._print(f"  [SEARCH ERROR] {query[:50]}: {e}")
                        search_errors += 1
                        continue
                    all_search_results.extend(results)

                if search_errors > 0:
                    log._print(f"  [SEARCH WARNING] {search_errors}/{len(queries)} queries failed")

                # F4: Fetch full page content for top results
                try:
                    await fetch_pages_for_results(all_search_results, max_pages=5)
                except Exception as e:
                    log._print(f"  [PAGE FETCH WARNING] {e}")

                # F5: LLM-based extraction from fetched pages, fallback to snippets
                for sr in all_search_results:
                    if sr.full_content:
                        try:
                            extracted_facts = await extract_evidence_from_page(
                                self._llm, sr.url, sr.full_content,
                            )
                            for fact_data in extracted_facts:
                                ev = EvidenceItem(
                                    evidence_id=f"E{len(evidence.items) + 1:03d}",
                                    topic=sr.title[:100] if sr.title else sr.url[:100],
                                    fact=fact_data["fact"][:500],
                                    url=sr.url,
                                    confidence=Confidence.MEDIUM,
                                )
                                if evidence.add(ev):
                                    total_admitted += 1
                        except BrainError:
                            raise  # Zero tolerance
                        except Exception as e:
                            log._print(f"  [EXTRACT WARNING] {sr.url[:50]}: {e}")
                    else:
                        # Fallback: use snippet/title as before
                        ev = EvidenceItem_from_search_result(sr, len(evidence.items))
                        if ev and evidence.add(ev):
                            total_admitted += 1

                # Wire evidence contradictions into blocker ledger
                from thinker.types import BlockerKind
                for ctr in evidence.contradictions:
                    if not any(b.detail == ctr.contradiction_id for b in blocker_ledger.blockers):
                        blocker_ledger.add(
                            kind=BlockerKind.CONTRADICTION,
                            source="evidence_ledger",
                            detected_round=round_num,
                            detail=ctr.contradiction_id,
                            models=[],
                        )

                log.search_result(phase.value, len(queries), total_admitted, time.monotonic() - t0)
                proof.record_research_phase(
                    phase.value, "brave", len(queries), total_admitted,
                )
                st.search_results[phase.value] = total_admitted
                st.evidence_items = [
                    {"evidence_id": e.evidence_id, "topic": e.topic,
                     "fact": e.fact, "url": e.url, "score": e.score}
                    for e in evidence.items
                ]
                st.evidence_count = len(evidence.items)

                if self._checkpoint(f"search{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT SEARCH{round_num}]", gate1=gate1)

            # Compare arguments (after R2+)
            if round_num > 1:
                t0 = time.monotonic()
                unaddressed = await argument_tracker.compare_with_round(
                    round_num - 1, round_result.texts,
                )
                addressed = len(argument_tracker.arguments_by_round.get(round_num - 1, [])) - len(unaddressed)
                ignored = [a for a in unaddressed if a.status == ArgumentStatus.IGNORED]
                mentioned = [a for a in unaddressed if a.status == ArgumentStatus.MENTIONED]
                log.arg_compare(round_num - 1, addressed, len(mentioned), len(ignored),
                                time.monotonic() - t0, unaddressed)
                unaddressed_text = argument_tracker.format_reinjection(unaddressed)
                st.unaddressed_text = unaddressed_text

            prior_views = round_result.texts

        # --- Classification (deterministic) ---
        final_round = self._config.rounds
        agreement = position_tracker.agreement_ratio(final_round)
        final_positions = position_tracker.positions_by_round.get(final_round, {})

        all_ignored = [a for a in argument_tracker.all_unaddressed if a.status == ArgumentStatus.IGNORED]
        all_mentioned = [a for a in argument_tracker.all_unaddressed if a.status == ArgumentStatus.MENTIONED]

        outcome_class = classify_outcome(
            agreement_ratio=agreement,
            ignored_arguments=len(all_ignored),
            mentioned_arguments=len(all_mentioned),
            evidence_count=len(evidence.items),
            contradictions=len(evidence.contradictions),
            open_blockers=len(blocker_ledger.open_blockers()),
            search_enabled=search_enabled,
        )
        st.agreement_ratio = agreement
        st.outcome_class = outcome_class

        # --- Synthesis Gate ---
        t0 = time.monotonic()
        final_views = prior_views
        report, report_json = await run_synthesis(
            self._llm, brief=brief, final_views=final_views,
            blocker_summary=blocker_ledger.summary(),
            outcome_class=outcome_class,
            evidence_text=evidence.format_for_prompt(),
        )
        log.synthesis_result(len(report), bool(report_json), time.monotonic() - t0)
        proof.set_synthesis_status("COMPLETE" if report else "FAILED")
        st.report = report[:5000]
        st.report_json = report_json

        if self._checkpoint("synthesis"):
            return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=report, gate1=gate1)

        # --- Gate 2 (deterministic) ---
        gate2 = run_gate2_deterministic(
            agreement_ratio=agreement,
            positions=final_positions,
            contradictions=evidence.contradictions,
            unaddressed_arguments=argument_tracker.all_unaddressed,
            open_blockers=blocker_ledger.open_blockers(),
            evidence_count=len(evidence.items),
            search_enabled=search_enabled,
        )
        log.gate2_result(
            gate2.outcome.value, agreement, outcome_class,
            len(all_ignored), len(evidence.items),
            len(evidence.contradictions), len(blocker_ledger.open_blockers()),
        )
        st.outcome = gate2.outcome.value
        self._checkpoint("gate2")

        # --- Invariant validation (F6) ---
        round_responded_ints = {int(k): v for k, v in st.round_responded.items()}
        inv_violations = validate_invariants(
            positions_by_round=position_tracker.positions_by_round,
            round_responded=round_responded_ints,
            evidence=evidence,
            blocker_ledger=blocker_ledger,
            rounds_completed=self._config.rounds,
        )
        for v in inv_violations:
            proof.add_violation(v["id"], v["severity"], v["detail"])

        # --- Post-synthesis residue verification (F1) ---
        residue_omissions = check_synthesis_residue(
            report=report,
            blockers=blocker_ledger.blockers,
            contradictions=evidence.contradictions,
            unaddressed_arguments=argument_tracker.all_unaddressed,
        )
        proof.set_synthesis_residue(residue_omissions)
        if any(o.get("threshold_violation") for o in residue_omissions):
            proof.add_violation(
                "RESIDUE-THRESHOLD", "WARN",
                f"Synthesis omitted >30% of structural findings ({len(residue_omissions)} omissions)",
            )

        # --- Final ---
        outcome = gate2.outcome
        proof.set_outcome(outcome, agreement, outcome_class)
        proof.set_final_status("COMPLETE")
        proof.set_evidence_count(len(evidence.items))

        # --- Acceptance status (F2) — must be computed last, after all violations ---
        proof.compute_acceptance_status()

        log.run_complete(outcome.value, outcome_class)

        return BrainResult(
            outcome=outcome, proof=proof.build(),
            report=report, gate1=gate1, gate2=gate2,
        )


def EvidenceItem_from_search_result(sr: SearchResult, counter: int):
    """Convert a SearchResult to an EvidenceItem for the ledger."""
    from thinker.types import Confidence
    content = sr.full_content or sr.snippet or sr.title
    if not content:
        return None
    return EvidenceItem(
        evidence_id=f"E{counter + 1:03d}",
        topic=sr.title[:100] if sr.title else sr.url[:100],
        fact=content[:500],
        url=sr.url,
        confidence=Confidence.MEDIUM,
    )


def _get_anthropic_token() -> str:
    """Get the Anthropic OAuth token.

    Priority:
    1. ANTHROPIC_OAUTH_TOKEN env var / .env (should be the 1-year setup-token)
    2. Fall back to ~/.claude/.credentials.json (rotating ~8h token)
    """
    import os
    token = os.environ.get("ANTHROPIC_OAUTH_TOKEN", "")
    if token:
        return token
    import json
    from pathlib import Path
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        try:
            creds = json.loads(creds_path.read_text(encoding="utf-8"))
            return creds.get("claudeAiOauth", {}).get("accessToken", "")
        except Exception:
            pass
    return ""


async def main():
    """CLI entry point for the Brain engine."""
    import argparse
    import json
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Thinker V8 Brain Engine")
    parser.add_argument("--brief", required=True, help="Path to brief markdown file")
    parser.add_argument("--rounds", type=int, default=4, help="Number of rounds (1-4)")
    parser.add_argument("--outdir", default="./output", help="Output directory")
    parser.add_argument("--verbose", action="store_true", help="Full logging at each stage")
    parser.add_argument("--stop-after", default=None,
                        help="Stop after STAGE, save checkpoint (gate1,r1,track1,search1,r2,...)")
    parser.add_argument("--resume", default=None,
                        help="Resume from a checkpoint JSON file (skips completed stages)")
    parser.add_argument("--full-run", action="store_true",
                        help="Run all stages without pausing (overrides default step-by-step mode)")
    search_group = parser.add_mutually_exclusive_group()
    search_group.add_argument("--search", action="store_true", default=None,
                              help="Force search on (overrides Gate 1 recommendation)")
    search_group.add_argument("--no-search", action="store_true", default=None,
                              help="Force search off (overrides Gate 1 recommendation)")
    args = parser.parse_args()

    brief_text = open(args.brief, encoding="utf-8").read()
    config = BrainConfig(
        rounds=args.rounds,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        anthropic_oauth_token=_get_anthropic_token(),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        zai_api_key=os.environ.get("ZAI_API_KEY", ""),
        brave_api_key=os.environ.get("BRAVE_API_KEY", ""),
        outdir=args.outdir,
    )

    # Load checkpoint if resuming
    resume_state = None
    if args.resume:
        resume_state = PipelineState.load(Path(args.resume))
        print(f"Resuming from checkpoint: {args.resume}")
        print(f"  Last stage: {resume_state.current_stage}")
        print(f"  Completed: {' → '.join(resume_state.completed_stages)}")

    from thinker.llm import LLMClient
    from thinker.brave_search import brave_search
    from thinker.sonar_search import sonar_search
    from functools import partial
    llm = LLMClient(config)

    # Step-by-step is the DEFAULT. --full-run disables it.
    debug_step = not args.full_run
    verbose = args.verbose or args.stop_after is not None or args.resume is not None or debug_step

    # Search: Bing via Playwright (headful, $0). Error if unavailable.
    search_fn = None
    try:
        from thinker.bing_search import bing_search
        search_fn = bing_search
        if verbose:
            print("  [SEARCH] Using Bing via Playwright (headful, $0)")
    except ImportError:
        print("  [SEARCH ERROR] Bing search requires playwright: pip install playwright && playwright install chromium")
        raise SystemExit(1)
    sonar_fn = partial(sonar_search, api_key=config.openrouter_api_key) if config.openrouter_api_key else None
    # Resolve search override from CLI flags
    search_override = None
    if args.search:
        search_override = True
    elif args.no_search:
        search_override = False

    brain = Brain(
        config=config, llm_client=llm, search_fn=search_fn,
        sonar_fn=sonar_fn,
        verbose=verbose, stop_after=args.stop_after, outdir=args.outdir,
        resume_state=resume_state, debug_step=debug_step,
        search_override=search_override,
    )
    try:
        result = await brain.run(brief_text)
    except BrainError as e:
        print(f"\n{'='*60}")
        print(f"  SYSTEM ERROR — Pipeline halted")
        print(f"{'='*60}")
        print(f"  Stage:   {e.stage}")
        print(f"  Error:   {e.message}")
        if e.detail:
            print(f"  Detail:  {e.detail}")
        print(f"  Checkpoint: {os.path.join(args.outdir, 'checkpoint.json')}")
        print(f"{'='*60}")
        # Save what we have so far
        os.makedirs(args.outdir, exist_ok=True)
        brain.log.save_log(Path(args.outdir) / "debug.log")
        brain.log.save_events_json(Path(args.outdir) / "events.json")
        await llm.close()
        raise SystemExit(1)

    # Save outputs
    os.makedirs(args.outdir, exist_ok=True)
    proof_path = os.path.join(args.outdir, "proof.json")
    with open(proof_path, "w", encoding="utf-8") as f:
        json.dump(result.proof, f, indent=2)
    report_path = os.path.join(args.outdir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result.report)

    # Save debug outputs
    brain.log.save_log(Path(args.outdir) / "debug.log")
    brain.log.save_events_json(Path(args.outdir) / "events.json")

    # Generate auto-populated diagram from stage registry + run data
    # Import all tagged modules so the registry is populated
    import thinker.gate1, thinker.rounds, thinker.argument_tracker  # noqa: F401
    import thinker.tools.position, thinker.search, thinker.synthesis, thinker.gate2  # noqa: F401
    import thinker.invariant, thinker.residue, thinker.page_fetch, thinker.evidence_extractor  # noqa: F401
    from thinker.pipeline import generate_architecture_html
    events_data = json.loads((Path(args.outdir) / "events.json").read_text())
    generate_architecture_html(
        Path(args.outdir) / "run-report.html",
        run_events=events_data, proof=result.proof, report=result.report,
    )

    print(f"\nOutcome: {result.outcome.value}")
    print(f"Class: {result.proof.get('v3_outcome_class', 'N/A')}")
    print(f"Proof: {proof_path}")
    print(f"Report: {report_path}")
    print(f"Debug: {os.path.join(args.outdir, 'run-report.html')}")

    await llm.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

```


### thinker/gate1.py


```python
"""Gate 1: Is the question answerable?

V8 spec Section 4, Gate 1:
One fast Sonnet call reads the brief. If the question is too vague or missing
key facts: push back with specific questions. Never guess. Never search for
missing context. The requester knows their situation — ask them.

Cost: ~$0.01. Saves ~$2 and 15 minutes on garbage questions.
"""
from __future__ import annotations

import re

from thinker.pipeline import pipeline_stage
from thinker.types import Gate1Result, Outcome

GATE1_PROMPT = """You are a question quality assessor for a multi-model deliberation system.

Read the following brief and determine:
1. Whether it provides enough context for 4 AI models to reason about independently
2. Whether web search would improve the deliberation quality

A brief PASSES if:
- The question is specific enough that a smart human would start working on it
- Key facts are provided (who, what, when, scope)
- The question has a clear deliverable (assess, determine, evaluate, compare)

A brief NEEDS MORE if:
- Critical context is missing (no system named, no timeline, no scope)
- The question is so vague that models would have to guess
- Key terms are ambiguous without clarification

SEARCH is YES if the brief contains:
- Specific regulatory/legal references that should be verified (GDPR articles, CFR sections, etc.)
- Numeric claims, statistics, or benchmarks that could be fact-checked
- References to specific products, versions, CVEs, or standards
- Questions where current/recent information matters

SEARCH is NO if:
- The brief is a pure reasoning/logic/strategy question with no factual claims to verify
- All necessary facts are already provided in the brief
- The question is about internal architecture or design choices, not external facts

IMPORTANT: You are NOT searching for information. You are NOT filling in blanks.
You are ONLY assessing the brief and recommending whether search would help.

Brief:
{brief}

Respond in this exact format:
VERDICT: PASS | NEED_MORE
SEARCH: YES | NO
SEARCH_REASONING: (one sentence explaining why search is or isn't needed)
QUESTIONS:
- (list specific questions if NEED_MORE, leave blank if PASS)
REASONING: (one paragraph on the verdict)"""


def parse_gate1_response(text: str) -> Gate1Result:
    """Parse Sonnet's Gate 1 response into a structured result."""
    # Extract verdict
    verdict_match = re.search(r"VERDICT:\s*(PASS|NEED_MORE)", text, re.IGNORECASE)
    if not verdict_match:
        # Unparseable → fail open (pass the brief through)
        return Gate1Result(passed=True, outcome=Outcome.DECIDE,
                          reasoning="Gate 1 response unparseable — passing through")

    verdict = verdict_match.group(1).upper()
    passed = verdict == "PASS"
    outcome = Outcome.DECIDE if passed else Outcome.NEED_MORE

    # Extract search recommendation (default YES if missing — conservative)
    search_match = re.search(r"SEARCH:\s*(YES|NO)", text, re.IGNORECASE)
    search_recommended = True  # Default: search
    if search_match:
        search_recommended = search_match.group(1).upper() == "YES"

    # Extract search reasoning
    search_reasoning = ""
    sr_match = re.search(r"SEARCH_REASONING:\s*(.+?)(?:\n|$)", text)
    if sr_match:
        search_reasoning = sr_match.group(1).strip()

    # Extract questions
    questions = []
    questions_match = re.search(r"QUESTIONS:\s*\n((?:- .+\n?)*)", text)
    if questions_match:
        for line in questions_match.group(1).strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                questions.append(line[2:].strip())

    # Extract reasoning
    reasoning = ""
    reasoning_match = re.search(r"REASONING:\s*(.+)", text, re.DOTALL)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()

    return Gate1Result(passed=passed, outcome=outcome, questions=questions,
                       reasoning=reasoning, search_recommended=search_recommended,
                       search_reasoning=search_reasoning)


@pipeline_stage(
    name="Gate 1",
    description="One fast Sonnet call checks if the brief has enough context for 4 models to reason independently. If not, pushes back with specific questions. Never guesses, never searches.",
    stage_type="gate",
    order=1,
    provider="sonnet",
    inputs=["brief"],
    outputs=["passed (bool)", "questions (list)", "reasoning (str)"],
    prompt=GATE1_PROMPT,
    logic="""PASS if: question specific, key facts provided (who/what/when/scope), clear deliverable.
NEED_MORE if: critical context missing, too vague, ambiguous terms.
MALFORMED response: fail open (PASS).
LLM failure: fail open (PASS).""",
    failure_mode="Fail open — don't block the pipeline on infra issues",
    cost="~$0.01 per call (Anthropic Max subscription = $0)",
    stage_id="gate1",
)
async def run_gate1(client, brief: str) -> Gate1Result:
    """Run Gate 1 assessment.

    Args:
        client: LLM client (real or mock) with async call(model, prompt) method.
        brief: The full brief text.

    Returns:
        Gate1Result with pass/fail, outcome, and any push-back questions.
    """
    resp = await client.call("sonnet", GATE1_PROMPT.format(brief=brief))

    if not resp.ok:
        from thinker.types import BrainError
        raise BrainError("gate1", f"Sonnet LLM call failed: {resp.error}",
                         detail="Gate 1 cannot assess brief quality without a working LLM.")

    return parse_gate1_response(resp.text)

```


### thinker/gate2.py


```python
"""Gate 2: Deterministic trust assessment.

No LLM call. Thresholds on mechanical tool data only.

For decision briefs: DECIDE or ESCALATE based on agreement + argument engagement.
For analysis briefs: always deliver, classification label attached.

Classification system (adapted from Chamber V11):
- CONSENSUS: models agree, all arguments addressed, no open issues
- CLOSED_WITH_ACCEPTED_RISKS: models agree, but open blockers/contradictions acknowledged
- PARTIAL_CONSENSUS: models agree on some points, diverge on others
- INSUFFICIENT_EVIDENCE: not enough evidence gathered to support conclusions
- NO_CONSENSUS: fundamental disagreement persists after all rounds
"""
from __future__ import annotations

from thinker.pipeline import pipeline_stage
from thinker.types import Argument, ArgumentStatus, Blocker, Contradiction, Gate2Assessment, Outcome, Position


@pipeline_stage(
    name="Gate 2",
    description="Fully deterministic trust assessment. No LLM call. Instant. Reproducible. Thresholds on mechanical tool data: agreement_ratio, ignored arguments, evidence count, contradictions, open blockers.",
    stage_type="deterministic",
    order=7,
    provider="deterministic (no LLM)",
    inputs=["agreement_ratio", "ignored_arguments", "evidence_count", "contradictions", "open_blockers", "search_enabled"],
    outputs=["outcome (DECIDE/ESCALATE)", "outcome_class (str)"],
    logic="""if agreement < 0.5 → NO_CONSENSUS
if search_enabled and evidence == 0 → INSUFFICIENT_EVIDENCE
if agreement >= 0.75 and ignored == 0 and contradictions == 0 and blockers == 0 → CONSENSUS
if agreement >= 0.75 and ignored <= 2 → CLOSED_WITH_ACCEPTED_RISKS
else → PARTIAL_CONSENSUS

DECIDE if agreement >= 0.75, else ESCALATE.""",
    thresholds={"agreement_ratio >= 0.75": "DECIDE", "agreement_ratio < 0.5": "NO_CONSENSUS", "ignored_arguments >= 3": "NO_CONSENSUS"},
    failure_mode="Cannot fail — deterministic computation.",
    cost="$0 (no LLM call)",
    stage_id="gate2",
)
def classify_outcome(
    agreement_ratio: float,
    ignored_arguments: int,
    mentioned_arguments: int,
    evidence_count: int,
    contradictions: int,
    open_blockers: int,
    search_enabled: bool,
) -> str:
    """Deterministic outcome classification.

    Returns one of: CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, PARTIAL_CONSENSUS,
    INSUFFICIENT_EVIDENCE, NO_CONSENSUS.
    """
    # NO_CONSENSUS: low agreement AND many ignored arguments
    if agreement_ratio < 0.5:
        return "NO_CONSENSUS"

    # INSUFFICIENT_EVIDENCE: search was enabled but found nothing
    if search_enabled and evidence_count == 0:
        return "INSUFFICIENT_EVIDENCE"

    # CONSENSUS: high agreement, all arguments engaged, no open issues
    if (agreement_ratio >= 0.75
            and ignored_arguments == 0
            and contradictions == 0
            and open_blockers == 0):
        return "CONSENSUS"

    # CLOSED_WITH_ACCEPTED_RISKS: high agreement but open issues acknowledged
    if agreement_ratio >= 0.75 and ignored_arguments <= 2:
        return "CLOSED_WITH_ACCEPTED_RISKS"

    # PARTIAL_CONSENSUS: moderate agreement or many arguments unengaged
    return "PARTIAL_CONSENSUS"


def run_gate2_deterministic(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list[Contradiction],
    unaddressed_arguments: list[Argument],
    open_blockers: list[Blocker],
    evidence_count: int,
    search_enabled: bool,
) -> Gate2Assessment:
    """Deterministic Gate 2 — no LLM call.

    For decision briefs: DECIDE requires agreement >= 0.75 and all arguments addressed.
    Otherwise: ESCALATE.
    """
    ignored = [a for a in unaddressed_arguments if a.status == ArgumentStatus.IGNORED]
    mentioned = [a for a in unaddressed_arguments if a.status == ArgumentStatus.MENTIONED]

    convergence_ok = agreement_ratio >= 0.75
    evidence_ok = evidence_count >= 3 or not search_enabled
    dissent_ok = len(ignored) <= 2  # A few ignored args don't block if agreement is high
    data_ok = evidence_count > 0 or not search_enabled
    no_blockers = len(open_blockers) == 0

    # DECIDE requires convergence — the conclusion is what matters
    # A few unaddressed minor arguments don't override strong agreement
    if convergence_ok:
        outcome = Outcome.DECIDE
    else:
        outcome = Outcome.ESCALATE

    outcome_class = classify_outcome(
        agreement_ratio=agreement_ratio,
        ignored_arguments=len(ignored),
        mentioned_arguments=len(mentioned),
        evidence_count=evidence_count,
        contradictions=len(contradictions),
        open_blockers=len(open_blockers),
        search_enabled=search_enabled,
    )

    return Gate2Assessment(
        outcome=outcome,
        convergence_ok=convergence_ok,
        evidence_credible=evidence_ok,
        dissent_addressed=dissent_ok,
        enough_data=data_ok,
        report_honest=no_blockers,
        reasoning=(
            f"Deterministic: agreement={agreement_ratio:.2f}, "
            f"ignored={len(ignored)}, evidence={evidence_count}, "
            f"contradictions={len(contradictions)}, blockers={len(open_blockers)}, "
            f"class={outcome_class}"
        ),
    )

```


### thinker/rounds.py


```python
"""Round execution for the Brain deliberation engine.

Topology: 4 -> 3 -> 2 -> 2
- R1: brief only (4 models, parallel)
- R2: brief + R1 views + evidence + unaddressed arguments (3 models)
- R3: brief + R2 views + evidence + unaddressed arguments (2 models)

Search requests: R1 and R2 prompts include a section asking models to list
0-5 search queries as an appendix. R3 does not (final convergence round).
"""
from __future__ import annotations

import asyncio

from thinker.config import ROUND_TOPOLOGY
from thinker.pipeline import pipeline_stage
from thinker.types import ModelResponse, RoundResult

# Evidence framing — makes clear that web-verified evidence outranks model opinions
_EVIDENCE_HEADER = (
    "## Web-Verified Evidence (AUTHORITATIVE — outranks model opinions)\n\n"
    "The following facts were retrieved from web sources and verified. "
    "When a model's prior claim conflicts with evidence below, the evidence takes precedence. "
    "Cite evidence IDs (E001-E999) when referencing these facts.\n\n"
)

_SEARCH_REQUEST_SECTION = (
    "\n## Search Requests (optional, 0-5)\n"
    "After your analysis, you may list 0-5 specific questions you want fact-checked "
    "via web search before the next round. These will be searched and results injected "
    "into the next round's prompt. If you have no search requests, write NONE.\n\n"
    "Format:\n"
    "SEARCH_REQUESTS:\n"
    "1. [specific, searchable query]\n"
    "2. ...\n"
)


def build_round_prompt(
    round_num: int,
    brief: str,
    prior_views: dict[str, str],
    evidence_text: str,
    unaddressed_arguments: str,
    is_last_round: bool = False,
) -> str:
    """Build the prompt for a given round.

    R1: brief + search request appendix.
    R2: brief + prior views + evidence + unaddressed args + search request appendix.
    R3: brief + prior views + evidence + unaddressed args (no search — final round).
    """
    parts = []

    parts.append("You are participating in a multi-model deliberation. "
                 "Analyze the following brief independently and thoroughly.\n")
    parts.append(f"## Brief\n\n{brief}\n")

    if round_num >= 2 and prior_views:
        parts.append("## Prior Round Views\n")
        parts.append("Other models provided these analyses in the previous round. "
                     "Consider their arguments but form your own independent judgment.\n")
        for model, view in prior_views.items():
            parts.append(f"### {model}\n{view}\n")

    if round_num >= 2 and evidence_text:
        parts.append(_EVIDENCE_HEADER)
        parts.append(f"{evidence_text}\n")

    if round_num >= 2 and unaddressed_arguments:
        parts.append("## Unaddressed Arguments From Prior Rounds\n")
        parts.append("The following arguments were raised but NOT substantively engaged with. "
                     "You MUST engage with each one — agree, rebut, or refine.\n")
        parts.append(f"{unaddressed_arguments}\n")

    parts.append("\n## Your Analysis\n")
    parts.append("Provide your independent assessment. Structure your response as:\n"
                 "1. Key findings\n"
                 "2. Your position (with confidence: HIGH/MEDIUM/LOW)\n"
                 "3. Key arguments supporting your position\n"
                 "4. Risks or uncertainties\n")

    # Search request appendix — R1 and R2 only (not the final round)
    if not is_last_round:
        parts.append(_SEARCH_REQUEST_SECTION)

    return "\n".join(parts)


@pipeline_stage(
    name="Deliberation Round",
    description="Calls all models for a round in parallel. R1: brief only (4 models). R2: brief + R1 views + evidence + unaddressed args (3 models). R3: final convergence (2 models). Models include search request appendix (0-5 queries) in R1 and R2.",
    stage_type="round",
    order=2,
    provider="r1, reasoner, glm5, kimi (topology narrows 4→3→2)",
    inputs=["brief", "prior_views", "evidence_text", "unaddressed_arguments"],
    outputs=["responses (dict[model, text])", "responded (list)", "failed (list)"],
    prompt="""R1 PROMPT:
You are participating in a multi-model deliberation.
Analyze the following brief independently and thoroughly.

## Brief
{brief}

## Your Analysis
1. Key findings
2. Your position (with confidence: HIGH/MEDIUM/LOW)
3. Key arguments supporting your position
4. Risks or uncertainties

## Search Requests (optional, 0-5)
SEARCH_REQUESTS:
1. [specific, searchable query]
(or NONE)

---
R2+ PROMPT adds:
## Prior Round Views (all models from previous round)
## Web-Verified Evidence (AUTHORITATIVE — outranks model opinions)
## Unaddressed Arguments (You MUST engage with each one)

R3 (final round): no search request section.""",
    logic="All models called in parallel. Failed models excluded. Zero responses = FATAL ESCALATE.",
    failure_mode="Individual model failure: excluded from results. All fail: pipeline stops with ESCALATE.",
    cost="R1: ~$0.40 (4 models) | R2: ~$0.30 (3 models) | R3: ~$0.20 (2 models)",
    stage_id="round",
)
async def execute_round(
    client,
    round_num: int,
    brief: str,
    prior_views: dict[str, str] | None = None,
    evidence_text: str = "",
    unaddressed_arguments: str = "",
    is_last_round: bool = False,
) -> RoundResult:
    """Execute a single deliberation round.

    Calls all models for this round in parallel. Returns a RoundResult
    with successful responses and a list of failed models.
    """
    models = ROUND_TOPOLOGY[round_num]
    prompt = build_round_prompt(
        round_num=round_num,
        brief=brief,
        prior_views=prior_views or {},
        evidence_text=evidence_text,
        unaddressed_arguments=unaddressed_arguments,
        is_last_round=is_last_round,
    )

    # Call all models in parallel
    tasks = {model: client.call(model, prompt) for model in models}
    responses: dict[str, ModelResponse] = {}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    failed = []
    for model, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            responses[model] = ModelResponse(
                model=model, ok=False, text="", elapsed_s=0.0, error=str(result),
            )
            failed.append(model)
        elif not result.ok:
            responses[model] = result
            failed.append(model)
        else:
            responses[model] = result

    return RoundResult(round_num=round_num, responses=responses, failed=failed)

```


### thinker/synthesis.py


```python
"""Synthesis Gate — generates the final deliberation report.

Not an agent — a single LLM call that synthesizes the final round's views
into a dual-format output: JSON (machine-readable) + markdown (human-readable).

The deterministic classification label (CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, etc.)
is appended to the output after the LLM call.
"""
from __future__ import annotations

from thinker.pipeline import pipeline_stage

SYNTHESIS_PROMPT = """You are the synthesis gate for a multi-model deliberation system.

Your job is to write a clear, honest report summarizing what the models concluded.

## Rules
1. You may ONLY summarize and synthesize the views below. DO NOT INVENT NEW ARGUMENTS.
2. If models disagreed, state the disagreement clearly — do not paper over it.
3. If evidence is weak, say so. Do not inflate confidence.
4. Use evidence IDs (E001-E999) when referencing specific facts.

## Brief
{brief}

## Final Round Views (these are the ONLY inputs you may use)
{views}

## Blocker Summary
{blocker_summary}

## Output Format

You MUST produce TWO sections separated by a line containing only "---JSON---".

SECTION 1: Markdown report
# Deliberation Report: [Title]

## TL;DR
[2-3 sentence executive summary]

## Verdict
[Position + confidence + consensus level]

## Consensus Map
### Agreed
[Points all models agreed on]
### Contested
[Points where models diverged — state both sides honestly]

## Key Findings
[Numbered, with evidence citations where available]

## Risk Factors
[Table: Risk | Severity | Mitigation]

---JSON---

SECTION 2: JSON object (fill fields if applicable, use "N/A" if not)
{{
  "title": "...",
  "tldr": "...",
  "verdict": "...",
  "confidence": "high|medium|low",
  "agreed_points": ["...", "..."],
  "contested_points": ["...", "..."],
  "key_findings": ["...", "..."],
  "risk_factors": [{{"risk": "...", "severity": "...", "mitigation": "..."}}],
  "evidence_cited": ["E001", "E002"],
  "unresolved_questions": ["...", "..."]
}}"""


def build_synthesis_prompt(
    brief: str,
    final_views: dict[str, str],
    blocker_summary: dict,
    evidence_text: str = "",
) -> str:
    views_text = "\n\n".join(f"### {m}\n{v}" for m, v in final_views.items())
    blocker_text = "\n".join(f"- {k}: {v}" for k, v in blocker_summary.items()) if blocker_summary else "None"
    prompt = SYNTHESIS_PROMPT.format(
        brief=brief, views=views_text, blocker_summary=blocker_text,
    )
    if evidence_text:
        prompt += (
            "\n\n## Web-Verified Evidence (AUTHORITATIVE)\n\n"
            "The following evidence was retrieved from web sources during deliberation. "
            "Cite evidence IDs when referencing specific facts.\n\n"
            f"{evidence_text}\n"
        )
    return prompt


def parse_synthesis_output(text: str) -> tuple[str, dict]:
    """Split synthesis output into markdown report and JSON object.

    Returns (markdown_report, json_data). If JSON parsing fails,
    json_data is a dict with error info.
    """
    import json

    if "---JSON---" in text:
        parts = text.split("---JSON---", 1)
        markdown = parts[0].strip()
        json_text = parts[1].strip()
    else:
        # LLM didn't follow format — treat whole thing as markdown
        markdown = text.strip()
        json_text = ""

    json_data = {}
    if json_text:
        # Strip markdown code fences if present
        json_text = json_text.strip()
        if json_text.startswith("```"):
            json_text = "\n".join(json_text.split("\n")[1:])
        if json_text.endswith("```"):
            json_text = "\n".join(json_text.split("\n")[:-1])
        try:
            json_data = json.loads(json_text.strip())
        except json.JSONDecodeError:
            json_data = {"parse_error": "Failed to parse JSON section", "raw": json_text[:500]}

    return markdown, json_data


@pipeline_stage(
    name="Synthesis Gate",
    description="Single Sonnet call. Sees ONLY final round views. Produces dual output: markdown (human-readable) + JSON (machine-readable). DO NOT INVENT NEW ARGUMENTS. Deterministic classification label appended after LLM call.",
    stage_type="synthesis",
    order=6,
    provider="sonnet",
    inputs=["brief", "final_views (R3 only)", "blocker_summary", "outcome_class"],
    outputs=["markdown_report (str)", "json_data (dict)"],
    prompt=SYNTHESIS_PROMPT,
    logic="""Rules: ONLY summarize final views. State disagreement honestly. Cite evidence IDs.
Dual output separated by ---JSON--- line.
Classification (CONSENSUS/CLOSED_WITH_ACCEPTED_RISKS/etc.) appended deterministically.""",
    failure_mode="LLM fails: return FAILED status with error details.",
    cost="1 Sonnet call ($0 on Max subscription)",
    stage_id="synthesis",
)
async def run_synthesis(
    client,
    brief: str,
    final_views: dict[str, str],
    blocker_summary: dict,
    outcome_class: str = "",
    evidence_text: str = "",
) -> tuple[str, dict]:
    """Run the Synthesis Gate. Returns (markdown_report, json_data).

    The outcome_class is appended to both outputs after the LLM call.
    """
    prompt = build_synthesis_prompt(brief, final_views, blocker_summary, evidence_text=evidence_text)
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        from thinker.types import BrainError
        raise BrainError("synthesis", f"Synthesis gate LLM call failed: {resp.error}",
                         detail="Cannot produce deliberation report without a working Sonnet call.")

    markdown, json_data = parse_synthesis_output(resp.text)

    # Append deterministic classification
    if outcome_class:
        markdown += f"\n\n---\n**Classification: {outcome_class}**\n"
        json_data["outcome_class"] = outcome_class

    return markdown, json_data

```


### thinker/search.py


```python
"""Search orchestration: model-requested + proactive queries, topic tracking.

Search flow:
1. Parse model search requests from their output appendices (direct, no guessing)
2. Sonnet proactive sweep for claims models didn't ask about
3. Deduplicate all queries
4. Execute via Playwright (primary) or Sonar (repeat topic) or Brave (fallback)
5. Keep top 10 results in Google ranking order (trust Google's authority ranking)
6. Search after R1 and R2 only (not R3)
7. Topic tracker persists across rounds — repeat topic triggers Sonar
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Callable, Awaitable, Optional

from thinker.pipeline import pipeline_stage
from thinker.types import Confidence, EvidenceItem, SearchResult


class SearchPhase(Enum):
    R1_R2 = "R1-R2"
    R2_R3 = "R2-R3"


PROACTIVE_PROMPT = """Scan these model outputs for verifiable claims that the models did NOT request to be searched.
Look for specific numbers, dates, versions, events, statistics, or regulatory references that should be fact-checked.

Model outputs:
{outputs}

Model-requested searches (ALREADY QUEUED — do not duplicate):
{already_queued}

Generate search queries ONLY for claims the models missed. If the models already covered everything, return NONE.

Format:
QUERIES:
1. [search query]
2. ...
(or NONE if nothing additional needed)"""


def parse_model_search_requests(model_output: str) -> list[str]:
    """Parse search requests from a model's output appendix.

    Models append a SEARCH_REQUESTS section with 0-5 queries.
    """
    queries = []
    in_section = False
    for line in model_output.split("\n"):
        line = line.strip()
        if "SEARCH_REQUESTS:" in line or "SEARCH REQUESTS:" in line:
            in_section = True
            continue
        if in_section:
            if line.upper() == "NONE" or line == "":
                break
            match = re.match(r"^\d+\.\s+(.+)", line)
            if match:
                queries.append(match.group(1).strip())
            elif line.startswith("- "):
                queries.append(line[2:].strip())
            else:
                if queries:
                    break
    # Strip surrounding quotes — models often wrap queries in "..." which
    # causes exact-match search returning 0 results
    return [q.strip('"\'*_ ') for q in queries[:5]]


class SearchOrchestrator:
    """Orchestrates all search activities between rounds."""

    def __init__(
        self,
        llm_client,
        search_fn: Callable[..., Awaitable[list[SearchResult]]],
        sonar_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        max_results: int = 10,
    ):
        self._llm = llm_client
        self._search = search_fn
        self._sonar = sonar_fn
        self._searched_topics: set[str] = set()
        self._max_results = max_results

    def mark_topic_searched(self, topic: str):
        self._searched_topics.add(topic.lower().strip())

    def _is_repeat_topic(self, query: str) -> bool:
        query_lower = query.lower().strip()
        for topic in self._searched_topics:
            topic_words = set(topic.split())
            query_words = set(query_lower.split())
            if len(topic_words & query_words) >= max(1, len(topic_words) // 2):
                return True
        return False

    def collect_model_requests(self, model_outputs: dict[str, str]) -> list[str]:
        """Parse search requests directly from model output appendices."""
        all_queries = []
        for model, output in model_outputs.items():
            queries = parse_model_search_requests(output)
            all_queries.extend(queries)
        return all_queries

    async def generate_proactive_queries(
        self, model_outputs: dict[str, str], already_queued: list[str],
    ) -> list[str]:
        """Sonnet sweep for claims models didn't ask to be searched."""
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        queued_text = "\n".join(f"- {q}" for q in already_queued) if already_queued else "NONE"
        resp = await self._llm.call(
            "sonnet",
            PROACTIVE_PROMPT.format(outputs=combined, already_queued=queued_text),
        )
        if not resp.ok:
            from thinker.types import BrainError
            raise BrainError("search", f"Proactive query generation failed: {resp.error}",
                             detail="Sonnet could not scan model outputs for unsearched claims.")
        return self._parse_queries(resp.text)

    def deduplicate(self, queries: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for q in queries:
            normalized = " ".join(q.lower().split())
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(q)
        return deduped

    async def execute_query(
        self, query: str, phase: SearchPhase,
    ) -> list[SearchResult]:
        """Execute a single search query. Results in ranking order (top 10)."""
        query = query.strip('"\'*_ ')  # Strip quotes and markdown that cause exact-match failures
        if self._is_repeat_topic(query) and self._sonar:
            results = await self._sonar(query)
        else:
            results = await self._search(query)
        self.mark_topic_searched(query)
        return results[:self._max_results]

    def _parse_queries(self, text: str) -> list[str]:
        for line in text.split("\n"):
            line = line.strip()
            if line.upper() == "NONE":
                return []
            if line:
                break
        queries = []
        for line in text.split("\n"):
            line = line.strip()
            match = re.match(r"^\d+\.\s+(.+)", line)
            if match:
                queries.append(match.group(1).strip())
        return queries


@pipeline_stage(
    name="Search Phase",
    description="Runs after R1 and R2 only. Collects model-requested searches from appendices (0-5 per model, no LLM needed). Sonnet proactive sweep for claims models missed. Dedup. Execute via Brave (primary) or Sonar (repeat topic). Top 10 results in search ranking order. Trust search engine ranking — no re-ranking.",
    stage_type="search",
    order=5,
    provider="brave ($0.01/query) + sonar (repeat topics) + sonnet (proactive sweep)",
    inputs=["model_outputs", "topic_tracker_state"],
    outputs=["evidence_items (added to ledger)", "queries_executed (int)"],
    prompt=PROACTIVE_PROMPT,
    logic="""1. Parse SEARCH_REQUESTS from model output appendices (direct, no LLM).
2. Sonnet proactive sweep for uncovered claims (1 LLM call).
3. Deduplicate (case-insensitive).
4. First-time topic → Brave. Repeat topic → Sonar Pro.
5. Results kept in search ranking order. Max 10 items in evidence ledger.""",
    failure_mode="Search fails: empty results, deliberation continues without evidence.",
    cost="~$0.05 per search phase (Brave) + 1 Sonnet call ($0)",
    stage_id="search",
)
def _register_search(): pass

```


### thinker/evidence.py


```python
"""Evidence Ledger — stores, deduplicates, scores, and formats evidence.

Evidence items are kept in insertion order (search engine's ranking order).
V8-F3 adds relevance scoring: under cap pressure, the lowest-scored item
is evicted instead of blindly rejecting new items.
Cap at max_items. Within the same score tier, insertion order is preserved.
"""
from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import urlparse

from thinker.types import Confidence, EvidenceItem
from thinker.tools.cross_domain import is_cross_domain

# Authoritative domains that get a score boost
_AUTHORITY_DOMAINS = {
    "nvd.nist.gov", "cve.mitre.org", "owasp.org", "sec.gov",
    "who.int", "cdc.gov", "fda.gov", "nih.gov",
    "ieee.org", "acm.org", "arxiv.org",
    "reuters.com", "bloomberg.com", "ft.com",
    "github.com", "docs.python.org", "docs.microsoft.com",
}


def score_evidence(item: EvidenceItem, brief_keywords: set[str]) -> float:
    """Score evidence item for relevance.

    Factors:
    - Keyword overlap with brief (0-5 points, 1 per keyword match, capped)
    - Source authority (0 or 2 points for known authoritative domains)
    - Base score of 1.0 so all items have positive score
    """
    score = 1.0

    # Keyword overlap
    text_lower = (item.topic + " " + item.fact).lower()
    kw_hits = 0
    for kw in brief_keywords:
        if kw.lower() in text_lower:
            kw_hits += 1
    score += min(kw_hits, 5)

    # Source authority
    try:
        domain = urlparse(item.url).netloc.lower()
        if any(auth in domain for auth in _AUTHORITY_DOMAINS):
            score += 2.0
    except Exception:
        pass

    return score


class EvidenceLedger:
    """Manages evidence items with dedup, cross-domain filtering, scoring, and cap enforcement.

    Items are kept in search engine ranking order (insertion order).
    Under cap pressure, the lowest-scored item is evicted if the new
    item scores higher. Otherwise the new item is rejected.
    """

    def __init__(self, max_items: int = 10, brief_domain: Optional[str] = None,
                 brief_keywords: Optional[set[str]] = None):
        self.items: list[EvidenceItem] = []
        self.max_items = max_items
        self.brief_domain = brief_domain
        self.brief_keywords: set[str] = brief_keywords or set()
        self._content_hashes: set[str] = set()
        self._seen_urls: set[str] = set()
        self.cross_domain_rejections: int = 0
        self.contradictions: list = []

    def add(self, item: EvidenceItem) -> bool:
        """Add evidence item. Returns False if rejected.

        Rejection reasons: duplicate content, duplicate URL, cross-domain,
        or lower-scored than all existing items when ledger is full.
        Under cap pressure: if the new item scores higher than the
        lowest-scored existing item, evict that item and insert the new one.
        """
        # Cross-domain filter
        if self.brief_domain and is_cross_domain(item.fact + " " + item.topic, self.brief_domain):
            self.cross_domain_rejections += 1
            return False

        # Content dedup
        content_hash = hashlib.sha256(item.fact.encode()).hexdigest()[:16]
        if content_hash in self._content_hashes:
            return False

        # URL dedup
        if item.url in self._seen_urls:
            return False

        # Score the new item
        item.score = score_evidence(item, self.brief_keywords)

        # Cap check with eviction
        if len(self.items) >= self.max_items:
            min_item = min(self.items, key=lambda e: e.score)
            if item.score > min_item.score:
                # Evict the lowest-scored item
                self._content_hashes.discard(min_item.content_hash)
                self._seen_urls.discard(min_item.url)
                self.items.remove(min_item)
            else:
                return False

        self._content_hashes.add(content_hash)
        self._seen_urls.add(item.url)
        item.content_hash = content_hash
        self.items.append(item)

        # Check for contradictions with existing items
        from thinker.tools.contradiction import detect_contradiction
        for existing in self.items[:-1]:
            ctr = detect_contradiction(existing, item)
            if ctr:
                self.contradictions.append(ctr)

        return True

    def format_for_prompt(self) -> str:
        """Format all evidence for injection into a model prompt."""
        if not self.items:
            return ""
        lines = []
        for i, item in enumerate(self.items, 1):
            lines.append(
                f"{{{item.evidence_id}}} {item.fact}\n"
                f"Source: {item.url}\n"
            )
        lines.append(
            "Any specific number, percentage, or dollar figure in your analysis "
            "MUST cite an evidence ID (E001-E999) from above."
        )
        return "\n".join(lines)

```


### thinker/evidence_extractor.py


```python
"""LLM-based evidence extraction from fetched page content.

V8-F5 (Spec Section 6): After fetching full page content, one Sonnet call
per page extracts specific facts, numbers, dates, and regulatory references.
Output: structured fact items for the evidence ledger.
"""
from __future__ import annotations

import re

from thinker.pipeline import pipeline_stage

EXTRACTION_PROMPT = """Extract specific, verifiable facts from this web page content.

URL: {url}
Content:
{content}

Extract ONLY concrete facts — specific numbers, dates, percentages, versions,
regulatory references, statistics, named entities. Skip opinions, commentary,
and vague claims.

Format each fact as:
FACT-N: [the specific fact]

If the content has no extractable facts, respond with: NONE"""


def parse_extracted_facts(text: str) -> list[dict]:
    """Parse extracted facts from Sonnet's response.

    Returns list of {"fact": str} dicts.
    """
    if not text or text.strip().upper() == "NONE":
        return []

    facts = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try FACT-N: format (handles bold markdown like **FACT-1:**)
        match = re.match(r"[*]*FACT-?\d+[*]*:?[*]*\s+(.+)", line)
        if match:
            facts.append({"fact": match.group(1).strip()})
            continue

        # Try numbered format: 1. fact text
        match = re.match(r"^\d+[.)]\s+(.+)", line)
        if match:
            facts.append({"fact": match.group(1).strip()})
            continue

        # Try bullet format: - FACT-N: text
        match = re.match(r"^[-*]\s+(?:FACT-?\d+:?\s+)?(.+)", line)
        if match:
            fact_text = match.group(1).strip()
            if len(fact_text) > 10:  # Skip very short fragments
                facts.append({"fact": fact_text})

    return facts


async def extract_evidence_from_page(
    llm_client, url: str, content: str, max_content: int = 30_000,
) -> list[dict]:
    """Extract structured facts from a page's content using Sonnet.

    Returns list of {"fact": str} dicts.
    Raises BrainError if the LLM call fails.
    """
    from thinker.types import BrainError

    if not content:
        return []

    truncated = content[:max_content]
    prompt = EXTRACTION_PROMPT.format(url=url, content=truncated)
    resp = await llm_client.call("sonnet", prompt)

    if not resp.ok:
        raise BrainError(
            "evidence_extraction",
            f"Evidence extraction failed for {url[:60]}: {resp.error}",
            detail="Sonnet could not extract facts from fetched page content.",
        )

    return parse_extracted_facts(resp.text)


@pipeline_stage(
    name="Evidence Extractor",
    description="LLM-based fact extraction from fetched page content. One Sonnet call per page extracts specific numbers, dates, percentages, versions, regulatory references, and statistics. Replaces raw snippet injection with curated, structured facts.",
    stage_type="search",
    order=5.2,
    provider="sonnet (1 call per page, $0 on Max subscription)",
    inputs=["url", "full_content (from page fetch)"],
    outputs=["facts (list[dict]) — each with 'fact' key"],
    prompt=EXTRACTION_PROMPT,
    logic="""1. Truncate page content to 30k chars
2. Sonnet extracts FACT-N: lines (concrete, verifiable facts only)
3. Parser handles FACT-N:, numbered (1.), and bullet (-) formats
4. NONE response = no extractable facts
5. Short fragments (<10 chars) skipped""",
    failure_mode="BrainError if Sonnet call fails (zero tolerance). Empty content returns empty list.",
    cost="1 Sonnet call per page ($0 on Max subscription)",
    stage_id="evidence_extractor",
)
def _register_evidence_extractor(): pass

```


### thinker/page_fetch.py


```python
"""Full page content fetch — retrieves and strips HTML from search result URLs.

V8-F4 (Spec Section 6): After search returns URLs, fetch top N pages via httpx.
Extract page text (strip HTML tags). Truncate to max_chars.
Store in SearchResult.full_content.

Also fixes V8-B1: Bing returns URLs without titles/snippets — fetching
the page provides the actual content.
"""
from __future__ import annotations

import re
from html import unescape

import httpx

from thinker.pipeline import pipeline_stage
from thinker.types import SearchResult


def strip_html(html: str) -> str:
    """Strip HTML tags, scripts, styles, and decode entities.

    Returns clean text suitable for evidence extraction.
    """
    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode HTML entities
    text = unescape(text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def truncate_content(text: str, max_chars: int = 50_000) -> str:
    """Truncate text to max_chars."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


async def fetch_page_content(
    url: str, timeout: float = 15.0, max_chars: int = 50_000,
) -> str:
    """Fetch a URL and return stripped, truncated text content.

    Returns empty string on any error (timeout, HTTP error, etc.).
    Does not raise — errors are expected for some URLs.
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ThinkerV8/1.0)"},
    ) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
            text = strip_html(html)
            return truncate_content(text, max_chars)
        except Exception:
            return ""


async def fetch_pages_for_results(
    results: list[SearchResult], max_pages: int = 5, max_chars: int = 50_000,
) -> None:
    """Fetch full page content for the top N search results in-place.

    Populates SearchResult.full_content for each result.
    Skips results that already have full_content.
    """
    for sr in results[:max_pages]:
        if sr.full_content:
            continue
        content = await fetch_page_content(sr.url, max_chars=max_chars)
        if content:
            sr.full_content = content
            # Also fill in title if missing (B1 fix for Bing)
            if not sr.title:
                # Use first sentence as title approximation
                sr.title = content[:100].split('.')[0].strip()[:200]


@pipeline_stage(
    name="Page Fetch",
    description="After search returns URLs, fetches top N pages via httpx. Strips HTML (scripts, styles, tags), decodes entities, truncates to 50k chars. Populates SearchResult.full_content. Also backfills empty titles from page text (fixes Bing B1).",
    stage_type="search",
    order=5.1,
    provider="httpx (async HTTP, $0)",
    inputs=["search_results (list[SearchResult])", "max_pages (default 5)"],
    outputs=["SearchResult.full_content populated in-place", "SearchResult.title backfilled if empty"],
    logic="""For each of top N results (default 5):
  1. Skip if full_content already set
  2. httpx GET with 15s timeout, follow redirects
  3. Strip <script>, <style>, HTML tags
  4. Decode HTML entities, collapse whitespace
  5. Truncate to 50k chars
  6. If title empty, use first sentence of content
Returns empty string on any error — does not raise.""",
    failure_mode="Individual page errors return empty string. Pipeline continues.",
    cost="$0 (direct HTTP fetch)",
    stage_id="page_fetch",
)
def _register_page_fetch(): pass

```


### thinker/invariant.py


```python
"""Invariant Validator — structural integrity checks before proof finalization.

V8-F6 (Spec Section 4): Runs after Gate 2. Checks positions exist for every
round, all rounds have responses, evidence IDs are sequential, no orphaned
BLK/CTR references. Returns violations with severity (WARN or ERROR).
"""
from __future__ import annotations

from thinker.evidence import EvidenceLedger
from thinker.pipeline import pipeline_stage
from thinker.tools.blocker import BlockerLedger
from thinker.types import Position


def validate_invariants(
    positions_by_round: dict[int, dict[str, Position]],
    round_responded: dict[int, list[str]],
    evidence: EvidenceLedger,
    blocker_ledger: BlockerLedger,
    rounds_completed: int,
) -> list[dict]:
    """Run all invariant checks. Returns list of violation dicts.

    Each violation: {"id": str, "severity": "WARN"|"ERROR", "detail": str}
    """
    violations: list[dict] = []

    # 1. Positions extracted for every completed round
    for rnd in range(1, rounds_completed + 1):
        if rnd not in positions_by_round or not positions_by_round[rnd]:
            violations.append({
                "id": "INV-POS-MISSING",
                "severity": "ERROR",
                "detail": f"No positions extracted for round {rnd}",
            })

    # 2. All rounds have at least one response
    for rnd in range(1, rounds_completed + 1):
        responded = round_responded.get(rnd, [])
        if not responded:
            violations.append({
                "id": "INV-ROUND-EMPTY",
                "severity": "ERROR",
                "detail": f"Round {rnd} has no model responses",
            })

    # 3. Evidence IDs are sequential (E001, E002, ...)
    if evidence.items:
        for i, item in enumerate(evidence.items):
            expected_id = f"E{i + 1:03d}"
            if item.evidence_id != expected_id:
                violations.append({
                    "id": "INV-EVIDENCE-SEQ",
                    "severity": "WARN",
                    "detail": f"Evidence ID gap: expected {expected_id}, got {item.evidence_id}",
                })
                break  # One violation is enough to flag the issue

    # 4. No orphaned blocker references (detected_round within completed rounds)
    for b in blocker_ledger.blockers:
        if b.detected_round > rounds_completed:
            violations.append({
                "id": "INV-BLK-ORPHAN",
                "severity": "WARN",
                "detail": (
                    f"Blocker {b.blocker_id} references round {b.detected_round} "
                    f"but only {rounds_completed} rounds completed"
                ),
            })

    # 5. No orphaned contradiction evidence references
    evidence_ids = {item.evidence_id for item in evidence.items}
    for ctr in evidence.contradictions:
        for eid in ctr.evidence_ids:
            if eid not in evidence_ids:
                violations.append({
                    "id": "INV-CTR-ORPHAN",
                    "severity": "WARN",
                    "detail": (
                        f"Contradiction {ctr.contradiction_id} references "
                        f"{eid} which is not in the evidence ledger"
                    ),
                })

    return violations


@pipeline_stage(
    name="Invariant Validator",
    description="Structural integrity checks after Gate 2. Verifies positions exist for every round, all rounds have responses, evidence IDs are sequential, no orphaned blocker or contradiction references. Returns violations with WARN/ERROR severity.",
    stage_type="deterministic",
    order=8,
    provider="deterministic (no LLM)",
    inputs=["positions_by_round", "round_responded", "evidence", "blocker_ledger", "rounds_completed"],
    outputs=["violations (list[dict]) — each with id, severity, detail"],
    logic="""1. For each round 1..N: positions extracted? If not → INV-POS-MISSING (ERROR)
2. For each round 1..N: at least one response? If not → INV-ROUND-EMPTY (ERROR)
3. Evidence IDs sequential (E001, E002, ...)? If gap → INV-EVIDENCE-SEQ (WARN)
4. Blocker detected_round <= rounds_completed? If not → INV-BLK-ORPHAN (WARN)
5. Contradiction evidence_ids all exist in ledger? If not → INV-CTR-ORPHAN (WARN)""",
    failure_mode="Cannot fail — deterministic computation.",
    cost="$0 (no LLM call)",
    stage_id="invariant_validator",
)
def _register_invariant_validator(): pass

```


### thinker/residue.py


```python
"""Post-synthesis residue verification.

V8-F1 (DoD D7): After synthesis, scan the report text to verify it
mentions all structural findings — blocker IDs, contradiction IDs,
and unaddressed argument IDs. This is a narrative completeness check,
not truth verification.
"""
from __future__ import annotations

from thinker.pipeline import pipeline_stage
from thinker.types import Argument, Blocker, Contradiction


def check_synthesis_residue(
    report: str,
    blockers: list[Blocker],
    contradictions: list[Contradiction],
    unaddressed_arguments: list[Argument],
) -> list[dict]:
    """Scan synthesis report for structural finding references.

    Returns list of omission dicts:
    {"type": "blocker"|"contradiction"|"argument", "id": str}

    If >30% of total structural findings are omitted, each omission
    gets threshold_violation=True.
    """
    omissions: list[dict] = []
    total_items = len(blockers) + len(contradictions) + len(unaddressed_arguments)

    # Check blocker IDs
    for b in blockers:
        if b.blocker_id not in report:
            omissions.append({"type": "blocker", "id": b.blocker_id})

    # Check contradiction IDs
    for c in contradictions:
        if c.contradiction_id not in report:
            omissions.append({"type": "contradiction", "id": c.contradiction_id})

    # Check unaddressed argument IDs
    for a in unaddressed_arguments:
        if a.argument_id not in report:
            omissions.append({"type": "argument", "id": a.argument_id})

    # Threshold check: >30% omitted
    threshold_violated = (
        total_items > 0 and len(omissions) / total_items > 0.30
    )
    if threshold_violated:
        for o in omissions:
            o["threshold_violation"] = True

    return omissions


@pipeline_stage(
    name="Residue Verification",
    description="Post-synthesis narrative completeness check. Scans the synthesis report text for BLK IDs, CTR IDs, and unaddressed argument IDs. If >30% of structural findings are omitted, flags a threshold violation. This is NOT truth verification — it checks whether the synthesis mentioned the findings, not whether it got them right.",
    stage_type="deterministic",
    order=9,
    provider="deterministic (no LLM)",
    inputs=["synthesis report text", "blockers", "contradictions", "unaddressed_arguments"],
    outputs=["omissions (list[dict]) — type, id, threshold_violation flag"],
    logic="""For each BLK ID: is it mentioned in the report text? If not → omission.
For each CTR ID: is it mentioned? If not → omission.
For each unaddressed argument ID: is it mentioned? If not → omission.
If omissions / total_items > 0.30 → threshold_violation=True on all omissions.""",
    failure_mode="Cannot fail — string matching only.",
    cost="$0 (no LLM call)",
    stage_id="residue_verification",
)
def _register_residue_verification(): pass

```


### thinker/proof.py


```python
"""Proof.json builder — the machine-readable audit trail.

Schema 2.0, compatible with V7 proof format. Every position, every evidence
item, every disagreement, every decision is recorded here.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from thinker.types import Outcome, Position
from thinker.tools.blocker import BlockerLedger


class ProofBuilder:
    """Incrementally builds proof.json throughout a Brain run."""

    def __init__(self, run_id: str, brief: str, rounds_requested: int):
        self._run_id = run_id
        self._brief = brief
        self._rounds_requested = rounds_requested
        self._timestamp = datetime.now(timezone.utc).isoformat()
        self._rounds: dict[str, dict] = {}
        self._positions: dict[str, dict] = {}
        self._position_changes: list[dict] = []
        self._outcome: dict = {}
        self._final_status: Optional[str] = None
        self._synthesis_status: Optional[str] = None
        self._evidence_items: int = 0
        self._research_phases: list[dict] = []
        self._blocker_ledger: Optional[BlockerLedger] = None
        self._invariant_violations: list[dict] = []
        self._acceptance_status: Optional[str] = None
        self._synthesis_residue_omissions: list[dict] = []
        self._search_decision: Optional[dict] = None
        self._v3_outcome_class: str = "not applicable"

    def record_round(self, round_num: int, responded: list[str], failed: list[str]):
        self._rounds[str(round_num)] = {
            "responded": responded,
            "failed": failed,
        }

    def record_positions(self, round_num: int, positions: dict[str, Position]):
        round_positions = {}
        for model, pos in positions.items():
            round_positions[model] = {
                "model": pos.model,
                "kind": pos.kind,
                "primary_option": pos.primary_option,
                "components": pos.components,
                "confidence": pos.confidence.value,
                "qualifier": pos.qualifier,
            }
        self._positions[str(round_num)] = round_positions

    def record_position_changes(self, changes: list[dict]):
        self._position_changes.extend(changes)

    def record_research_phase(self, phase: str, method: str,
                              queries: int, items_admitted: int):
        self._research_phases.append({
            "phase": phase, "method": method,
            "queries_attempted": queries, "items_admitted": items_admitted,
        })

    def set_evidence_count(self, count: int):
        self._evidence_items = count

    def set_outcome(self, outcome: Outcome, agreement_ratio: float,
                    outcome_class: str):
        self._outcome = {
            "outcome_class": outcome_class,
            "agreement_ratio": agreement_ratio,
            "verdict": outcome.value,
        }
        self._v3_outcome_class = outcome_class

    def set_final_status(self, status: str):
        self._final_status = status

    def set_synthesis_status(self, status: str):
        self._synthesis_status = status

    def set_blocker_ledger(self, ledger: BlockerLedger):
        self._blocker_ledger = ledger

    def compute_acceptance_status(self):
        """Compute acceptance_status from run metrics.

        ACCEPTED: clean run — DECIDE outcome, CONSENSUS class, no violations.
        ACCEPTED_WITH_WARNINGS: anything else (non-fatal issues).
        Never REJECTED — if fatal, BrainError stops the pipeline before proof.
        """
        from thinker.types import AcceptanceStatus
        is_clean = (
            self._outcome.get("verdict") == "DECIDE"
            and self._outcome.get("outcome_class") == "CONSENSUS"
            and len(self._invariant_violations) == 0
        )
        if is_clean:
            self._acceptance_status = AcceptanceStatus.ACCEPTED.value
        else:
            self._acceptance_status = AcceptanceStatus.ACCEPTED_WITH_WARNINGS.value

    def set_synthesis_residue(self, omissions: list[dict]):
        self._synthesis_residue_omissions = omissions

    def set_search_decision(self, source: str, value: bool, reasoning: str,
                            gate1_recommended: Optional[bool] = None,
                            gate1_search_reasoning: Optional[str] = None):
        """Record who decided search on/off and why.

        source: "gate1" | "cli_override"
        value: True (search on) or False (search off)
        reasoning: Why this decision was made
        gate1_recommended: Gate 1's original recommendation (if overridden)
        gate1_search_reasoning: Gate 1's reasoning for its recommendation (if overridden)
        """
        self._search_decision = {
            "source": source,
            "value": value,
            "reasoning": reasoning,
        }
        if source == "cli_override" and gate1_recommended is not None:
            self._search_decision["gate1_recommended"] = gate1_recommended
            if gate1_search_reasoning:
                self._search_decision["gate1_search_reasoning"] = gate1_search_reasoning

    def add_violation(self, violation_id: str, severity: str, detail: str):
        self._invariant_violations.append({
            "id": violation_id, "severity": severity, "detail": detail,
        })

    def build(self) -> dict:
        """Build the complete proof.json dict."""
        blocker_list = []
        blocker_summary = {"total_blockers": 0, "by_status": {}, "by_kind": {}, "open_at_end": 0}
        if self._blocker_ledger:
            for b in self._blocker_ledger.blockers:
                blocker_list.append({
                    "blocker_id": b.blocker_id,
                    "kind": b.kind.value,
                    "source_dimension": b.source,
                    "detected_round": b.detected_round,
                    "status": b.status.value,
                    "status_history": b.status_history,
                    "models_involved": b.models_involved,
                    "evidence_ids": b.evidence_ids,
                    "detail": b.detail,
                    "resolution_note": b.resolution_note,
                })
            blocker_summary = self._blocker_ledger.summary()

        return {
            "proof_schema_version": "2.0",
            "run_id": self._run_id,
            "timestamp": self._timestamp,
            "protocol_version": "v8",
            "rounds_requested": self._rounds_requested,
            "final_status": self._final_status,
            "synthesis_status": self._synthesis_status,
            "acceptance_status": self._acceptance_status,
            "search_decision": self._search_decision,
            "v3_outcome_class": self._v3_outcome_class,
            "rounds": self._rounds,
            "evidence_items": self._evidence_items,
            "research_phases": self._research_phases,
            "controller_outcome": self._outcome,
            "model_positions_by_round": self._positions,
            "position_changes": self._position_changes,
            "blocker_ledger": blocker_list,
            "blocker_summary": blocker_summary,
            "invariant_violations": self._invariant_violations,
            "synthesis_residue_omissions": self._synthesis_residue_omissions,
        }

```


### thinker/checkpoint.py


```python
"""Checkpoint system for step-by-step pipeline debugging.

Usage:
  # Run up to a specific stage, save state, exit:
  python -m thinker.brain --brief b1.md --stop-after gate1

  # Inspect the checkpoint:
  python -m thinker.checkpoint output/checkpoint.json

  # Resume from checkpoint:
  python -m thinker.brain --resume output/checkpoint.json --stop-after r1

  # Resume and run to completion:
  python -m thinker.brain --resume output/checkpoint.json

Stage IDs for --stop-after:
  gate1, r1, track1, search1, r2, track2, search2, r3, track3, synthesis, gate2
"""
from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

CHECKPOINT_VERSION = "1.0"


@dataclass
class PipelineState:
    """Serializable pipeline state for checkpointing."""
    checkpoint_version: str = CHECKPOINT_VERSION
    brief: str = ""
    rounds: int = 3
    run_id: str = ""
    current_stage: str = ""
    completed_stages: list[str] = field(default_factory=list)

    # Gate 1
    gate1_passed: bool = False
    gate1_reasoning: str = ""
    gate1_questions: list[str] = field(default_factory=list)
    gate1_search_recommended: bool = True
    gate1_search_reasoning: str = ""

    # Round outputs
    round_texts: dict[str, dict[str, str]] = field(default_factory=dict)  # {round_num: {model: text}}
    round_responded: dict[str, list[str]] = field(default_factory=dict)
    round_failed: dict[str, list[str]] = field(default_factory=dict)

    # Arguments
    arguments_by_round: dict[str, list[dict]] = field(default_factory=dict)
    unaddressed_text: str = ""
    all_unaddressed: list[dict] = field(default_factory=list)

    # Positions
    positions_by_round: dict[str, dict[str, dict]] = field(default_factory=dict)
    position_changes: list[dict] = field(default_factory=list)

    # Evidence
    evidence_items: list[dict] = field(default_factory=list)
    evidence_count: int = 0

    # Search
    search_queries: dict[str, list[str]] = field(default_factory=dict)
    search_results: dict[str, int] = field(default_factory=dict)

    # Classification
    agreement_ratio: float = 0.0
    outcome_class: str = ""

    # Synthesis
    report: str = ""
    report_json: dict = field(default_factory=dict)

    # Gate 2
    outcome: str = ""

    def save(self, path: Path):
        path.write_text(json.dumps(asdict(self), indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        data = json.loads(path.read_text(encoding="utf-8"))
        saved_version = data.get("checkpoint_version", "0.0")
        if saved_version != CHECKPOINT_VERSION:
            raise ValueError(
                f"Checkpoint version mismatch: file has {saved_version}, "
                f"code expects {CHECKPOINT_VERSION}. "
                f"Delete the checkpoint and re-run from scratch."
            )
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# Valid stage IDs in pipeline order
STAGE_ORDER = [
    "gate1",
    "r1", "track1", "search1",
    "r2", "track2", "search2",
    "r3", "track3",
    "synthesis", "gate2",
]


def should_stop(current_stage: str, stop_after: Optional[str]) -> bool:
    """Check if we should stop after the current stage."""
    if not stop_after:
        return False
    if current_stage == stop_after:
        return True
    return False


def print_checkpoint(path: str):
    """Pretty-print a checkpoint file for inspection."""
    state = PipelineState.load(Path(path))
    print(f"\n{'='*60}")
    print(f"  CHECKPOINT: {path}")
    print(f"{'='*60}")
    print(f"  Run ID:     {state.run_id}")
    print(f"  Brief:      {len(state.brief)} chars")
    print(f"  Stage:      {state.current_stage}")
    print(f"  Completed:  {' → '.join(state.completed_stages)}")
    print()

    if "gate1" in state.completed_stages:
        print(f"  Gate 1:     {'PASS' if state.gate1_passed else 'NEED_MORE'}")
        print(f"  Reasoning:  {state.gate1_reasoning[:150]}...")
        print()

    for rnd in ["1", "2", "3"]:
        if rnd in state.round_responded:
            responded = state.round_responded[rnd]
            failed = state.round_failed.get(rnd, [])
            print(f"  R{rnd}: responded={responded}, failed={failed}")
            # Show positions if available
            if rnd in state.positions_by_round:
                for m, p in state.positions_by_round[rnd].items():
                    print(f"    {m}: {p.get('option', '?')} [{p.get('confidence', '?')}]")
            # Show args
            if rnd in state.arguments_by_round:
                n = len(state.arguments_by_round[rnd])
                print(f"    Arguments: {n}")
            print()

    if state.search_results:
        for phase, count in state.search_results.items():
            print(f"  Search {phase}: {state.search_queries.get(phase, ['?'])} → {count} evidence")
        print()

    if state.outcome_class:
        print(f"  Agreement:  {state.agreement_ratio:.2f}")
        print(f"  Class:      {state.outcome_class}")
        print(f"  Outcome:    {state.outcome}")
        print()

    if state.report:
        print(f"  Report:     {len(state.report)} chars")
    print(f"{'='*60}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print_checkpoint(sys.argv[1])
    else:
        print("Usage: python -m thinker.checkpoint <checkpoint.json>")
        print(f"\nValid stage IDs for --stop-after: {', '.join(STAGE_ORDER)}")

```


### thinker/argument_tracker.py


```python
"""Argument Tracker — the core V8 innovation.

V8 spec Section 4, Argument Tracker:
After each round, one Sonnet call extracts all distinct arguments. Another
Sonnet call compares them with the next round's outputs to identify which
arguments were addressed, mentioned in passing, or ignored. Unaddressed
arguments are explicitly re-injected into the next round's prompt.

This replaces the Minority Archive, Acknowledgment Scanner, and all
keyword-matching machinery from V7.
"""
from __future__ import annotations

import re

from thinker.pipeline import pipeline_stage
from thinker.types import Argument, ArgumentStatus


EXTRACT_PROMPT = """Read the following model outputs from round {round_num} of a multi-model deliberation.
Extract every distinct argument made by any model. An argument is a specific claim,
reasoning step, evidence interpretation, or position.

Model outputs:
{outputs}

List each argument as:
ARG-N: [model_name] argument text

Be exhaustive. Include ALL arguments, even minor ones. Do not merge arguments
from different models — track each separately."""

COMPARE_PROMPT = """Here are the arguments from round {prev_round}:
{arguments}

Here are the model outputs from round {curr_round}:
{outputs}

For each argument, classify it as:
- ADDRESSED: The argument was directly engaged with (agreed, rebutted, or refined with reasoning)
- MENTIONED: The argument was referenced but not substantively engaged with
- IGNORED: The argument does not appear in any model's output at all

Be strict. "Mentioned" means the model acknowledged the point but didn't reason about it.
"Addressed" requires genuine engagement — agreement with new reasoning, or a specific rebuttal.

Respond as:
ARG-N: ADDRESSED | MENTIONED | IGNORED"""


def parse_arguments(text: str, round_num: int) -> list[Argument]:
    """Parse extracted arguments from Sonnet's response.

    Handles multiple formats Sonnet may use:
      ARG-1: [r1] argument text
      ARG-1: r1 - argument text
      ARG-1: **r1** argument text
    """
    args = []
    for line in text.strip().split("\n"):
        line = line.strip()
        # Try bracket format first: ARG-1: [model] text
        match = re.match(r"(ARG-\d+):\s+\[(\w+)\]\s+(.+)", line)
        if not match:
            # Try dash format: ARG-1: model - text
            match = re.match(r"(ARG-\d+):\s+[*]*(\w+)[*]*\s*[-–—]\s*(.+)", line)
        if not match:
            # Try bare format: ARG-1: model text (model is first word)
            match = re.match(r"(ARG-\d+):\s+[*]*(\w+)[*]*\s+(.+)", line)
        if match:
            model = match.group(2).lower()
            # Skip non-model words
            if model in ("the", "this", "that", "both", "all", "note"):
                continue
            # Prefix ARG-ID with round number to prevent cross-round collisions
            # LLM outputs ARG-1..ARG-N each round; R1-ARG-1 != R3-ARG-1
            raw_id = match.group(1)
            unique_id = f"R{round_num}-{raw_id}"
            args.append(Argument(
                argument_id=unique_id,
                round_num=round_num,
                model=model,
                text=match.group(3).strip(),
            ))
    return args


def parse_comparison(text: str, prev_round: int = 0) -> dict[str, ArgumentStatus]:
    """Parse argument comparison from Sonnet's response.

    Handles both prefixed (R1-ARG-1) and unprefixed (ARG-1) IDs.
    When unprefixed, adds the R{prev_round} prefix to match stored IDs.
    """
    statuses: dict[str, ArgumentStatus] = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        # Try prefixed format first: R1-ARG-1: ADDRESSED
        match = re.match(r"(R\d+-ARG-\d+):\s+(ADDRESSED|MENTIONED|IGNORED)", line)
        if match:
            statuses[match.group(1)] = ArgumentStatus[match.group(2)]
            continue
        # Unprefixed format: ARG-1: ADDRESSED — add round prefix
        match = re.match(r"(ARG-\d+):\s+(ADDRESSED|MENTIONED|IGNORED)", line)
        if match:
            arg_id = f"R{prev_round}-{match.group(1)}" if prev_round else match.group(1)
            statuses[arg_id] = ArgumentStatus[match.group(2)]
    return statuses


class ArgumentTracker:
    """Tracks arguments across rounds and re-injects unaddressed ones."""

    def __init__(self, llm_client):
        self._llm = llm_client
        self.arguments_by_round: dict[int, list[Argument]] = {}
        self.all_unaddressed: list[Argument] = []  # Cumulative across all rounds
        self.last_raw_response: str = ""  # For debug logging

    async def extract_arguments(
        self, round_num: int, model_outputs: dict[str, str],
    ) -> list[Argument]:
        from thinker.types import BrainError
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        resp = await self._llm.call(
            "sonnet",
            EXTRACT_PROMPT.format(round_num=round_num, outputs=combined),
        )
        if not resp.ok:
            raise BrainError(f"track{round_num}", f"Argument extraction failed: {resp.error}",
                             detail="Sonnet could not extract arguments from round outputs.")
        self.last_raw_response = resp.text
        args = parse_arguments(resp.text, round_num)
        if not args:
            raise BrainError(f"track{round_num}", "Argument extraction returned 0 arguments",
                             detail=f"Raw response: {resp.text[:300]}")
        self.arguments_by_round[round_num] = args
        return args

    async def compare_with_round(
        self, prev_round: int, curr_outputs: dict[str, str],
    ) -> list[Argument]:
        from thinker.types import BrainError
        prev_args = self.arguments_by_round.get(prev_round, [])
        if not prev_args:
            return []

        args_text = "\n".join(
            f"{a.argument_id}: [{a.model}] {a.text}" for a in prev_args
        )
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in curr_outputs.items())
        curr_round = prev_round + 1

        resp = await self._llm.call(
            "sonnet",
            COMPARE_PROMPT.format(
                prev_round=prev_round, arguments=args_text,
                curr_round=curr_round, outputs=combined,
            ),
        )
        if not resp.ok:
            raise BrainError(f"track{curr_round}",
                             f"Argument comparison failed: {resp.error}",
                             detail=f"Could not compare R{prev_round} args against R{curr_round} outputs.")

        statuses = parse_comparison(resp.text, prev_round=prev_round)
        unaddressed = []
        for arg in prev_args:
            status = statuses.get(arg.argument_id, ArgumentStatus.IGNORED)
            arg.status = status
            if status in (ArgumentStatus.IGNORED, ArgumentStatus.MENTIONED):
                arg.addressed_in_round = None
                unaddressed.append(arg)
            else:
                arg.addressed_in_round = curr_round

        # Accumulate: add newly unaddressed args, remove any that were addressed
        addressed_ids = {a.argument_id for a in prev_args if a.status == ArgumentStatus.ADDRESSED}
        existing_ids = {a.argument_id for a in self.all_unaddressed}
        self.all_unaddressed = [
            a for a in self.all_unaddressed if a.argument_id not in addressed_ids
        ] + [a for a in unaddressed if a.argument_id not in existing_ids]
        return unaddressed

    def format_reinjection(self, unaddressed: list[Argument]) -> str:
        if not unaddressed:
            return ""
        lines = []
        for arg in unaddressed:
            status_label = "IGNORED" if arg.status == ArgumentStatus.IGNORED else "only mentioned"
            lines.append(f"{arg.argument_id}: [{arg.model}] {arg.text} ({status_label} in previous round)")
        return (
            "The following arguments from prior rounds were NOT substantively addressed. "
            "You MUST engage with each one — agree with reasoning, rebut with evidence, or refine.\n\n"
            + "\n".join(lines)
        )


@pipeline_stage(
    name="Argument Tracker",
    description="Core V8 innovation. After each round, Sonnet extracts all distinct arguments. After R2+, compares them with current round to identify ADDRESSED/MENTIONED/IGNORED. Unaddressed arguments re-injected into next round's prompt. Arguments can't be silently dropped.",
    stage_type="track",
    order=3,
    provider="sonnet (2 calls: extract + compare)",
    inputs=["model_outputs (dict[model, text])"],
    outputs=["arguments (list[Argument])", "unaddressed (list)", "reinjection_text (str)"],
    prompt=EXTRACT_PROMPT,
    logic="""EXTRACT: Sonnet reads all outputs, extracts ARG-N: [model] text.
COMPARE (R2+): For each prior arg — ADDRESSED (engaged), MENTIONED (name-dropped), IGNORED (absent).
RE-INJECT: IGNORED + MENTIONED args added to next round with "You MUST engage".""",
    failure_mode="Extract fails: empty args. Compare fails: re-inject all (conservative).",
    cost="2 Sonnet calls per round ($0 on Max subscription)",
    stage_id="argument_tracker",
)
def _register_argument_tracker(): pass

```


### thinker/config.py


```python
"""Configuration for the Thinker V8 Brain engine."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for a single LLM."""
    name: str
    model_id: str
    provider: str  # "openrouter", "anthropic", "deepseek", or "zai"
    max_tokens: int
    timeout_s: int
    is_thinking: bool = False


# --- Model roster (V8 spec Section 4) ---

R1_MODEL = ModelConfig("r1", "deepseek/deepseek-r1-0528", "openrouter", 30_000, 720, is_thinking=True)
REASONER_MODEL = ModelConfig("reasoner", "deepseek-reasoner", "deepseek", 30_000, 720, is_thinking=True)
GLM5_MODEL = ModelConfig("glm5", "glm-5", "zai", 16_000, 480)
KIMI_MODEL = ModelConfig("kimi", "moonshotai/kimi-k2", "openrouter", 16_000, 480)
SONNET_MODEL = ModelConfig("sonnet", "claude-sonnet-4-6", "anthropic", 16_000, 120)

# --- Round topology (V8 spec: 4 -> 3 -> 2 -> 2) ---

ROUND_TOPOLOGY: dict[int, list[str]] = {
    1: ["r1", "reasoner", "glm5", "kimi"],
    2: ["r1", "reasoner", "glm5"],
    3: ["r1", "reasoner"],
    4: ["r1", "reasoner"],
}

MODEL_REGISTRY: dict[str, ModelConfig] = {
    "r1": R1_MODEL,
    "reasoner": REASONER_MODEL,
    "glm5": GLM5_MODEL,
    "kimi": KIMI_MODEL,
    "sonnet": SONNET_MODEL,
}


@dataclass
class BrainConfig:
    """Runtime configuration for a Brain run."""
    rounds: int = 4
    max_evidence_items: int = 10
    max_search_queries_per_phase: int = 5
    search_after_rounds: int = 2  # Search runs after rounds 1..N (default: after R1 and R2)
    openrouter_api_key: str = ""
    anthropic_oauth_token: str = ""
    deepseek_api_key: str = ""
    zai_api_key: str = ""
    brave_api_key: str = ""
    outdir: str = "./output"

```


### thinker/tools/position.py


```python
"""Position Tracker — tracks model positions per round and measures convergence."""
from __future__ import annotations

import re
from collections import Counter

from thinker.config import MODEL_REGISTRY
from thinker.pipeline import pipeline_stage
from thinker.types import Confidence, Position

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
            from thinker.types import BrainError
            raise BrainError(f"track{round_num}", f"Position extraction failed: {resp.error}",
                             detail="Sonnet could not extract positions from round outputs.")
        self.last_raw_response = resp.text

        positions = self._parse_positions(resp.text, round_num)
        if not positions:
            from thinker.types import BrainError
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

        options = [_normalize_position(p.primary_option) for p in positions.values()]
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
                        framework_positions.setdefault(fw.strip(), []).append(
                            label.strip().lower()
                        )
                    else:
                        framework_positions.setdefault("default", []).append(
                            comp.strip().lower()
                        )
            else:
                framework_positions.setdefault("default", []).append(
                    _normalize_position(p.primary_option)
                )

        if not framework_positions:
            return 0.0

        ratios = []
        for fw, labels in framework_positions.items():
            counts = Counter(labels)
            majority = counts.most_common(1)[0][1]
            ratios.append(majority / len(labels))
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

        for line in text.strip().split("\n"):
            line = line.strip()

            # Try markdown table row with model/framework
            # Handles: | `r1/PCI_DSS` | position | HIGH | qualifier |
            # Also: | 1 | `r1/PCI_DSS` | position | HIGH | qualifier | (leading column)
            table_match = re.search(
                r"\|\s*`?(\w+)/(\w+)`?\s*\|\s*(.+?)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|",
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
            table_simple = re.search(
                r"\|\s*`?(\w+)`?\s*\|\s*(.+?)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|",
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

```


### thinker/tools/blocker.py


```python
"""Blocker Lifecycle — tracks evidence gaps, contradictions, and disagreements."""
from __future__ import annotations

from thinker.types import Blocker, BlockerKind, BlockerStatus


class BlockerLedger:
    def __init__(self):
        self.blockers: list[Blocker] = []
        self._counter = 0

    def add(self, kind: BlockerKind, source: str, detected_round: int,
            detail: str = "", models: list[str] | None = None) -> Blocker:
        self._counter += 1
        blocker = Blocker(
            blocker_id=f"BLK{self._counter:03d}",
            kind=kind,
            source=source,
            detected_round=detected_round,
            detail=detail,
            models_involved=models or [],
            status_history=[{"status": "OPEN", "round": detected_round, "trigger": "detected"}],
        )
        self.blockers.append(blocker)
        return blocker

    def resolve(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.RESOLVED, round_num, trigger, note)

    def defer(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.DEFERRED, round_num, trigger, note)

    def drop(self, blocker_id: str, round_num: int, trigger: str, note: str = ""):
        self._update_status(blocker_id, BlockerStatus.DROPPED, round_num, trigger, note)

    def open_blockers(self) -> list[Blocker]:
        return [b for b in self.blockers if b.status == BlockerStatus.OPEN]

    def summary(self) -> dict:
        by_status = {}
        by_kind = {}
        for b in self.blockers:
            by_status[b.status.value] = by_status.get(b.status.value, 0) + 1
            by_kind[b.kind.value] = by_kind.get(b.kind.value, 0) + 1
        return {
            "total_blockers": len(self.blockers),
            "by_status": by_status,
            "by_kind": by_kind,
            "open_at_end": len(self.open_blockers()),
        }

    def _update_status(self, blocker_id: str, new_status: BlockerStatus,
                       round_num: int, trigger: str, note: str):
        for b in self.blockers:
            if b.blocker_id == blocker_id:
                b.status = new_status
                b.resolution_note = note
                b.status_history.append({
                    "status": new_status.value, "round": round_num, "trigger": trigger,
                })
                return

```


### thinker/tools/contradiction.py


```python
"""Contradiction Detector — finds numeric conflicts between evidence items."""
from __future__ import annotations

import re
from typing import Optional

from thinker.types import Contradiction, EvidenceItem

_NUMBER_PATTERN = re.compile(r"\b(\d[\d,.]*%?)\b")


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_PATTERN.findall(text))


def _topic_overlap(a: str, b: str) -> int:
    words_a = {w.lower() for w in a.split() if len(w) >= 4}
    words_b = {w.lower() for w in b.split() if len(w) >= 4}
    return len(words_a & words_b)


_CONTRADICTION_COUNTER = 0


def detect_contradiction(
    item_a: EvidenceItem, item_b: EvidenceItem,
) -> Optional[Contradiction]:
    global _CONTRADICTION_COUNTER

    if _topic_overlap(item_a.topic + " " + item_a.fact, item_b.topic + " " + item_b.fact) < 2:
        return None

    nums_a = _extract_numbers(item_a.fact)
    nums_b = _extract_numbers(item_b.fact)

    if not nums_a or not nums_b:
        return None

    # If all numbers in the smaller set appear in the larger set, no contradiction
    # (one item may just have more detail)
    if nums_a.issubset(nums_b) or nums_b.issubset(nums_a):
        return None

    _CONTRADICTION_COUNTER += 1
    # HIGH if the unique numbers differ significantly (both have exclusive numbers)
    exclusive_a = nums_a - nums_b
    exclusive_b = nums_b - nums_a
    severity = "HIGH" if exclusive_a and exclusive_b else "MEDIUM"
    return Contradiction(
        contradiction_id=f"CTR{_CONTRADICTION_COUNTER:03d}",
        evidence_ids=[item_a.evidence_id, item_b.evidence_id],
        topic=item_a.topic,
        severity=severity,
    )

```


### thinker/tools/cross_domain.py


```python
"""Cross-domain evidence filter.

Prevents medical evidence from polluting security briefs, finance from
infrastructure briefs, etc. Domain detection via keyword families.
"""
from __future__ import annotations

DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "security": {"cve", "vulnerability", "exploit", "rce", "xss", "sql injection",
                 "buffer overflow", "privilege escalation", "malware", "breach",
                 "authentication", "authorization", "firewall", "encryption"},
    "medical": {"dosage", "patient", "clinical", "diagnosis", "treatment",
                "medication", "symptom", "therapy", "pharmaceutical", "surgery"},
    "finance": {"stock", "equity", "portfolio", "etf", "dividend", "trading",
                "market cap", "earnings", "revenue", "valuation", "bond"},
    "infrastructure": {"server", "database", "kubernetes", "docker", "deployment",
                       "latency", "throughput", "scaling", "load balancer", "cdn"},
    "compliance": {"gdpr", "hipaa", "sox", "pci", "dora", "regulation", "audit",
                   "compliance", "certification", "framework"},
}

# Which domains are compatible with each other
COMPATIBLE_DOMAINS: dict[str, set[str]] = {
    "security": {"security", "infrastructure", "compliance"},
    "medical": {"medical"},
    "finance": {"finance"},
    "infrastructure": {"infrastructure", "security", "compliance"},
    "compliance": {"compliance", "security", "infrastructure"},
}


def detect_domain(text: str) -> str | None:
    """Detect the primary domain of a text based on keyword density."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)
    if not scores:
        return None
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else None


def is_cross_domain(evidence_text: str, brief_domain: str) -> bool:
    """Check if evidence is from an incompatible domain."""
    ev_domain = detect_domain(evidence_text)
    if ev_domain is None:
        return False  # Can't determine domain — allow it
    compatible = COMPATIBLE_DOMAINS.get(brief_domain, {brief_domain})
    return ev_domain not in compatible

```


### thinker/bing_search.py


```python
"""Primary search via Playwright Bing (headful browser).

Uses a real browser to search Bing, extracting results from the rendered DOM.
This is resilient to HTML structure changes and avoids CAPTCHA blocks that
affect curl_cffi/httpx approaches.

Headful mode is required — headless Chromium gets fingerprinted by Bing.
"""
from __future__ import annotations

import asyncio
from urllib.parse import quote_plus

from thinker.types import SearchResult


def _cite_to_url(cite_text: str) -> str:
    """Convert Bing cite text to a real URL.

    Bing cite tags show: 'https://www.example.com › path › page'
    Convert to: 'https://www.example.com/path/page'
    """
    if not cite_text:
        return ""
    # Replace ' › ' separators with '/'
    url = cite_text.replace(" › ", "/").replace("›", "/").strip()
    # Ensure it starts with https://
    if not url.startswith("http"):
        url = "https://" + url
    return url


async def bing_search(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search Bing via Playwright headful browser.

    Returns up to max_results SearchResult items with titles and snippets
    in Bing's ranking order. Raises SearchError on failure.
    """
    from thinker.brave_search import SearchError

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise SearchError("Bing search requires playwright: pip install playwright && playwright install chromium")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            url = f"https://www.bing.com/search?q={quote_plus(query)}&scope=web&FORM=HDRSC1"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # Check for CAPTCHA
            page_content = await page.content()
            if "captcha" in page_content.lower() and "b_algo" not in page_content.lower():
                await browser.close()
                raise SearchError(f"Bing CAPTCHA block for: {query[:50]}")

            # Extract results from rendered DOM
            raw_results = await page.evaluate("""() => {
                const items = document.querySelectorAll('li.b_algo');
                return Array.from(items).map(item => {
                    const a = item.querySelector('h2 a');
                    const cite = item.querySelector('cite');
                    const snippet = item.querySelector('.b_caption p, .b_lineclamp2, .b_paractl');
                    return {
                        title: a ? a.innerText : '',
                        cite: cite ? cite.innerText : '',
                        snippet: snippet ? snippet.innerText : '',
                    };
                });
            }""")

            await browser.close()

            # Build results using cite-based URLs (real URLs, not redirects)
            results: list[SearchResult] = []
            seen_urls: set[str] = set()
            for item in raw_results:
                real_url = _cite_to_url(item.get("cite", ""))
                if not real_url or real_url in seen_urls:
                    continue
                seen_urls.add(real_url)
                results.append(SearchResult(
                    url=real_url,
                    title=item.get("title", "")[:200],
                    snippet=item.get("snippet", "")[:500],
                ))
                if len(results) >= max_results:
                    break

            return results

    except SearchError:
        raise
    except Exception as e:
        raise SearchError(f"Bing search failed: {e}")

```

