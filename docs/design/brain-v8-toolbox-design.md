# Brain V8 — Toolbox Design (from implementation)

**Source:** `thinker/tools/`, `thinker/evidence.py`, `thinker/invariant.py`, `thinker/residue.py`, `thinker/argument_tracker.py`, `thinker/divergent_framing.py`

Every tool below is wired into the pipeline. They are not optional plugins — they run on every pass through their respective stages.

---

## 1. Argument Tracker

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

## 2. Position Tracker

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

## 3. Evidence Ledger

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

## 4. Contradiction Detector

**File:** `thinker/tools/contradiction.py`
**Type:** Deterministic (no LLM)
**Runs:** On every evidence add (called by EvidenceLedger)

**What it does:**
Pairwise comparison between a new evidence item and every existing item. Detects numeric conflicts:

1. Checks **topic overlap** — counts shared words (4+ chars) between items. Needs ≥2 shared words to proceed.
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

## 5. Cross-Domain Filter

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

Plus a compatibility matrix (e.g., security ↔ infrastructure are compatible; security ↔ medical are not).

Detects the brief's domain and each evidence item's domain by keyword density scoring (threshold ≥2). If an item's domain is incompatible with the brief's domain, it's rejected.

---

## 6. Ungrounded Stat Detector

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

## 7. Blocker Ledger

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

## 8. Divergent Framing Pass

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

## 9. Invariant Validator

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

## 10. Residue Verification (Synthesis Verifier)

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

## Pipeline Integration Summary

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
