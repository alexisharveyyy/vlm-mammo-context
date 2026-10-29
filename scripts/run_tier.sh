#!/bin/sh
# Run one tier (docs/RUN_DESIGN.md) for every model in order, resumably, then
# the following tiers up to T4.
#
#   nohup sh scripts/run_tier.sh T1 > /dev/null 2>&1 &
#
# Each model runs under caffeinate through the pinned runner. Progress goes to
# data/logs/<tier>_<model>.log (local, not committed). Rerunning the same
# command resumes where it stopped. A model that exits non-zero is retried up
# to RETRIES times (default 2), resuming from its completed calls, except after
# a determinism audit mismatch (exit 3), which stops at once. A model that still
# fails stops the chain. CHAIN=0 runs this tier only.
set -u

tier="$1"
models="${MODELS:-qwen3_vl_8b medgemma_1_5_4b internvl3_5_8b}"
retries="${RETRIES:-2}"
pause="${RETRY_PAUSE:-60}"
cd "$(git rev-parse --show-toplevel)"
mkdir -p data/logs
export PYTHONUNBUFFERED=1

for model in $models; do
    log="data/logs/${tier}_${model}.log"
    attempt=0
    while :; do
        attempt=$((attempt + 1))
        echo "$(date -u +%FT%TZ) start $tier $model attempt $attempt" >> "$log"
        caffeinate -dimsu uv run python scripts/pinned_step.py --config configs/models.yaml -- \
            uv run --group models python -m models.run --tier "$tier" --model "$model" >> "$log" 2>&1
        status=$?
        echo "$(date -u +%FT%TZ) end $tier $model exit=$status" >> "$log"
        if [ "$status" -eq 0 ]; then
            break
        fi
        if [ "$status" -eq 3 ] || [ "$attempt" -gt "$retries" ]; then
            echo "$(date -u +%FT%TZ) stopping: $model exited $status (attempt $attempt)" \
                >> "data/logs/${tier}.status"
            exit "$status"
        fi
        echo "$(date -u +%FT%TZ) retrying: $model exited $status (attempt $attempt)" \
            >> "data/logs/${tier}.status"
        sleep "$pause"
    done
done
echo "$(date -u +%FT%TZ) $tier complete" >> "data/logs/${tier}.status"

case "$tier" in
    T0) next=T1 ;;
    T1) next=T2 ;;
    T2) next=T3 ;;
    T3) next=T4 ;;
    *) next= ;;
esac
if [ -n "$next" ] && [ "${CHAIN:-1}" != 0 ]; then
    exec sh scripts/run_tier.sh "$next"
fi
