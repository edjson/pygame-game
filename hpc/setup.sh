#!/bin/bash
# One-time environment setup on the cluster login node.
#   bash hpc/setup.sh            # CUDA build of torch (NVIDIA GPU nodes)
#   bash hpc/setup.sh rocm       # ROCm build (only if the cluster has AMD GPUs)
# The venv is pinned to Python 3.12. pygame has no wheel for 3.14 (the Pinnacles conda
# base python), and the source build pip falls back to either fails or comes out without
# pygame.font, which settings.py needs at import. uv fetches 3.12 if the cluster lacks it.
set -euo pipefail
cd "$(dirname "$0")/.."
FLAVOR=${1:-cuda}

command -v uv >/dev/null || { echo "needs uv: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2; exit 1; }
uv venv --allow-existing --python 3.12 venv   # keeps a venv that queued jobs may be using
PIP="uv pip install --python venv/bin/python"
case "$FLAVOR" in
  cuda) $PIP torch --index-url https://download.pytorch.org/whl/cu126 ;;
  rocm) $PIP torch --index-url https://download.pytorch.org/whl/rocm6.4 ;;
  cpu)  $PIP torch --index-url https://download.pytorch.org/whl/cpu ;;
esac
$PIP pygame numpy tqdm groq
# Import what training imports. The login node has no GPU, so report torch's CUDA build
# rather than cuda.is_available().
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -c \
  "import sys, torch, settings; print('python', sys.version.split()[0], '| torch', torch.__version__, '| cuda build', torch.version.cuda)"
