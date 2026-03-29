# V8 Brain — Handoff to Next Conversation

**Date:** 2026-03-29
**Repo:** https://github.com/mralfrednemo-maker/brain-v8
**Latest commit:** `0c59d13` on master
**Code:** `C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8\`

---

## Read These First (in order)

1. `V8-DOD.md` — Definition of Done. What's done, what's not, design constraints.
2. `HANDOFF.md` — Architecture overview, providers, key files, live run results.
3. `OPERATIONS.md` — How to run, CLI flags, debug, troubleshooting.
4. `_audit_thinker/THINKER-DOD-AND-PLAN.md` — Parent DoD for full platform.
5. `_audit_thinker/docs/superpowers/specs/2026-03-26-thinker-v8-architecture-design.md` — Original V8 spec.

---

## What Was Built (this session)

- Resume from checkpoint (`--resume`)
- Sonar search for repeat topics
- Per-framework position extraction
- Position validation against MODEL_REGISTRY
- Bing free search via curl_cffi (primary, $0)
- Brave API search (fallback, $0.01/query)
- Zero-tolerance error handling (BrainError)
- Step-by-step as default (`--full-run` to override)
- All Daedalus audit fixes (2 rounds)
- 103 unit tests, 6 briefs tested live

## What To Build Next

### Features (priority order)

**V8-F1: Post-synthesis residue verification** (DoD D7)
- After synthesis Sonnet call, scan the report text
- Check: does the report mention every BLK ID from blocker ledger?
- Check: does the report mention every CTR ID from evidence contradictions?
- Check: does the report address the key unaddressed arguments?
- Add `synthesis_residue_omissions` list to proof.json
- If >30% of structural findings omitted → add violation to proof
- This is a narrative completeness check, not truth verification

**V8-F2: acceptance_status in proof** (DoD D10)
- Add `acceptance_status` field to proof.json
- ACCEPTED: clean run, no violations
- ACCEPTED_WITH_WARNINGS: run completed but with warnings (e.g. 0 evidence, some search failures)
- Never REJECTED — if something is fatal, BrainError stops the pipeline before proof is written
- Compute after Gate 2, before proof finalization

**V8-F3: Evidence priority scoring** (DoD D2)
- Current: FIFO cap (first 10 items kept, rest rejected)
- Needed: incoming evidence scored for relevance. Under cap pressure, evict lowest-scored item
- Score factors: keyword overlap with brief, source authority (domain reputation), freshness
- Keep insertion order within same score tier (trust search ranking)

**V8-F4: Full page content fetch** (Spec §6)
- After search returns URLs, fetch top N pages via httpx
- Extract page text (strip HTML tags)
- Truncate to max_chars (e.g. 50k)
- Store in SearchResult.full_content
- This gives models real articles instead of 200-char snippets

**V8-F5: LLM-based evidence extraction** (Spec §6)
- After fetching full page content, one Sonnet call per page
- Extract: specific facts, numbers, dates, regulatory references
- Output: structured fact items for evidence ledger
- This replaces raw snippet injection with curated facts

**V8-F6: Invariant validator** (Spec §4)
- Run after Gate 2, before proof finalization
- Checks: positions extracted for every round, all rounds have responses, evidence IDs are sequential, no orphaned BLK/CTR references
- Add violations to proof with severity (WARN or ERROR)
- Feeds into acceptance_status (V8-F2)

### Bug Fixes

**V8-B1: Bing search titles/snippets**
- Current: Bing returns URLs but no titles or snippets (data-url extraction)
- Fix: Tied to V8-F4 — fetch pages to get content
- Alternative: Parse `<cite>` tags and nearby `<p>` text more aggressively

**V8-B2: Checkpoint schema versioning**
- Add `checkpoint_version: str = "1.0"` to PipelineState
- On load, check version matches current code
- If mismatch, warn or error (prevents loading incompatible checkpoints)

**V8-B3: Position components lost on resume**
- `_restore_trackers` creates Position with `components=[option]`
- Should store full `components` list in checkpoint (per-framework breakdown)
- Fix in PipelineState: store components in positions_by_round dict

**V8-B4: Test coverage gaps**
- 9 modules with 0 tests: checkpoint, debug, pipeline, brave_search, sonar_search, bing_search, blocker, cross_domain, playwright_search
- Add at least 1 test per module
- Priority: checkpoint (resume correctness), bing_search (primary search), blocker (wired but untested)

---

## Design Constraints (DO NOT CHANGE)

1. **Zero tolerance.** BrainError on any failure. No degraded mode.
2. **No budgets.** No wall clock limits, no token limits. Don't add them.
3. **Thinking models: 30k tokens, 720s timeout.** R1, Reasoner. Don't reduce.
4. **Non-thinking models: 8k-16k tokens.** Don't reduce.
5. **Gate 2 is deterministic.** No LLM call in Gate 2.
6. **Step-by-step is default.** `--full-run` to override.
7. **Bing free is primary search.** Brave is fallback. Don't swap without reason.
8. **FIFO evidence cap.** Trust search engine ranking order.

## Testing Protocol

- Step-by-step is default — every stage pauses
- Test each brief one at a time, one stage at a time
- Analyse output at each stage before continuing
- If ANY error: stop, fix, re-run from that stage
- Never batch-run multiple briefs in parallel during debug phase
- Test briefs: `tests/fixtures/briefs/` (b1, b4, b7, b8, b9, b10)

## Key Files

```
thinker-v8/
├── .env                     # API keys (gitignored)
├── V8-DOD.md                # Definition of Done
├── HANDOFF.md               # Architecture overview
├── HANDOFF-NEXT.md           # THIS FILE — next session handoff
├── OPERATIONS.md            # How to run
├── brain-debug.sh           # Wrapper script
├── test_search_standalone.py # Search diagnostics
├── thinker/
│   ├── brain.py             # Orchestrator + CLI
│   ├── checkpoint.py        # Stop/resume
│   ├── config.py            # Models, topology
│   ├── types.py             # BrainError, all types
│   ├── llm.py               # 4-provider LLM client
│   ├── gate1.py             # Gate 1 (Sonnet)
│   ├── gate2.py             # Gate 2 (deterministic)
│   ├── rounds.py            # Round execution
│   ├── search.py            # Search orchestrator
│   ├── synthesis.py         # Synthesis gate
│   ├── argument_tracker.py  # Core V8 innovation
│   ├── evidence.py          # Evidence ledger
│   ├── proof.py             # Proof builder
│   ├── bing_search.py       # Primary search (free)
│   ├── brave_search.py      # Fallback search ($0.01)
│   ├── sonar_search.py      # Repeat topic search
│   └── tools/
│       ├── position.py      # Per-framework positions
│       ├── contradiction.py
│       ├── ungrounded.py
│       ├── blocker.py
│       └── cross_domain.py
└── tests/                   # 103 tests
```
