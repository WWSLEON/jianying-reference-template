#!/bin/bash
# 验证安装：全部打印 OK 才算通过
set -e
V=/workspace/zxc/venv/bin/python; P=/workspace/zxc/pipeline
ffmpeg -version | head -1
$V -c "import cv2,numpy,torch;print('cv2',cv2.__version__,'numpy',numpy.__version__,'torch',torch.__version__,'cuda',torch.cuda.is_available());cv2.DISOpticalFlow_create(0);print('OK libs')"
(cd /workspace/sam2 && $V -c "from sam2.build_sam import build_sam2_video_predictor as b;p=b('configs/sam2.1/sam2.1_hiera_t.yaml','/workspace/sam2/ck/t.pt',device='cpu');print('OK sam2')")
for f in silver_swap_v3 recolor_v3 recolor_dual_v7 recolor_black_v2 mirror_keep_text hue_swap silver_swap; do $V $P/$f.py --help >/dev/null && echo "OK $f --help"; done
$V -m py_compile $P/sam2_track.py && echo "OK sam2_track compile"
bash -n $P/silver_v3_run.sh && bash -n $P/recolor_v3_run.sh && echo "OK sh syntax"
echo ALL_OK
