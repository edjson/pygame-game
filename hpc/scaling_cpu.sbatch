#!/bin/bash
# CPU-only node: strong scaling of simulation + CPU learner.
# Partition names differ per cluster -- run `sinfo -s` and edit --partition.
#SBATCH --job-name=dqn-scale-cpu
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=logs/%x-%j.out
cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate
bash hpc/bench.sh cpu "results/cpu_$SLURM_JOB_ID"
