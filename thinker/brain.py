"""Brain Orchestrator — wires the full V9 deliberation pipeline.

Flow:
  Preflight -> Dimensions -> R1(+adversarial) -> PerspectiveCards -> FramingPass
  -> UngroundedR1 -> Search(R1) -> R2 -> FrameSurvivalR2 -> UngroundedR2 -> Search(R2)
  -> R3 -> FrameSurvivalR3 -> R4 -> SemanticContradiction -> SynthesisPacket
  -> Synthesis -> Stability -> Gate 2

Debug modes:
  --verbose          : Full logging at each stage
  --stop-after STAGE : Run up to STAGE, save checkpoint, exit
  --resume FILE      : Resume from a checkpoint file

Stage IDs: preflight, dimensions, r1, track1, perspective_cards, framing_pass,
           ungrounded_r1, search1, r2, track2, frame_survival_r2, ungrounded_r2, search2,
           r3, track3, frame_survival_r3, r4, track4,
           semantic_contradiction, synthesis_packet, synthesis, stability, gate2
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
from thinker.gate2 import run_gate2_deterministic, classify_outcome
from thinker.invariant import validate_invariants
from thinker.page_fetch import fetch_pages_for_results
from thinker.proof import ProofBuilder
from thinker.residue import check_synthesis_residue, run_deep_semantic_scan
from thinker.rounds import execute_round
from thinker.search import SearchOrchestrator, SearchPhase
from thinker.synthesis import run_synthesis
from thinker.tools.blocker import BlockerLedger
from thinker.tools.position import PositionTracker
from thinker.checkpoint import PipelineState, should_stop
from thinker.types import ArgumentStatus, BlockerKind, BrainError, BrainResult, Confidence, EvidenceItem, Outcome, Position, SearchResult
from thinker.preflight import run_preflight
from thinker.dimension_seeder import run_dimension_seeder, format_dimensions_for_prompt
from thinker.perspective_cards import extract_perspective_cards, format_perspective_card_instructions
from thinker.divergent_framing import (
    run_framing_extract, run_frame_survival_check,
    check_exploration_stress, format_frames_for_prompt,
)
from thinker.semantic_contradiction import run_semantic_contradiction_pass
from thinker.tools.ungrounded import find_ungrounded_stats, generate_verification_queries
from thinker.stability import run_stability_tests
from thinker.decisive_claims import extract_decisive_claims
from thinker.analysis_mode import get_analysis_round_preamble, get_analysis_synthesis_contract
from thinker.synthesis_packet import build_synthesis_packet, format_synthesis_packet_for_prompt
from thinker.residue import check_disposition_coverage
from thinker.types import (
    DimensionSeedResult, DivergenceResult, FrameSurvivalStatus, Modality, PreflightResult, StabilityResult,
)


class Brain:
    """The V9 Brain deliberation engine."""

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
        self._search_override = search_override  # None=preflight decides, True=force on, False=force off
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
        if stage_id == "preflight":
            pf = st.preflight or {}
            self.log._print(f"  Preflight: {pf.get('answerability', 'N/A')} | {pf.get('modality', 'N/A')} | {pf.get('effort_tier', 'N/A')}")

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
                confidence=Confidence[ev_data.get("confidence", "MEDIUM")],
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
        st = self.state
        resuming = len(st.completed_stages) > 0
        run_id = st.run_id if resuming else f"brain-{int(time.time())}"
        st.brief = brief
        st.rounds = self._config.rounds
        st.run_id = run_id

        if resuming:
            self.log._print(f"\n  [RESUME] Resuming from stage: {st.current_stage}")
            self.log._print(f"  [RESUME] Completed stages: {' → '.join(st.completed_stages)}")

        proof = ProofBuilder(run_id, brief, self._config.rounds)
        try:
            return await self._run_pipeline(brief, run_id, proof)
        except BrainError as e:
            # DOD §19: proof.json required "always", including on ERROR.
            # Write partial proof with error_class before re-raising.
            proof.set_error_class(
                "INFRASTRUCTURE" if "LLM" in e.message or "call failed" in e.message
                else "FATAL_INTEGRITY"
            )
            proof.set_final_status(f"ERROR:{e.stage}")
            proof.set_timestamp_completed()
            e.partial_proof = proof.build()
            raise

    async def _run_pipeline(self, brief: str, run_id: str,
                            proof: ProofBuilder) -> BrainResult:
        """Inner pipeline execution — separated so run() can catch BrainError and write partial proof."""
        log = self.log
        st = self.state
        resuming = len(st.completed_stages) > 0
        run_start_time = time.monotonic()
        # DOD §19: topology and config_snapshot
        proof.set_topology({
            str(r): models for r, models in ROUND_TOPOLOGY.items()
        } | {"round_model_counts": [len(m) for m in ROUND_TOPOLOGY.values()]})
        proof.set_config_snapshot({
            "rounds": self._config.rounds,
            "max_evidence_items": self._config.max_evidence_items,
            "max_search_queries_per_phase": self._config.max_search_queries_per_phase,
            "search_after_rounds": self._config.search_after_rounds,
        })
        # Truncated brief for Sonnet extraction stages (framing, synthesis, etc.)
        # Deliberating models (R1/Reasoner/GLM5/Kimi) get the full brief.
        # Sonnet extraction stages only need the question context, not full source code.
        brief_for_sonnet = brief[:15000] if len(brief) > 15000 else brief
        brief_keywords = {w.lower() for w in brief.split() if len(w) >= 4}
        search_log_entries: list = []
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

        # V9 state — initialized here so they're available even on resume
        preflight_result = PreflightResult()  # defaults
        dimension_result = DimensionSeedResult()
        dimension_text = ""
        alt_frames_text = ""
        divergence_result = DivergenceResult()
        semantic_ctrs: list = []
        decisive_claims: list = []
        is_analysis_mode = False
        stability_result = StabilityResult()

        # Restore tracker state if resuming
        if resuming:
            prior_views, unaddressed_text = self._restore_trackers(
                argument_tracker, position_tracker, evidence,
            )
            # Restore V9 state from checkpoint
            from thinker.types import (
                Answerability, QuestionClass, StakesClass, EffortTier, SearchScope,
                DimensionItem, FrameInfo, FrameType,
            )
            if st.preflight:
                pf = st.preflight
                preflight_result = PreflightResult(
                    answerability=Answerability(pf.get("answerability", "ANSWERABLE")),
                    question_class=QuestionClass(pf.get("question_class", "OPEN")),
                    stakes_class=StakesClass(pf.get("stakes_class", "STANDARD")),
                    effort_tier=EffortTier(pf.get("effort_tier", "STANDARD")),
                    modality=Modality(pf.get("modality", "DECIDE")),
                    search_scope=SearchScope(pf.get("search_scope", "TARGETED")),
                    exploration_required=pf.get("exploration_required", False),
                    short_circuit_allowed=pf.get("short_circuit_allowed", False),
                    fatal_premise=pf.get("fatal_premise", False),
                    reasoning=pf.get("reasoning", ""),
                )
            if st.dimensions:
                dim = st.dimensions
                items = [DimensionItem(
                    dimension_id=d.get("dimension_id", ""),
                    name=d.get("name", ""),
                ) for d in dim.get("items", [])]
                dimension_result = DimensionSeedResult(
                    items=items, dimension_count=dim.get("dimension_count", 0),
                )
                dimension_text = format_dimensions_for_prompt(dimension_result.items)
            if st.divergence:
                div = st.divergence
                divergence_result = DivergenceResult(
                    framing_pass_executed=div.get("framing_pass_executed", False),
                    exploration_stress_triggered=div.get("exploration_stress_triggered", False),
                )
                for f_data in div.get("alt_frames", []):
                    try:
                        divergence_result.alt_frames.append(FrameInfo(
                            frame_id=f_data.get("frame_id", ""),
                            text=f_data.get("text", ""),
                            frame_type=FrameType(f_data.get("frame_type", "INVERSION")),
                            survival_status=FrameSurvivalStatus(f_data.get("survival_status", "ACTIVE")),
                            material_to_outcome=f_data.get("material_to_outcome", True),
                        ))
                    except (ValueError, KeyError):
                        pass
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
        else:
            prior_views = {}
            unaddressed_text = ""

        # --- PreflightAssessment (V9 — replaces Gate 1) ---
        if not self._stage_done("preflight"):
            log._print("  [PREFLIGHT] Running PreflightAssessment...")
            t0 = time.monotonic()
            preflight_result = await run_preflight(self._llm, brief)
            log._print(f"  [PREFLIGHT] {preflight_result.answerability.value} | "
                       f"{preflight_result.modality.value} | {preflight_result.effort_tier.value} "
                       f"({time.monotonic() - t0:.1f}s)")

            if preflight_result.answerability.value in ("NEED_MORE", "INVALID_FORM"):
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            # DOD 4.5: FATAL_PREMISE cross-check — override answerability if LLM missed it
            if preflight_result.fatal_premise and preflight_result.answerability.value == "ANSWERABLE":
                log._print("  [PREFLIGHT] FATAL_PREMISE detected but answerability=ANSWERABLE — overriding to NEED_MORE")
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            # DOD 4.4: Material false/unverifiable assumptions block admission
            if preflight_result.has_fatal_assumptions:
                log._print("  [PREFLIGHT] Material UNVERIFIABLE/FALSE assumption detected — overriding to NEED_MORE")
                proof.set_preflight(preflight_result)
                proof.set_final_status("PREFLIGHT_REJECTED")
                return BrainResult(
                    outcome=Outcome.NEED_MORE, proof=proof.build(),
                    report="", preflight=preflight_result,
                )

            st.preflight = preflight_result.to_dict()
            st.modality = preflight_result.modality.value
            is_analysis_mode = preflight_result.modality == Modality.ANALYSIS
            proof.set_preflight(preflight_result)

            # --- Defect Routing (V9, DESIGN-V3.md Section 1.1) ---
            from thinker.types import PremiseFlagRouting
            for flag in preflight_result.premise_flags:
                if flag.resolved:
                    continue
                if flag.routing == PremiseFlagRouting.REQUESTER_FIXABLE:
                    # DOD 4.3: REQUESTER_FIXABLE → NEED_MORE (must not be admitted)
                    log._print(f"  [DEFECT] {flag.flag_id}: REQUESTER_FIXABLE → rejecting brief")
                    proof.set_preflight(preflight_result)
                    proof.set_final_status("PREFLIGHT_REJECTED")
                    return BrainResult(
                        outcome=Outcome.NEED_MORE, proof=proof.build(),
                        report="", preflight=preflight_result,
                    )
                elif flag.routing == PremiseFlagRouting.MANAGEABLE_UNKNOWN:
                    blocker_ledger.add(
                        kind=BlockerKind.COVERAGE_GAP,
                        source=f"preflight:{flag.flag_id}",
                        detected_round=0,
                        detail=f"Manageable unknown: {flag.summary}",
                        models=[],
                        severity="HIGH" if flag.severity.value == "CRITICAL" else "MEDIUM",
                    )
                    log._print(f"  [DEFECT] {flag.flag_id}: MANAGEABLE_UNKNOWN → blocker registered")
                elif flag.routing == PremiseFlagRouting.FRAMING_DEFECT:
                    dimension_text += f"\n\n## Reframing Required (Premise Defect)\n{flag.summary}\nYou MUST engage with this reframing in your analysis.\n"
                    log._print(f"  [DEFECT] {flag.flag_id}: FRAMING_DEFECT → reframe injected into R1")

            if self._checkpoint("preflight"):
                return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report="[STOPPED AT PREFLIGHT]", preflight=preflight_result)
        else:
            if st.preflight:
                preflight_result = PreflightResult(
                    modality=Modality(st.preflight.get("modality", "DECIDE")),
                )
            is_analysis_mode = preflight_result.modality == Modality.ANALYSIS

        # --- Dimension Seeder (V9) ---
        if not self._stage_done("dimensions"):
            log._print("  [DIMENSIONS] Running Dimension Seeder...")
            t0 = time.monotonic()
            dimension_result = await run_dimension_seeder(self._llm, brief)
            dimension_text = format_dimensions_for_prompt(dimension_result.items)
            log._print(f"  [DIMENSIONS] {dimension_result.dimension_count} dimensions ({time.monotonic() - t0:.1f}s)")
            st.dimensions = dimension_result.to_dict()
            proof.set_dimensions(dimension_result)
            if self._checkpoint("dimensions"):
                return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report="[STOPPED AT DIMENSIONS]", preflight=preflight_result, dimensions=dimension_result)

        # --- Search Decision (V9: uses preflight.search_scope) ---
        from thinker.types import SearchScope
        has_search_provider = self._search_fn is not None
        if self._search_override is not None:
            search_enabled = self._search_override and has_search_provider
            source = "cli_override"
            reasoning = "Forced on via --search" if self._search_override else "Forced off via --no-search"
            proof.set_search_decision(source=source, value=search_enabled, reasoning=reasoning)
            log._print(f"  [SEARCH DECISION] {source}: {'ON' if search_enabled else 'OFF'} "
                        f"(Preflight scope: {preflight_result.search_scope.value})")
        else:
            search_enabled = (preflight_result.search_scope != SearchScope.NONE) and has_search_provider
            proof.set_search_decision(
                source="preflight",
                value=search_enabled,
                reasoning=f"Preflight search_scope={preflight_result.search_scope.value}",
            )
            log._print(f"  [SEARCH DECISION] preflight: {'ON' if search_enabled else 'OFF'} — scope={preflight_result.search_scope.value}")

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
                # ANALYSIS mode: prepend exploration preamble to brief
                effective_brief = (get_analysis_round_preamble() + brief) if is_analysis_mode else brief
                round_result = await execute_round(
                    self._llm, round_num=round_num, brief=effective_brief,
                    prior_views=prior_views if round_num > 1 else None,
                    evidence_text=evidence.format_for_prompt() if round_num > 1 else "",
                    unaddressed_arguments=unaddressed_text if round_num > 1 else "",
                    is_last_round=is_last_round,
                    adversarial_model="kimi" if round_num == 1 else "",
                    dimension_text=dimension_text if round_num == 1 else "",
                    perspective_card_instructions=format_perspective_card_instructions() if round_num == 1 else "",
                    alt_frames_text=alt_frames_text if round_num >= 2 else "",
                )
                log.round_result(round_num, round_result.responded, round_result.failed,
                                 round_result.texts, time.monotonic() - t0)
                proof.record_round(round_num, round_result.responded, round_result.failed)
                # Store full text for resume — truncation loses SEARCH_REQUESTS appendix
                st.round_texts[str(round_num)] = round_result.texts
                st.round_responded[str(round_num)] = round_result.responded
                st.round_failed[str(round_num)] = round_result.failed

                if round_result.failed:
                    failed_details = "; ".join(
                        f"{m}: {round_result.responses[m].error}"
                        for m in round_result.failed
                        if m in round_result.responses
                    )
                    raise BrainError(
                        f"round{round_num}",
                        f"Model(s) failed in round {round_num}: {', '.join(round_result.failed)}",
                        detail=failed_details,
                    )

                if self._checkpoint(f"r{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT R{round_num}]", preflight=preflight_result)

            # --- Tracking phase (skip if already done on resume) ---
            if not self._stage_done(track_stage):
                # Extract arguments
                t0 = time.monotonic()
                args = await argument_tracker.extract_arguments(round_num, round_result.texts)
                # Assign dimension_id by keyword matching
                if dimension_result and dimension_result.items:
                    dim_names = {d.dimension_id: d.name for d in dimension_result.items}
                    argument_tracker.assign_dimensions(args, dim_names)
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
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT TRACK{round_num}]", preflight=preflight_result)
            else:
                log._print(f"  [RESUME] Skipping track{round_num} (already completed)")

            # --- V9: Mark adversarial slot assigned (DOD §10) ---
            if round_num == 1:
                divergence_result.adversarial_slot_assigned = True
                divergence_result.adversarial_model_id = "kimi"

            # --- V9: Post-R1 perspective cards + framing pass ---
            if round_num == 1 and not self._stage_done("perspective_cards"):
                perspective_cards = extract_perspective_cards(round_result.texts)
                st.perspective_cards = [c.to_dict() for c in perspective_cards]
                proof.set_perspective_cards(perspective_cards)
                self._checkpoint("perspective_cards")

            if round_num == 1 and not self._stage_done("framing_pass"):
                log._print("  [FRAMING] Running framing extract...")
                t0 = time.monotonic()
                divergence_result = await run_framing_extract(self._llm, brief_for_sonnet, round_result.texts)
                # Check exploration stress (use R1 agreement)
                r1_agreement = position_tracker.agreement_ratio(1)
                if check_exploration_stress(r1_agreement, preflight_result.question_class, preflight_result.stakes_class):
                    divergence_result.exploration_stress_triggered = True
                    from thinker.types import FrameInfo, FrameType
                    seed_frames = [
                        FrameInfo(
                            frame_id="SEED-INV", text="What if the opposite of the emerging consensus is true? Argue against the majority position.",
                            origin_round=1, origin_model="controller", frame_type=FrameType.INVERSION,
                        ),
                        FrameInfo(
                            frame_id="SEED-STAKE", text="Consider the perspective of the stakeholder most harmed by the emerging consensus.",
                            origin_round=1, origin_model="controller", frame_type=FrameType.OPPOSITE_STANCE,
                        ),
                    ]
                    divergence_result.alt_frames.extend(seed_frames)
                    divergence_result.stress_seed_frames = [f.to_dict() for f in seed_frames]
                    log._print(f"  [STRESS] Exploration stress triggered — {len(seed_frames)} seed frames injected")
                st.divergence = divergence_result.to_dict()
                proof.set_divergence(divergence_result)
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                log._print(f"  [FRAMING] {len(divergence_result.alt_frames)} frames extracted ({time.monotonic() - t0:.1f}s)")
                self._checkpoint("framing_pass")

            # --- V9: Post-R2 frame survival ---
            if round_num == 2 and not self._stage_done("frame_survival_r2"):
                log._print("  [FRAMING] Running frame survival check (R2)...")
                t0 = time.monotonic()
                divergence_result.alt_frames = await run_frame_survival_check(
                    self._llm, divergence_result.alt_frames, round_result.texts, round_num=2,
                    is_analysis_mode=is_analysis_mode,
                )
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                st.divergence = divergence_result.to_dict()
                log._print(f"  [FRAMING] Frame survival R2 done ({time.monotonic() - t0:.1f}s)")
                self._checkpoint("frame_survival_r2")

            # --- V9: Post-R3 frame survival ---
            if round_num == 3 and not self._stage_done("frame_survival_r3"):
                log._print("  [FRAMING] Running frame survival check (R3)...")
                t0 = time.monotonic()
                divergence_result.alt_frames = await run_frame_survival_check(
                    self._llm, divergence_result.alt_frames, round_result.texts, round_num=3,
                    is_analysis_mode=is_analysis_mode,
                )
                alt_frames_text = format_frames_for_prompt(divergence_result.alt_frames)
                st.divergence = divergence_result.to_dict()
                log._print(f"  [FRAMING] Frame survival R3 done ({time.monotonic() - t0:.1f}s)")
                self._checkpoint("frame_survival_r3")

            # --- Ungrounded Stat Detection (V9, post-R1 and post-R2, DECIDE only per DOD §9.3) ---
            if round_num in (1, 2) and not is_analysis_mode and not self._stage_done(f"ungrounded_r{round_num}"):
                all_round_text = " ".join(round_result.texts.values())
                ungrounded = find_ungrounded_stats(all_round_text, evidence.active_items)
                if round_num == 1:
                    st.ungrounded_r1_executed = True
                else:
                    st.ungrounded_r2_executed = True
                if ungrounded:
                    log._print(f"  [UNGROUNDED] R{round_num}: {len(ungrounded)} ungrounded stats detected")
                    verification_queries = generate_verification_queries(ungrounded, all_round_text)
                    st.search_queries[f"ungrounded_r{round_num}"] = verification_queries
                    # Track per-claim for DOD §9.2 schema
                    for i, stat in enumerate(ungrounded):
                        st.ungrounded_flagged_claims.append({
                            "claim_id": f"UG-R{round_num}-{i+1}",
                            "text": stat,
                            "numeric": True,
                            "verified": False,
                            "blocker_id": None,
                            "severity": "MEDIUM",
                            "status": "UNVERIFIED_CLAIM",
                        })
                self._checkpoint(f"ungrounded_r{round_num}")

            # --- Post-R3: unresolved ungrounded stats become UNVERIFIED_CLAIM blockers (DECIDE only) ---
            if round_num == 3 and not is_analysis_mode:
                all_r3_text = " ".join(round_result.texts.values())
                ungrounded_r3 = find_ungrounded_stats(all_r3_text, evidence.active_items)
                for i, stat in enumerate(ungrounded_r3):
                    blk = blocker_ledger.add(
                        kind=BlockerKind.UNVERIFIED_CLAIM,
                        source="ungrounded_stat_detector",
                        detected_round=3,
                        detail=f"Unverified numeric claim persists after R3: {stat}",
                        severity="CRITICAL",
                        models=[],
                    )
                    # Update tracked claim with blocker link
                    for fc in st.ungrounded_flagged_claims:
                        if fc["text"] == stat and fc["blocker_id"] is None:
                            fc["blocker_id"] = blk.blocker_id
                            fc["severity"] = "CRITICAL"
                            break
                    else:
                        # New claim at R3 not seen earlier
                        st.ungrounded_flagged_claims.append({
                            "claim_id": f"UG-R3-{i+1}",
                            "text": stat,
                            "numeric": True,
                            "verified": False,
                            "blocker_id": blk.blocker_id,
                            "severity": "CRITICAL",
                            "status": "UNVERIFIED_CLAIM",
                        })
                if ungrounded_r3:
                    log._print(f"  [UNGROUNDED] R3: {len(ungrounded_r3)} unresolved → UNVERIFIED_CLAIM blockers")

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
                all_search_results: list[SearchResult] = []
                from thinker.types import SearchLogEntry, QueryProvenance, QueryStatus
                # Determine provenance per query
                ungrounded_qs = set(st.search_queries.get(f"ungrounded_r{round_num}", []))
                for query in queries[:self._config.max_search_queries_per_phase]:
                    provenance = QueryProvenance.UNGROUNDED_STAT if query in ungrounded_qs else QueryProvenance.MODEL_CLAIM
                    try:
                        results = await search_orch.execute_query(query, phase)
                    except Exception as e:
                        search_log_entries.append(SearchLogEntry(
                            query_id=f"Q-{len(search_log_entries)+1}", query_text=query[:200],
                            provenance=provenance, issued_after_stage=f"r{round_num}",
                            query_status=QueryStatus.FAILED,
                        ))
                        raise BrainError(
                            f"search_round{round_num}",
                            f"Search query failed: {query[:80]}",
                            detail=str(e),
                        )
                    search_log_entries.append(SearchLogEntry(
                        query_id=f"Q-{len(search_log_entries)+1}", query_text=query[:200],
                        provenance=provenance, issued_after_stage=f"r{round_num}",
                        pages_fetched=len(results),
                        query_status=QueryStatus.SUCCESS if results else QueryStatus.ZERO_RESULT,
                    ))
                    all_search_results.extend(results)

                # F4: Fetch full page content for top results
                try:
                    await fetch_pages_for_results(all_search_results, max_pages=5)
                except BrainError:
                    raise
                except Exception as e:
                    raise BrainError(
                        f"page_fetch_round{round_num}",
                        f"Page fetch failed",
                        detail=str(e),
                    )

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
                            raise
                        except Exception as e:
                            raise BrainError(
                                f"evidence_extract_round{round_num}",
                                f"Evidence extraction failed for {sr.url[:80]}",
                                detail=str(e),
                            )
                    else:
                        # Fallback: use snippet/title as before
                        ev = EvidenceItem_from_search_result(sr, len(evidence.items))
                        if ev and evidence.add(ev):
                            total_admitted += 1

                # Wire evidence contradictions into blocker ledger
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
                     "fact": e.fact, "url": e.url, "score": e.score,
                     "confidence": e.confidence.value}
                    for e in evidence.items
                ]
                st.evidence_count = len(evidence.items)

                if self._checkpoint(f"search{round_num}"):
                    return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=f"[STOPPED AT SEARCH{round_num}]", preflight=preflight_result)

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

        # --- Semantic Contradiction (V9) ---
        if not self._stage_done("semantic_contradiction"):
            log._print("  [SEMANTIC] Running semantic contradiction pass...")
            t0 = time.monotonic()
            semantic_ctrs = await run_semantic_contradiction_pass(self._llm, evidence.active_items)
            log._print(f"  [SEMANTIC] {len(semantic_ctrs)} semantic contradictions ({time.monotonic() - t0:.1f}s)")
            self._checkpoint("semantic_contradiction")

        # --- Decisive Claim Extraction (V9) ---
        if not self._stage_done("decisive_claims"):
            log._print("  [CLAIMS] Extracting decisive claims...")
            t0 = time.monotonic()
            decisive_claims = await extract_decisive_claims(
                self._llm, final_views=prior_views, evidence_text=evidence.format_for_prompt(),
            )
            log._print(f"  [CLAIMS] {len(decisive_claims)} decisive claims ({time.monotonic() - t0:.1f}s)")
            proof.set_decisive_claims(decisive_claims)
            self._checkpoint("decisive_claims")

        # --- Synthesis Packet (V9) ---
        packet = build_synthesis_packet(
            brief=brief_for_sonnet,
            final_positions=final_positions,
            arguments=[a for args in argument_tracker.arguments_by_round.values() for a in args],
            frames=divergence_result.alt_frames if hasattr(divergence_result, 'alt_frames') else [],
            blockers=blocker_ledger.blockers,
            decisive_claims=decisive_claims,
            contradictions_numeric=evidence.contradictions,
            contradictions_semantic=semantic_ctrs,
            premise_flags=preflight_result.premise_flags,
            evidence_items=evidence.active_items,
        )
        synthesis_packet_text = format_synthesis_packet_for_prompt(packet)
        if is_analysis_mode:
            synthesis_packet_text += get_analysis_synthesis_contract()
        proof.set_synthesis_packet(packet)
        self._checkpoint("synthesis_packet")

        # Record arguments with resolution status in proof
        all_args = []
        for rnd_args in argument_tracker.arguments_by_round.values():
            all_args.extend(rnd_args)
        proof.set_arguments(all_args)

        # --- Synthesis Gate ---
        t0 = time.monotonic()
        final_views = prior_views
        report, report_json, dispositions = await run_synthesis(
            self._llm, brief=brief_for_sonnet, final_views=final_views,
            blocker_summary=blocker_ledger.summary(),
            outcome_class=outcome_class,
            evidence_text=evidence.format_for_prompt(),
            synthesis_packet_text=synthesis_packet_text,
        )
        log.synthesis_result(len(report), bool(report_json), time.monotonic() - t0)
        proof.set_synthesis_status("COMPLETE" if report else "FAILED")
        st.report = report[:5000]
        st.report_json = report_json

        if self._checkpoint("synthesis"):
            return BrainResult(outcome=Outcome.ESCALATE, proof=proof.build(), report=report, preflight=preflight_result)

        # --- ANALYSIS mode proof additions ---
        if is_analysis_mode:
            # DOD §18.5: "ANALYSIS output contains verdict language → ERROR"
            # Check the header — ANALYSIS must have "EXPLORATORY MAP" header, not verdict/recommendation
            report_header = (report[:500] if report else "").lower()
            if report and "exploratory map" not in report_header:
                # Missing required header — check for explicit decision language
                decision_phrases = ["we recommend", "our recommendation is", "the answer is",
                                    "therefore we decide", "we conclude that you should"]
                verdict_found = [p for p in decision_phrases if p in report_header]
                if verdict_found:
                    raise BrainError(
                        "analysis_verdict_check",
                        f"ANALYSIS output contains verdict language in header: {verdict_found[:3]}",
                        detail="DOD §18.5: ANALYSIS mode must produce exploratory map, not verdict.",
                    )

            # Analysis map: DOD §18.3 — hierarchical object keyed by dimension_id
            analysis_map = {
                "header": "EXPLORATORY MAP — NOT A DECISION",
                "dimensions": {},
                "hypothesis_ledger": [],
                "total_argument_count": len(all_args),
                "dimension_coverage_score": dimension_result.dimension_coverage_score,
            }
            if report_json and isinstance(report_json, dict):
                for key in report_json:
                    if key.startswith("DIM-"):
                        analysis_map["dimensions"][key] = report_json[key]
                    elif key == "hypothesis_ledger":
                        analysis_map["hypothesis_ledger"] = report_json[key]
            proof.set_analysis_map(analysis_map)

            # DOD §18.4: debug sunset enforcement
            # Counter persisted via file in outdir
            sunset_file = Path(self._config.outdir) / ".analysis_debug_remaining"
            if sunset_file.exists():
                try:
                    remaining = int(sunset_file.read_text().strip())
                except (ValueError, OSError):
                    remaining = self._config.analysis_debug_runs_remaining
            else:
                remaining = self._config.analysis_debug_runs_remaining

            debug_active = remaining > 0
            new_remaining = max(0, remaining - 1) if debug_active else 0
            # Persist decremented counter
            try:
                sunset_file.parent.mkdir(parents=True, exist_ok=True)
                sunset_file.write_text(str(new_remaining))
            except OSError:
                pass  # Non-fatal: counter resets next run

            # DOD §18.4 schema: debug_gate2_result and actual_output
            # filled after Gate 2 runs (stored as placeholders, updated below)
            analysis_debug_data = {
                "debug_mode": debug_active,
                "debug_gate2_result": None,  # Filled after Gate 2
                "actual_output": None,  # Filled after Gate 2
                "rules_enforced": not debug_active,  # Rules always enforced; debug affects audit only
                "remaining_debug_runs": new_remaining,
                "analysis_mode_active": True,
                "dimension_coverage_score": dimension_result.dimension_coverage_score,
            }
            proof.set_analysis_debug(analysis_debug_data)

        # --- Stability Tests (V9) ---
        stability_result = run_stability_tests(
            positions=final_positions,
            decisive_claims=decisive_claims,
            assumptions=preflight_result.critical_assumptions,
            round_positions=position_tracker.positions_by_round,
            question_class=preflight_result.question_class,
            stakes_class=preflight_result.stakes_class,
            independent_evidence_present=evidence.high_authority_evidence_present,
        )
        proof.set_stability(stability_result)
        self._checkpoint("stability")
        log._print(f"  [STABILITY] conclusion={stability_result.conclusion_stable} "
                   f"reason={stability_result.reason_stable} "
                   f"assumption={stability_result.assumption_stable} "
                   f"groupthink_warning={stability_result.groupthink_warning}")

        # --- Compute dimension coverage + register COVERAGE_GAP blockers (V9) ---
        if dimension_result and dimension_result.items:
            for dim in dimension_result.items:
                dim_args = [a for a in all_args if a.dimension_id == dim.dimension_id]
                dim.argument_count = len(dim_args)
                dim.coverage_status = "SATISFIED" if len(dim_args) >= 2 else ("PARTIAL" if dim_args else "ZERO")
                # Register COVERAGE_GAP blocker for zero-coverage mandatory dimensions
                if dim.coverage_status == "ZERO" and dim.mandatory and not dim.justified_irrelevance:
                    blocker_ledger.add(
                        kind=BlockerKind.COVERAGE_GAP,
                        source=f"dimension:{dim.dimension_id}",
                        detected_round=self._config.rounds,
                        detail=f"Zero arguments for mandatory dimension: {dim.name}",
                        models=[],
                        severity="CRITICAL",
                    )
            covered = sum(1 for d in dimension_result.items if d.argument_count >= 2)
            dimension_result.dimension_coverage_score = covered / len(dimension_result.items) if dimension_result.items else 0.0

        # --- V9: Evidence refs validation (DOD §10.3) ---
        # "Cited evidence missing from both stores → ERROR"
        # Only validate when evidence was actually collected (search ran).
        # With no search, LLM may hallucinate E-IDs but there's nothing to validate against.
        if evidence.all_evidence_ids():
            all_evidence_refs = []
            for c in decisive_claims:
                all_evidence_refs.extend(c.evidence_refs)
            for a in all_args:
                all_evidence_refs.extend(a.evidence_refs)
            phantom_refs = evidence.validate_refs(all_evidence_refs)
            if phantom_refs:
                # DOD §10.3 + §1.2: phantom evidence is not infrastructure failure → ESCALATE via blocker
                blocker_ledger.add(
                    kind=BlockerKind.UNVERIFIED_CLAIM,
                    source="evidence_validation",
                    detected_round=self._config.rounds,
                    detail=f"Cited evidence missing from both stores: {phantom_refs[:5]}",
                    models=[],
                    severity="CRITICAL",
                )

        # --- V9: Disposition Coverage Verification (runs BEFORE Gate 2 per DOD §14.6) ---
        from thinker.types import DispositionObject, DispositionTargetType
        disposition_objects = []
        for d in dispositions:
            try:
                disposition_objects.append(DispositionObject(
                    target_type=DispositionTargetType(d["target_type"]),
                    target_id=d["target_id"],
                    status=d["status"],
                    importance=d["importance"],
                    narrative_explanation=d["narrative_explanation"],
                ))
            except (ValueError, KeyError):
                pass

        active_frames_for_residue = [f for f in divergence_result.alt_frames
                         if f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)]
        coverage = check_disposition_coverage(
            dispositions=disposition_objects,
            open_blockers=blocker_ledger.blockers,
            active_frames=active_frames_for_residue,
            decisive_claims=decisive_claims,
            contradictions_numeric=evidence.contradictions,
            contradictions_semantic=semantic_ctrs,
            open_material_arguments=argument_tracker.all_unaddressed,  # DOD §11.3
        )
        proof.set_residue_verification(coverage)
        proof.set_synthesis_dispositions(disposition_objects)

        if coverage.get("deep_scan_triggered"):
            # DOD §14.6: deep scan MUST run when triggered
            deep_scan_result = run_deep_semantic_scan(report, coverage.get("omissions", []))
            coverage["deep_scan"] = deep_scan_result
            proof.set_residue_verification(coverage)  # Update with deep scan data
            if deep_scan_result["material_omissions_remain"]:
                # DOD §14.6: "Material omissions unresolved after deep scan → ESCALATE"
                # Register CRITICAL blocker so D6 triggers ESCALATE
                blocker_ledger.add(
                    kind=BlockerKind.COVERAGE_GAP,
                    source="deep_semantic_scan",
                    detected_round=self._config.rounds,
                    detail=(f"Deep scan: {deep_scan_result['still_missing']} material omissions "
                            f"remain after scan (omission rate {coverage['omission_rate']:.0%})"),
                    models=[],
                    severity="CRITICAL",
                )

        # Legacy string-match residue check (supplementary)
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

        # --- Gate 2 (deterministic) ---
        # Compute stage integrity for D1 (DOD §3.3)
        # Include conditional stages that should have executed
        required_stages = ["preflight", "dimensions"]
        for i in range(1, self._config.rounds + 1):
            required_stages.append(f"r{i}")
            required_stages.append(f"track{i}")
            if i == 1:
                required_stages.extend(["perspective_cards", "framing_pass"])
                if not is_analysis_mode:  # DOD §9.3: ungrounded DECIDE only
                    required_stages.append("ungrounded_r1")
            if i == 2:
                required_stages.append("frame_survival_r2")
                if not is_analysis_mode:
                    required_stages.append("ungrounded_r2")
            if i == 3:
                required_stages.append("frame_survival_r3")
        required_stages.extend(["semantic_contradiction", "decisive_claims", "synthesis_packet", "synthesis"])
        completed = set(self.state.completed_stages)
        fatal_stages = [s for s in required_stages if s not in completed]

        # DOD §11.3: broken supersession links → ERROR-level violations (BEFORE Gate 2)
        for bl in argument_tracker._broken_supersession_links:
            proof.add_violation(
                "SUPERSESSION-BROKEN", "ERROR",
                f"Argument {bl['argument_id']} claimed superseded_by {bl['claimed_superseded_by']} "
                f"but target not found: {bl['reason']}",
            )

        # Merge numeric + semantic contradictions for Gate 2 (DOD §16 D8)
        all_contradictions = list(evidence.contradictions) + list(semantic_ctrs)

        gate2 = run_gate2_deterministic(
            agreement_ratio=agreement,
            positions=final_positions,
            contradictions=all_contradictions,
            unaddressed_arguments=argument_tracker.all_unaddressed,
            open_blockers=blocker_ledger.open_blockers(),
            evidence_count=len(evidence.items),
            search_enabled=search_enabled,
            preflight=preflight_result,
            divergence=divergence_result,
            stability=stability_result,
            decisive_claims=decisive_claims,
            dimensions=dimension_result,
            total_arguments=len(all_args),
            archive_evidence_count=len(evidence.archive_items),
            stage_integrity_fatal=fatal_stages if fatal_stages else None,
        )
        log.gate2_result(
            gate2.outcome.value, agreement, outcome_class,
            len(all_ignored), len(evidence.items),
            len(evidence.contradictions), len(blocker_ledger.open_blockers()),
        )
        st.outcome = gate2.outcome.value

        # Record gate2 trace in proof (V9)
        if gate2.rule_trace:
            proof.set_gate2_trace(
                modality=gate2.modality or "DECIDE",
                rule_trace=gate2.rule_trace,
                final_outcome=gate2.outcome.value,
            )

        # DOD §18.4: fill debug_gate2_result and actual_output after Gate 2
        if is_analysis_mode and proof._analysis_debug:
            proof._analysis_debug["debug_gate2_result"] = gate2.outcome.value
            proof._analysis_debug["actual_output"] = gate2.outcome.value

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

        # --- Final: Wire all remaining proof sections ---
        outcome = gate2.outcome
        proof.set_outcome(outcome, agreement, outcome_class)
        proof.set_final_status("COMPLETE")
        proof.set_evidence_count(len(evidence.items))

        # Two-tier evidence
        proof.set_evidence_two_tier(evidence.active_items, evidence.archive_items, evidence.eviction_log)

        # Search log
        proof.set_search_log(search_log_entries)

        # Ungrounded stats (DOD §9.2 schema)
        # Mark claims that were verified by evidence after search
        for fc in st.ungrounded_flagged_claims:
            if fc["status"] == "UNVERIFIED_CLAIM" and fc["blocker_id"] is None:
                # Check if the stat now appears in evidence
                stat_text = fc["text"]
                if any(stat_text in ev.fact for ev in evidence.active_items):
                    fc["verified"] = True
                    fc["status"] = "CLEAR"
        proof.set_ungrounded_stats({
            "post_r1_executed": st.ungrounded_r1_executed,
            "post_r2_executed": st.ungrounded_r2_executed,
            "flagged_claims": st.ungrounded_flagged_claims,
        })

        # Contradictions (numeric + semantic)
        proof.set_contradictions(evidence.contradictions, semantic_ctrs)

        # Cross-domain analogies from divergence
        if divergence_result.cross_domain_analogies:
            proof.set_analogies(divergence_result.cross_domain_analogies)

        # Stage integrity
        proof.set_stage_integrity(
            required=required_stages + ["gate2"],
            order=self.state.completed_stages,
            fatal=fatal_stages,
        )

        # Diagnostics
        proof.set_diagnostics({
            "total_elapsed_s": round(time.monotonic() - run_start_time, 1),
            "rounds_completed": self._config.rounds,
            "search_enabled": search_enabled,
            "models_used": list(set(m for rnd in st.round_responded.values() for m in rnd)),
        })

        # DOD §19: synthesis_output and timestamp_completed
        proof.set_synthesis_output({
            "report": report[:5000] if report else None,
            "report_json": st.report_json,
        })
        proof.set_timestamp_completed()
        proof.set_error_class(None)  # No error if we reach here

        # --- Acceptance status (F2) — must be computed last, after all violations ---
        proof.compute_acceptance_status()

        log.run_complete(outcome.value, outcome_class)

        return BrainResult(
            outcome=outcome, proof=proof.build(),
            report=report, preflight=preflight_result, gate2=gate2,
            dimensions=dimension_result,
            stability=stability_result,
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
                        help="Stop after STAGE, save checkpoint (preflight,dimensions,r1,track1,...)")
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
        # DOD §19: write partial proof.json on ERROR
        if hasattr(e, 'partial_proof') and e.partial_proof:
            error_proof_path = os.path.join(args.outdir, "proof.json")
            with open(error_proof_path, "w", encoding="utf-8") as f:
                json.dump(e.partial_proof, f, indent=2)
            print(f"  Proof:   {error_proof_path} (partial — error_class set)")
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
    import thinker.preflight, thinker.rounds, thinker.argument_tracker  # noqa: F401
    import thinker.tools.position, thinker.search, thinker.synthesis, thinker.gate2  # noqa: F401
    import thinker.invariant, thinker.residue, thinker.page_fetch, thinker.evidence_extractor  # noqa: F401
    import thinker.preflight, thinker.dimension_seeder  # noqa: F401
    import thinker.perspective_cards, thinker.divergent_framing  # noqa: F401
    import thinker.semantic_contradiction, thinker.stability  # noqa: F401
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
