#!/usr/bin/env bash
# auto-heal.sh — autonomous Brain V9 self-healing loop
# Runs N rounds: test → commit → rebuild brief → run brain → read report → fire Codex → repeat
# Usage: bash auto-heal.sh [rounds=5]

set -euo pipefail

ROUNDS="${1:-5}"
PROJ="C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8"
CODEX_BIN="node C:/Users/chris/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs"
LOG_DIR="$PROJ/output/auto-heal-logs"
mkdir -p "$LOG_DIR"

echo "[auto-heal] Starting autonomous loop — $ROUNDS rounds"
echo "[auto-heal] $(date)"

for i in $(seq 1 "$ROUNDS"); do
    ROUND_NUM=$(($(ls "$PROJ/output/" | grep -E "^self-review-v9-round[0-9]+" | grep -oE "[0-9]+" | sort -n | tail -1) + 1))
    echo ""
    echo "========================================"
    echo "[auto-heal] === Iteration $i / $ROUNDS ==="
    echo "[auto-heal] === Brain round $ROUND_NUM ==="
    echo "========================================"

    # --- Step 1: Run tests ---
    echo "[auto-heal] Running tests..."
    cd "$PROJ"
    if ! python -m pytest tests/ -x -q > "$LOG_DIR/tests-round${ROUND_NUM}.log" 2>&1; then
        echo "[auto-heal] TESTS FAILED — aborting loop"
        cat "$LOG_DIR/tests-round${ROUND_NUM}.log" | tail -20
        exit 1
    fi
    PASSED=$(grep -oE "[0-9]+ passed" "$LOG_DIR/tests-round${ROUND_NUM}.log" | tail -1)
    echo "[auto-heal] Tests OK: $PASSED"

    # --- Step 2: Commit ---
    echo "[auto-heal] Committing changes..."
    cd "$PROJ"
    git add -A
    if git diff --cached --quiet; then
        echo "[auto-heal] Nothing to commit — skipping"
    else
        git commit -m "Brain V9 auto-heal: pre-round-${ROUND_NUM} fixes

Automated commit from auto-heal.sh before round $ROUND_NUM.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
        echo "[auto-heal] Committed"
    fi

    # --- Step 3: Rebuild brief ---
    echo "[auto-heal] Rebuilding brief..."
    BRIEF_OUT=$(python build_self_review_v9.py 2>&1)
    echo "[auto-heal] $BRIEF_OUT"

    # --- Step 4: Run brain ---
    OUTDIR="$PROJ/output/self-review-v9-round${ROUND_NUM}"
    LOGFILE="$PROJ/output/round${ROUND_NUM}.log"
    echo "[auto-heal] Launching brain round $ROUND_NUM..."
    python -m thinker.brain \
        --brief tests/fixtures/briefs/self-review-v9.md \
        --outdir "$OUTDIR" \
        --full-run \
        --skip-assumption-gate \
        > "$LOGFILE" 2>&1
    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        echo "[auto-heal] Brain run FAILED (exit $EXIT_CODE)"
        tail -30 "$LOGFILE"
        echo "[auto-heal] Aborting loop"
        exit 1
    fi

    REPORT="$OUTDIR/report.md"
    if [ ! -f "$REPORT" ]; then
        echo "[auto-heal] No report generated — aborting"
        exit 1
    fi

    echo "[auto-heal] Brain round $ROUND_NUM complete"

    # --- Step 5: Extract verdict ---
    VERDICT=$(grep -E "^\*\*Classification:" "$REPORT" | head -1 || echo "UNKNOWN")
    VERDICT_LINE=$(grep -E "^## Verdict|^\*\*Verdict|^Both models agree" "$REPORT" | head -1 || echo "")
    echo "[auto-heal] Verdict: $VERDICT"
    echo "[auto-heal] $VERDICT_LINE"

    # If DECIDE or clean consensus, stop
    if echo "$VERDICT" | grep -qiE "DECIDE|COMPLIANT|CLEAN"; then
        echo "[auto-heal] Clean verdict reached — stopping loop"
        break
    fi

    # --- Step 6: Fire Codex with full report ---
    echo "[auto-heal] Sending report to Codex for fixes..."
    REPORT_CONTENT=$(cat "$REPORT")

    $CODEX_BIN task --model gpt-5.4 --fresh --write \
"Brain V9 deliberation pipeline (thinker-v8 project). The Brain just completed Round $ROUND_NUM of its self-review audit. Below is the full report. Implement ALL actionable CRITICAL and IMPORTANT findings from the Key Findings section.

Rules:
- Only fix things that are verifiable in the actual source files — do not guess at unverifiable gaps
- Do NOT touch SHORT_CIRCUIT enforcement (explicitly deferred)
- Do NOT touch token/budget enforcement (explicitly deferred)
- After all fixes, run: python -m pytest tests/ -x -q
- All tests must pass before finishing

FULL REPORT:
$REPORT_CONTENT" \
        > "$LOG_DIR/codex-round${ROUND_NUM}.log" 2>&1

    CODEX_EXIT=$?
    if [ $CODEX_EXIT -ne 0 ]; then
        echo "[auto-heal] Codex FAILED (exit $CODEX_EXIT)"
        tail -20 "$LOG_DIR/codex-round${ROUND_NUM}.log"
        echo "[auto-heal] Aborting loop"
        exit 1
    fi

    # Check Codex result
    CODEX_RESULT=$(tail -5 "$LOG_DIR/codex-round${ROUND_NUM}.log")
    echo "[auto-heal] Codex done: $CODEX_RESULT"

    echo "[auto-heal] Iteration $i complete — sleeping 5s before next round"
    sleep 5
done

echo ""
echo "[auto-heal] Loop finished at $(date)"
echo "[auto-heal] Final round: $ROUND_NUM"
