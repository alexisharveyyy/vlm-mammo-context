#!/bin/sh
# Run one tier (docs/RUN_DESIGN.md) for every model in order, resumably.
#
#   nohup sh scripts/run_tier.sh T0 > /dev/null 2>&1 &
#
# Each model runs under caffeinate through the pinned runner. Progress goes to
# data/logs/<tier>_<model>.log (local, not committed). Rerunning the same
# command resumes where it stopped. Stops at the first model that fails.
set -u

tier="$1"
models="${MODELS:-qwen3_vl_8b medgemma_1_5_4b internvl3_5_8b}"
cd "$(git rev-parse --show-toplevel)"
mkdir -p data/logs

for model in $models; do
    log="data/logs/${tier}_${model}.log"
    echo "$(date -u +%FT%TZ) start $tier $model" >> "$log"
    caffeinate -dimsu uv run python scripts/pinned_step.py --config configs/models.yaml -- \
        uv run --group models python -m models.run --tier "$tier" --model "$model" >> "$log" 2>&1
    status=$?
    echo "$(date -u +%FT%TZ) end $tier $model exit=$status" >> "$log"
    if [ "$status" -ne 0 ]; then
        echo "$(date -u +%FT%TZ) stopping: $model exited $status" >> "data/logs/${tier}.status"
        exit "$status"
    fi
done
echo "$(date -u +%FT%TZ) $tier complete" >> "data/logs/${tier}.status"
