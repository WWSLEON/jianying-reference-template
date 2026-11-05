#!/usr/bin/env python
"""v3: brown-only gate inside smoothed SAM2 mask; bit-restore outside; narrow feather; low-alpha EMA."""
import argparse, subprocess, json, time
import numpy as np, cv2

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('--masks', required=True)
ap.add_argument('--stride', type=int, default=3)
ap.add_argument('--hue', type=float, default=275.)
ap.add_argument('--h0', type=float, default=14.); ap.add_argument('--h1', type=float, default=50.)
ap.add_argument('--smin', type=float, default=70.); ap.add_argument('--sat', type=float, default=1.05)
ap.add_argument('--alpha', type=float, default=0.28)  # stronger temporal smooth
ap.add_argument('--W', type=int, default=1080); ap.add_argument('--H', type=int, default=1920)
ap.add_argument('--crf', type=int, default=16); ap.add_argument('--stats', default='')
A = ap.parse_args()

info = json.loads(subprocess.check_output([
    'ffprobe','-v','error','-select_streams','v:0',
    '-show_entries','stream=width,height,r_frame_rate','-of','json', A.src
]))['streams'][0]
w, h, fps = info['width'], info['height'], info['r_frame_rate']

dec = subprocess.Popen(['ffmpeg','-v','error','-i',A.src,'-f','rawvideo','-pix_fmt','bgr24','-'], stdout=subprocess.PIPE)
enc = subprocess.Popen([
    'ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{A.W}x{A.H}','-r',fps,'-i','-',
    '-i',A.src,'-map','0:v','-map','1:a?','-c:v','libx264','-preset','fast','-crf',str(A.crf),
    '-pix_fmt','yuv420p','-c:a','copy','-shortest', A.out
], stdin=subprocess.PIPE)

MK = np.load(A.masks, mmap_mode='r')
if MK.ndim == 3: MK = MK[:, None]

k_er = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

def gate(i):
    k = i // A.stride; r = (i % A.stride) / A.stride
    k1 = min(k + 1, len(MK) - 1); k = min(k, len(MK) - 1)
    m = (MK[k][0].astype(np.float32) * (1 - r) + MK[k1][0].astype(np.float32) * r) / 255.0
    m = cv2.resize(m, (w, h))
    # narrow: erode (pull away from scarf/face/sleeve spill) + small feather (NOT dilate-15)
    u = (m * 255).astype(np.uint8)
    u = cv2.erode(u, k_er)
    m = cv2.GaussianBlur(u, (5, 5), 0).astype(np.float32) / 255.0
    return m

def ramp(x, a, b):
    return np.clip((x - a) / (b - a + 1e-6), 0, 1)

dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)
ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
n = w * h * 3; i = 0; S = None; prev = None; diffs = []
out_chg = []; out_tot = 0; t0 = time.time(); mid = (A.h0 + A.h1) / 2

while True:
    b = dec.stdout.read(n)
    if len(b) < n: break
    fr = np.frombuffer(b, np.uint8).reshape(h, w, 3)
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    H = hsv[..., 0] * 360 / 256; Ss = hsv[..., 1]; V = hsv[..., 2]

    # brown hue band
    wt = ramp(H, A.h0, A.h0 + 12) * ramp(-H, -A.h1, -A.h1 + 12) * ramp(Ss, A.smin * 0.5, A.smin) * ramp(V, 40, 60)
    # exclude red scarf/tie (high S, low H, high V)
    red = (H <= 14) & (Ss >= 120) & (V >= 80)
    # exclude skin (high V, moderate S)
    skin = (V >= 150) & (Ss <= 110) & (H >= 5) & (H <= 45)
    # exclude near-black shirt
    black = V <= 45
    wt = wt * (~red) * (~skin) * (~black)
    wt = cv2.GaussianBlur(wt.astype(np.float32), (3, 3), 0) * gate(i)

    if S is None:
        S = wt
    else:
        fl = dis.calc(g, prev, None)
        Sw = cv2.remap(S, xs + fl[..., 0], ys + fl[..., 1], cv2.INTER_LINEAR)
        Sn = (1 - A.alpha) * Sw + A.alpha * wt
        diffs.append(float(np.abs(Sn - S).mean()))
        S = Sn
    prev = g

    big = cv2.resize(fr, (A.W, A.H), interpolation=cv2.INTER_LANCZOS4)
    hb = cv2.cvtColor(big, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    Hb = hb[..., 0] * 360 / 256
    nh = (A.hue + (Hb - mid) * 0.5) % 360
    # slight lift: sat * sat, V mildly up inside recolor
    hb2 = np.dstack([nh * 256 / 360 % 256, np.clip(hb[..., 1] * A.sat, 0, 255), np.clip(hb[..., 2] * 1.04, 0, 255)])
    gr = cv2.cvtColor(np.clip(hb2, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR_FULL).astype(np.float32)
    Y0 = big.astype(np.float32) @ np.array([.114, .587, .299], np.float32)
    Y1 = gr @ np.array([.114, .587, .299], np.float32)
    gr = np.clip(gr * (Y0 / np.maximum(Y1, 1))[..., None] * 0.55 + gr * 0.45, 0, 255)

    m = np.clip(cv2.resize(S, (A.W, A.H)), 0, 1)
    # sharpen only where mask is active
    blended = big.astype(np.float32) + (gr - big.astype(np.float32)) * m[..., None]
    sharp = cv2.addWeighted(blended, 1.2, cv2.GaussianBlur(blended, (0, 0), 1.0), -0.2, 0)
    out = blended + (sharp - blended) * m[..., None]
    # HARD restore outside mask → bit-identical to resized original
    outside = m < 0.02
    out[outside] = big[outside]
    # soft clamp near edge: already soft m; outside exact
    out_u8 = np.clip(out, 0, 255).astype(np.uint8)

    # outside diff stats (should be 0)
    chg = int(np.count_nonzero(np.any(out_u8 != big, axis=2) & outside))
    out_chg.append(chg); out_tot += int(outside.sum())

    enc.stdin.write(out_u8.tobytes()); i += 1
    if i % 300 == 0: print('frame', i, flush=True)

enc.stdin.close(); enc.wait()
st = {
    'frames': i, 'sec': round(time.time() - t0, 1),
    'mask_meandiff': float(np.mean(diffs)) if diffs else 0.0,
    'p99': float(np.percentile(diffs, 99)) if diffs else 0.0,
    'outside_changed_pixels': int(sum(out_chg)),
    'outside_pixels_total': int(out_tot),
    'outside_changed_ratio': float(sum(out_chg) / max(out_tot, 1)),
}
print(json.dumps(st))
if A.stats: json.dump(st, open(A.stats, 'w'))
