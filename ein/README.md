# Ein — Multi-Model Deliberation & Design Synthesis

Ein is a browser automation platform that runs ChatGPT, Gemini, and Claude in parallel on the same problem, then forces convergence through structured rounds. Named after Einstein.

There are **two pipelines** for two different kinds of work:

| Pipeline | Script | Best for | Approach |
|----------|--------|----------|----------|
| **Design Synthesis** | `ein-design.py` | Merging documents, creating unified specs, policy drafts | Collaborative cross-pollination |
| **Adversarial Deliberation** | `ein-selenium.py` | Questions, decisions, risk assessment, truth-seeking | Contrarian lenses + cross-examination |

Both scripts validate your brief at startup and point you to the other pipeline if it's a better fit. Bypass with `--skip-check`.

---

## ein-design.py — Cross-Pollination Pipeline

### What it does

Three LLMs independently draft a document from your brief, then iteratively revise by reading each other's work. A final round has ChatGPT synthesize the converged result using 2/3 majority on remaining disagreements.

### Pipeline flow

```
draft ──→ cross_1 ──→ cross_2 ──→ [cross_3] ──→ [cross_4] ──→ final
  │          │           │            │              │            │
  │     Each engine   Same, using   Optional 3rd   Forced       ChatGPT
  │     gets other    cross_1       round if       concession   synthesizes
  │     two's drafts  outputs       divergence     (max N       with 2/3
  │     + revises                   remains        HOLDs)       majority
  │
  3 engines write independently
  (8 files uploaded + prompt)
```

- **cross_3** is optional — run it if cross_2 still has unresolved splits
- **cross_4** uses the forced-concession template (`cross4-final-position-lock-prompt.txt`) — only if cross_3 still shows significant divergence. Each model may HOLD on at most N points and must CONCEDE the rest with reasoning.
- **final** launches only the ChatGPT browser

### Quick start

```bash
cd C:\Users\chris\PROJECTS\the-thinker\ein

# Full draft phase (all 3 engines)
python ein-design.py \
  --phase draft \
  --prompt C:\path\to\your-brief.txt \
  --upload-files "file1.py,file2.md,file3.md"

# Cross-pollination round 1 (resume from ledger)
python ein-design.py \
  --phase cross_1 \
  --resume C:\Users\chris\PROJECTS\design-ledger-YYYYMMDD-HHMMSS.json \
  --upload-files "file1.py,file2.md,file3.md"

# Continue with cross_2, cross_3, final...
python ein-design.py --phase cross_2 --resume <ledger>
python ein-design.py --phase cross_3 --resume <ledger>
python ein-design.py --phase final --resume <ledger>
```

### Key arguments

| Argument | Default | Purpose |
|----------|---------|---------|
| `--phase` | `all` | Which phase to run: `draft`, `cross_1`, `cross_2`, `cross_3`, `final` |
| `--resume` | — | Path to ledger JSON from a previous run (required for cross/final phases) |
| `--prompt` | `phase1-v5-prompt.txt` | Path to the draft brief |
| `--upload-files` | — | Comma-separated files to upload to each engine |
| `--quality-criterion` | `"more thorough, better reasoned, and more actionable"` | Defines what "stronger" means during cross-pollination |
| `--model-chatgpt` | `thinking` | ChatGPT model |
| `--model-gemini` | `Pro` | Gemini model |
| `--model-claude` | `Opus` | Claude model |
| `--skip-check` | — | Skip brief suitability validation |
| `--kill-stale` | — | Kill orphaned automation Chrome processes |

### Suitable topic types

- Policy analysis
- Strategic decisions
- Research synthesis
- Comparative evaluation
- Document merge / unification
- Architecture or design specs

### How prompts are delivered

- **Draft phase**: prompt text is pasted directly into the chat (first message, no clutter)
- **Cross-pollination & final**: prompt is written to a temp file (`ein_prompt_<phase>_<id>.txt`) and uploaded as an attachment. The chat message says: `Your prompt for this round is in the attached file: <filename>`. This keeps conversations clean.

### Convergence analysis

After each cross-pollination round, compare rejection appendices across engines:

- If all topics have 2/3 majority → proceed to `final`
- If 2+ topics are still SPLIT → run another cross round
- If cross_3 still has splits → run cross_4 (forced concession, max N HOLDs)

### Output files

| File | Content |
|------|---------|
| `design-ledger-YYYYMMDD-HHMMSS.json` | Full pipeline state, all responses, conversation URLs |
| `ein-design-draft-results.json` | Draft phase responses per engine |
| `ein-design-cross_N-results.json` | Cross-pollination round N responses |
| `ein-design-final-results.json` | ChatGPT's final synthesis |
| `ein-design-FINAL-SYNTHESIS.md` | Extracted final document (if saved manually) |

---

## ein-selenium.py — Adversarial Deliberation Pipeline

### What it does

Three LLMs debate a question or decision through structured adversarial phases: opening positions, contrarian challenges, cross-examination, and facilitator synthesis.

### Pipeline flow

```
Phase 1 ──→ Phase 1.5 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
  │             │             │           │           │
  Opening    Contrarian     Cross-      Synthesis   Final
  positions  challenges    examination  (2/3        assembly
  (3 fresh   (each gets    (each       majority)
  chats)     adversarial   defends
             lens)         under
                           pressure)
```

### Quick start

```bash
cd C:\Users\chris\PROJECTS\the-thinker\ein

# Full deliberation run
python ein-selenium.py

# Single phase
python ein-selenium.py --phase 1

# Kill stale Chrome first
python ein-selenium.py --kill-stale
```

### Suitable topic types

- Truth-seeking / factual claims
- Decision-making (should we do X?)
- Risk assessment (what could go wrong?)
- Ethical / governance questions
- Adversarial review (stress-testing assumptions)

---

## Browser Automation

Both pipelines use SeleniumBase with undetected-chromedriver (`uc=True`) to control three separate Chrome profiles:

| Engine | Profile directory |
|--------|------------------|
| ChatGPT | `C:\Users\chris\PROJECTS\chrome-automation-profile` |
| Gemini | `C:\Users\chris\PROJECTS\chrome-automation-profile-2` |
| Claude | `C:\Users\chris\PROJECTS\chrome-automation-profile-3` |

### Safety features

- **User Chrome protection**: at startup, all non-automation Chrome PIDs are snapshotted. The kill function will never terminate a PID from that snapshot.
- **Global session watchdog**: runs every 12 seconds for the pipeline lifetime. Clicks Claude's "Continue" button if it appears. Pings all browser sessions and warns if any go dead.
- **Browser launch retry**: each browser gets 3 launch attempts with crash file cleanup between retries.
- **Streaming debounce**: the stop-button must be absent for 6 consecutive seconds before a response is considered complete (handles Claude's tool-use pauses).

### Prerequisite

All three Chrome profiles must be logged in to their respective services. On first run, the script will wait up to 120-300 seconds for manual login.

---

## Ledger System

Both pipelines write a JSON ledger that tracks:

- Pipeline metadata (question, context, timestamps)
- Conversation registry (URLs for each engine's chat)
- Phase results (full response text, char counts, source type, timing)
- Pipeline status (completed phases, next phase)

The `--resume` flag loads a ledger and navigates browsers back to existing conversations, allowing phase-by-phase execution across sessions.

---

## Working test scripts (tools/browser-automation/)

Individual test scripts for validating browser automation outside the pipeline:

| Script | Purpose |
|--------|---------|
| `test_parallel.py` | All 3 services simultaneously via threads |
| `test_chatgpt_upload.py` | ChatGPT file upload + Thinking model |
| `test_gemini_upload.py` | Gemini file upload + Pro model |
| `test_claude_upload.py` | Claude file upload + step-by-step screenshots |
| `test_claude_model_select.py` | Claude model cycling + Extended Thinking toggle |
| `natural_browser.py` | Core browser automation library |

---

## File inventory

```
ein/
  ein-design.py                       # Cross-pollination pipeline
  ein-design-ledger.py                # Ledger module for ein-design
  ein-selenium.py                     # Adversarial deliberation pipeline
  ein-selenium-ledger.py              # Ledger module for ein-selenium
  ein-parallel.py                     # WebSocket/MCP parallel driver (legacy)
  ein-parallel-ledger.py              # Ledger module for ein-parallel
  cross4-final-position-lock-prompt.txt  # Forced-concession template
  README.md                           # This file

tools/browser-automation/
  test_parallel.py                    # Parallel browser test
  test_chatgpt_upload.py              # ChatGPT upload test
  test_gemini_upload.py               # Gemini upload test
  test_claude_upload.py               # Claude upload test
  test_claude_model_select.py         # Claude model selector test
  natural_browser.py                  # Browser automation library
  agent_tool_wrappers.py              # LangChain/CrewAI wrappers
```
