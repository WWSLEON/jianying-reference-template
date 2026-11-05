# 数字人避重出片安装包

给另一个账户的 bot 使用。不含本机导出路径（桌面/设备序列号）。

## 目录
- `skills/zxc-digital-human-bundle/` — 总包（工作守则 + 流程入口）
- `skills/zxc-digital-human-dedup/` — 换色/避重/导出
- `skills/clothing-recolor/` — 静图改衣色预览
- `skills/image-to-video/` — 静图转动图
- `kit/` — zxc_full_kit_v2（pipeline、`00_给Bot的执行指令.md`、prompts、SAM2 校验）

## 安装到新盒子
```bash
cd kit
bash tools/install.sh
bash tools/verify.sh
```
`install.sh` 会安装 venv 到 `/workspace/zxc/venv`、pipeline 到 `/workspace/zxc/pipeline`、SAM2 权重到 `/workspace/sam2/ck/t.pt`（本仓库不含 149MB 权重，脚本会从 Facebook 官方地址下载；期望 sha256 见 `kit/sam2_ck/t.pt.sha256`）。

把 `skills/*/SKILL.md` 交给 bot 做成对应技能即可。

导出目标由各 bot 自己的记忆决定；`zxc-digital-human-dedup` 里 NAS 路径只是占位默认。
