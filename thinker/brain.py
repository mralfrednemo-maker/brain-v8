"""Brain Orchestrator — wires the full V8 deliberation pipeline.

Flow:
  Gate 1 -> R1 -> Search(R1) -> R2 -> Search(R2) -> R3 -> Synthesis Gate -> Deterministic Gate 2

Debug modes:
  --verbose    : Full logging at each stage
  --step       : Pause at each stage, inspect data, press Enter to continue
"""
from __future__ import annotations

import time
from typing import Callable, Awaitable, Optional

from thinker.argument_tracker import ArgumentTracker
from thinker.config import BrainConfig, ROUND_TOPOLOGY
from thinker.debug import RunLog
from thinker.evidence import EvidenceLedger
from thinker.gate1 import run_gate1
from thinker.gate2 import run_gate2_deterministic, classify_outcome
from thinker.proof import ProofBuilder
from thinker.rounds import execute_round
from thinker.search import SearchOrchestrator, SearchPhase
from thinker.synthesis import run_synthesis
from thinker.tools.blocker import BlockerLedger
from thinker.tools.position import PositionTracker
from thinker.types import ArgumentStatus, BrainResult, Outcome, SearchResult


class Brain:
    """The V8 Brain deliberation engine."""

    def __init__(
        self,
        config: BrainConfig,
        llm_client,
        search_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        verbose: bool = False,
        step: bool = False,
    ):
        self._config = config
        self._llm = llm_client
        self._search_fn = search_fn
        self.log = RunLog(verbose=verbose, step=step)

    async def run(self, brief: str) -> BrainResult:
        """Execute a full Brain deliberation."""
        log = self.log
        run_id = f"brain-{int(time.time())}"
        proof = ProofBuilder(run_id, brief, self._config.rounds)
        evidence = EvidenceLedger(max_items=self._config.max_evidence_items)
        argument_tracker = ArgumentTracker(self._llm)
        position_tracker = PositionTracker(self._llm)
        blocker_ledger = BlockerLedger()
        search_enabled = self._search_fn is not None
        search_orch = SearchOrchestrator(
            self._llm, search_fn=self._search_fn,
        ) if search_enabled else None
        proof.set_blocker_ledger(blocker_ledger)

        # --- Gate 1 ---
        log.gate1_start(len(brief))
        t0 = time.monotonic()
        gate1 = await run_gate1(self._llm, brief)
        log.gate1_result(gate1.passed, gate1.reasoning, gate1.questions, time.monotonic() - t0)

        if not gate1.passed:
            proof.set_final_status("GATE1_REJECTED")
            return BrainResult(
                outcome=gate1.outcome, proof=proof.build(),
                report="", gate1=gate1,
            )

        # --- Deliberation Rounds ---
        prior_views: dict[str, str] = {}
        unaddressed_text = ""

        for round_num in range(1, self._config.rounds + 1):
            is_last_round = round_num == self._config.rounds
            models = ROUND_TOPOLOGY[round_num]
            log.round_start(round_num, models, is_last_round)

            # Execute round
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

            if not round_result.responded:
                proof.set_final_status("FAILED_NO_RESPONSES")
                proof.add_violation("BV1", "FATAL", f"No models responded in round {round_num}")
                return BrainResult(
                    outcome=Outcome.ESCALATE, proof=proof.build(),
                    report="", gate1=gate1,
                )

            # Extract arguments
            t0 = time.monotonic()
            args = await argument_tracker.extract_arguments(round_num, round_result.texts)
            log.arg_extract(round_num, args, time.monotonic() - t0, argument_tracker.last_raw_response)

            # Extract positions
            t0 = time.monotonic()
            positions = await position_tracker.extract_positions(round_num, round_result.texts)
            log.pos_extract(round_num, positions, time.monotonic() - t0, position_tracker.last_raw_response)
            proof.record_positions(round_num, positions)

            # Track position changes
            if round_num > 1:
                changes = position_tracker.get_position_changes(round_num - 1, round_num)
                log.pos_changes(round_num - 1, round_num, changes)
                proof.record_position_changes(changes)

            # Search phase — after R1 and R2 only
            if not is_last_round and search_orch:
                phase = SearchPhase.R1_R2 if round_num == 1 else SearchPhase.R2_R3
                t0 = time.monotonic()

                model_requests = search_orch.collect_model_requests(round_result.texts)
                proactive = await search_orch.generate_proactive_queries(
                    round_result.texts, already_queued=model_requests,
                )
                queries = search_orch.deduplicate(model_requests + proactive)
                log.search_start(phase.value, model_requests, proactive)

                total_admitted = 0
                for query in queries[:self._config.max_search_queries_per_phase]:
                    results = await search_orch.execute_query(query, phase)
                    for sr in results:
                        ev = EvidenceItem_from_search_result(sr, total_admitted)
                        if ev and evidence.add(ev):
                            total_admitted += 1

                log.search_result(phase.value, len(queries), total_admitted, time.monotonic() - t0)
                proof.record_research_phase(
                    phase.value, "brave", len(queries), total_admitted,
                )

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

        # --- Synthesis Gate ---
        t0 = time.monotonic()
        final_views = prior_views
        report, report_json = await run_synthesis(
            self._llm, brief=brief, final_views=final_views,
            blocker_summary=blocker_ledger.summary(),
            outcome_class=outcome_class,
        )
        log.synthesis_result(len(report), bool(report_json), time.monotonic() - t0)
        proof.set_synthesis_status("COMPLETE" if report else "FAILED")

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

        # --- Final ---
        outcome = gate2.outcome
        proof.set_outcome(outcome, agreement, outcome_class)
        proof.set_final_status("COMPLETE")
        proof.set_evidence_count(len(evidence.items))

        log.run_complete(outcome.value, outcome_class)

        return BrainResult(
            outcome=outcome, proof=proof.build(),
            report=report, gate1=gate1, gate2=gate2,
        )


def EvidenceItem_from_search_result(sr: SearchResult, counter: int):
    """Convert a SearchResult to an EvidenceItem for the ledger."""
    from thinker.types import Confidence, EvidenceItem
    content = sr.full_content or sr.snippet
    if not content:
        return None
    return EvidenceItem(
        evidence_id=f"E{counter + 1:03d}",
        topic=sr.title[:100],
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
    parser.add_argument("--budget", type=int, default=3600, help="Wall clock budget in seconds")
    parser.add_argument("--outdir", default="./output", help="Output directory")
    parser.add_argument("--verbose", action="store_true", help="Full logging at each stage")
    parser.add_argument("--step", action="store_true", help="Pause at each stage (implies --verbose)")
    args = parser.parse_args()

    brief_text = open(args.brief, encoding="utf-8").read()
    config = BrainConfig(
        rounds=args.rounds,
        wall_clock_budget_s=args.budget,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        anthropic_oauth_token=_get_anthropic_token(),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        zai_api_key=os.environ.get("ZAI_API_KEY", ""),
        brave_api_key=os.environ.get("BRAVE_API_KEY", ""),
        outdir=args.outdir,
    )

    from thinker.llm import LLMClient
    from thinker.brave_search import brave_search
    from functools import partial
    llm = LLMClient(config)

    search_fn = partial(brave_search, api_key=config.brave_api_key) if config.brave_api_key else None
    brain = Brain(
        config=config, llm_client=llm, search_fn=search_fn,
        verbose=args.verbose, step=args.step,
    )
    result = await brain.run(brief_text)

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
