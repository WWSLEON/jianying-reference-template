---
name: zxc-digital-human-bundle
description: >-
  数字人出片全套打包（避重改色 + 预览图改色 + 图转视频 + 导出 + 工作守则）。新 bot
  接手数字人换色/避重/预览/出视频/导出类工作时，先加载这一个技能。
---
# 数字人出片全套技能包

给新接手的 bot：本包整合了小葵 Group 的成熟流程和阿喜 Group 实战总结。细节分别在 `zxc-digital-human-dedup`、`clothing-recolor`、`image-to-video` 三个共享技能里，遇到对应任务时再加载它们，严格照做，禁止自创流程或乱改脚本。

## 一、工作守则
- 角色：数字人避重出片。用户给一条即梦成片（口型已对好），用 0 积分做换色/镜像变体；口型、音频、文字（除非用户要求）保持原样。
- 禁止 Vidu/MiniMax/付费模型，除非用户点名。成片不得花屏、闪屏、模糊。
- 速度优先：直接复用成熟脚本和参数，不反复调参。预览图几秒出，成片每条目标 3–5 分钟。
- 省额度：简单操作走轻量路径；确实需要复杂推理时，先提醒用户「该任务需要更复杂的模型推理」，让用户选择。
- 任务结束报告北京时间总用时和积分（0）。简体中文，短回复，如实说明瑕疵。
- 持续优化：每次用户说「导出」，代表成片已达标，同时把这次验证有效的流程和参数更新进技能。

## 二、标准流程
1. **预览图（几秒）**：用 ffmpeg 抽一帧，按 `clothing-recolor` 用 GenerateImage 带原帧做参考图，锁死脸/发/手/背景/字幕/其它衣物，只改目标衣服颜色。发给用户确认后再做视频，不要先跑 SAM2 样片。
2. **成片（0 积分）**：按 `zxc-digital-human-dedup` 的决策表选路线。
   - 衣服色相独特：`recolor_v3_run.sh <src> none <out> <color>`
   - 粉色等近肤色：SAM2 + `recolor_dual_v7.py` / `silver_v3_run.sh`
   - 暖棕等近肤色/背景色：SAM2 只追衣服（负点放脸、颈、围巾、领带、衬衫、背景）→ recolor_v3（紫：`--hue 275 --h0 12 --h1 55 --smin 80`）→ mask 相邻帧 0.25/0.5/0.25 加权 + 双向 EMA → open → erode(5) → close → 窄羽化(5) → 纯净渲染（mask 内加原衣色色相门限，排除红/肤色/近黑；EMA alpha 0.28；m<0.02 的像素逐像素回填原帧；锐化只作用在 mask 内，脚本 `/workspace/zxc/work/v_purple/render_v3_clean.py`）。一次跑完，不要分多轮修。
   - 黑衣：SAM2 + `recolor_black_v2.py`
   - 画面镜像、文字不镜像：`mirror_keep_text.py`
3. **质检**：mask 帧间 mean<0.006、p99<0.02；mask 外改变像素为 0，衣服以外的元素不得变色；观众等其它素材不变；1080×1920；音频原样拷贝。不合格自己修，不交半成品。
4. **静图转视频**（用户要让图片动起来时）：按 `image-to-video` 用 GenerateVideo，以静图为首帧，只写轻微动作。需要口型对歌时不用这个，走即梦模板 + 避重路径。

## 三、导出规则（路径按各自设备上用户的指定）
- 用户确认导出后，导出放到后台一次跑完，不因用户中途插话中断或重来。
- 默认先高质量压缩再传：`ffmpeg -c:v libx264 -preset veryfast -crf 18-20 -c:a copy -movflags +faststart`。画质基本无差、体积小；用户特别要求时才传原片。
- 命名：`<歌名>_<颜色>_<YYYY-MM-DD>.mp4`，一次导出多条时在末尾加 `_1`/`_2`/`_3`，重名顺延，不覆盖。
- 用户已授权直接存到本地目标目录，不再询问确认。
- 步骤：压缩 → CopyFromBox 到目标 Mac 主目录 → 一条命令 `mkdir -p` 并 `mv` 改名进去；禁止全盘 find，整段不超过 1 分钟。
- 目标机器和目录：首次问用户（可让用户给设备名或序列号，用 `ioreg -l | grep IOPlatformSerialNumber` 核对），记进自己的记忆。

## 四、环境（共用同一台盒子电脑）
- 工作根 `/workspace/zxc`，venv `/workspace/zxc/venv`，SAM2 权重 `/workspace/sam2/ck/t.pt`
- 硬性指令文档：`/workspace/share/kit_split/zxc_full_kit_v2/00_给Bot的执行指令.md`
- 完整包 `/workspace/share/zxc_full_kit_v2.zip`；不含权重的小包 `/workspace/share/zxc_full_kit_v2_nocp.zip`
