#!/bin/bash
# 一键安装：路径必须与原盒子完全一致（脚本内写死 /workspace/zxc/venv 与 /workspace/sam2/ck/t.pt）
set -e
KIT=$(cd "$(dirname "$0")/.." && pwd)
sudo apt-get update -y && sudo apt-get install -y ffmpeg git python3-venv || true
mkdir -p /workspace/zxc
python3 -m venv /workspace/zxc/venv
V=/workspace/zxc/venv/bin
$V/pip install -U pip
$V/pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
$V/pip install opencv-python-headless numpy hydra-core iopath pillow tqdm
[ -d /workspace/sam2/.git ] || git clone https://github.com/facebookresearch/sam2.git /workspace/sam2
(cd /workspace/sam2 && git checkout 2b90b9f5ceec907a1c18123530e92e794ad901a4 2>/dev/null || true)
(cd /workspace/sam2 && SAM2_BUILD_CUDA=0 $V/pip install --no-build-isolation -e . ) || echo "sam2 pip安装失败也可：脚本以 cd /workspace/sam2 运行，可直接 import"
mkdir -p /workspace/sam2/ck
if [ -f "$KIT/sam2_ck/t.pt" ]; then cp "$KIT/sam2_ck/t.pt" /workspace/sam2/ck/t.pt
else curl -L -o /workspace/sam2/ck/t.pt https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt; fi
rm -rf /workspace/zxc/pipeline_kit_backup; [ -d /workspace/zxc/pipeline ] && mv /workspace/zxc/pipeline /workspace/zxc/pipeline_kit_backup || true
cp -r "$KIT/pipeline" /workspace/zxc/pipeline; chmod +x /workspace/zxc/pipeline/*
bash "$KIT/tools/verify.sh"
