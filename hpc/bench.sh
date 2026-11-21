#!/bin/bash
# Strong-scaling sweep: fixed 128 envs, vary worker processes. Called by the sbatch files.
#   bench.sh <device> <out_root>
# Two phases per worker count:
#   simonly  - learning disabled, epsilon held at $EPS (default 0.15 = the training floor,
#              so ~85% of actions run the network) -> rollout (sim + inference) throughput
#   full     - real training (sim + inference + learner) -> end-to-end throughput
#              (epsilon decays from 1.0 as in a fresh run, so most actions are still random)
# Every run passes --episodes 1e9 so its time limit ends it, not ai.train's default of 1000 episodes.
set -uo pipefail
DEVICE=$1; OUT=$2
ENVS=${ENVS:-128}
SIM_T=${SIM_T:-180}; FULL_T=${FULL_T:-300}
EPS=${EPS:-0.15}
NCPU=${SLURM_CPUS_PER_TASK:-$(nproc)}
WORKERS=${WORKERS:-"1 2 4 8 16 32 64 128"}
mkdir -p "$OUT"
nvidia-smi -L > "$OUT/gpu.txt" 2>/dev/null || rocm-smi > "$OUT/gpu.txt" 2>/dev/null || true
lscpu > "$OUT/lscpu.txt"

for W in $WORKERS; do
  [ "$W" -ge "$NCPU" ] && { echo "skip W=$W (only $NCPU cpus)"; continue; }
  echo "=== $DEVICE workers=$W ==="
  python -m ai.train --mode multi --workers $W --envs $ENVS --fresh --seed 0 \
      --device $DEVICE --warmup-eps 1000000000 --epsilon $EPS --time-limit $SIM_T \
      --run-dir "$OUT/simonly_w$W" --save-every 1000000000 --episodes 1000000000
  python -m ai.train --mode multi --workers $W --envs $ENVS --fresh --seed 0 \
      --device $DEVICE --warmup-eps 20 --max-steps 1000 --time-limit $FULL_T \
      --run-dir "$OUT/full_w$W" --save-every 1000000000 --episodes 1000000000
done
python hpc/summarize.py "$OUT" | tee "$OUT/results.md"
