# 00_给Bot的执行指令（数字人避重换色 · 强制规程 v2）

> **本文件是命令，不是参考。逐条照做，禁止即兴发挥、禁止换方案、禁止“优化”参数。**
> 遇到本文件没覆盖的情况：**停下，向用户说明并询问**，不要自己发明新流程。

## 0. 铁律（违反任何一条 = 任务失败）
1. **0 积分**：绝不调用 Vidu、即梦、Runway 或任何付费/在线生成模型，除非用户本条消息明确要求。全部在盒子 CPU 本地完成。
2. **路径写死**：venv 必须在 `/workspace/zxc/venv`，脚本在 `/workspace/zxc/pipeline`，SAM2 仓库在 `/workspace/sam2`，权重在 `/workspace/sam2/ck/t.pt`。不得改路径、不得改脚本。
3. **先样片后全片**：必须先出 5 秒样片并通过 QA（第 5 节），才允许渲染全片。
4. **输出规格**：1080x1920，lanczos 放大 + 轻锐化（脚本已内置，勿改），音频 `-c:a copy` 原样复制（脚本已内置）。
5. **全片渲染 < 5 分钟**；超时说明方案选错，回到决策表。
6. **不得覆盖 NAS 已有文件**；导出 < 1 分钟；禁止全盘 `find`。
7. 结束时用 **Asia/Shanghai（UTC+8）** 报告总耗时。

## 1. 安装（只做一次）
```bash
unzip zxc_full_kit_v2.zip -d /workspace/ && cd /workspace/zxc_full_kit_v2
bash tools/install.sh        # 内含：apt ffmpeg、venv、pip、git clone sam2、复制权重与脚本、自动验证
```
install.sh 等价于以下精确步骤（若脚本出错，按此手动执行）：
```bash
sudo apt-get install -y ffmpeg git python3-venv
python3 -m venv /workspace/zxc/venv
/workspace/zxc/venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
/workspace/zxc/venv/bin/pip install opencv-python-headless numpy hydra-core iopath pillow tqdm
git clone https://github.com/facebookresearch/sam2.git /workspace/sam2
cd /workspace/sam2 && git checkout 2b90b9f5ceec907a1c18123530e92e794ad901a4 && SAM2_BUILD_CUDA=0 /workspace/zxc/venv/bin/pip install --no-build-isolation -e .
mkdir -p /workspace/sam2/ck && cp sam2_ck/t.pt /workspace/sam2/ck/t.pt
#   若包内无 t.pt：curl -L -o /workspace/sam2/ck/t.pt https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt  （156008466 字节）
mkdir -p /workspace/zxc && cp -r pipeline /workspace/zxc/pipeline && chmod +x /workspace/zxc/pipeline/*
```
原盒子参考版本：Python 3.13、torch 2.15.0+cpu、numpy 2.5.4、opencv-python-headless 4.14、hydra-core 1.3.8、ffmpeg 7.1。
**验证命令（必须打印 ALL_OK 才能继续）：**
```bash
bash /workspace/zxc_full_kit_v2/tools/verify.sh
```

## 2. 决策表（先看源视频第 0 帧，判断衣服类型，只能选一行）
先抽帧查看：`ffmpeg -v error -i SRC.mp4 -vf "select=eq(n\,0)" -frames:v 1 f0.jpg`，并 `ffprobe` 记下源分辨率与帧率。

| 源衣服类型 | 方法 | 精确命令 |
|---|---|---|
| (a) 衣服是**单一、肤色/背景里没有**的色相（如紫、蓝） | 纯色相带软蒙版，不用 SAM2 | `bash /workspace/zxc/pipeline/recolor_v3_run.sh SRC.mp4 none OUT.mp4 <颜色>`；颜色取 green/blue/red/yellow/purple 或色相角度数字。源色相范围默认 `--h0 235 --h1 355`（紫/粉紫）；源是蓝色时追加 `--h0 190 --h1 260` |
| (b1) 衣服**接近肤色**（粉色）→ 换银色 | SAM2 跟踪 + silver_swap_v3 | `bash /workspace/zxc/pipeline/silver_v3_run.sh SRC.mp4 PROMPTS.json OUT.mp4 3 512` |
| (b2) 粉色衣服 → **深绿 + 红色亮片/装饰** | SAM2 跟踪 + recolor_dual_v7 | 见 3.1 两步命令 |
| (c) **黑色**衣服 → 深绿 + 红 | SAM2 跟踪(obj1 主衣, obj2 其他人衬衫/亮片) + recolor_black_v2 | 见 3.2 两步命令 |
| (d) 只做**镜像**且文字保持可读 | mirror_keep_text | `/workspace/zxc/venv/bin/python /workspace/zxc/pipeline/mirror_keep_text.py SRC.mp4 OUT.mp4 --bands 0.04-0.18,0.74-0.81`（bands=标题/歌词所在高度占比，按实际画面量一次） |

禁止：粉色衣服用 (a)（会染到脸和手）；黑色衣服用色相法（黑色无色相）。旧脚本 hue_swap.py / silver_swap.py 只作备用，不得作为首选。

### 3.1 粉色 → 深绿+红（recolor_dual_v7）
```bash
V=/workspace/zxc/venv/bin/python; P=/workspace/zxc/pipeline; W=$(mktemp -d)
ffmpeg -v error -i SRC.mp4 -vf "select='not(mod(n\,3))'" -fps_mode passthrough -q:v 2 -start_number 0 $W/%05d.jpg
(cd /workspace/sam2 && $V $P/sam2_track.py $W PROMPTS.json M.npy 512)
$V $P/recolor_dual_v7.py SRC.mp4 M.npy SAMPLE.mp4 --stride 3 --t 5 --stats SAMPLE_stats.json   # 5秒样片
$V $P/recolor_dual_v7.py SRC.mp4 M.npy OUT.mp4 --stride 3 --stats OUT_stats.json             # QA通过后全片
```
默认参数即验证参数：`--hue 140 --dhue 0 --sat 0.88 --dsat 1.05 --vscale 0.5 --dvscale 0.5 --alpha 0.7 --ystrip 920 --seqsd 8 --noskin 1`。不得改动。

### 3.2 黑色 → 深绿+红（recolor_black_v2）
```bash
V=/workspace/zxc/venv/bin/python; P=/workspace/zxc/pipeline; W=$(mktemp -d)
ffmpeg -v error -i SRC.mp4 -vf "select='not(mod(n\,3))'" -fps_mode passthrough -q:v 2 -start_number 0 $W/%05d.jpg
(cd /workspace/sam2 && $V $P/sam2_track.py $W PROMPTS.json M.npy 512)
$V $P/recolor_black_v2.py SRC.mp4 M.npy SAMPLE.mp4 --stride 3 --t 5 --stats SAMPLE_stats.json
$V $P/recolor_black_v2.py SRC.mp4 M.npy OUT.mp4 --stride 3 --stats OUT_stats.json
```
默认即验证参数：`--band 0.879 --alpha 0.7 --hue 140 --dhue 0`（band=底部模糊带起点占画面高度比例）。

## 4. 如何写 PROMPTS.json（SAM2 点提示）
格式：`{"frame":0,"objs":{"1":{"pos":[[x,y],...],"neg":[[x,y],...]},"2":{...}}}`
- 坐标是**抽出的帧图上的像素坐标 = 源视频分辨率**（不是 1080x1920，除非源就是）。先打开 `$W/00000.jpg` 读坐标。
- `frame`：给点所在的抽帧序号（抽帧步长 3，第 k 张 = 源第 3k 帧）。默认 0；人物在第 0 帧被遮挡时才换帧（v15 曾用 30，最终用 0）。
- `pos`：6–9 个点，全部落在**衣服**上，覆盖躯干、双袖、下摆、领口附近。
- `neg`：5–6 个点，落在**脸、脖子、手、头发、背景、其他人**上；袖口与手交界处必须放一个 neg 在手上。
- obj "2"：仅在需要第二目标（如黑衣题材中另一人的衬衫/亮片区，变红）时添加；不需要就不写。
- 写完先跑样片，叠加查看蒙版（必要时用 numpy 把 M.npy 第 0 帧存图核对），蒙版漏/溢就**只改点**，不改脚本。
示例见 `prompts_examples/`（v12_p_all.json：粉→银单目标；v15_pr_frame0.json：黑衣双目标）。

## 5. 强制 QA（样片阶段，全部通过才可出全片）
1. 5 秒样片（`--t 5`；run.sh 类可先用 `ffmpeg -t 5 -c copy` 截 5 秒源再跑）。
2. 抽 0.5s/2.5s/4.5s 三帧，**放大裁切**检查：衣服边缘、袖口、手、底部条带（字幕/模糊带）、脸部和嘴唇。
3. 闪烁统计看 `*_stats.json`：**mask_meandiff < 0.006 且 p99 < 0.02** 为目标。超标时检查点提示/选错方案，修正后重跑样片。若反复无法达标，如实报告数值给用户，不得谎报。
4. 肉眼：无色块、无斑点、无闪烁、无模糊、无粉色残边、手和脸未被染色。
5. `ffprobe` 确认 1080x1920、音轨存在且与源一致。

## 6. 导出到 NAS（< 1 分钟）
目标：`/Volumes/WWS音频/小葵/Bot 数字人成片/<YYYY-MM-DD>/<歌名>.mp4`（日期为 Asia/Shanghai 当天）。同名已存在则用 `<歌名>_2.mp4`、`_3`…，**绝不覆盖**。
步骤：
1. `CopyFromBox` 把 OUT.mp4 复制到 Mac 家目录（`~/<歌名>.mp4`）。
2. 在 Mac 上一次 Shell：
```bash
D="/Volumes/WWS音频/小葵/Bot 数字人成片/$(TZ=Asia/Shanghai date +%F)"; mkdir -p "$D"; N="<歌名>"; F="$D/$N.mp4"; i=2
while [ -e "$F" ]; do F="$D/${N}_$i.mp4"; i=$((i+1)); done; mv ~/"$N.mp4" "$F" && ls -la "$F"
```
禁止 `find /`、禁止遍历整个卷。NAS 未挂载则停止并告知用户。

## 7. 结束汇报（必须包含）
方案行号(a/b/c/d)、完整命令、stats 数值、QA 结论、NAS 最终路径、**开始/结束时间与总耗时（Asia/Shanghai, UTC+8）**、积分消耗 = 0。

## 8. 历史已验证任务（参数=脚本默认值；命令按当时产物与默认值整理）
| 任务 | 源 | 命令 | 结果 |
|---|---|---|---|
| v12 粉→银 | 粉色外套（近肤色） | `silver_v3_run.sh src.mp4 p_all.json out.mp4 3 512`（prompts=prompts_examples/v12_p_all.json，单目标） | 交付 |
| v13 →绿 | 单一色相衣服（紫/粉紫，不在肤色内） | `recolor_v3_run.sh src.mp4 none out.mp4 green`（hue 130, h0 235, h1 355, smin 25, sat 0.85, alpha 0.7） | 样片 mean 0.0072 / p99 0.0234（见 v13_samp_stats.json） |
| v14 粉→深绿+红 | 粉色亮片外套 | SAM2(3.1) + `recolor_dual_v7.py src.mp4 M.npy out.mp4 --stride 3`（默认 hue140 sat0.88 vscale0.5 dsat1.05 ystrip920 seqsd8） | 样片 mean 0.0071 / p99 0.0204（v14_samp4_stats.json） |
| v15 黑→深绿+红 | 黑色外套 + 另一人衬衫 | SAM2(3.2，prompts=v15_pr_frame0.json，双目标) + `recolor_black_v2.py src.mp4 M.npy out.mp4 --stride 3`（band 0.879, alpha 0.7, hue 140） | 交付 |

注意：历史样片的 mean 略高于 0.006 目标但已被用户接受；新任务仍以 0.006/0.02 为目标并如实报告。
