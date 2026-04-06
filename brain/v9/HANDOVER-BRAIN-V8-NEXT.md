# V8 Brain — Handoff to Next Conversation

**Date:** 2026-03-29
**Repo:** https://github.com/mralfrednemo-maker/brain-v8
**Code:** `C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8\`

---

## Read These First (in order)

1. `V8-DOD.md` — Definition of Done. **ALL ITEMS COMPLETE.**
2. `HANDOFF.md` — Architecture overview, providers, key files.
3. `OPERATIONS.md` — How to run, CLI flags, debug, troubleshooting.

---

## What Was Built (this session — 2026-03-29)

### DoD Features (all complete, 218 tests)

| # | Feature | File | Tests |
|---|---------|------|-------|
| F1 | Post-synthesis residue verification | `thinker/residue.py` | 8 |
| F2 | acceptance_status in proof | `thinker/proof.py` + `thinker/types.py` | 5 |
| F3 | Evidence priority scoring with eviction | `thinker/evidence.py` | 7 |
| F4 | Full page content fetch | `thinker/page_fetch.py` | 11 |
| F5 | LLM-based evidence extraction | `thinker/evidence_extractor.py` | 11 |
| F6 | Invariant validator | `thinker/invariant.py` | 7 |

### DoD Bug Fixes (all complete)

| # | Fix | Detail |
|---|-----|--------|
| B1 | Bing empty titles/snippets | Fixed by F4 page fetch backfill |
| B2 | Checkpoint schema versioning | `CHECKPOINT_VERSION = "1.0"`, ValueError on mismatch |
| B3 | Position components lost on resume | Full components + kind saved/restored |
| B4 | 9 modules with 0 test coverage | All covered (103 → 218 tests) |

### Beyond-DoD Improvements

| Item | Detail |
|------|--------|
| Bing search replaced | curl_cffi → Playwright headful browser. Bing HTML changed, broke parser. |
| Gate 1 search decision | `SEARCH: YES/NO` recommendation. CLI `--search`/`--no-search` override. Recorded in proof.json. |
| Evidence serialization | Evidence items now saved to checkpoint (was missing). |
| Resume proof population | Skipped rounds now repopulate proof.json from checkpoint. |
| Markdown query stripping | Models wrapping queries in `*"..."*` caused 0 Bing results. |
| Architecture diagram | 11 stages registered, all new modules in pipeline flow. |

---

## Current Architecture (11 stages)

```
Gate 1 → R1(4) → Args → Pos → Search → Fetch → Extract →
R2(3) → Args → Pos → Search → Fetch → Extract →
R3(2) → Args → Pos → R4(2) → Args → Pos →
Synthesis → Gate 2 → Invariants → Residue → [acceptance_status]
```

## Search Provider

- **Primary:** Bing via Playwright headful browser (`bing_search.py`)
- Uses DOM extraction (`li.b_algo` → title, cite, snippet)
- Cite tags converted to real URLs (`_cite_to_url`)
- **No fallback.** If Bing fails, pipeline errors.
- Google is blocked (IP flagged). Brave API works but not used (Bing gives ranking).
- Headful mode required — headless gets fingerprinted.

## Search Decision Flow

```
CLI --search    → force search ON  (overrides Gate 1)
CLI --no-search → force search OFF (overrides Gate 1)
No flag         → Gate 1 decides (SEARCH: YES/NO based on brief content)
```

proof.json records: `search_decision.source`, `.value`, `.reasoning`, `.gate1_recommended` (if overridden)

## E2E Test Results (Playwright Bing, 2026-03-29)

| Brief | Topic | Verdict | Class | Agreement | Evidence |
|-------|-------|---------|-------|-----------|----------|
| b1 | JWT breach + GDPR/HIPAA/SOC2 | DECIDE | PARTIAL_CONSENSUS | 1.00 | 10 |
| b9 | DB migration (ClickHouse/Snowflake/PG) | DECIDE | PARTIAL_CONSENSUS | 1.00 | 10 |
| b10 | LLM banking risk + EU AI Act | ESCALATE | PARTIAL_CONSENSUS | 0.625 | 10 |

b10 ESCALATE is correct — EU AI Act classification has genuine disagreement that more evidence surfaced.

---

## Design Constraints (DO NOT CHANGE)

1. **Zero tolerance.** BrainError on any failure. No degraded mode.
2. **No budgets.** No wall clock limits, no token limits. Don't add them.
3. **Thinking models: 30k tokens, 720s timeout.** R1, Reasoner. Don't reduce.
4. **Non-thinking models: 8k-16k tokens.** Don't reduce.
5. **Gate 2 is deterministic.** No LLM call in Gate 2.
6. **Step-by-step is default.** `--full-run` to override.
7. **Bing Playwright is primary search.** Headful. No fallback.
8. **Evidence cap: 10 items.** F3 scoring for eviction. Trust search ranking within same score.

## Testing Protocol

- Step-by-step is default — every stage pauses
- Test each brief one at a time, one stage at a time
- Analyse output at each stage before continuing
- If ANY error: stop, fix, re-run from that stage
- Never batch-run multiple briefs in parallel during debug phase
- Test briefs: `tests/fixtures/briefs/` (b1, b4, b7, b8, b9, b10)

## What To Build Next

### Chamber (next major component)

Build from scratch, standalone. The Chamber is the multi-Brain orchestrator — runs multiple Brain instances in parallel with different framings and synthesizes across them.

See: `_audit_thinker/THINKER-DOD-AND-PLAN.md` for parent DoD.

### Potential Brain Improvements (not blocking Chamber)

- **Evidence cap increase** — Currently 10 items. With Playwright Bing returning 10 results per query and F5 extracting multiple facts per page, we're hitting the cap early. Consider increasing to 20-30.
- **Search phase 2 evidence** — R2-R3 search often admits 0 evidence because ledger is already full from R1-R2 search. Related to cap issue.
- **Residue threshold tuning** — 30% omission threshold fires on every run because synthesis can't reference 50+ argument IDs. May need to scale threshold with total findings count.

## Key Files

```
thinker-v8/
├── .env                          # API keys (gitignored)
├── V8-DOD.md                     # Definition of Done (ALL COMPLETE)
├── HANDOFF.md                    # Architecture overview
├── HANDOVER-BRAIN-V8-NEXT.md     # THIS FILE
├── OPERATIONS.md                 # How to run
├── thinker/
│   ├── brain.py                  # Orchestrator + CLI
│   ├── checkpoint.py             # Stop/resume (versioned)
│   ├── config.py                 # Models, topology
│   ├── types.py                  # BrainError, all types
│   ├── llm.py                    # 4-provider LLM client
│   ├── gate1.py                  # Gate 1 (Sonnet) + search decision
│   ├── gate2.py                  # Gate 2 (deterministic)
│   ├── rounds.py                 # Round execution
│   ├── search.py                 # Search orchestrator
│   ├── synthesis.py              # Synthesis gate
│   ├── argument_tracker.py       # Core V8 innovation
│   ├── evidence.py               # Evidence ledger + F3 scoring
│   ├── evidence_extractor.py     # F5: LLM fact extraction
│   ├── invariant.py              # F6: Structural integrity
│   ├── residue.py                # F1: Synthesis completeness
│   ├── page_fetch.py             # F4: httpx page fetch
│   ├── proof.py                  # Proof builder
│   ├── pipeline.py               # Stage registry + diagram
│   ├── debug.py                  # Logging infrastructure
│   ├── bing_search.py            # Playwright headful Bing
│   ├── brave_search.py           # Brave API (not used currently)
│   ├── sonar_search.py           # Sonar Pro (repeat topics)
│   └── tools/
│       ├── position.py           # Per-framework positions
│       ├── contradiction.py      # Numeric conflict detection
│       ├── ungrounded.py         # Ungrounded stat detector
│       ├── blocker.py            # Blocker lifecycle
│       └── cross_domain.py       # Domain filter
└── tests/                        # 218 tests
```
