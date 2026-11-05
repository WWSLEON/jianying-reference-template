#!/usr/bin/env python
"""Horizontal mirror, but keep burned-in titles/lyrics readable (re-overlay original text pixels in given y bands).
usage: mirror_keep_text.py SRC OUT --bands 0.04-0.18,0.74-0.81"""
import sys,argparse,subprocess,json,numpy as np,cv2
from concurrent.futures import ProcessPoolExecutor
a=argparse.ArgumentParser();a.add_argument('src');a.add_argument('out');a.add_argument('--bands',default='0.04-0.18,0.74-0.81');A=a.parse_args()
B=[tuple(map(float,b.split('-'))) for b in A.bands.split(',')]
def proc(fr):
    h=fr.shape[0];out=fr[:,::-1].copy()
    hsv=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV);H,S,V=hsv[...,0].astype(int)*2,hsv[...,1],hsv[...,2]
    t=((V>190)&(S<45))|((H>=40)&(H<=70)&(S>110)&(V>170))
    band=np.zeros(h,bool)
    for lo,hi in B: band[int(lo*h):int(hi*h)]=True
    t=(t&band[:,None]).astype(np.uint8)
    t=cv2.morphologyEx(t,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
    m=cv2.dilate(t,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
    md=cv2.dilate(m,np.ones((5,5),np.uint8))[:,::-1].copy()
    out=cv2.inpaint(out,md,3,cv2.INPAINT_TELEA)
    m=cv2.GaussianBlur(m.astype(np.float32),(3,3),0)[...,None]
    return (fr*m+out*(1-m)).astype(np.uint8)
if __name__=='__main__':
    if A.out.endswith('.jpg'):
        cv2.imwrite(A.out,proc(cv2.imread(A.src)));sys.exit()
    i=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',A.src]))['streams'][0]
    w,h,fps=i['width'],i['height'],i['r_frame_rate']
    dec=subprocess.Popen(['ffmpeg','-v','error','-i',A.src,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{w}x{h}','-r',fps,'-i','-','-i',A.src,'-map','0:v','-map','1:a','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','copy',A.out],stdin=subprocess.PIPE)
    n=w*h*3
    def fr():
        while True:
            b=dec.stdout.read(n)
            if len(b)<n:return
            yield np.frombuffer(b,np.uint8).reshape(h,w,3)
    with ProcessPoolExecutor() as ex:
        for o in ex.map(proc,fr(),chunksize=8): enc.stdin.write(o.tobytes())
    enc.stdin.close();enc.wait()
