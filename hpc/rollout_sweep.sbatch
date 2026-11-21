#!/bin/bash
# GPU node: rollout throughput (sim + inference, learning off) with epsilon held at the
# training floor: 1..31 envs with one worker each, then the training config (128 envs, 31 workers).
#   sbatch hpc/rollout_sweep.sbatch
#   EPS=1.0 sbatch hpc/rollout_sweep.sbatch    # random actions only (no inference), like --fresh
#SBATCH --job-name=dqn-rollout
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=logs/%x-%j.out
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used --format=csv -l 5 \
    > "logs/gpu-util-$SLURM_JOB_ID.csv" 2>/dev/null &
SMI=$!
OUT="results/rollout_runs_$SLURM_JOB_ID.txt"
python bench/rollout_bench.py --envs 1 2 4 8 16 31 --epsilon ${EPS:-0.15} --device cuda \
    --tag "gpu_$SLURM_JOB_ID" --out "$OUT"
python bench/rollout_bench.py --envs 128 --workers 31 --epsilon ${EPS:-0.15} --device cuda \
    --tag "gpu_$SLURM_JOB_ID" --out "$OUT"
kill $SMI 2>/dev/null
