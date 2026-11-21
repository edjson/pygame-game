#!/bin/bash
# CPU node: hit rate of the trained enemies (greedy LSTM-DQN) vs scripted chase-and-shoot enemies
# against the scripted player bot, same seeds for both (bench/hit_rate_eval.py).
# Partition names differ per cluster -- run `sinfo -s` and edit --partition.
#   sbatch hpc/hit_rate_eval.sbatch
#   EPISODES=1000 sbatch hpc/hit_rate_eval.sbatch
#   WEIGHTS=results/train_12345/weights.pt sbatch hpc/hit_rate_eval.sbatch    # a checkpoint from train_gpu.sbatch
#SBATCH --job-name=dqn-hitrate
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=logs/%x-%j.out
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
python bench/hit_rate_eval.py --episodes ${EPISODES:-200} --weights "${WEIGHTS:-ai/weights/weights.pt}" \
    --workers $SLURM_CPUS_PER_TASK --out "results/hit_rate_runs_$SLURM_JOB_ID.txt"
