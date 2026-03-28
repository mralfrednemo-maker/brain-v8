#!/usr/bin/env bash
# brain-debug.sh — Default debug runner for Thinker V8 Brain
#
# Wraps python -m thinker.brain with --debug-step ON by default.
# Pass --no-step to disable step-by-step mode.
#
# Usage:
#   ./brain-debug.sh --brief briefs/b1.md --outdir output/b1
#   ./brain-debug.sh --brief briefs/b1.md --outdir output/b1 --no-step   # full run
#   ./brain-debug.sh --brief briefs/b1.md --outdir output/b1 --resume output/b1/checkpoint.json

set -euo pipefail
cd "$(dirname "$0")"

# Check for --no-step flag
NO_STEP=false
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--no-step" ]; then
        NO_STEP=true
    else
        ARGS+=("$arg")
    fi
done

# Add --debug-step unless --no-step was passed or --stop-after is present
if [ "$NO_STEP" = false ]; then
    HAS_STOP_AFTER=false
    for arg in "${ARGS[@]}"; do
        if [ "$arg" = "--stop-after" ]; then
            HAS_STOP_AFTER=true
            break
        fi
    done
    if [ "$HAS_STOP_AFTER" = false ]; then
        ARGS+=("--debug-step")
    fi
fi

echo "============================================================"
echo "  Thinker V8 Brain — Debug Runner"
echo "  Mode: $([ "$NO_STEP" = true ] && echo 'FULL RUN' || echo 'STEP-BY-STEP (press Enter at each stage, q to stop)')"
echo "============================================================"
echo

python -m thinker.brain "${ARGS[@]}"
