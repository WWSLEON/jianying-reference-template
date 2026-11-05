---
name: zxc-digital-human-dedup
description: >-
  中下沉数字人短视频批量出片：用户给一条即梦成片（口型已对好）作模板，0积分做n条避重变体（换衣服颜色/背景/镜像/调色），先出快速预览图，再按规则导出。用户说“换色/避重/出n条/导出”时使用。
---
# 数字人避重出片（0 积分）

用户给一条即梦成片当模板，口型与音频保持原样，做颜色/镜像变体。禁止 Vidu/付费模型，除非用户明确点名。每条成片目标 ≤5 分钟（不含首次调参）。输出无花屏、闪屏、模糊。结束时报告北京时间总用时与积分（0）。

## 路径

- 工作根：`/workspace/zxc`
- 管线：`pipeline/`
- 输出：`out/`
- SAM2：`/workspace/sam2`，权重 `/workspace/sam2/ck/t.pt`
- 虚拟环境：`/workspace/zxc/venv`

## 快速预览图（先给用户确认，几秒出）

抽一帧（`ffmpeg -ss 2 -i src.mp4 -frames:v 1 frame.png`），用 GenerateImage 带这张帧做参考图，提示里锁死脸/发/手/背景/字幕/其它衣物，只改目标衣服颜色。用户认可再做视频，不要先跑 SAM2 样片。

## 决策表（先看源片再选路）

1. **衣服色相独特**（如紫袍，画面别处没有）：`pipeline/recolor_v3_run.sh <src> none <out> <color>`
   - color：`green|blue|red|yellow|purple|` 或色相角度
   - 可用 `--h0/--h1 --sat --ss/--t`
2. **衣服接近肤色**（如粉袍）：SAM2 追踪外套 → `recolor_dual_v7.py`（外套深绿 + 亮片/胸针深红）或 `silver_swap_v3.py`（银灰）
3. **暖棕衣服（近肤色/背景）改任意色**：见下方「近肤色/暖棕衣服改色一次到位」
4. **黑衣服**：SAM2 追踪 → `recolor_black_v2.py`
5. **多人红衣（红西装/红礼服/红头花，有红唇）改绿**：`venv/bin/python pipeline/recolor_red_v16.py`（色彩选红 + MediaPipe 脸/耳排除 + 近脸肤色保护 + 光流时序平滑，无 SAM2）。v16 验证：用户评「非常好」，全片渲染约 5 分钟。
6. **画面镜像、文字不镜像**：`mirror_keep_text.py --bands 0.04-0.18,0.74-0.81`

## 标准命令

```bash
# 紫袍→绿（v13）
cd /workspace/zxc && pipeline/recolor_v3_run.sh work/v13/src.mp4 none out/video_13_green.mp4 green

# 粉袍→银灰（v12）
cd /workspace/zxc && pipeline/silver_v3_run.sh work/v12/src.mp4 work/v12/p_all.json out/video_12_silver_v3.mp4 3 512

# 粉袍→深绿+深红装饰（v14）
cd /workspace/zxc && venv/bin/python pipeline/recolor_dual_v7.py work/v14/src.mp4 out/video_12_silver_v3_masks.npy out/video_14_darkgreen_v5.mp4 --stats out/video_14_darkgreen_v5_stats.json

# 多人红衣→深绿（v16，默认 hue 145 vgain 0.82 crf 16）
cd /workspace/zxc && venv/bin/python pipeline/recolor_red_v16.py work/v16/src.mp4 out/video_16_green.mp4 --stats out/video_16_green_stats.json

# 黑袍→深绿+深红亮片（v15）
cd /workspace/zxc && venv/bin/python pipeline/recolor_black_v2.py work/v15/src.mp4 work/v15/m_full.npy out/video_15_darkgreen_v2.mp4
```

SAM2 追踪：`sam2_track.py`，stride 3，长边 512。提示点 json：源分辨率第 0 帧，衣服正点、脸/手/背景负点。

## 近肤色/暖棕衣服改色一次到位（2026-11-05 棕西装→紫 验证）

1. SAM2 stride3/512 只追目标衣服：正点在衣身两侧，负点放脸、颈、围巾、领带、衬衫、背景、道具。
2. recolor_v3：`--hue 275 --h0 12 --h1 55 --smin 80`（紫，其它色改 hue）。
3. mask 平滑：相邻帧 0.25/0.5/0.25 加权 + 双向 EMA → open → erode(5) → close → 窄羽化(5)。
4. 纯净渲染（`work/v_purple/render_v3_clean.py`）：mask 内加原衣色色相门限（棕约 h14–50），排除红/肤色/近黑；EMA alpha 0.28；m<0.02 像素逐像素回填原帧；锐化仅 mask 内。
5. 质检：meandiff<0.006、p99<0.02，mask 外改变像素 = 0，观众帧不变色。
全片约 4–6 分钟，直接从第 1 步一次跑完，别分多轮修。

## 质检（必做）

- 放大看袖口/领口/手/底带
- 闪屏：mask 帧间变化 mean<0.006、p99<0.02（历史可接受值略高时需写明）
- mask 外像素与原片一致，非衣服元素不得变色
- 全片 ≤5 分钟；1080×1920 lanczos+轻锐化；音频原样拷贝

## 导出（用户说「导出」）

导出目标机器与目录以各 bot 记忆里用户指定的为准；没有指定时默认 NAS：`/Volumes/WWS音频/小葵/Bot 数字人成片/<YYYY-MM-DD>/<歌名>.mp4`

规则：
- 用户确认导出后，导出放到后台一次跑完，不因用户中途插话而中断或重来。
- 默认先高质量压缩再传：`ffmpeg -c:v libx264 -preset veryfast -crf 18-20 -c:a copy -movflags +faststart`，画质基本无差、体积小、传得快；用户特别要求时才传原片。
- 命名：`<歌名>_<颜色>_<YYYY-MM-DD>.mp4`，一次多条在末尾加 `_1`/`_2`/`_3`；重名顺延不覆盖。
- 用户已授权直接存到本地目标目录，不再询问确认。

步骤：
1. 压缩（见上）
2. `CopyFromBox` 到目标 Mac 主目录
3. 一条命令 `mkdir -p` 目标文件夹并 `mv` 改名进去
4. 禁止全盘 find；整段 <1 分钟
5. 导出同时把这次验证有效的流程与参数更新进本技能

机器：`61739196-2786-4e0b-bb36-907a1bc6a96b`（Air）、`d51b6b11-f87c-4961-9635-78304f96d60f`（MBP）

## 给其他账号 bot

把 `/workspace/share/zxc_full_kit_v2.zip`（含权重）或 `zxc_full_kit_v2_nocp.zip` + 公开下载的 `sam2.1_hiera_tiny.pt` 交给对方，严格按包内 `00_给Bot的执行指令.md` 安装到固定路径，禁止自创流程。
