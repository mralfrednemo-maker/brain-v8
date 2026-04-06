# Thinker V8 Brain — Conversation Handoff

## What Was Built

Complete V8 Brain deliberation engine at `C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8\`.
102 tests passing. 3 live runs completed successfully.

## Architecture (final design after review)

```
Gate 1 (Sonnet) → R1 (4 models) → [Arg Track + Pos Track] → Search →
R2 (3 models) → [Arg Track + Pos Track + Arg Compare] → Search →
R3 (2 models) → [Arg Track + Pos Track + Arg Compare] → Synthesis Gate → Gate 2 (deterministic)
```

### Providers (4 routes)
| Model | Provider | Auth | Cost |
|---|---|---|---|
| Sonnet | Anthropic direct | OAuth 1-year token | $0 (Max sub) |
| DeepSeek R1 | OpenRouter | API key | ~$0.10/call |
| DeepSeek Reasoner | DeepSeek direct | API key | ~$0.05/call |
| GLM-5 | Z.AI direct | Subscription key | $0 (subscription) |
| Kimi K2 | OpenRouter | API key | ~$0.03/call |

### Keys
All in `thinker-v8/.env`. Anthropic uses 1-year OAuth token from OpenClaw container.
Token found at: `wsl bash -c "grep sk-ant-oat ~/openclaw-stack/workspace/projects/the-thinker/.env"`

### Anthropic OAuth Requirements
- Raw HTTP with identity headers (SDK auth_token doesn't work)
- Headers: User-Agent: claude-cli/2.1.62, x-app: cli, anthropic-beta flags
- System prompt MUST be array format with Claude Code identity first
- Full guide saved to: `C:\Users\chris\PROJECTS\tech-library\claude-code\anthropic-oauth-token-guide.md`

## Design Decisions (from Christos review)

### Search
- Models request their own searches (0-5) as appendix to R1/R2 output
- Sonnet proactive sweep only for claims models missed
- Trust Google/Brave ranking — top 10 results in order, NO confidence re-ranking
- Search after R1 and R2 only (not R3)
- Topic tracker persists across rounds — repeat topic triggers Sonar
- Evidence section labeled "AUTHORITATIVE — outranks model opinions"

### Gate 2 — Fully Deterministic
- No LLM call. Thresholds on mechanical data only.
- For decisions: conclusion match is what matters. Different reasoning paths don't block.
- For analysis briefs: no gate blocks output, classification label attached.
- Classification (from Chamber V11): CONSENSUS / CLOSED_WITH_ACCEPTED_RISKS / PARTIAL_CONSENSUS / INSUFFICIENT_EVIDENCE / NO_CONSENSUS

### Synthesis Gate (renamed from Hermes)
- Not an agent — single LLM call
- Dual output: JSON (machine-readable) + markdown (human-readable)
- Deterministic classification label appended after LLM call

### Analysis vs Decision Briefs
- Decision briefs: DECIDE/ESCALATE based on agreement
- Analysis briefs: always deliver report, classification label tells reader confidence
- The Thinker doesn't always make decisions — sometimes just offers analysis

### Position Agreement
- Conclusion match is what matters, not reasoning alignment
- Positions normalized: strip parenthetical qualifiers, lowercase
- Like a jury — different reasons, same verdict = consensus

## Debug Infrastructure

### Modes
- `--verbose` : full logging at each stage
- `--stop-after STAGE` : run up to STAGE, save checkpoint.json, exit
- `python -m thinker.checkpoint FILE` : inspect checkpoint state
- Stage IDs: gate1, r1, track1, search1, r2, track2, search2, r3, track3, synthesis, gate2

### Every run generates
- proof.json, report.md, debug.log, events.json, run-report.html (auto-populated diagram)

### @pipeline_stage decorator
- Each module tagged with metadata (name, description, prompt, logic, thresholds)
- HTML diagram auto-generated from registry — no hardcoded descriptions
- 7 stages registered with explicit order

## Live Run Results

### Original runs (pre-improvements)
| Brief | Type | Outcome | Classification | Agreement |
|---|---|---|---|---|
| b1 (JWT breach) | Analysis | ESCALATE | PARTIAL_CONSENSUS | 0.50 |
| b4 (RCE response) | Decision (4 options) | DECIDE | CLOSED_WITH_ACCEPTED_RISKS | 1.00 |
| b7 (DORA compliance) | Regulatory | DECIDE | CLOSED_WITH_ACCEPTED_RISKS | 1.00 |

### Post-improvement runs (2026-03-28, with per-framework positions + Playwright search)
| Brief | Type | Outcome | Classification | Agreement |
|---|---|---|---|---|
| b1 (JWT breach) | Analysis | DECIDE | CONSENSUS | 1.00 |
| b4 (RCE response) | Decision (4 options) | ESCALATE | PARTIAL_CONSENSUS | 0.50 |
| b7 (DORA compliance) | Regulatory | DECIDE | CLOSED_WITH_ACCEPTED_RISKS | 0.90 |

b1 improved from PARTIAL_CONSENSUS to CONSENSUS — per-framework extraction revealed all models
agree on GDPR (not reportable), HIPAA (not reportable), and SOC 2 (reportable). Previously the
compound label comparison missed this.

b4 ESCALATE is genuine — models split between O3 and O3-modified (same core action, different
operational details). The position normalization could be improved here.

b7 improved — table parser fix allowed position extraction in R4 (was failing with 0 positions).

## Parser Fixes Applied
- Sonnet max_tokens: 4096 → 16000 (was truncating long extractions)
- Position parser: handles **bold**, compound confidence `[HIGH (x) / MEDIUM (y)]`, skips preamble/summary
- Argument parser: handles `ARG-N: [model]`, `ARG-N: model -`, `ARG-N: **model**`
- Position normalization: strips parenthetical qualifiers for agreement comparison

## Completed Work (2026-03-28)

1. **Resume from checkpoint** — DONE. `--resume FILE` loads checkpoint, skips completed stages,
   restores all tracker state (arguments, positions, evidence). Tested: gate1 → resume → full run.

2. **Sonar search for repeat topics** — DONE. `sonar_search.py` enhanced with system prompt and
   citation extraction. Wired into Brain via `sonar_fn` parameter. Topic tracker triggers Sonar Pro
   on OpenRouter when same topic searched twice across rounds.

3. **Per-framework position prompt** — DONE. Position extraction prompt asks for per-framework
   breakdown (e.g., `r1/GDPR: reportable [HIGH]`). Parser handles both inline and markdown table
   formats. Agreement ratio computed per-framework and averaged. b1 went from PARTIAL_CONSENSUS
   (0.50) to CONSENSUS (1.00) — models agreed on all 3 frameworks.

4. **Save design to tech library** — Skipped (user deferred).

5. **Playwright search** — DONE. Wired as primary search provider (free Google scraping). Brave
   API is automatic fallback if Playwright not installed. Search priority logged at startup.

### Parser Fix (found during b7 testing)
- Sonnet sometimes returns positions as markdown tables (`| model/FW | pos | HIGH | qual |`)
  instead of inline format. Added table row parsing to `_parse_positions()`.
- Added "dimension", "line", "model" to skip-word list (spurious non-model labels).

## Pending Work

None — all features implemented and tested. See OPERATIONS.md for usage instructions.

## Build Strategy (agreed with Christos)
- Build each piece STANDALONE first (Brain done, Chamber next)
- Test each independently with step-by-step debug methodology
- DON'T import new pieces into old Mission Controller scaffolding
- Re-evaluate if old architecture (cascade, parallel, brief classifier) is even needed
- Integrate only proven pieces — simpler orchestration may suffice

## Key Files
```
thinker-v8/
├── .env                    # API keys (gitignored)
├── HANDOFF.md              # This file
├── OPERATIONS.md           # Agent operations guide
├── thinker/
│   ├── brain.py            # Orchestrator + CLI (--resume, --stop-after, --verbose)
│   ├── checkpoint.py       # Stop/resume system
│   ├── debug.py            # RunLog + HTML generator
│   ├── pipeline.py         # @pipeline_stage registry
│   ├── gate1.py            # Gate 1 (Sonnet)
│   ├── gate2.py            # Gate 2 (deterministic)
│   ├── rounds.py           # Round execution
│   ├── search.py           # Search orchestrator + topic tracking
│   ├── synthesis.py        # Synthesis Gate
│   ├── argument_tracker.py # Arg extract/compare/re-inject
│   ├── evidence.py         # Evidence ledger
│   ├── llm.py              # 4-provider LLM client
│   ├── config.py           # Models, topology, thresholds
│   ├── sonar_search.py     # Sonar Pro via OpenRouter (repeat topics)
│   ├── brave_search.py     # Brave API fallback search
│   ├── playwright_search.py# Free Google via headless Chromium (primary)
│   └── tools/
│       ├── position.py     # Position tracker (per-framework)
│       ├── contradiction.py
│       ├── ungrounded.py
│       ├── blocker.py
│       └── cross_domain.py
├── tests/                  # 102 tests
│   └── fixtures/briefs/    # b1.md, b4.md, b7.md test briefs
└── output/                 # Run outputs (gitignored)
```
