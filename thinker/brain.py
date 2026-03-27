"""Brain Orchestrator — wires the full V8 deliberation pipeline.

Flow:
  Gate 1 -> R1 -> Search -> [Argument Track -> Round -> Search] x (rounds-1) -> Synthesis -> Gate 2

V8 spec Section 4.
"""
from __future__ import annotations

import time
from typing import Callable, Awaitable, Optional

from thinker.argument_tracker import ArgumentTracker
from thinker.config import BrainConfig, ROUND_TOPOLOGY
from thinker.evidence import EvidenceLedger
from thinker.gate1 import run_gate1
from thinker.gate2 import run_gate2
from thinker.proof import ProofBuilder
from thinker.rounds import execute_round
from thinker.search import SearchOrchestrator, SearchPhase
from thinker.synthesis import run_synthesis
from thinker.tools.blocker import BlockerLedger
from thinker.tools.position import PositionTracker
from thinker.tools.ungrounded import find_ungrounded_stats
from thinker.types import BrainResult, Outcome, SearchResult


class Brain:
    """The V8 Brain deliberation engine.

    Usage:
        brain = Brain(config, llm_client, search_fn)
        result = await brain.run(brief)
        # result.outcome is DECIDE, ESCALATE, or NEED_MORE
        # result.proof is the proof.json dict
        # result.report is the Hermes markdown
    """

    def __init__(
        self,
        config: BrainConfig,
        llm_client,
        search_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
    ):
        self._config = config
        self._llm = llm_client
        self._search_fn = search_fn

    async def run(self, brief: str) -> BrainResult:
        """Execute a full Brain deliberation."""
        run_id = f"brain-{int(time.time())}"
        proof = ProofBuilder(run_id, brief, self._config.rounds)
        evidence = EvidenceLedger(max_items=self._config.max_evidence_items)
        argument_tracker = ArgumentTracker(self._llm)
        position_tracker = PositionTracker(self._llm)
        blocker_ledger = BlockerLedger()
        proof.set_blocker_ledger(blocker_ledger)

        # --- Gate 1 ---
        gate1 = await run_gate1(self._llm, brief)
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
            # Execute round
            round_result = await execute_round(
                self._llm, round_num=round_num, brief=brief,
                prior_views=prior_views if round_num > 1 else None,
                evidence_text=evidence.format_for_prompt() if round_num > 1 else "",
                unaddressed_arguments=unaddressed_text if round_num > 1 else "",
            )
            proof.record_round(round_num, round_result.responded, round_result.failed)

            if not round_result.responded:
                proof.set_final_status("FAILED_NO_RESPONSES")
                proof.add_violation("BV1", "FATAL", f"No models responded in round {round_num}")
                return BrainResult(
                    outcome=Outcome.ESCALATE, proof=proof.build(),
                    report="", gate1=gate1,
                )

            # Extract arguments
            await argument_tracker.extract_arguments(round_num, round_result.texts)

            # Extract positions
            positions = await position_tracker.extract_positions(round_num, round_result.texts)
            proof.record_positions(round_num, positions)

            # Track position changes
            if round_num > 1:
                changes = position_tracker.get_position_changes(round_num - 1, round_num)
                proof.record_position_changes(changes)

            # Search phase (between rounds, not after the last round)
            if round_num < self._config.rounds and self._search_fn:
                search_orch = SearchOrchestrator(
                    self._llm, search_fn=self._search_fn,
                )
                phase = SearchPhase.R1_R2 if round_num == 1 else SearchPhase.R2_R3

                reactive = await search_orch.generate_reactive_queries(round_result.texts)
                proactive = await search_orch.generate_proactive_queries(round_result.texts)
                queries = search_orch.deduplicate(reactive + proactive)

                total_admitted = 0
                for query in queries[:self._config.max_search_queries_per_phase]:
                    results = await search_orch.execute_query(query, phase)
                    for sr in results:
                        if sr.full_content:
                            facts = await search_orch.extract_facts(sr.full_content, sr.url, query)
                            for fact in facts:
                                if evidence.add(fact):
                                    total_admitted += 1

                proof.record_research_phase(
                    phase.value, "playwright", len(queries), total_admitted,
                )

            # Compare arguments (after R2+)
            if round_num > 1:
                unaddressed = await argument_tracker.compare_with_round(
                    round_num - 1, round_result.texts,
                )
                unaddressed_text = argument_tracker.format_reinjection(unaddressed)

            # Prepare prior views for next round
            prior_views = round_result.texts

        # --- Synthesis ---
        final_views = prior_views  # Last round's outputs
        report = await run_synthesis(
            self._llm, brief=brief, final_views=final_views,
            blocker_summary=blocker_ledger.summary(),
        )
        proof.set_synthesis_status("COMPLETE" if "DEGRADED" not in report else "DEGRADED")

        # --- Gate 2 ---
        final_round = self._config.rounds
        agreement = position_tracker.agreement_ratio(final_round)
        final_positions = position_tracker.positions_by_round.get(final_round, {})
        gate2 = await run_gate2(
            self._llm,
            agreement_ratio=agreement,
            positions=final_positions,
            contradictions=[],  # TODO: wire contradiction detector
            unaddressed_arguments=argument_tracker.all_unaddressed,
            open_blockers=blocker_ledger.open_blockers(),
            evidence_count=len(evidence.items),
            report_text=report,
        )

        # --- Final status ---
        outcome = gate2.outcome
        outcome_class = "CONSENSUS" if agreement >= 0.8 else "PARTIAL_CONSENSUS" if agreement >= 0.5 else "NO_CONSENSUS"
        proof.set_outcome(outcome, agreement, outcome_class)
        proof.set_final_status("COMPLETE")
        proof.set_evidence_count(len(evidence.items))

        return BrainResult(
            outcome=outcome, proof=proof.build(),
            report=report, gate1=gate1, gate2=gate2,
        )


async def main():
    """CLI entry point for the Brain engine."""
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser(description="Thinker V8 Brain Engine")
    parser.add_argument("--brief", required=True, help="Path to brief markdown file")
    parser.add_argument("--rounds", type=int, default=4, help="Number of rounds (1-4)")
    parser.add_argument("--budget", type=int, default=3600, help="Wall clock budget in seconds")
    parser.add_argument("--outdir", default="./output", help="Output directory")
    args = parser.parse_args()

    brief_text = open(args.brief, encoding="utf-8").read()
    config = BrainConfig(
        rounds=args.rounds,
        wall_clock_budget_s=args.budget,
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        zai_api_key=os.environ.get("ZAI_API_KEY", ""),
        brave_api_key=os.environ.get("BRAVE_API_KEY", ""),
        outdir=args.outdir,
    )

    from thinker.llm import LLMClient
    from thinker.playwright_search import google_search
    llm = LLMClient(config)

    brain = Brain(config=config, llm_client=llm, search_fn=google_search)
    result = await brain.run(brief_text)

    os.makedirs(args.outdir, exist_ok=True)
    proof_path = os.path.join(args.outdir, "proof.json")
    with open(proof_path, "w", encoding="utf-8") as f:
        json.dump(result.proof, f, indent=2)
    report_path = os.path.join(args.outdir, "hermes-final-report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result.report)

    print(f"Outcome: {result.outcome.value}")
    print(f"Proof: {proof_path}")
    print(f"Report: {report_path}")

    await llm.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
