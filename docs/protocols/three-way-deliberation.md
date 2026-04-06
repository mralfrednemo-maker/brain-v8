# Ein — Three-Way Deliberation Protocol

Claude Code (main thread) acts as **facilitator only** — orchestrates, routes, summarizes, applies mechanical logic. The facilitator **never introduces arguments of its own**. All substance comes from the three participants.

## Participants

| Role | Engine | Mechanism |
|------|--------|-----------|
| **Facilitator** | Claude Code main thread | Orchestrates all phases. No positions, no opinions. |
| **Participant 1** | Opus subagent (effort max) | `Agent` tool (Phase 1-1.5), new `Agent` for Phase 2-4. Has web search. |
| **Participant 2** | ChatGPT | `chatgpt_ask` MCP. New chat per window. |
| **Participant 3** | Gemini Pro | `gemini_ask(model="Pro")` MCP. New chat per window. |

## Facilitator Authorities & Constraints

The facilitator has **process initiative** but **zero substantive initiative**.

**The hard rule:** If it wasn't said by Opus, ChatGPT, or Gemini — it doesn't exist in the deliberation.

| Authority | What it means | Constraint |
|-----------|--------------|------------|
| **Re-prompt** | Can ask a model to expand a shallow response | Max once per model per phase. "Expand on point 3" — never suggest what the expansion should say. |
| **Scope exclusion** | Can exclude off-topic material from routing | Must state what was excluded and why. Never rewrite it. |
| **Position decomposition** | Can break compound positions into sub-axes for 2/3 logic | Must present decomposition to user before applying. Never argue which sub-position is correct. |
| **Quality flagging** | Can note gaps ("no participant addressed X") in the ledger | Never argue what the gap implies. Just note it exists. |

| Facilitator CAN | Facilitator CANNOT |
|-----------------|-------------------|
| Summarize what was said | Add what wasn't said |
| Re-prompt for depth ("expand on point 3") | Suggest what the expansion should contain |
| Exclude off-topic material | Rewrite it to be on-topic |
| Decompose compound positions into sub-axes | Argue which sub-position is correct |
| Note "no participant addressed X" | Argue what X implies |
| Flag "these two arguments contradict each other" | Say which one is correct |
| Present comparison tables | Bold, rank, or reorder to suggest priority |

## Thread Architecture

Two separate thread windows. The ledger bridges them.

| Window | Phases | Purpose | Thread lifecycle |
|--------|--------|---------|-----------------|
| **Exploration** | 1 + 1.5 | Generate maximum aspects. Breadth. | Start threads → discard after 1.5 |
| **Debate** | 2 + 3 + 4 | Evaluate, challenge, converge. Depth. | Fresh threads → maintain through Phase 4 |

| Phase | Opus subagent | ChatGPT | Gemini |
|-------|--------------|---------|--------|
| 1 — Opening | Launch Agent | `new_chat` | `new_chat` |
| 1.5 — Contrarian | `SendMessage` | `chatgpt_ask` | `gemini_ask` |
| — BREAK — | Agent done | — | — |
| 2 — Cross-Exam R1 | Launch NEW Agent | `new_chat` | `new_chat` |
| 3 — Cross-Exam R2 | `SendMessage` | `chatgpt_ask` | `gemini_ask` |
| 4 — Final Positions | `SendMessage` | `chatgpt_ask` | `gemini_ask` |

## The Argument Ledger

The facilitator maintains a running ledger that captures all participant arguments across both exploration rounds. The ledger is the sole bridge between the Exploration and Debate windows.

### Ledger entry format

| Field | What |
|-------|------|
| **Source** | R1-A through R2-C (anonymized — no model names in Debate window) |
| **Position** | One-sentence stance (extracted, not invented) |
| **Key arguments** | 2-4 distinct arguments (extracted, not invented) |
| **Frame** | What lens was used (technical, economic, risk, stakeholder, etc.) |
| **Attacks** (R2 only) | Which R1 arguments this entry challenges |

**IMPORTANT:** The ledger summary is a navigational aid. The **full text** of all 6 responses is always included alongside it when sent to models. The summary never replaces the actual responses.

### Persistent ledger (mandatory)

The ledger MUST be written to a temp file — not held only in the facilitator's working memory. Context compaction, long runs, or handovers can lose in-memory state.

**File:** `deliberation-ledger-{timestamp}.md` in the working directory.

**Lifecycle:**
1. After Phase 1: facilitator creates the file with 3 entries (R1-A, R1-B, R1-C) + full text of all 3 responses.
2. After Phase 1.5: facilitator appends 3 entries (R2-A, R2-B, R2-C) + full text of all 3 contrarian responses.
3. After Phase 2: facilitator appends the 3 Phase 2 analyses (for reference, not as ledger entries).
4. After each subsequent phase: facilitator appends that phase's responses.
5. After Phase 5: facilitator appends the synthesis.

The file is append-only during the run. The facilitator reads from it when constructing prompts for Phase 2+ to ensure no content is lost to context compaction. This is the authoritative record — if the facilitator's memory and the file disagree, the file wins.

---

## Brief Design Guide

The brief is the single most important input to the deliberation. A bad brief wastes all 6 views.

### No rigid axes — let the models find them

Do NOT pre-define axes of disagreement in the brief. The 6-view structure (3 opening + 3 contrarian) is the hedge against blind spots — if all three openings miss an angle, the contrarian round exists precisely to catch it.

**Why:** Pre-defined axes act as blinders. The models will focus on what you tell them to focus on and miss dimensions you didn't think of. Example: in a "Brain V9 vs. Deliberation Protocol" question, neither the facilitator nor the user thought to list "web access vs. Playwright search" as an axis — but it's a legitimate differentiator that the models would surface on their own.

**The rule:** State the question. Provide the context files. Say "Identify your own dimensions of comparison — you are not restricted to any pre-defined axes." Stop there.

### Seed hints (optional, use with care)

If the question is so broad that models might waste their opening on surface-level observations, you MAY add: "Some dimensions to consider include (but are not limited to): [list]." The explicit "not limited to" language gives permission to go beyond. But prefer no hints — the 6-view structure handles breadth.

**When to use seeds:** Only when the topic is genuinely unfamiliar to the models and they might not know where to start.
**When to avoid seeds:** When the topic is well-understood (architecture decisions, tool comparisons, design trade-offs). The models will find the right dimensions.

### Scope expansion

The brief can include more than one question if they're tightly related. Example: "Is X redundant? And if not, what should Y adopt from X?" This turns binary judgments into constructive output. But keep questions to 2 max — more than that dilutes focus.

---

## Protocol

### Phase 0 — Brief *(facilitator + user)*

Before touching any engine:

1. Facilitator reads all referenced files (artifacts, context docs).
2. Facilitator proposes:
   - The exact deliberation question (one sentence, debatable — may include a secondary constructive question)
   - What context files will be uploaded to all engines
   - Whether context is sufficient or something is missing
   - NO pre-defined axes (see Brief Design Guide above)
3. Facilitator presents the brief to the user.
4. **HARD STOP — User must explicitly confirm "go."** No assumptions, no "I'll proceed unless you object."

---

### Phase 1 — Opening Statements *(all 3 in parallel)*

**Setup sequence:**
1. Launch Opus subagent + `chatgpt_new_chat()` + `gemini_new_chat()` — all parallel
2. `gemini_set_model("Pro")` — after new_chat
3. Upload context files to ChatGPT + Gemini (parallel): `chatgpt_upload_file` + `gemini_upload_file`
4. Send opening prompt to all three (parallel)

**Opening prompt (identical for all three):**

```
You are participating in a structured three-way deliberation. The question is:

"{deliberation question}"

Context: {brief context from Phase 0}

{context files attached/inlined}

Give your opening position in 4-6 paragraphs. Be specific and take a
clear stance. Do not hedge. Identify your own dimensions of comparison
— you are not restricted to any pre-defined axes.

IMPORTANT: Do you have enough context from the provided documents and
briefing to give a well-informed response? If not, tell me what
additional information you need before proceeding.
```

**After all three respond:**

Facilitator builds ledger entries R1-A, R1-B, R1-C and presents a factual comparison table. No ranking, no commentary on strength.

| Axis | Opus | ChatGPT | Gemini |
|------|------|---------|--------|
| Axis 1 | [position] | [position] | [position] |
| Axis 2 | [position] | [position] | [position] |

---

### Phase 1.5 — Contrarian Round *(facilitator assigns lenses, then all 3 in parallel)*

**Facilitator analyzes (internally, no engine calls):**
1. Identifies the dominant shared direction across the three openings.
2. Assigns each participant a different contrarian lens:

| Lens | Prompt |
|------|--------|
| **Opposite conclusion** | "What is the strongest case that the opposite of the emerging direction is correct?" |
| **Missing stakeholder/risk** | "What critical stakeholder, risk, or second-order effect did all three openings ignore?" |
| **Pre-mortem** | "Assume we followed this direction and it failed catastrophically in 12 months. What went wrong?" |

**Assignment rule:** The model that contributed MOST to the emerging consensus gets "opposite conclusion" — forced to argue against their own position.

**Contrarian prompt (each gets all 3 openings + their assigned lens):**

```
Here are the three opening positions on "{deliberation question}":

PERSPECTIVE A:
{Opus opening — full text}

PERSPECTIVE B:
{ChatGPT opening — full text}

PERSPECTIVE C:
{Gemini opening — full text}

YOUR CONTRARIAN TASK — {assigned lens name}:

{lens-specific prompt from table above}

Do NOT just disagree for the sake of it. Instead: what is the strongest,
most inconvenient truth that undermines the direction all three positions
are heading? What would a smart skeptic say that would make all three
uncomfortable?

Be specific. Take a clear stance. 4-6 paragraphs.

IMPORTANT: Do you have enough context from the provided documents and
briefing to give a well-informed response? If not, tell me what
additional information you need before proceeding.
```

**After all three respond:**

Facilitator completes the ledger (6 entries: R1-A, R1-B, R1-C, R2-A, R2-B, R2-C).

**Exploration window threads are now discarded.**

---

### Phase 2 — Cross-Exam R1 *(fresh threads, all 3 in parallel)*

**Setup:**
1. Launch NEW Opus subagent + `chatgpt_new_chat()` + `gemini_new_chat()` — all parallel
2. `gemini_set_model("Pro")` — after new_chat
3. Re-upload context files to ChatGPT + Gemini
4. Send Cross-Exam R1 prompt to all three (parallel)

**Cross-Exam R1 prompt (identical for all three):**

```
You are participating in a structured deliberation. The question is:

"{deliberation question}"

{brief context from Phase 0}

{context files attached/inlined}

Below are 6 perspectives gathered from an exploration round — 3 opening
positions and 3 contrarian challenges. You have not seen these before.
Treat them as input to evaluate, not positions to defend.

--- LEDGER SUMMARY ---
{6-entry ledger}

--- FULL EXPLORATION RESPONSES ---

PERSPECTIVE A (Opening):
{full text}

PERSPECTIVE B (Opening):
{full text}

PERSPECTIVE C (Opening):
{full text}

PERSPECTIVE D (Contrarian):
{full text}

PERSPECTIVE E (Contrarian):
{full text}

PERSPECTIVE F (Contrarian):
{full text}

--- YOUR TASK ---

1. Which of these 6 perspectives has the STRONGEST argument and why?
2. Which has the WEAKEST and why?
3. Where do perspectives contradict each other in ways that cannot
   both be true? Identify the real fault lines.
4. What is YOUR position on this question, informed by all 6 views?
   Take a clear stance. Do not hedge.
5. What is the single most important thing that ALL 6 perspectives
   either missed or underweighted?
6. HALLUCINATION CHECK: Identify any factual premise or core assumption
   that multiple perspectives agreed upon, but for which NO ONE provided
   concrete evidence. Challenge the weakest shared assumption.

IMPORTANT: Do you have enough context from the provided documents and
briefing to give a well-informed response? If not, tell me what
additional information you need before proceeding.
```

**After all three respond:**

Facilitator presents a factual comparison table of the three analyses. Routes responses verbatim to the next phase.

---

### Phase 3 — Cross-Exam R2 *(same threads, all 3 in parallel)*

Each model gets the other two's Phase 2 responses. **Routed verbatim — no summarization.**

**Cross-Exam R2 prompt:**

```
Here are the other two participants' analyses:

PARTICIPANT X:
{other model 1's full Phase 2 response}

PARTICIPANT Y:
{other model 2's full Phase 2 response}

Respond directly:

1. Where do you AGREE with their analysis? Be specific — which of
   their judgments do you share?
2. Where do you DISAGREE? What did they get wrong?
3. They identified fault lines and gaps. Are those the RIGHT fault
   lines? Or did they miss the real ones?
4. Has your position shifted after seeing their analysis? If yes,
   what moved you? If no, why not?

IMPORTANT: Do you have enough context from the provided documents and
briefing to give a well-informed response? If not, tell me what
additional information you need before proceeding.
```

---

### Phase 4 — Final Positions *(same threads, all 3 in parallel)*

Each model gets the other two's Phase 3 responses. **Routed verbatim.**

**Final positions prompt:**

```
Final round. Here are the other two participants' latest responses:

PARTICIPANT X:
{other model 1's full Phase 3 response}

PARTICIPANT Y:
{other model 2's full Phase 3 response}

Do NOT repeat arguments already made. State your FINAL position:

1. POSITION: Your stance in 2-3 sentences.
2. STRONGEST EVIDENCE: The single most compelling argument from the
   entire debate (any phase, any participant) that supports your
   position.
3. BIGGEST CONCESSION: The strongest point AGAINST your position
   that you cannot fully rebut.
4. REMAINING UNCERTAINTY: What would you need to know to be more
   confident?
5. VERDICT: For decision questions — a direct, actionable answer.
   For analysis questions — your recommended framework, prioritized
   considerations, or key takeaways.

IMPORTANT: Do you have enough context from the provided documents and
briefing to give a well-informed response? If not, tell me what
additional information you need before proceeding.
```

---

### Phase 5 — Synthesis *(facilitator only — mechanical, no opinion)*

The facilitator produces a structured output using ONLY material from the participants.

**Step 1: Position decomposition.**
Break compound positions into sub-axes. Present decomposition to user if non-obvious.

**Step 2: Apply 2/3 logic per sub-axis.**

| Condition | Classification |
|-----------|---------------|
| 3/3 agree | **CONSENSUS** |
| 2/3 agree | **MAJORITY** — conclusion follows majority, dissent noted with reasoning |
| All 3 differ | **DISPUTE** — all three positions presented, user decides |

**Synthesis output template:**

```
SYNTHESIS — {deliberation question}

DECISION TABLE:
| Axis/Sub-axis | Opus | ChatGPT | Gemini | Status |
|---------------|------|---------|--------|--------|
| ... | ... | ... | ... | CONSENSUS / MAJORITY / DISPUTE |

CONSENSUS ITEMS (3/3 or 2/3):
- [Axis]: [The majority/unanimous position].
  Supported by: [arguments from ledger, cited by label]
  {If 2/3: Dissent from [model]: [their argument]}

DISPUTES (all 3 differ):
- [Axis]: Three positions exist:
  - [Model 1]: [position + strongest argument]
  - [Model 2]: [position + strongest argument]
  - [Model 3]: [position + strongest argument]
  USER DECIDES.

CONCESSIONS (extracted from Phase 4):
- [Model 1] conceded: [what]
- [Model 2] conceded: [what]
- [Model 3] conceded: [what]

REMAINING UNCERTAINTY (extracted from Phase 4):
- [What models flagged as unknown/needed]

UNRESOLVED GROUNDING FLAGS (extracted from Phase 2):
- [Any premise flagged as ungrounded by participants in Phase 2
   that was never resolved or evidenced in subsequent rounds]

RAW PHASE 4 RESPONSES:
{Full text of all three final positions}
```

---

## Rules

1. **Facilitator never introduces arguments.** Works exclusively with participant-produced material.
2. **Facilitator never ranks or emphasizes.** Comparison tables are factual grids, not ranked lists.
3. **Responses routed verbatim** in Phases 3 and 4. No paraphrasing, no "key takeaways."
4. **Phase 0 is not optional.** HARD STOP until user confirms.
5. **Re-prompt authority:** Max once per model per phase if response is shallow. "Expand on point 3" — never suggest content.
6. **Scope exclusion authority:** Can exclude off-topic material. Must state what and why.
7. **If one engine fails**, note it and continue with two. Don't fabricate responses.
8. **User can inject** at any phase — their input overrides the protocol.
9. **Full text always included.** Ledger summaries are navigational, never a replacement for the actual responses.

## Invocation

User says: `deliberate: <topic or question>`

Or asks for a multi-model deliberation on a topic.

## Lightweight Mode — Poll

For quick opinion checks (not full deliberations):

User: `poll: <question>`

Facilitator sends question to all three (parallel), collects responses, presents a factual three-column comparison. No cross-examination, no synthesis. Phase 0 still applies.

## Model Defaults

- **Gemini**: always pass `model="Pro"` in `gemini_ask`
- **ChatGPT**: user's choice or default
- **Opus subagent**: effort max, launched via Agent tool

User can override models explicitly: "deliberate using o3 and gemini-2.5-flash"
