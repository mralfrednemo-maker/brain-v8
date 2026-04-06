# Thinker

Multi-platform deliberation engine.

## Platforms

### Brain
Fixed-round parallel deliberation (4→3→2→2 topology).
- `brain/v9/` — V9 implementation (V3.0 design, 33 modules, 349 tests)
- `brain/v10/` — V10 implementation (V3.1 delta, in development)
- `brain/legacy/` — V3 single-file orchestrator (reference only)

### Chamber
Circular adversarial governance (Strategist → Critic → Auditor → Researcher cycles).
- `chamber/v3/` — V3 implementation

### Controller
Mission controller — routes briefs to Brain, Chamber, or both.
- `controller/mission_controller.py`

### Ein
Three-way parallel deliberation (Claude + ChatGPT + Gemini via browser automation).
- `ein/`

## Supporting

- `tools/browser-automation/` — Playwright/Selenium browser helpers for Ein
- `briefs/` — E2E test briefs (b1–b7)
- `docs/design/` — Design docs and DODs for all versions
- `docs/protocols/` — Three-way deliberation protocol
- `docs/archive/` — Legacy planning documents

## Running Brain V9

```bash
cd brain/v9
pip install -e ".[dev]"
python -m brain.brain --brief ../../briefs/b1-brain-factual-incident.md
```

## Running Brain V10

```bash
cd brain/v10
pip install -e ".[dev]"
python -m brain.brain --brief ../../briefs/b1-brain-factual-incident.md
```
