---
name: clothing-recolor
description: >-
  Use when the user wants to recolor a person’s clothes in a photo (e.g.
  衣服换成/替换颜色/外衣改色) while keeping face, pose, background, and everything else
  unchanged.
---
# Clothing recolor (photo)

Keep the shot identical; only change named clothing colors.

## Inputs
- Source image (attachment or path)
- Color map in plain words, e.g. outer coat → lemon yellow; decoration + lining → deep yellow

## Steps
1. Ack in one short line naming the color changes.
2. Call `GenerateImage` with:
   - `reference_image_paths`: [source image]
   - `aspect_ratio`: match the source when obvious (portrait often `3:4`)
   - `description`: edit instruction that (a) locks face, hair, pose, hands, background, props, lighting, framing as identical; (b) lists each garment part → exact target color; (c) says do not change anything else
3. Read the result. If outer vs trim/lining contrast is wrong (same yellow everywhere, wrong hue), retry once with stronger contrast wording and both the source + last output as references.
4. Deliver with `SendToUser`: short confirmation + attach the image (`images` or `type: attachment`). Offer one tweak line only if a named part still missed.

## Prompt pattern
> Edit this exact photo. Keep [subject], face, hair, pose, hands, [background/props], lighting, and framing identical. Only change clothing: [part A] becomes [color A]; [part B] becomes [color B]. Do not change anything else.

For contrast (light coat + dark trim): say the light color and dark color in the same sentence and that they must not match.

## Do not
- Redesign silhouette, fabric type, or jewelry unless asked
- Recolor skin, hair, eyes, walls, or props
- Narrate tool names to the user

## Handoff
Skills are shared across the owner’s bots. After save, tell the user the skill pill so they can point another bot (e.g. 阿喜 Group) at `@clothing-recolor` / the same recipe.
