#!/bin/bash
# Long real training run for the learning curve (reward vs. time / episodes).
#SBATCH --job-name=dqn-train
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used --format=csv -l 30 \
    > "logs/gpu-util-$SLURM_JOB_ID.csv" 2>/dev/null &
python -m ai.train --mode multi --workers ${WORKERS:-31} --envs 128 --fresh --device cuda \
    --episodes 20000 --time-limit $((11*3600)) --log-interval 60 --save-every 500 \
    --run-dir "results/train_$SLURM_JOB_ID"
