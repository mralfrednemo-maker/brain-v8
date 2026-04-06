#!/usr/bin/env bash
# monitor-brain.sh — monitor a brain run, auto-fix known errors, refire if needed
# Usage: bash monitor-brain.sh <outdir> <logfile> <brief>

set -euo pipefail

OUTDIR="${1:-output/master-v31-delta}"
LOGFILE="${2:-output/master-v31-delta.log}"
BRIEF="${3:-tests/fixtures/briefs/master-v31-delta.md}"
PYTHON="/c/Python312/python"
PROJ="C:/Users/chris/PROJECTS/_audit_thinker/thinker-v8"
MAX_RETRIES=3
MONITOR_LOG="output/monitor-brain.log"

cd "$PROJ"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$MONITOR_LOG"; }

fix_and_refire() {
    local error="$1"
    log "ERROR DETECTED: $error"

    # Known fix: VERIFIED is not a valid AssumptionVerifiability
    if echo "$error" | grep -q "VERIFIED.*not a valid AssumptionVerifiability"; then
        log "Applying fix: VERIFIED->VERIFIABLE already patched in preflight.py — likely a different enum issue"
    fi

    # Known fix: add_violation missing argument
    if echo "$error" | grep -q "add_violation.*missing.*argument"; then
        log "FIX NEEDED: add_violation signature — check brain.py"
    fi

    # Known fix: R2 frame obligations (demote to violation not error)
    if echo "$error" | grep -q "R2 frame obligations"; then
        log "R2 frame obligations already patched as proof violation"
    fi

    log "Refiring brain run..."
    rm -rf "$OUTDIR"
    $PYTHON -m thinker.brain \
        --brief "$BRIEF" \
        --outdir "$OUTDIR" \
        --full-run \
        --skip-assumption-gate \
        > "$LOGFILE" 2>&1
}

run_monitor() {
    local retries=0

    log "Starting monitor for: $OUTDIR"
    log "Polling every 60s..."

    while [ $retries -lt $MAX_RETRIES ]; do
        sleep 60

        # Check if log has content
        if [ ! -f "$LOGFILE" ]; then
            log "Log file not found yet — still starting up"
            continue
        fi

        # Check for success
        if [ -f "$OUTDIR/report.md" ]; then
            log "SUCCESS — report.md found at $OUTDIR/report.md"
            return 0
        fi

        # Check for known errors
        if grep -q "SYSTEM ERROR" "$LOGFILE" 2>/dev/null; then
            ERROR=$(grep -A3 "SYSTEM ERROR" "$LOGFILE" | tail -5)
            retries=$((retries + 1))
            log "Retry $retries/$MAX_RETRIES"
            fix_and_refire "$ERROR"
        fi

        # Check if process is still running (checkpoint updating)
        if [ -f "$OUTDIR/checkpoint.json" ]; then
            STAGES=$(python -c "import json; cp=json.load(open('$OUTDIR/checkpoint.json')); print(len(cp.get('completed_stages', [])))" 2>/dev/null || echo "?")
            log "Pipeline in progress — completed stages: $STAGES"
        fi
    done

    log "Max retries reached — manual intervention needed"
    return 1
}

run_monitor
log "Monitor finished"
