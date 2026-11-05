#!/usr/bin/env python
"""Fast full-frame hue swap: every pixel in a source hue band -> target hue (no segmentation). Audio copied.
usage: hue_swap.py SRC OUT --src-lo 235 --src-hi 310 --dst 135 [--sat 1.0 --val 0.95]"""
import sys, argparse, subprocess, json, numpy as np, cv2
from concurrent.futures import ProcessPoolExecutor
ap=argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--src-lo",type=float,default=235); ap.add_argument("--src-hi",type=float,default=310)
ap.add_argument("--dst",type=float,default=135); ap.add_argument("--sat",type=float,default=1.0); ap.add_argument("--val",type=float,default=0.95)
ap.add_argument("--min-sat",type=float,default=0.08); A=ap.parse_args()
p=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,r_frame_rate","-of","json",A.src]))["streams"][0]
W,H,fr=p["width"],p["height"],p["r_frame_rate"]
lo,hi,mid=A.src_lo/2,A.src_hi/2,(A.src_lo+A.src_hi)/4  # opencv hue 0..180
def proc(b):
    f=np.frombuffer(b,np.uint8).reshape(H,W,3)
    hsv=cv2.cvtColor(f,cv2.COLOR_RGB2HSV).astype(np.float32); h,s,v=hsv[...,0],hsv[...,1],hsv[...,2]
    g=np.clip((h-lo)/4,0,1)*np.clip((hi-h)/4,0,1)*np.clip((s/255-A.min_sat)/0.06,0,1)
    g=cv2.GaussianBlur(g,(0,0),1.2)
    nh=(A.dst/2+(h-mid)*0.3)%180
    out=hsv.copy(); out[...,0]=h*(1-g)+nh*g; out[...,1]=np.clip(s*(1-g)+s*A.sat*g,0,255); out[...,2]=np.clip(v*(1-g)+v*A.val*g,0,255)
    # hue blend across wrap is fine since g is ~0/1 except at soft edges
    return cv2.cvtColor(out.astype(np.uint8),cv2.COLOR_HSV2RGB).tobytes()
dec=subprocess.Popen(["ffmpeg","-v","error","-i",A.src,"-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
enc=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",fr,"-i","-","-i",A.src,"-map","0:v","-map","1:a?","-c:v","libx264","-preset","fast","-crf","16","-pix_fmt","yuv420p","-c:a","copy","-shortest",A.out],stdin=subprocess.PIPE)
n=W*H*3
def frames():
    while True:
        b=dec.stdout.read(n)
        if len(b)<n: return
        yield b
with ProcessPoolExecutor(8) as ex:
    for o in ex.map(proc,frames(),chunksize=8): enc.stdin.write(o)
enc.stdin.close(); enc.wait()
