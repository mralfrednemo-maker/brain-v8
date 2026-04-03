# Multi-Platform Deliberation — Facilitation Guide

**Purpose:** How to run a combined Brain V8 + ChatGPT + Claude facilitation session to tackle a topic effectively.
**Author:** Lessons learned from the Brain V8 DoD review session (2026-03-31).
**Audience:** The facilitator (Claude) and the human operator.

---

## The Three Roles

| Platform | Role | Style | When to use |
|----------|------|-------|-------------|
| Brain V8 | **Evaluator** | Verdict + evidence. Stays inside the brief. Does not prescribe fixes. | When you need a rigorous, multi-model, evidence-backed assessment |
| ChatGPT | **Advisor** | Diagnosis + prescription. Expands beyond the question. Proposes solutions. | When you need structural proposals, alternative framings, or iterative drafting |
| Claude (facilitator) | **Mediator + contributor** | Synthesizes, identifies gaps neither party raised, drafts consolidations, runs logistics | Always present — orchestrates the process |

### Key principle
**Brain V8 finds truth. ChatGPT proposes action. Claude connects them.**

The brain should never prescribe fixes — that weakens the verdict. ChatGPT should not be the sole evaluator — it over-prescribes and can drift from the actual constraints. Claude should not dominate the substance — the value comes from independent perspectives converging.

---

## Session Structure

### Phase 0 — Agree the context *(mandatory before any platform call)*

**Hard rule: no Brain V8 run and no ChatGPT call until Phase 0 is complete.**

1. Claude reads all relevant files (the artifact being reviewed, architecture docs, prior outputs)
2. Claude proposes to the human:
   - The exact question or task being evaluated
   - What files will be sent to each platform
   - Whether any context is missing or ambiguous
3. Claude writes the brief and **presents it to the human for review**.
4. **HARD STOP — Human must explicitly confirm "go" before any platform call is made.** Claude must NOT proceed after presenting the brief. Wait for the human to review the content, adjust if needed, and give explicit go-ahead. No assumptions, no "I'll proceed unless you object."

This step is not optional. Running platforms on an incorrectly framed question or missing context wastes the entire session and produces findings that don't map to the real problem. Claude has consistently failed to get context right autonomously — the human review is load-bearing, not ceremonial. Fix the framing first.

### Multi-round facilitation rule — same brief, independent perspectives

When running sequential facilitation rounds with different platform pairs (e.g., Round 1: Brain V8 + ChatGPT, Round 2: ChatGPT + Gemini):

- **Both rounds evaluate the SAME brief.** Do not modify the brief between rounds unless the human explicitly instructs it.
- **Round 1 outputs are PROPOSALS, not decisions.** Do not present them as locked or settled in Round 2.
- **Only items the human explicitly confirms become locked decisions.** Platform consensus is not human approval.
- **The second round must provide an INDEPENDENT perspective** on the same questions — not a review of Round 1's conclusions.
- After both rounds complete, present a combined synthesis to the human. The human decides what is locked before any subsequent round (e.g., DoD drafting) begins.

---

### Phase 1 — Prepare the brief

Write a clear brief with:
- **GOAL**: what the system/document/architecture is supposed to achieve (1-2 paragraphs)
- **TASK**: what you want assessed (specific numbered questions, not open-ended)
- **CONTENT**: the artifact being reviewed (code, spec, DoD, architecture doc)

Save the brief as a file (`.txt` or `.md`). You'll need it for both platforms.

### Phase 2 — Fire both platforms in parallel

**Brain V8:**
```bash
python -m thinker.brain --brief <brief-file> --outdir output/<topic> --stop-after gate1 --verbose
```
Run step-by-step. Watch Gate 1's search decision — for closed reviews (code, specs, internal docs), search should be NO. Resume stage by stage.

**ChatGPT:**
Send the same brief. Use file upload for anything over ~4,000 characters (see ChatGPT Integration section below).

**Claude:**
While both are running, prepare your own observations. Don't wait — you'll have points neither platform raises.

### Phase 3 — Collect and map agreement

Once both respond, build a table:

| Finding | Brain V8 | ChatGPT | Claude |
|---------|----------|---------|--------|
| Finding A | Yes | Yes | — |
| Finding B | Yes | — | — |
| Finding C | — | Yes | — |
| Finding D | — | — | Yes |

This immediately shows:
- **Consensus**: both raised it independently — high confidence
- **Unique to one**: may be valid but needs verification
- **Claude additions**: genuine gaps neither platform saw

### Phase 4 — Cross-pollinate

Share Brain V8's report with ChatGPT. Ask specifically:
1. Do you agree with these findings?
2. Brain V8 raised X, Y, Z that you didn't — do you accept them?
3. You raised A, B, C that Brain V8 didn't — are these still distinct?
4. Do you accept Claude's additions?

This forces engagement rather than parallel monologues.

### Phase 5 — Draft the deliverable

Based on full agreement, **Claude drafts** the consolidated output (revised DoD, architecture decision, action plan — whatever the goal was).

Then send to ChatGPT for section-by-section review: ACCEPT / REVISE / REJECT.

### Phase 6 — Iterate until convergence

Address all REVISE feedback. Typically 1-2 rounds is enough. If a point is genuinely contested, flag it as "contested" in the deliverable with both positions stated.

---

## ChatGPT Integration — MCP Tools & Lessons Learned

### Available MCP tools (chatgpt-web)

| Tool | Purpose |
|------|---------|
| `mcp__chatgpt-web__chatgpt_new_chat` | Start a fresh conversation thread |
| `mcp__chatgpt-web__chatgpt_ask` | Send a prompt and get a response |
| `mcp__chatgpt-web__chatgpt_upload_file` | Upload a file to the current thread |
| `mcp__chatgpt-web__chatgpt_list_chats` | List recent conversations |
| `mcp__chatgpt-web__chatgpt_switch_chat` | Switch to an existing conversation |
| `mcp__chatgpt-web__chatgpt_list_models` | List available models |
| `mcp__chatgpt-web__chatgpt_set_model` | Switch the active model |

### The 5,000 character limit

ChatGPT's web UI converts any paste over ~5,000 characters into an attachment. Use file upload for any content over ~4,500 characters.

### Correct sequence when file upload is needed

```
1. chatgpt_new_chat()
   → Opens a fresh thread (preferred over chatgpt_ask with start_fresh=true)

2. chatgpt_upload_file(file_path="path/to/document.md")
   → File attaches to the current thread

3. chatgpt_ask(prompt="Review the uploaded file. <your question>")
   → ChatGPT reads the file and responds
```

**Why `chatgpt_new_chat()` not `chatgpt_ask(start_fresh=true)`:**
- `chatgpt_new_chat()` opens a clean thread with no dummy message in the context
- `start_fresh=true` is fine when there's no file upload, but adds a "Stand by" message to the thread history that pollutes context

### For multi-part inline prompts (under 5k each)

If you must split a prompt across messages:
```
Message 1: "I'll send this in 3 parts. Wait until I say END OF PARTS before responding."
Message 2: "PART 1 — [content]"
Message 3: "PART 2 — [content]"
Message 4: "PART 3 — END OF PARTS. Now respond."
```

### Thread recovery

If you need to return to a previous conversation:
```
1. chatgpt_list_chats()       → find the old thread by title
2. chatgpt_switch_chat(title) → switch back to it
3. chatgpt_ask(...)           → continue in the original thread
```

**Never use `start_fresh=true` to recover from errors** — it destroys context. Always switch back.

---

## Claude's Role as Facilitator — How to Prompt

When starting a facilitation session, the human should set context:

> "I want to run a combined deliberation. Brain V8 evaluates, ChatGPT advises, you facilitate and contribute your own points. Run both in parallel, then map agreement, cross-pollinate findings, and draft a consolidated output."

### Claude's responsibilities during facilitation:

1. **Before the run**: Prepare the brief, decide if search is needed, save as file
2. **During parallel runs**: Develop independent observations — don't wait passively
3. **After both respond**: Build the agreement map, identify unique findings from each
4. **Cross-pollination**: Share each platform's findings with the other, ask for engagement
5. **Drafting**: Write the consolidated deliverable based on full agreement
6. **Iteration**: Handle ChatGPT's section-by-section feedback, incorporate revisions
7. **Quality control**: Flag when ChatGPT over-prescribes or Brain V8 under-delivers on actionability

### Claude's contribution style:

- **Be objective.** You are a third perspective, not a cheerleader.
- **Name root causes.** Both platforms may describe symptoms — you should name the underlying gap (e.g., "credible is never operationalized" is the root cause of several scattered findings).
- **Be concise.** Add 2-4 points maximum. More dilutes impact.
- **Don't repeat.** If both platforms already said it, don't echo it — just note the consensus.

---

## Brain V8 — Brief Design for Different Tasks

### Closed review (code, spec, DoD)
- Bundle all relevant files into the brief
- Exclude non-logic files (debug, visualization, tests)
- Gate 1 should say SEARCH: NO
- Example: the self-review brief bundled 25 source files + V8-DOD.md

### Factual assessment (regulatory, technical claims)
- Brief states the claims to verify
- Gate 1 should say SEARCH: YES
- Evidence will be fetched and injected into rounds 1-2

### Architecture decision (should we use X or Y?)
- Brief states the options, constraints, and evaluation criteria
- Gate 1 decides search based on whether benchmarks/specs need verification
- Evidence resolves factual disputes; deliberation resolves trade-offs

### Gap analysis (does X meet requirement Y?)
- Brief = the artifact + the requirement spec + "identify gaps"
- Works best as a closed review (SEARCH: NO) unless the requirements reference external standards

---

## What NOT to Do

- **Don't let Brain V8 prescribe fixes.** Its job is verdict + evidence. If it starts suggesting solutions, the brief is too broad — tighten it.
- **Don't use ChatGPT as the sole evaluator.** It over-prescribes and drifts from constraints you haven't shared. Always cross-check with Brain V8.
- **Don't paste >4,500 characters into ChatGPT inline.** Use file upload.
- **Don't use `start_fresh=true` to recover from errors.** Switch back to the existing thread.
- **Don't skip the agreement map.** Without it, you're just reading two reports — the value is in the convergence and the gaps.
- **Don't run Brain V8 with `--full-run` during facilitation.** Use step-by-step so you can catch issues at each gate before they propagate.
- **Don't let Claude be passive.** The facilitator should contribute substantive points, not just relay messages.
