---
name: image-to-video
description: >-
  Use when the user wants to turn a still (especially a just-generated/recolored
  portrait) into a short video clip: 图转视频 / 生成视频 / 动起来 / 出视频. Not for lyric MV
  autocut or digital-human recolor pipelines.
---
# Image → video (Grok Imagine)

Animate a still into a short MP4. Prefer this after a recolor / GenerateImage result when the user asks for motion.

## Inputs
- Source still path (attachment, GenerateImage asset, or prior deliverable)
- Motion brief (optional): e.g. gentle singing gesture, subtle coat shimmer, camera hold
- Duration / aspect only if the user names them (default tool: ~6s; aspect follows the image)

## Steps
1. Ack in one short line: which image → video, and the motion you will use.
2. Call `GenerateVideo` once:
   - `image_path`: the still (first frame)
   - `prompt`: subject + motion + camera + mood; keep identity and wardrobe locked to the still (same person, same lemon coat / colors, same background). Prefer subtle natural motion (breathing, hand gesture, fabric shimmer, slight head turn)—not scene redesign.
   - `filename`: short descriptive `.mp4`
   - Set `duration` / `aspect_ratio` / `resolution` only when asked (`1080p` only for plain image-to-video without last-frame/keyframes/refs)
3. Optional modes (only if asked):
   - End on another still: also set `last_frame_path`
   - Guide look with refs: `reference_image_paths` + cite `<IMAGE_n>` in the prompt
4. Deliver: first `SendToUser` `type: attachment` with the returned `file://` mp4, then one short text line. Do not claim you watched it unless a videoReview/watchVideo pass ran.
5. If the user rejects motion (wrong gesture, face drift, clothes changed), one retry with a tighter prompt that forbids wardrobe/face change; do not fan out parallel generations.

## Prompt pattern
> Animate this exact still. Keep the same elderly woman, face, hair, lemon-yellow coat, deep-yellow floral and lining, piano and red wall. Subtle singing gesture and gentle hand movement; soft fabric shimmer; camera locked; no cut, no outfit change, no new props.

## Do not
- Call Vidu / MiniMax / paid lip-sync tools unless the user explicitly names them
- Use this skill for 即梦模板避重改色 (use `zxc-digital-human-dedup`) or 剪映歌词短片 (use `jianying-lyric-mv-autocut`)
- Invent lip-sync to a song track here—GenerateVideo does not attach arbitrary audio; if they need lip-sync singing video, stop and use the Jimeng-template / digital-human path they already run
- Narrate tool names to the user

## Handoff
Shared in the owner’s skill library. Point another bot at `@image-to-video` / id `image-to-video`.
