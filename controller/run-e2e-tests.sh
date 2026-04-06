#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# run-e2e-tests.sh — E2E test runner for Mission Controller
#
# This script runs all 9 test cases, captures outputs into clean per-test
# bundle directories, and produces a summary report.
#
# Usage:
#   cd /path/to/mission-controller-package
#   bash run-e2e-tests.sh [--rounds 2] [--budget 1800] [--tests T1,T3,T4]
#
# Each test creates:
#   results/<test-id>/
#     ├── mission-proof.json      ← canonical authority artifact
#     ├── mission.log             ← controller log
#     ├── brain-proof.json        ← Brain proof (if Brain ran)
#     ├── chamber.log             ← Chamber log (if Chamber ran)
#     ├── discrepancy.json        ← discrepancy packet (parallel only)
#     ├── hermes-report.md        ← Brain synthesis report (if produced)
#     └── test-meta.json          ← test metadata + pass/fail + timing
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
REPORTS_DIR="$SCRIPT_DIR/reports"
MC="$SCRIPT_DIR/mission_controller.py"
BRIEFS_DIR="$SCRIPT_DIR/briefs"

ROUNDS=4
BUDGET=3600
RUN_TESTS=""

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rounds) ROUNDS="$2"; shift 2 ;;
        --budget) BUDGET="$2"; shift 2 ;;
        --tests)  RUN_TESTS="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

mkdir -p "$RESULTS_DIR" "$REPORTS_DIR"

# ── Helpers ────────────────────────────────────────────────────────────────

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

run_test() {
    local TEST_ID="$1"
    local BRIEF="$2"
    local MODE="$3"
    local TEST_ROUNDS="${4:-$ROUNDS}"
    local EXPECTED_MODE="$5"
    local EXPECTED_AUTHORITY="$6"
    local DESCRIPTION="$7"

    # Skip if --tests specified and this test not in list
    if [[ -n "$RUN_TESTS" ]] && [[ ! ",$RUN_TESTS," == *",$TEST_ID,"* ]]; then
        log "SKIP $TEST_ID (not in --tests list)"
        return 0
    fi

    local TEST_DIR="$RESULTS_DIR/$TEST_ID"
    rm -rf "$TEST_DIR"
    mkdir -p "$TEST_DIR"

    log "═══ $TEST_ID: $DESCRIPTION ═══"
    log "  Brief: $BRIEF"
    log "  Mode: $MODE"
    log "  Expected: mode=$EXPECTED_MODE authority=$EXPECTED_AUTHORITY"

    # Clean reports dir before each test to avoid stale files
    rm -f "$REPORTS_DIR"/mission-* "$REPORTS_DIR"/discrepancy-* "$REPORTS_DIR"/chamber-v3-*.log

    local START_TIME
    START_TIME=$(date +%s)

    local EXIT_CODE=0
    local STDOUT_FILE="$TEST_DIR/stdout.log"

    # Build command
    local CMD="python3 $MC --brief $BRIEFS_DIR/$BRIEF --rounds $TEST_ROUNDS --budget $BUDGET"
    if [[ "$MODE" != "auto" ]]; then
        CMD="$CMD --mode $MODE"
    fi

    # Run
    log "  Running: $CMD"
    if $CMD > "$STDOUT_FILE" 2>&1; then
        EXIT_CODE=0
    else
        EXIT_CODE=$?
    fi

    local END_TIME
    END_TIME=$(date +%s)
    local ELAPSED=$((END_TIME - START_TIME))
    log "  Completed in ${ELAPSED}s (exit=$EXIT_CODE)"

    # ── Collect artifacts ──

    # Mission proof (find the latest one)
    local LATEST_PROOF
    LATEST_PROOF=$(ls -t "$REPORTS_DIR"/mission-proof-*.json 2>/dev/null | head -1 || true)
    if [[ -n "$LATEST_PROOF" ]]; then
        cp "$LATEST_PROOF" "$TEST_DIR/mission-proof.json"
    fi

    # Mission log
    local LATEST_LOG
    LATEST_LOG=$(ls -t "$REPORTS_DIR"/mission-*.log 2>/dev/null | head -1 || true)
    if [[ -n "$LATEST_LOG" ]]; then
        cp "$LATEST_LOG" "$TEST_DIR/mission.log"
    fi

    # Discrepancy packet
    local LATEST_DISC
    LATEST_DISC=$(ls -t "$REPORTS_DIR"/discrepancy-*.json 2>/dev/null | head -1 || true)
    if [[ -n "$LATEST_DISC" ]]; then
        cp "$LATEST_DISC" "$TEST_DIR/discrepancy.json"
    fi

    # Brain proof (find in brain-* subdirs)
    local BRAIN_DIR
    BRAIN_DIR=$(ls -dt "$REPORTS_DIR"/brain-* 2>/dev/null | head -1 || true)
    if [[ -n "$BRAIN_DIR" && -d "$BRAIN_DIR" ]]; then
        [[ -f "$BRAIN_DIR/proof.json" ]] && cp "$BRAIN_DIR/proof.json" "$TEST_DIR/brain-proof.json"
        [[ -f "$BRAIN_DIR/hermes-final-report.md" ]] && cp "$BRAIN_DIR/hermes-final-report.md" "$TEST_DIR/hermes-report.md"
        [[ -f "$BRAIN_DIR/orchestrator.log" ]] && cp "$BRAIN_DIR/orchestrator.log" "$TEST_DIR/brain-orchestrator.log"
    fi

    # Chamber log
    local LATEST_CHAMBER
    LATEST_CHAMBER=$(ls -t "$REPORTS_DIR"/chamber-v3-*.log 2>/dev/null | grep -v trace | head -1 || true)
    if [[ -n "$LATEST_CHAMBER" ]]; then
        cp "$LATEST_CHAMBER" "$TEST_DIR/chamber.log"
    fi

    # ── Validate ──

    local PASS="UNKNOWN"
    local ACTUAL_MODE=""
    local ACTUAL_AUTH=""
    local ACTUAL_ACCEPT=""
    local FAIL_REASONS=""

    if [[ -f "$TEST_DIR/mission-proof.json" ]]; then
        ACTUAL_MODE=$(python3 -c "import json; print(json.load(open('$TEST_DIR/mission-proof.json')).get('mode','?'))" 2>/dev/null || echo "?")
        ACTUAL_AUTH=$(python3 -c "import json; print(json.load(open('$TEST_DIR/mission-proof.json')).get('final_authority','?'))" 2>/dev/null || echo "?")
        ACTUAL_ACCEPT=$(python3 -c "import json; print(json.load(open('$TEST_DIR/mission-proof.json')).get('acceptance_status','?'))" 2>/dev/null || echo "?")

        PASS="PASS"

        # Check expected mode (allow degraded variants)
        if [[ "$ACTUAL_MODE" != "$EXPECTED_MODE" && "$ACTUAL_MODE" != "${EXPECTED_MODE}_degraded" ]]; then
            PASS="FAIL"
            FAIL_REASONS="${FAIL_REASONS}mode=$ACTUAL_MODE (expected $EXPECTED_MODE); "
        fi

        # Check expected authority
        if [[ "$ACTUAL_AUTH" != "$EXPECTED_AUTHORITY" ]]; then
            # For parallel, authority depends on brief classification
            if [[ "$EXPECTED_AUTHORITY" == "classification" ]]; then
                # Accept either brain or chamber for classification-dependent tests
                if [[ "$ACTUAL_AUTH" != "brain" && "$ACTUAL_AUTH" != "chamber" ]]; then
                    PASS="FAIL"
                    FAIL_REASONS="${FAIL_REASONS}authority=$ACTUAL_AUTH (expected brain or chamber); "
                fi
            else
                PASS="FAIL"
                FAIL_REASONS="${FAIL_REASONS}authority=$ACTUAL_AUTH (expected $EXPECTED_AUTHORITY); "
            fi
        fi

        # Check acceptance
        if [[ "$ACTUAL_ACCEPT" != "ACCEPTED" ]]; then
            PASS="FAIL"
            FAIL_REASONS="${FAIL_REASONS}acceptance=$ACTUAL_ACCEPT; "
        fi
    else
        PASS="FAIL"
        FAIL_REASONS="no mission-proof.json produced; "
    fi

    # ── Write test metadata ──

    python3 -c "
import json
meta = {
    'test_id': '$TEST_ID',
    'description': '$DESCRIPTION',
    'brief': '$BRIEF',
    'mode_requested': '$MODE',
    'expected_mode': '$EXPECTED_MODE',
    'expected_authority': '$EXPECTED_AUTHORITY',
    'actual_mode': '$ACTUAL_MODE',
    'actual_authority': '$ACTUAL_AUTH',
    'actual_acceptance': '$ACTUAL_ACCEPT',
    'exit_code': $EXIT_CODE,
    'elapsed_seconds': $ELAPSED,
    'pass': '$PASS' == 'PASS',
    'fail_reasons': '$FAIL_REASONS'.strip('; ') if '$FAIL_REASONS' else None,
}
print(json.dumps(meta, indent=2))
" > "$TEST_DIR/test-meta.json"

    if [[ "$PASS" == "PASS" ]]; then
        log "  ✅ PASS: mode=$ACTUAL_MODE authority=$ACTUAL_AUTH accepted=$ACTUAL_ACCEPT (${ELAPSED}s)"
    else
        log "  ❌ FAIL: $FAIL_REASONS(${ELAPSED}s)"
    fi

    echo ""
}

# ── Test Definitions ────────────────────────────────────────────────────────

log "Mission Controller E2E Test Suite"
log "Rounds: $ROUNDS  Budget: ${BUDGET}s"
log ""

# T1: Brain-only factual incident (auto-routed) — 4 rounds for max convergence
run_test "T1" "b1-brain-factual-incident.md" "auto" "4" \
    "brain_only" "brain" "Brain-only factual incident (auto-routed, 4 rounds)"

# T2: Chamber-only vendor selection (auto-routed)
run_test "T2" "b2-chamber-vendor-selection.md" "auto" "$ROUNDS" \
    "chamber_only" "chamber" "Chamber-only vendor selection (auto-routed)"

# T3: Cascade — hybrid database migration (auto-routed)
run_test "T3" "b3-cascade-db-migration.md" "auto" "$ROUNDS" \
    "cascade" "chamber" "Cascade DB migration (auto-routed)"

# T4: Parallel — incident response (manual parallel)
run_test "T4" "b4-parallel-incident-response.md" "parallel" "2" \
    "parallel" "classification" "Parallel incident response (manual)"

# T5: Open-ended brief — cascade (Brain explores, then Chamber selects)
run_test "T5" "b5-ambiguous-team-structure.md" "auto" "$ROUNDS" \
    "cascade" "chamber" "Open-ended brief (auto → cascade for broader exploration)"

# T6: Cascade with open-ended brief (manual cascade)
run_test "T6" "b6-cascade-open-ended-sla.md" "cascade" "$ROUNDS" \
    "cascade" "chamber" "Cascade open-ended SLA (option safeguard test)"

# T7: Brain-only regulatory factual (auto-routed) — 4 rounds for max convergence
run_test "T7" "b7-brain-regulatory-factual.md" "auto" "4" \
    "brain_only" "brain" "Brain-only regulatory factual (auto-routed, 4 rounds)"

# T8: Forced Brain-only on recommendation brief
run_test "T8" "b4-parallel-incident-response.md" "brain" "3" \
    "brain_only" "brain" "Forced brain-only on recommendation brief"

# T9: Forced Chamber-only on same brief
run_test "T9" "b4-parallel-incident-response.md" "chamber" "$ROUNDS" \
    "chamber_only" "chamber" "Forced chamber-only on recommendation brief"

# ── Summary ────────────────────────────────────────────────────────────────

log "═══════════════════════════════════════════════════════════════"
log "E2E Test Summary"
log "═══════════════════════════════════════════════════════════════"

TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0

for TEST_DIR in "$RESULTS_DIR"/T*; do
    [[ -d "$TEST_DIR" ]] || continue
    TEST_ID=$(basename "$TEST_DIR")
    if [[ -f "$TEST_DIR/test-meta.json" ]]; then
        TOTAL=$((TOTAL + 1))
        IS_PASS=$(python3 -c "import json; print(json.load(open('$TEST_DIR/test-meta.json')).get('pass', False))" 2>/dev/null)
        DESC=$(python3 -c "import json; print(json.load(open('$TEST_DIR/test-meta.json')).get('description', '?'))" 2>/dev/null)
        ELAPSED=$(python3 -c "import json; print(json.load(open('$TEST_DIR/test-meta.json')).get('elapsed_seconds', '?'))" 2>/dev/null)
        if [[ "$IS_PASS" == "True" ]]; then
            PASSED=$((PASSED + 1))
            log "  ✅ $TEST_ID: $DESC (${ELAPSED}s)"
        else
            FAILED=$((FAILED + 1))
            REASON=$(python3 -c "import json; print(json.load(open('$TEST_DIR/test-meta.json')).get('fail_reasons', '?'))" 2>/dev/null)
            log "  ❌ $TEST_ID: $DESC — $REASON"
        fi
    fi
done

log ""
log "Total: $TOTAL  Passed: $PASSED  Failed: $FAILED"

if [[ $FAILED -gt 0 ]]; then
    log ""
    log "Failed test bundles are in: $RESULTS_DIR/T*"
    log "Check test-meta.json and mission.log in each failed test directory."
    exit 1
else
    log ""
    log "All tests passed."
    exit 0
fi
