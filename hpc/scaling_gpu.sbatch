#!/bin/bash
# GPU node: same sweep with the learner + inference on the GPU.
# Run `sinfo -o "%P %G %c %m"` to find the GPU partition and gres name.
#SBATCH --job-name=dqn-scale-gpu
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=logs/%x-%j.out
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used --format=csv -l 5 \
    > "logs/gpu-util-$SLURM_JOB_ID.csv" 2>/dev/null &
SMI=$!
WORKERS="1 2 4 8 16 31" bash hpc/bench.sh cuda "results/gpu_$SLURM_JOB_ID"
kill $SMI 2>/dev/null
