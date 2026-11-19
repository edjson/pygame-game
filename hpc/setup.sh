#!/bin/bash
# One-time environment setup on the cluster login node.
#   bash hpc/setup.sh            # CUDA build of torch (NVIDIA GPU nodes)
#   bash hpc/setup.sh rocm       # ROCm build (only if the cluster has AMD GPUs)
# Check `module avail python` / `module avail anaconda` first and load one if
# the system python is older than 3.10.
set -euo pipefail
cd "$(dirname "$0")/.."
FLAVOR=${1:-cuda}

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
case "$FLAVOR" in
  cuda) pip install torch --index-url https://download.pytorch.org/whl/cu126 ;;
  rocm) pip install torch --index-url https://download.pytorch.org/whl/rocm6.4 ;;
  cpu)  pip install torch --index-url https://download.pytorch.org/whl/cpu ;;
esac
pip install pygame numpy tqdm groq
python -c "import torch, pygame; print('torch', torch.__version__, 'cuda?', torch.cuda.is_available())"
