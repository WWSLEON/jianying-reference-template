#!/bin/bash
# usage: silver_v3_run.sh SRC.mp4 PROMPTS.json OUT.mp4 [STRIDE=3] [SAMSIZE=512]
set -e;SRC=$(realpath $1);PJ=$(realpath $2);OUT=$(realpath $3);ST=${4:-3};SZ=${5:-512};W=$(mktemp -d);V=/workspace/zxc/venv/bin/python;P=/workspace/zxc/pipeline
ffmpeg -v error -i "$SRC" -vf "select='not(mod(n\,$ST))'" -fps_mode passthrough -q:v 2 -start_number 0 $W/%05d.jpg
(cd /workspace/sam2 && $V $P/sam2_track.py $W "$PJ" $W/m.npy $SZ 2>&1 | grep -a "^done")
$V $P/silver_swap_v3.py "$SRC" $W/m.npy "$OUT" --stride $ST --stats "${OUT%.mp4}_stats.json"
cp $W/m.npy "${OUT%.mp4}_masks.npy";rm -rf $W
