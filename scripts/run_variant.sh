#!/bin/sh
# Run one Phase 7 robustness variant (configs/robustness.yaml) for each of
# its models in order, resumably.
#
#   nohup sh scripts/run_variant.sh position_end > /dev/null 2>&1 &
#
# Like scripts/run_tier.sh: each model runs under caffeinate through the
# pinned runner, progress goes to data/logs/<variant>_<model>.log, rerunning
# resumes, and it stops at the first model that fails.
set -u

variant="$1"
cd "$(git rev-parse --show-toplevel)"
models=$(uv run python -c "import sys; from models.run import load_variant; print(' '.join(load_variant(sys.argv[1])['models']))" "$variant") || exit 2
mkdir -p data/logs

for model in $models; do
    log="data/logs/${variant}_${model}.log"
    echo "$(date -u +%FT%TZ) start $variant $model" >> "$log"
    caffeinate -dimsu uv run python scripts/pinned_step.py --config configs/models.yaml -- \
        uv run --group models python -m models.run --variant "$variant" --model "$model" >> "$log" 2>&1
    status=$?
    echo "$(date -u +%FT%TZ) end $variant $model exit=$status" >> "$log"
    if [ "$status" -ne 0 ]; then
        echo "$(date -u +%FT%TZ) stopping: $model exited $status" >> "data/logs/${variant}.status"
        exit "$status"
    fi
done
echo "$(date -u +%FT%TZ) $variant complete" >> "data/logs/${variant}.status"
