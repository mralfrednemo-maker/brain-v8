# Brain V8 — Technical Design (from implementation)

**Source:** `C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8\thinker\`
**258 tests passing. DoD v2.1 complete.**

---

## 1. Purpose

Brain V8 is a multi-model deliberation engine. It takes a question (a "brief"), runs it through 4 LLMs in adversarial debate with web-sourced evidence, and produces a structured outcome (DECIDE / ESCALATE / NO_CONSENSUS / ERROR) with a complete audit trail (proof.json).

It serves OpenClaw — a team of AI agents. When an agent faces a decision it can't make alone, it submits a brief to Brain V8. If the models converge with evidence, the agent gets an answer it can act on. If they don't, Christos (the human operator) reviews.

---

## 2. Pipeline Flow

```
Brief (markdown text)
    │
    ▼
GATE 1 ─── Single Sonnet call (~5s)
│  Checks: Is the brief specific? Has context? Has deliverable?
│  Outputs: PASS/FAIL + search recommendation (YES/NO)
│  On FAIL: returns NEED_MORE with specific follow-up questions
│  On unparseable LLM response: fail-closed (rejects the brief)
    │
    ▼
CS AUDIT ─── Single Sonnet call
│  Classifies the brief:
│    stakes_class: LOW / STANDARD / HIGH
│    question_class: TRIVIAL / WELL_ESTABLISHED / OPEN / AMBIGUOUS / INVALID
│    effort_tier: SHORT_CIRCUIT / STANDARD / ELEVATED
│    premise_flags: list of detected defects (type + severity + summary)
│  On INVALID question with unrepairable defect: ERROR
│  On unparseable output: ERROR (fail-closed)
    │
    ▼
ADVERSARIAL ASSIGNMENT ─── Controller logic (no LLM)
│  Kimi K2 is assigned CONTRARIAN role for R1
│  Gets a modified system prompt: "argue the strongest credible opposing position"
│  Assignment type and model ID recorded in proof.json
    │
    ▼
ROUND 1 ─── 4 models in parallel (DeepSeek R1, Reasoner, GLM-5, Kimi K2)
│  Each sees ONLY the brief. No model sees another's output.
│  Each appends 0-5 search queries to its response.
│  Kimi runs with adversarial preamble.
    │
    ▼
ARGUMENT TRACKER ─── Single Sonnet call
│  Extracts every distinct argument from R1 outputs
│  Each argument gets a stable ID: R1-ARG-1, R1-ARG-2, ...
    │
    ▼
POSITION TRACKER ─── Single Sonnet call
│  Extracts each model's position (option label + confidence + qualifier)
│  Computes agreement_ratio for Gate 2
    │
    ▼
DIVERGENT FRAMING PASS ─── Single Sonnet call (post-R1 only)
│  Extracts alternative frames from R1 outputs (INVERSION, PREMISE_CHALLENGE, etc.)
│  Extracts cross-domain analogies
│  Each frame gets a stable ID: FRAME-1, FRAME-2, ...
│  Frames are injected into R2+ prompts
    │
    ▼
SEARCH PHASE ─── Runs after R1 and R2
│  1. Collect model-requested search queries (from response appendices)
│  2. Sonnet generates proactive queries (claims models missed)
│  3. Deduplicate all queries
│  4. Execute: Bing via Playwright (first time) or Sonar Pro (repeat topic)
│  5. Fetch full page content (httpx, top 5 pages, 50k chars max each)
│  6. Sonnet extracts structured facts from each page → EvidenceItems
│  7. Evidence added to EvidenceLedger (dedup, scoring, cap enforcement, contradiction check)
    │
    ▼
ROUND 2 ─── 3 models (R1, Reasoner, GLM-5)
│  See: brief + all R1 views + evidence + unaddressed arguments + active alt frames
│  Argument Tracker extracts + compares with R1 arguments
│  Position Tracker extracts + computes agreement
│  Frame survival check (two-vote drop rule)
│  Search runs again after R2
    │
    ▼
ROUND 3 ─── 2 models (R1, Reasoner)
│  Same as R2 but no further search
│  Argument Tracker compares with R2
│  Frame survival check continues
    │
    ▼
ROUND 4 ─── 2 models (R1, Reasoner)
│  Closing arguments. No search request section.
│  Argument Tracker compares with R3
│  Frame survival check continues
    │
    ▼
GATE 2 ─── Deterministic (no LLM call)
│  Ordered rules (DoD v2.1, rules 1-13):
│    1. Fatal integrity failure → ERROR
│    2. agreement_ratio < 0.50 → NO_CONSENSUS
│    3. agreement_ratio < 0.75 → ESCALATE
│    4. Unresolved critical argument/blocker → ESCALATE
│    5. Decisive claims lack evidence → ESCALATE
│    6. Critical contradictions unresolved → ESCALATE
│    7. Missing CS Audit → ERROR
│    8. Missing adversarial slot/framing pass → ERROR
│    9. Unresolved CRITICAL premise flag → ESCALATE
│   10. Material alt frame ACTIVE/CONTESTED without rebuttal → ESCALATE
│   11. Fast consensus without evidence + not allowed → ESCALATE
│   12. Otherwise → DECIDE
    │
    ▼
SYNTHESIS ─── Single Sonnet call
│  Sees ONLY the final round's views
│  Produces: markdown report + JSON data (separated by ---JSON---)
│  Outcome class label appended deterministically after the call
    │
    ▼
INVARIANT VALIDATOR ─── Deterministic (no LLM)
│  5 structural checks:
│    - Positions exist for every completed round
│    - Every round has at least one response
│    - Evidence IDs are sequential
│    - No blocker references a future round
│    - No contradiction references orphaned evidence
│  Returns WARN or ERROR violations
    │
    ▼
RESIDUE VERIFICATION ─── Deterministic (no LLM)
│  Scans synthesis report for BLK/CTR/argument IDs
│  If >30% of structural findings are missing from the narrative → threshold_violation
    │
    ▼
PROOF BUILDER ─── Assembles proof.json v2.1
│  Contains: run_id, brief, model identities, gate results, per-round data,
│  evidence ledger, claim-to-evidence bindings, outcome, config snapshot,
│  input fingerprint, invariant violations, synthesis residue, CS audit data,
│  divergence data (frames, analogies)
```

---

## 3. Model Roster

| ID | Model | Provider | Used in |
|----|-------|----------|---------|
| r1 | deepseek-r1-0528 | OpenRouter | R1, R2, R3, R4 |
| reasoner | deepseek-reasoner | DeepSeek direct | R1, R2, R3, R4 |
| glm5 | glm-5-turbo | Z.AI | R1, R2 |
| kimi | kimi-k2 | OpenRouter | R1 only (adversarial) |
| sonnet | claude-sonnet-4-6 | Anthropic OAuth | All orchestration (Gate 1, CS Audit, argument/position extraction, search proactive, evidence extraction, framing pass, synthesis) |

**Round topology (fixed):** R1=4 models, R2=3, R3=2, R4=2.

**Timeout/token policy:**
- Thinking models (R1, Reasoner): 720s, 30k max_tokens
- Non-thinking (GLM-5, Kimi): 480s, 16k max_tokens
- Sonnet (orchestration): 120s, 16k max_tokens
- Timeout = ERROR. No retry.

---

## 4. Key Architectural Decisions

**Models have no memory.** Each round is a fresh inference call. Prior-round context is re-injected via prompts. The Argument Tracker ensures no argument is silently lost between rounds.

**Gate 2 is fully deterministic.** Same proof state → same outcome. No LLM call. All thresholds configurable in BrainConfig.

**Search is model-driven.** Models tell the pipeline what to search for (reactive). Sonnet also scans for unverified claims (proactive). Pipeline never guesses what to search.

**Evidence has a cap.** EvidenceLedger holds max 10 items. When full, new items evict the lowest-scored item if they score higher. Eviction is score-based.

**Checkpoint/resume supported.** Pipeline can stop at any stage boundary and resume from checkpoint.json. Schema version must match on resume.

**Zero tolerance.** Any failure → BrainError → ERROR outcome. No degraded mode. proof.json is still written on ERROR (records what failed and where).

---

## 5. File Map

```
thinker/
├── brain.py          # Main orchestrator (Brain class, run() method)
├── config.py         # Model configs, round topology, BrainConfig
├── types.py          # All shared types and enums
├── pipeline.py       # @pipeline_stage decorator, stage registry, HTML diagram
├── llm.py            # Unified LLM client (4 providers)
├── gate1.py          # Gate 1: brief admission + search recommendation
├── gate2.py          # Gate 2: deterministic outcome classification
├── cs_audit.py       # Common Sense Audit: effort calibration + premise validation
├── rounds.py         # Deliberation rounds: prompt building + parallel execution
├── argument_tracker.py # Argument extraction + comparison + re-injection
├── divergent_framing.py # Frame extraction + survival tracking + analogy tracking
├── synthesis.py      # Final report + JSON generation
├── search.py         # Search orchestrator (reactive + proactive)
├── bing_search.py    # Bing via Playwright
├── brave_search.py   # Brave API
├── sonar_search.py   # Sonar Pro via OpenRouter
├── playwright_search.py # Google via Playwright (legacy)
├── page_fetch.py     # Full page content fetch via httpx
├── evidence_extractor.py # LLM-based fact extraction from pages
├── evidence.py       # EvidenceLedger: scoring, dedup, cap, contradiction
├── invariant.py      # Post-Gate 2 integrity checks
├── residue.py        # Synthesis completeness verification
├── proof.py          # ProofBuilder: assembles proof.json
├── checkpoint.py     # Checkpoint/resume state management
├── debug.py          # RunLog + HTML report generation
└── tools/
    ├── position.py      # PositionTracker: position extraction + agreement
    ├── contradiction.py # Numeric contradiction detection between evidence
    ├── cross_domain.py  # Cross-domain evidence filtering
    ├── ungrounded.py    # Ungrounded stat detection + verification query gen
    └── blocker.py       # BlockerLedger: lifecycle tracking for blockers
```
