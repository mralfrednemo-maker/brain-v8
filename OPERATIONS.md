# Thinker V8 Brain — Operations Guide

## Location

```
C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8\
```

## Prerequisites

- Python 3.12+
- Dependencies: `pip install httpx python-dotenv playwright`
- Playwright browser: `python -m playwright install chromium`
- API keys in `.env` (see below)

## .env Configuration

```env
OPENROUTER_API_KEY=sk-or-...       # R1 (DeepSeek R1), Kimi K2, Sonar Pro
ANTHROPIC_OAUTH_TOKEN=sk-ant-...   # Sonnet (Max subscription, 1-year token)
DEEPSEEK_API_KEY=sk-...            # DeepSeek Reasoner (direct)
ZAI_API_KEY=...                    # GLM-5 (subscription)
BRAVE_API_KEY=BSA...               # Brave search (fallback, $0.01/query)
```

## Running a Brief

### Full run (all stages)
```bash
cd C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8
python -m thinker.brain --brief path/to/brief.md --outdir output/run-name --verbose
```

### Debug step-by-step (DEFAULT during development)
```bash
# Use the wrapper — --debug-step is ON by default
./brain-debug.sh --brief brief.md --outdir output/test

# Full run (no pausing) — pass --no-step
./brain-debug.sh --brief brief.md --outdir output/test --no-step

# Or call directly with the flag
python -m thinker.brain --brief brief.md --outdir output/test --debug-step
```

At each pause you see:
- Stage completed and pipeline progress
- Stage-specific metrics (positions, arguments, evidence, agreement)
- Press **Enter** to continue, **q** to stop

### Manual step-by-step (with checkpoint files)
```bash
# Stop after Gate 1
python -m thinker.brain --brief brief.md --outdir output/test --stop-after gate1

# Inspect checkpoint
python -m thinker.checkpoint output/test/checkpoint.json

# Resume from checkpoint, stop after R1
python -m thinker.brain --brief brief.md --outdir output/test --resume output/test/checkpoint.json --stop-after r1

# Resume and run to completion
python -m thinker.brain --brief brief.md --outdir output/test --resume output/test/checkpoint.json
```

### Stage IDs for --stop-after
```
gate1 → r1 → track1 → search1 → r2 → track2 → search2 → r3 → track3 → r4 → track4 → synthesis → gate2
```

## CLI Flags

| Flag | Description |
|------|-------------|
| `--brief FILE` | Path to brief markdown file (required) |
| `--rounds N` | Number of deliberation rounds, 1-4 (default: 4) |
| `--budget N` | Wall clock budget in seconds (default: 3600) |
| `--outdir DIR` | Output directory (default: ./output) |
| `--verbose` | Full logging at each stage |
| `--stop-after STAGE` | Run up to STAGE, save checkpoint, exit |
| `--resume FILE` | Resume from checkpoint JSON (skips completed stages) |
| `--debug-step` | Pause after every stage for analysis (implies --verbose). Press Enter to continue, 'q' to stop. |

## Output Files

Every run generates in `--outdir`:

| File | Contents |
|------|----------|
| `proof.json` | Machine-readable proof of deliberation |
| `report.md` | Human-readable synthesis report |
| `debug.log` | Full verbose log |
| `events.json` | Structured event stream |
| `run-report.html` | Auto-populated architecture diagram |
| `checkpoint.json` | Pipeline state for resume |

## Search System

Search providers:

1. **Brave API** (primary, $0.01/query) — requires BRAVE_API_KEY in .env
2. **Sonar Pro** (repeat topics only) — Perplexity via OpenRouter, triggered when topic tracker detects a repeat search across rounds

Playwright was tested but all search engines (Google, Bing, DuckDuckGo) block headless browsers with CAPTCHA. Brave API is reliable and cheap.

If no search provider is available, deliberation continues without evidence.

## Position Extraction

The position tracker supports two formats:

**Single-dimension** (decision briefs with O1/O2/O3/O4 options):
```
r1: O3 [HIGH] — controlled isolation first
```

**Per-framework** (analysis briefs spanning multiple standards):
```
r1/GDPR: not-reportable [HIGH] — no personal data exposed
r1/SOC_2: reportable [MEDIUM] — security incident documentation required
r1/HIPAA: not-reportable [HIGH] — no PHI accessed
```

Position normalization handles label drift: "O3", "O3-modified", "Enhanced Option 3" all normalize to `o3` for agreement comparison.

## Writing Briefs

A good brief has:
- **Situation**: What happened, specific facts, numbers, timeline
- **Context**: System details, stakeholders, constraints
- **Question**: Clear deliverable — assess, determine, evaluate, compare
- Brief MUST be self-contained — models can't ask clarifying questions

See `tests/fixtures/briefs/` for examples (b1.md, b4.md, b7.md).

## Running Tests

```bash
cd C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8
python -m pytest tests/ -v           # All 102 tests
python -m pytest tests/ -x -v        # Stop on first failure
python -m pytest tests/test_brain_e2e.py -v  # E2E only
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 0 positions extracted | Sonnet used unexpected format — check `last_raw_response` in debug log. Parser handles inline, per-framework, and table formats. |
| Search returns 0 evidence | Playwright may be blocked by Google CAPTCHA. Try running with Brave fallback. |
| Checkpoint resume skips too much | Check `completed_stages` in checkpoint.json — stages are appended, not replaced. |
| Anthropic 401 | OAuth token may have expired. Check `.env` ANTHROPIC_OAUTH_TOKEN. |
| Model timeout | Default timeouts: Sonnet 120s, GLM5/Kimi 480s, R1/Reasoner 720s. Increase in config.py if needed. |

## Architecture Quick Reference

```
Gate 1 (Sonnet) → R1 (4 models) → [Arg Track + Pos Track] → Search →
R2 (3 models) → [Arg Track + Pos Track + Arg Compare] → Search →
R3 (2 models) → [Arg Track + Pos Track + Arg Compare] →
R4 (2 models) → [Arg Track + Pos Track + Arg Compare] →
Synthesis Gate (Sonnet) → Gate 2 (deterministic, no LLM)
```

Round topology: R1=4 models → R2=3 → R3=2 → R4=2
Models: DeepSeek R1, DeepSeek Reasoner, GLM-5, Kimi K2, Sonnet (orchestrator)
