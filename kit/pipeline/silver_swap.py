#!/usr/bin/env python
"""Pink/any hue band -> silver gradient (low sat) + dark gray (high sat). Audio copied.
usage: silver_swap.py SRC OUT --lo 322 --hi 360 --split 75"""
import sys,argparse,subprocess,json,numpy as np,cv2
from concurrent.futures import ProcessPoolExecutor
a=argparse.ArgumentParser();a.add_argument('src');a.add_argument('out')
a.add_argument('--lo',type=float,default=322);a.add_argument('--hi',type=float,default=360);a.add_argument('--split',type=float,default=75)
a.add_argument('--wrap',type=float,default=10);a.add_argument('--wsat',type=float,default=70)
a.add_argument('--grow',type=int,default=0)
A=a.parse_args()
_fd=None
def hsv_s(fr): return cv2.cvtColor(fr,cv2.COLOR_BGR2HSV)[...,1]
def face_box(fr):
    global _fd
    if _fd is None: _fd=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    g=cv2.cvtColor(fr,cv2.COLOR_BGR2GRAY);W=g.shape[1];f=[r for r in _fd.detectMultiScale(g,1.1,5,minSize=(W//14,W//14),maxSize=(W//5,W//5)) if r[1]+r[3]<0.45*g.shape[0]]
    return [(int(x-0.2*w),int(y-0.3*h),int(x+1.2*w),int(y+1.1*h)) for x,y,w,h in f]
def proc(fr):
    V=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV)[...,2].astype(np.float32)
    hb=cv2.cvtColor(cv2.GaussianBlur(fr,(9,9),0),cv2.COLOR_BGR2HSV).astype(np.float32);H=hb[...,0]*2;S=hb[...,1];Vb=hb[...,2]
    band=(H>=A.lo)|((H<A.wrap)&(S<A.wsat)&(Vb>140))
    m=(band&(S>10)).astype(np.uint8)
    k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9));m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,k);m=cv2.morphologyEx(m,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
    if A.grow:
        reg=cv2.dilate(cv2.morphologyEx(m,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(21,21))),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(A.grow,A.grow)))
        Hr=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV)[...,0].astype(np.float32)*2
        m=m|(reg&(((Hr>=300)|(Hr<=A.wrap-2)|((Hr<=15)&(hsv_s(fr)<75)))&(hsv_s(fr)>18)).astype(np.uint8))
    for x0,y0,x1,y1 in face_box(fr): m[max(y0,0):max(y1,0),max(x0,0):max(x1,0)]=0
    m=cv2.GaussianBlur(m.astype(np.float32),(7,7),0)
    hi=np.clip((S-A.split+15)/30,0,1)  # 0 silver,1 dark gray
    h,w=V.shape;gy=np.linspace(1.05,0.72,h)[:,None]  # top bright -> bottom darker
    gx=1+0.08*np.sin(np.linspace(0,3.14,w))[None,:]
    sil=np.clip(V*0.55*gy*gx+95*gy,0,255)
    dg=np.clip(V*0.22+18,0,85)
    L=sil*(1-hi)+dg*hi
    g=np.stack([L*1.03,L*1.0,L*0.97],-1)  # slight cool tint (BGR)
    out=fr.astype(np.float32)*(1-m[...,None])+g*m[...,None]
    return np.clip(out,0,255).astype(np.uint8)
if __name__=='__main__':
    if A.out.endswith('.jpg'):
        cv2.imwrite(A.out,proc(cv2.imread(A.src)));sys.exit()
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',A.src]))['streams'][0]
    w,h,fps=info['width'],info['height'],info['r_frame_rate']
    dec=subprocess.Popen(['ffmpeg','-v','error','-i',A.src,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{w}x{h}','-r',fps,'-i','-','-i',A.src,'-map','0:v','-map','1:a','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','copy',A.out],stdin=subprocess.PIPE)
    n=w*h*3
    def frames():
        while True:
            b=dec.stdout.read(n)
            if len(b)<n:return
            yield np.frombuffer(b,np.uint8).reshape(h,w,3)
    with ProcessPoolExecutor() as ex:
        for o in ex.map(proc,frames(),chunksize=8): enc.stdin.write(o.tobytes())
    enc.stdin.close();enc.wait()
