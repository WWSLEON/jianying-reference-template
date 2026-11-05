#!/bin/bash
# usage: recolor_v3_run.sh SRC.mp4 PROMPTS.json|none OUT.mp4 [COLOR=green|hue-deg] [extra recolor_v3.py args...]
# PROMPTS=none -> pure soft hue-band mask (best when all clothing shares one hue not present in skin/bg; flicker-free).
set -e;SRC=$(realpath $1);PJ=$2;OUT=$(realpath $3);C=${4:-green};shift 4||shift $#;V=/workspace/zxc/venv/bin/python;P=/workspace/zxc/pipeline
case $C in green)HUE=130;;blue)HUE=220;;red)HUE=0;;yellow)HUE=55;;purple)HUE=275;;*)HUE=$C;;esac
MA=();if [ "$PJ" != none ];then W=$(mktemp -d);ffmpeg -v error -i "$SRC" -vf "select='not(mod(n\,3))'" -fps_mode passthrough -q:v 2 -start_number 0 $W/%05d.jpg
(cd /workspace/sam2 && $V $P/sam2_track.py $W "$(realpath $PJ)" $W/m.npy 512 2>&1|grep -a "^done");MA=(--masks $W/m.npy --stride 3);fi
$V $P/recolor_v3.py "$SRC" "$OUT" --hue $HUE "${MA[@]}" --stats "${OUT%.mp4}_stats.json" "$@"
[ -n "$W" ] && rm -rf $W;true
