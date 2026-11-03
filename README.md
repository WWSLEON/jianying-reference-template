# 剪映参考复刻模板 · Codex Skill

把参考视频整理成可编辑的剪映换图模板：对标照片运动、字幕、转场、特效和色调，并通过原生预览与导出验收。

本技能侧重缩短重复劳动：同款复用已验收工程，新参考先验证难点短样；辅助工具完成素材准备、参考指纹检索、资源可用性检查、技术验收和原生草稿只读备份。

## 安装到另一个 Codex 账号

将下面这段话发给目标账号的 Codex：

```text
请用 skill-installer 安装这个技能：
https://github.com/WWSLEON/jianying-reference-template/tree/main/skills/jianying-reference-template
```

也可把仓库中的 `skills/jianying-reference-template` 文件夹放进目标环境的 Codex 技能目录，默认是 `~/.codex/skills/`，设置过 `CODEX_HOME` 时使用其 `skills/` 子目录。安装完成后按安装器提示刷新技能列表，再调用：

```text
使用 $jianying-reference-template，按我给的参考视频制作剪映换图模板。
```

## 运行条件

- 在装有剪映专业版的 macOS 本机执行；云端 Linux 任务无法直接控制另一台电脑的剪映。
- Codex 需要可用的本机应用控制工具，或由用户配合完成原生 UI 步骤。仓库本身不提供操作系统控制服务。
- 辅助脚本使用 Python 3.10+、Pillow、FFmpeg 和 ffprobe。
- 剪映账号、字体及会员资源按接收方自己的登录和权限使用。

辅助工具可独立运行，不依赖作者电脑的 Python 环境。安装 Python 依赖的示例：

```bash
JY_SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/jianying-reference-template"
python3 -m venv "$JY_SKILL_DIR/.venv"
"$JY_SKILL_DIR/.venv/bin/python" -m pip install -r "$JY_SKILL_DIR/requirements.txt"
"$JY_SKILL_DIR/.venv/bin/python" "$JY_SKILL_DIR/scripts/template_tool.py" --help
```

FFmpeg/ffprobe 可放在 PATH 中，或通过 `FFMPEG`、`FFPROBE` 环境变量、命令的 `--ffmpeg` / `--ffprobe` 参数指定。若已有 `jianying-editor` 技能，可用 `JY_EDITOR_SKILL` 指向其目录以复用 `bin/` 工具。剪映默认应用位置为 `/Applications/VideoFusion-macOS.app`，可通过 `JY_APP_PATH` 覆盖。

## 工作方式

1. 查询参考 SHA256，命中本人已验收案例时复用最终原生稿，跳过拆镜和搜字体。
2. 新参考先一次性准备分镜图、声音和稳定照片，再并行分析不同难点。
3. 最难效果先做约2–4秒原生小样，验证机制、参数动画和字幕层级。
4. 小样通过后完成主工程；修正一段，只复查变化窗口。
5. 从剪映原生导出 MP4，再检查帧数、画幅、帧率、音轨和实际画面。

草稿制作可使用剪映原生 UI；已有兼容草稿生成器（例如本机的 `jianying-editor`）时也可接入，以提高效率。此仓库不捆绑该生成器、剪映软件或其官方资源包，辅助脚本不会直接生成完整剪映时间线。

## 辅助命令

```bash
JY_SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/jianying-reference-template"
JY_PY="$JY_SKILL_DIR/.venv/bin/python"
JY_TOOL="$JY_SKILL_DIR/scripts/template_tool.py"

"$JY_PY" "$JY_TOOL" lookup --reference '/path/reference.mp4'
"$JY_PY" "$JY_TOOL" prepare --reference '/path/reference.mp4' --photo '/path/photo.jpg' --out '/path/new-workspace'
"$JY_PY" "$JY_TOOL" resources --query '虚焦'
"$JY_PY" "$JY_TOOL" verify --video '/path/export.mp4' --reference '/path/reference.mp4' --decode --out '/path/verification.json'
"$JY_PY" "$JY_TOOL" snapshot --draft '/path/native-draft' --out '/path/new-backup'
```

`verify` 只证明文件技术检查通过，不能证明视觉相同。`snapshot` 原样备份原生草稿，不解密、不修改原稿，也不自动打包外部引用的素材。

## 本地缓存与分享边界

公开 `case-index.json` 初始为空。请把自己的已验收案例保存在 `references/case-index.local.json`，把本机资源目录和验收状态保存在 `references/resource-registry.local.json`。也可用 `JY_CASE_INDEX`、`JY_RESOURCE_REGISTRY` 指定索引文件。读取顺序为：环境变量指定文件 → 本地索引 → 公开索引。

本地索引、工作素材、会话、缓存和虚拟环境已加入 `.gitignore`。公开资源登记表只提供历史候选ID和功能说明，接收方必须从自己的剪映库定位并原生核验，不能把历史记录当成在新电脑上已验收。

本仓库不含私人照片、原声、字幕图片、导出视频、个人案例指纹、原生工程、登录数据或官方效果二进制。扁平参考视频无法证明原作者全部原始素材ID；有视觉近似或文字可编辑性限制时，技能要求如实说明，不承诺逐像素完全一致。
