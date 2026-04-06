# Thinker Repo Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the thinker ecosystem into a clean multi-platform, multi-version layout under a single `thinker/` repo.

**Architecture:** Copy (not move) all platform code into versioned directories under `brain/`, `chamber/`, `controller/`, `ein/`, `tools/`. No source files are deleted. V9 brain module is renamed from `thinker/` to `brain/` everywhere. V10 starts as a clean copy of V9 brain + tests.

**Tech Stack:** Python 3.11+, git, bash (WSL Ubuntu)

---

## File Map

**Created:**
- `brain/v9/brain/` — copy of `_audit_thinker/thinker-v8/thinker/` (renamed module)
- `brain/v9/tests/` — copy of `_audit_thinker/thinker-v8/tests/`
- `brain/v9/pyproject.toml` — adapted from `_audit_thinker/thinker-v8/pyproject.toml`
- `brain/v9/output/` — copy of `_audit_thinker/thinker-v8/output/`
- `brain/v9/*.md`, `brain/v9/*.py`, `brain/v9/*.sh` — V9 support files
- `brain/v10/brain/` — copy of `brain/v9/brain/` (starting point for V10 deltas)
- `brain/v10/tests/` — copy of `brain/v9/tests/` (adapted imports)
- `brain/v10/pyproject.toml` — version = "10.0.0"
- `brain/legacy/brain-v3-orchestrator.py` — from `the-thinker/`
- `chamber/v3/chamber/consensus_runner.py` — from `the-thinker/consensus_runner_v3.py`
- `chamber/v3/tests/` — 3 test files from `the-thinker/tests/`
- `controller/mission_controller.py`, `controller/validate_bundle.py`, `controller/run-e2e-tests.sh`
- `ein/` — 6 Python files + README (paths updated)
- `tools/browser-automation/` — from `the-thinker/browser-automation/`
- `briefs/` — 7 brief files
- `docs/design/` — all design/DOD/MASTER docs
- `docs/protocols/` — three-way-deliberation and protocol files
- `docs/archive/` — THINKER-DOD-AND-PLAN.md and older docs
- `README.md` — updated architecture overview

---

### Task 1: Create directory skeleton

**Files:**
- Create: `brain/v9/`, `brain/v10/`, `brain/legacy/`, `chamber/v3/`, `controller/`, `ein/`, `tools/`, `briefs/`, `docs/design/`, `docs/protocols/`, `docs/archive/`

- [ ] **Step 1: Create all directories**

Run from repo root (`C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8/`):

```bash
mkdir -p brain/v9 brain/v10/brain brain/v10/tests brain/legacy
mkdir -p chamber/v3/chamber chamber/v3/tests
mkdir -p controller ein tools/browser-automation
mkdir -p briefs docs/design docs/protocols docs/archive
```

- [ ] **Step 2: Verify**

```bash
find . -maxdepth 3 -type d | grep -E "^./(brain|chamber|controller|ein|tools|briefs|docs)" | sort
```

Expected: all directories listed above.

- [ ] **Step 3: Commit skeleton**

```bash
git add brain/ chamber/ controller/ ein/ tools/ briefs/ docs/
git commit -m "chore: create thinker multi-platform directory skeleton"
```

---

### Task 2: Copy Brain V9

**Files:**
- Create: `brain/v9/brain/` (all 33 files renamed from `thinker/`)
- Create: `brain/v9/tests/`
- Create: `brain/v9/pyproject.toml`
- Create: `brain/v9/output/`
- Create: `brain/v9/*.md`, `brain/v9/*.sh`, `brain/v9/*.py`

- [ ] **Step 1: Copy module and tests**

```bash
cp -r thinker/ brain/v9/brain/
cp -r tests/ brain/v9/tests/
cp -r output/ brain/v9/output/
```

- [ ] **Step 2: Copy support files**

```bash
cp pyproject.toml brain/v9/pyproject.toml
cp auto-heal.sh brain-debug.sh monitor-brain.sh brain/v9/ 2>/dev/null || true
cp build_self_review.py build_self_review_v9.py brain/v9/ 2>/dev/null || true
cp HANDOFF.md HANDOFF-NEXT.md brain/v9/ 2>/dev/null || true
cp HANDOVER-BRAIN-V8-NEXT.md OPERATIONS.md brain/v9/ 2>/dev/null || true
cp V8-DOD*.md brain/v9/ 2>/dev/null || true
```

- [ ] **Step 3: Update V9 pyproject.toml**

Edit `brain/v9/pyproject.toml`:

```toml
[project]
name = "brain-v9"
version = "9.0.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "anthropic>=0.40",
    "playwright>=1.48",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 4: Fix imports — rename thinker → brain in V9 module**

```bash
# All internal imports: from thinker.X → from brain.X
find brain/v9/brain/ -name "*.py" -exec sed -i 's/from thinker\./from brain\./g' {} +
find brain/v9/brain/ -name "*.py" -exec sed -i 's/import thinker\./import brain\./g' {} +
# Fix tests
find brain/v9/tests/ -name "*.py" -exec sed -i 's/from thinker\./from brain\./g' {} +
find brain/v9/tests/ -name "*.py" -exec sed -i 's/import thinker\./import brain\./g' {} +
```

- [ ] **Step 5: Verify import rename**

```bash
grep -r "from thinker\." brain/v9/ | head -5
grep -r "import thinker\." brain/v9/ | head -5
```

Expected: no results (all renamed to `brain.`).

- [ ] **Step 6: Commit V9**

```bash
git add brain/v9/
git commit -m "chore: copy Brain V9 into brain/v9/ (rename module thinker→brain)"
```

---

### Task 3: Create Brain V10 starting point

**Files:**
- Create: `brain/v10/brain/` (copy of V9, imports already correct)
- Create: `brain/v10/tests/`
- Create: `brain/v10/pyproject.toml`

- [ ] **Step 1: Copy V9 brain and tests into V10**

```bash
cp -r brain/v9/brain/ brain/v10/brain/
cp -r brain/v9/tests/ brain/v10/tests/
```

- [ ] **Step 2: Create V10 pyproject.toml**

Create `brain/v10/pyproject.toml`:

```toml
[project]
name = "brain-v10"
version = "10.0.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "anthropic>=0.40",
    "playwright>=1.48",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Verify V10 is self-contained**

```bash
cd brain/v10
python -c "import sys; sys.path.insert(0, '.'); from brain.types import Outcome; print('OK')"
cd ../..
```

Expected: `OK`

- [ ] **Step 4: Commit V10 baseline**

```bash
git add brain/v10/
git commit -m "chore: create Brain V10 baseline (copy of V9, ready for V3.1 deltas)"
```

---

### Task 4: Copy Brain V3 legacy

**Files:**
- Create: `brain/legacy/brain-v3-orchestrator.py`

- [ ] **Step 1: Copy legacy file**

```bash
cp "C:/Users/chris/PROJECTS/the-thinker/brain-v3-orchestrator.py" brain/legacy/
```

- [ ] **Step 2: Commit**

```bash
git add brain/legacy/
git commit -m "chore: archive Brain V3 orchestrator to brain/legacy/"
```

---

### Task 5: Copy Chamber V3

**Files:**
- Create: `chamber/v3/chamber/consensus_runner.py`
- Create: `chamber/v3/tests/test_explicit_options.py`, `test_search_gate.py`, `test_slp.py`

- [ ] **Step 1: Copy chamber module**

```bash
cp "C:/Users/chris/PROJECTS/the-thinker/consensus_runner_v3.py" chamber/v3/chamber/consensus_runner.py
touch chamber/v3/chamber/__init__.py
```

- [ ] **Step 2: Copy tests**

```bash
cp "C:/Users/chris/PROJECTS/the-thinker/tests/test_explicit_options.py" chamber/v3/tests/
cp "C:/Users/chris/PROJECTS/the-thinker/tests/test_search_gate.py" chamber/v3/tests/
cp "C:/Users/chris/PROJECTS/the-thinker/tests/test_slp.py" chamber/v3/tests/
```

- [ ] **Step 3: Commit**

```bash
git add chamber/v3/
git commit -m "chore: copy Chamber V3 into chamber/v3/"
```

---

### Task 6: Copy Controller and Ein

**Files:**
- Create: `controller/mission_controller.py`, `controller/validate_bundle.py`, `controller/run-e2e-tests.sh`
- Create: `ein/` (6 Python files + README)

- [ ] **Step 1: Copy controller**

```bash
cp "C:/Users/chris/PROJECTS/the-thinker/mission_controller.py" controller/
cp "C:/Users/chris/PROJECTS/the-thinker/validate_bundle.py" controller/
cp "C:/Users/chris/PROJECTS/the-thinker/run-e2e-tests.sh" controller/
```

- [ ] **Step 2: Copy Ein files**

```bash
cp "C:/Users/chris/PROJECTS/the-thinker/ein/"*.py ein/
cp "C:/Users/chris/PROJECTS/the-thinker/ein/README.md" ein/
cp "C:/Users/chris/PROJECTS/the-thinker/ein/cross4-final-position-lock-prompt.txt" ein/ 2>/dev/null || true
```

- [ ] **Step 3: Fix Ein hardcoded paths**

In `ein/ein-design.py` and `ein/ein-parallel.py`, update any path references:

```bash
# Replace old path prefix with new one
find ein/ -name "*.py" -exec sed -i \
  's|_audit_thinker/thinker-v8/|brain/v9/|g' {} +
find ein/ -name "*.py" -exec sed -i \
  's|_audit_thinker\\thinker-v8\\|brain\\v9\\|g' {} +
```

- [ ] **Step 4: Fix Ein README browser-automation path**

```bash
sed -i 's|browser-automation/|tools/browser-automation/|g' ein/README.md
```

- [ ] **Step 5: Commit**

```bash
git add controller/ ein/
git commit -m "chore: copy Controller and Ein; fix Ein hardcoded paths"
```

---

### Task 7: Copy tools, briefs, and docs

**Files:**
- Create: `tools/browser-automation/`
- Create: `briefs/` (7 briefs)
- Create: `docs/design/`, `docs/protocols/`, `docs/archive/`

- [ ] **Step 1: Copy browser automation tools**

```bash
cp -r "C:/Users/chris/PROJECTS/the-thinker/browser-automation/"* tools/browser-automation/
```

- [ ] **Step 2: Copy briefs**

```bash
cp "C:/Users/chris/PROJECTS/the-thinker/briefs/"*.md briefs/
```

- [ ] **Step 3: Copy design docs**

```bash
cp "C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8/output/design-session/"*.md docs/design/
cp "C:/Users/chris/Downloads/BRAIN-V10-DESIGN-DOD-DELTA.txt" docs/design/
```

- [ ] **Step 4: Copy protocol docs**

```bash
cp "C:/Users/chris/PROJECTS/the-thinker/three-way-deliberation.md" docs/protocols/
cp "C:/Users/chris/PROJECTS/the-thinker/protocols/"*.md docs/protocols/ 2>/dev/null || true
```

- [ ] **Step 5: Copy archive docs**

```bash
cp "C:/Users/chris/PROJECTS/_audit_thinker/THINKER-DOD-AND-PLAN.md" docs/archive/
cp "C:/Users/chris/PROJECTS/_audit_thinker/docs/"*.md docs/archive/ 2>/dev/null || true
```

- [ ] **Step 6: Commit**

```bash
git add tools/ briefs/ docs/
git commit -m "chore: copy tools, briefs, and design docs into thinker repo"
```

---

### Task 8: Update root README and CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md` (if exists at root)

- [ ] **Step 1: Create root README.md**

Create `README.md` at repo root:

```markdown
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
```

- [ ] **Step 2: Copy the-thinker CLAUDE.md to root if not present**

```bash
cp "C:/Users/chris/PROJECTS/the-thinker/CLAUDE.md" CLAUDE.md 2>/dev/null || true
```

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: add root README with thinker platform overview"
```

---

### Task 9: Verify V10 tests run

- [ ] **Step 1: Install V10 in dev mode**

```bash
cd brain/v10
pip install -e ".[dev]"
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -x -q 2>&1 | tail -20
```

Expected: same pass/fail ratio as V9 (all 349 tests pass, or same failures as V9 baseline).

- [ ] **Step 3: Record baseline**

```bash
pytest tests/ -q 2>&1 | tail -5 > ../../docs/design/v10-test-baseline.txt
cat ../../docs/design/v10-test-baseline.txt
```

- [ ] **Step 4: Commit**

```bash
cd ../..
git add docs/design/v10-test-baseline.txt
git commit -m "chore: record V10 test baseline before delta implementation"
```

---

### Task 10: Rename GitHub repo (manual step)

- [ ] **Step 1: Rename repo on GitHub**

Go to `https://github.com/mralfrednemo-maker/brain-v8` → Settings → Repository name → change to `thinker`.

- [ ] **Step 2: Update remote URL**

```bash
git remote set-url origin https://github.com/mralfrednemo-maker/thinker.git
git remote -v
```

Expected: `origin https://github.com/mralfrednemo-maker/thinker.git`

- [ ] **Step 3: Push restructured repo**

```bash
git push origin master
```

---

**Restructuring complete.** V10 baseline is in `brain/v10/` with all V9 tests passing. Ready for Brain V10 delta implementation plan.
