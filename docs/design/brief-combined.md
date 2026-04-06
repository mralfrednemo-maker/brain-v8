# Brain V8 — Expanded Design Brief

**Date:** 2026-04-01
**Type:** Design facilitation — CLOSED REVIEW. Do not search the web.

---

## WHAT BRAIN V8 IS

Brain V8 is a multi-model deliberation pipeline built for OpenClaw — a team of AI agents run by Christos. Its purpose is to remove Christos as the decision bottleneck. An agent sends a question, Brain V8 runs it through multiple AI models in adversarial debate with evidence, and produces a structured outcome with a full audit trail (proof.json).

**Current outcomes:**
- DECIDE — models converged, evidence supports it. Agent can act.
- ESCALATE — partial consensus or unresolved blockers. Christos reviews.
- NO_CONSENSUS — models fundamentally disagree. Irreducible split.
- ERROR — LLM or search unavailable. Full stop. No partial results.
- NEED_MORE — question too vague or missing context. Returned before the run starts.

**Current architecture flow:**
```
Gate 1 (Sonnet, ~5s) ── Is the question answerable? Search needed?
    │
    ▼
Round 1 (4 models, parallel) ── Independent opinions, no evidence yet
    │
    ▼
Search Phase ── Model-driven queries, full page fetch, fact extraction
    │
    ▼
Round 2 (3 models) ── Debate with evidence
    │
    ▼
Round 3 (2 models) ── Narrowing, resolve disagreements
    │
    ▼
Round 4 (2 models) ── Closing arguments
    │
    ▼
Gate 2 (Deterministic) ── Can we trust this? → DECIDE / ESCALATE / NO_CONSENSUS / ERROR
    │
    ▼
Synthesis ── Human-readable report + proof.json
```

**The 5 requirements every piece of code must serve:**
- R0: Enough context to reason about
- R1: Multiple independent opinions
- R2: Grounded in evidence
- R3: Honest about disagreement
- R4: Knows when it can't decide

**Zero tolerance:** Any failure in any stage → ERROR. No degraded mode. No silent continuation. LLM down = stop. Search down = stop.

**Round topology is FIXED:** 4→3→2→2. Do not propose changes to this.

---

## WHAT WE WANT TO ACHIEVE

Four expansions to the platform:

**1. Common sense reasoning** — The pipeline should reason like a smart human: calibrate effort to actual difficulty, detect when premises are flawed, reject trivially broken questions early, and not waste full deliberation on questions that don't need it.

**2. Multi-aspect exploration** — Models should look at an issue from multiple angles before converging. Currently they tend to converge quickly on the obvious answer. We need mechanisms that trigger broad exploration — different perspectives, different framings, different assumptions — before the pipeline narrows toward consensus.

**3. Insufficient context detection** — The pipeline must detect when a question looks specific but is built on unstated assumptions that will make the answer useless. A human would immediately ask "wait, what about X?" — the pipeline doesn't. This goes beyond Gate 1's current check (is the brief vague?).

**4. ANALYSIS mode** — A new outcome for questions that seek understanding, not a decision. ANALYSIS reuses the existing decision pipeline where possible. The question is: what do we keep, what do we omit, what do we expand — or is something totally new needed?

**Locked decision (user confirmed):** The outcome taxonomy is nested by modality:
- DECIDE modality (verdict-seeking): DECIDE, ESCALATE, NO_CONSENSUS
- ANALYSIS modality (map-seeking): ANALYSIS
- Universal: NEED_MORE, ERROR

---

## TASK

Answer these four questions. For each, give specific, actionable design recommendations — not general observations. Be concrete about mechanisms and pipeline changes.

1. **Can LLMs exhibit common sense reasoning? If yes, what concrete pipeline mechanisms make it happen?**

2. **How do we get models to explore multiple aspects of an issue? What triggers broad exploration?**

3. **Gap analysis: what's missing or suboptimal in the current pipeline design — everything except the LLM round topology (4→3→2→2), which is fixed?** Look at: Gate 1, Search, Gate 2, Synthesis, proof.json, argument tracking, evidence handling. What needs to change? Submit proposals only if they bring genuine value to the quality of the outcome.

4. **ANALYSIS reuses the decision pipeline. What do we keep, what do we omit, what do we expand — or is something totally new needed?**

---

## CONTEXT DOCUMENT 1: TECHNICAL DESIGN

# Brain V8 — Technical Design (from implementation)

**Source:** `C:\Users\chris\PROJECTS\_audit_thinker\thinker-v8\thinker\`
**258 tests passing. DoD v2.1 complete.**

---

### 1. Purpose

Brain V8 is a multi-model deliberation engine. It takes a question (a "brief"), runs it through 4 LLMs in adversarial debate with web-sourced evidence, and produces a structured outcome (DECIDE / ESCALATE / NO_CONSENSUS / ERROR) with a complete audit trail (proof.json).

It serves OpenClaw — a team of AI agents. When an agent faces a decision it can't make alone, it submits a brief to Brain V8. If the models converge with evidence, the agent gets an answer it can act on. If they don't, Christos (the human operator) reviews.

---

### 2. Pipeline Flow

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

### 3. Model Roster

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

### 4. Key Architectural Decisions

**Models have no memory.** Each round is a fresh inference call. Prior-round context is re-injected via prompts. The Argument Tracker ensures no argument is silently lost between rounds.

**Gate 2 is fully deterministic.** Same proof state → same outcome. No LLM call. All thresholds configurable in BrainConfig.

**Search is model-driven.** Models tell the pipeline what to search for (reactive). Sonnet also scans for unverified claims (proactive). Pipeline never guesses what to search.

**Evidence has a cap.** EvidenceLedger holds max 10 items. When full, new items evict the lowest-scored item if they score higher. Eviction is score-based.

**Checkpoint/resume supported.** Pipeline can stop at any stage boundary and resume from checkpoint.json. Schema version must match on resume.

**Zero tolerance.** Any failure → BrainError → ERROR outcome. proof.json is still written on ERROR (records what failed and where).

---

### 5. File Map

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

---

## CONTEXT DOCUMENT 2: TOOLBOX DESIGN

# Brain V8 — Toolbox Design (from implementation)

**Source:** `thinker/tools/`, `thinker/evidence.py`, `thinker/invariant.py`, `thinker/residue.py`, `thinker/argument_tracker.py`, `thinker/divergent_framing.py`

Every tool below is wired into the pipeline. They are not optional plugins — they run on every pass through their respective stages.

---

### 1. Argument Tracker

**File:** `thinker/argument_tracker.py`
**Type:** LLM-based (Sonnet)
**Runs:** After every round (R1-R4)

**What it does:**
After each round, makes one Sonnet call to extract every distinct argument made by any model. Each argument gets a round-prefixed ID (R1-ARG-1, R2-ARG-3, etc.) to prevent cross-round collision.

Starting from R2, a second Sonnet call compares the previous round's arguments against the current round's outputs. Each prior argument is classified:
- **ADDRESSED** — the model engaged with it substantively
- **MENTIONED** — referenced but not engaged
- **IGNORED** — not mentioned at all

MENTIONED and IGNORED arguments are re-injected into the next round's prompt with: "You MUST engage with each one." This is the core mechanism that prevents valid arguments from being permanently lost — models have no memory between rounds, so without re-injection, an argument that was strong in R1 can vanish by R3 with no trace.

**Data tracked per argument:**
- id (R{round}-ARG-{n})
- model (who made it)
- text (the argument itself)
- status (ADDRESSED / MENTIONED / IGNORED)
- critical (boolean)

**Integration point:** Unaddressed argument count feeds into Gate 2 (rule 4: unresolved critical arguments → ESCALATE).

---

### 2. Position Tracker

**File:** `thinker/tools/position.py`
**Type:** LLM-based (Sonnet)
**Runs:** After every round (R1-R4)

**What it does:**
After each round, one Sonnet call extracts each model's position: what option they support, at what confidence (HIGH/MEDIUM/LOW), with what qualifiers.

Handles three position formats:
- **Single-dimension:** "O1: Approach A" / "O2: Approach B"
- **Per-framework compound:** "r1/GDPR: reportable + r1/SOC_2: documentation-required"
- **Markdown table:** models as rows, dimensions as columns

Computes **agreement_ratio** = (count of models on majority position) / (total models). For compound positions, averages agreement across frameworks.

Tracks position changes between rounds (which model shifted from what to what).

**Data tracked per position:**
- model
- option (normalized label)
- confidence (HIGH/MEDIUM/LOW)
- qualifier (free text)
- round

**Integration point:** agreement_ratio is the primary input to Gate 2 rules 2-3. Position changes are recorded in proof.json.

---

### 3. Evidence Ledger

**File:** `thinker/evidence.py`
**Type:** Deterministic (no LLM)
**Runs:** During search phases (after R1 and R2)

**What it does:**
Central store for all evidence collected during the run. Enforces quality and relevance.

On every `add()`:
1. **Deduplication** — rejects items with matching content hash or URL
2. **Cross-domain filter** — calls `is_cross_domain()` to reject off-topic evidence (e.g., medical evidence in a security brief)
3. **Scoring** — keyword overlap with brief (0-5 pts) + authority domain bonus (+2 pts for nvd.nist.gov, arxiv.org, etc.) + base 1.0
4. **Cap enforcement** — max 10 items. When full, a new higher-scoring item evicts the lowest-scored existing item. Lower-scoring new items are rejected.
5. **Contradiction check** — calls `detect_contradiction()` against every existing item

**Data tracked per item:**
- id (E001, E002, ...)
- url, title, source domain
- content (extracted fact text)
- fetch timestamp
- score
- full_content (raw page text, if available)

**Known issue (from self-review):** Eviction under cap pressure can silently drop contradiction-bearing evidence. If E003 contradicts E007 and E003 gets evicted, the contradiction record is orphaned. This is the DC-5/V8-F3 finding — the most critical open bug.

---

### 4. Contradiction Detector

**File:** `thinker/tools/contradiction.py`
**Type:** Deterministic (no LLM)
**Runs:** On every evidence add (called by EvidenceLedger)

**What it does:**
Pairwise comparison between a new evidence item and every existing item. Detects numeric conflicts:

1. Checks **topic overlap** — counts shared words (4+ chars) between items. Needs >=2 shared words to proceed.
2. Extracts **all numbers** from both items.
3. If both items have numbers AND their number-sets are mutually exclusive (neither is a subset), flags a contradiction.

**Severity:**
- HIGH — both items have exclusive numbers (conflicting facts)
- MEDIUM — one item has numbers the other doesn't (possible conflict)

**Data tracked per contradiction:**
- id (CTR-1, CTR-2, ...)
- item_a_id, item_b_id
- severity
- description

**Limitation:** Only catches numeric conflicts. Cannot detect semantic contradictions ("Company X is growing" vs "Company X is shrinking") unless they include conflicting numbers. This is acknowledged in the architecture spec as the biggest gap.

**Integration point:** Contradiction count feeds into Gate 2 rule 6. CTR IDs are checked in residue verification.

---

### 5. Cross-Domain Filter

**File:** `thinker/tools/cross_domain.py`
**Type:** Deterministic (no LLM)
**Runs:** On every evidence add (called by EvidenceLedger)

**What it does:**
Prevents off-topic evidence from polluting the ledger. Maintains keyword families for 5 domains:
- Security (CVE, vulnerability, exploit, firewall, ...)
- Medical (patient, diagnosis, clinical, ...)
- Finance (revenue, portfolio, trading, ...)
- Infrastructure (server, kubernetes, deployment, ...)
- Compliance (regulation, audit, GDPR, ...)

Plus a compatibility matrix (e.g., security <-> infrastructure are compatible; security <-> medical are not).

Detects the brief's domain and each evidence item's domain by keyword density scoring (threshold >=2). If an item's domain is incompatible with the brief's domain, it's rejected.

---

### 6. Ungrounded Stat Detector

**File:** `thinker/tools/ungrounded.py`
**Type:** Deterministic (no LLM)
**Status:** Exists but NOT actively called in the current pipeline

**What it does:**
Scans model output text for numeric claims (percentages, dollar amounts, specific numbers). For each, checks:
- Does it have a nearby E-ID citation (e.g., `{E001}`)?
- Does the number appear in the evidence corpus?

If neither, the stat is flagged as "ungrounded" — a claim the model invented or recalled from training data without verification.

Also generates search queries to verify ungrounded stats.

**Why it's not active:** The proactive search in `search.py` partially covers this function (Sonnet scans for unverified claims). The standalone detector was built for V7 and hasn't been wired into the V8 pipeline loop yet.

---

### 7. Blocker Ledger

**File:** `thinker/tools/blocker.py`
**Type:** Deterministic (no LLM)
**Runs:** Throughout the pipeline

**What it does:**
Tracks all structured blockers — issues that could prevent a trustworthy outcome. Each blocker gets a sequential ID (BLK001, BLK002, ...) and a lifecycle:

- **OPEN** — detected, not yet resolved
- **RESOLVED** — addressed with evidence or argument
- **DEFERRED** — acknowledged but not blocking this run
- **DROPPED** — determined to be non-material

Each status change records: which round, what triggered it, and a note.

**Blocker kinds:**
- EVIDENCE_GAP — searched for something, didn't find it
- CONTRADICTION — conflicting evidence
- UNRESOLVED_DISAGREEMENT — models disagree on a critical point
- CONTESTED_POSITION — position held by minority with evidence

**Integration point:** `open_blockers()` feeds into Gate 2 rule 4. BLK IDs are checked in residue verification.

---

### 8. Divergent Framing Pass

**File:** `thinker/divergent_framing.py`
**Type:** LLM-based (Sonnet)
**Runs:** After R1 (extraction), after R2+ (survival check)

**What it does:**
Post-R1, Sonnet extracts alternative frames from the round's outputs. A frame is a fundamentally different way to look at the question — not just a different answer, but a different framing of what the question means.

**Frame types:** INVERSION, OBJECTIVE_REWRITE, PREMISE_CHALLENGE, CROSS_DOMAIN_ANALOGY, OPPOSITE_STANCE, REMOVE_PROBLEM

Each frame gets a stable ID (FRAME-1, FRAME-2, ...) and is tracked through subsequent rounds.

**Frame survival rules (two-vote drop):**
- A frame starts as ACTIVE
- A single model's objection → CONTESTED (not dropped)
- Two models' objections with traceable rebuttal references → DROPPED
- A frame can be ADOPTED (incorporated into the main position)
- Silent disappearance of a material frame → ERROR

Active/contested frames are injected into R2+ prompts so models must engage with them.

**Cross-domain analogies** are also tracked: source domain, target claim, transfer mechanism, test status (UNTESTED/SUPPORTED/REJECTED). An UNTESTED analogy cannot carry decisive factual weight.

**Integration point:** Unrebutted material frames block DECIDE at Gate 2 (rule 10). Frame data recorded in proof.json divergence section.

---

### 9. Invariant Validator

**File:** `thinker/invariant.py`
**Type:** Deterministic (no LLM)
**Runs:** After Gate 2

**What it does:**
Five structural integrity checks on the pipeline's output:

1. **INV-POS-MISSING** (ERROR) — positions were extracted for every completed round
2. **INV-ROUND-EMPTY** (ERROR) — every round has at least one model response
3. **INV-EVIDENCE-SEQ** (WARN) — evidence IDs are sequential (E001, E002, ...) with no gaps
4. **INV-BLK-ORPHAN** (WARN) — no blocker references a future round
5. **INV-CTR-ORPHAN** (WARN) — no contradiction references an evidence ID not in the ledger

Returns a list of violations with severity. ERROR violations would make the run untrustworthy.

---

### 10. Residue Verification (Synthesis Verifier)

**File:** `thinker/residue.py`
**Type:** Deterministic (no LLM)
**Runs:** After synthesis

**What it does:**
Checks that the synthesis report actually discusses the structural findings. Scans the report text for:
- Every BLK-{id} from the blocker ledger
- Every CTR-{id} from contradictions
- Every unaddressed argument ID

If a finding ID is absent from the report, it's recorded as an omission. If more than 30% of all structural findings are omitted, flags `threshold_violation=True` — meaning the synthesis is incomplete and may be hiding important disagreements or gaps.

This is string matching only. It checks that Hermes MENTIONED the findings, not that Hermes genuinely engaged with them. The architecture spec notes this gap — "Hermes can mention a blocker without genuinely addressing it."

---

### Pipeline Integration Summary

| Stage | Tools that run | Type |
|-------|---------------|------|
| After Gate 1 | CS Audit | LLM |
| After R1 | Argument Tracker, Position Tracker, Divergent Framing Pass | LLM |
| Search phase | SearchOrchestrator → Evidence Extractor → EvidenceLedger (includes Contradiction Detector + Cross-Domain Filter) | LLM + Deterministic |
| After R2 | Argument Tracker, Position Tracker, Frame Survival Check | LLM |
| After R3 | Argument Tracker, Position Tracker, Frame Survival Check | LLM |
| After R4 | Argument Tracker, Position Tracker, Frame Survival Check | LLM |
| Gate 2 | Deterministic classifier (consumes all tracker outputs) | Deterministic |
| After Gate 2 | Invariant Validator | Deterministic |
| After Synthesis | Residue Verification | Deterministic |
