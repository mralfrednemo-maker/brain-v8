#!/usr/bin/env bash
# brain-debug.sh — Runner for Thinker V8 Brain
#
# DEFAULT: step-by-step mode (pauses after each stage).
# Pass --full-run to disable pausing and run all stages at once.
#
# Usage:
#   ./brain-debug.sh --brief briefs/b1.md --outdir output/b1
#   ./brain-debug.sh --brief briefs/b1.md --outdir output/b1 --full-run

set -euo pipefail
cd "$(dirname "$0")"

HAS_FULL_RUN=false
for arg in "$@"; do
    if [ "$arg" = "--full-run" ]; then
        HAS_FULL_RUN=true
        break
    fi
done

echo "============================================================"
echo "  Thinker V8 Brain"
echo "  Mode: $([ "$HAS_FULL_RUN" = true ] && echo 'FULL RUN (no pauses)' || echo 'STEP-BY-STEP (default — press Enter at each stage, q to stop)')"
echo "============================================================"
echo

python -m thinker.brain "$@"
