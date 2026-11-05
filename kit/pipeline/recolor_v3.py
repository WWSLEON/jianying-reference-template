#!/usr/bin/env python
"""Garment recolor by soft hue band (+ optional SAM2 mask gate). Hue-rotates pixels in [--h0,--h1] deg to --hue, keeps V/texture,
temporal flow-EMA on the weight map, lanczos upscale + mild sharpen, audio copied.
Dual coat+decoration colors (e.g. dark green + dark red): see recolor_dual_v3.py / recolor_dual_run.sh.
usage: recolor_v3.py SRC OUT [--masks M.npy --stride 3] [--hue 130 --h0 235 --h1 320 --smin 25 --sat 0.85] [--ss --t]"""
import argparse,subprocess,json,time,numpy as np,cv2
a=argparse.ArgumentParser();a.add_argument('src');a.add_argument('out');a.add_argument('--masks',default='');a.add_argument('--stride',type=int,default=3)
for k,v in dict(hue=130.,h0=235.,h1=355.,smin=25.,sat=0.85,alpha=0.7,ss=0.,t=0.).items():a.add_argument('--'+k,type=float,default=v)
a.add_argument('--W',type=int,default=1080);a.add_argument('--H',type=int,default=1920);a.add_argument('--crf',type=int,default=16);a.add_argument('--stats',default='')
A=a.parse_args()
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',A.src]))['streams'][0]
w,h,fps=info['width'],info['height'],info['r_frame_rate']
cut=(['-ss',str(A.ss)] if A.ss else [])+(['-t',str(A.t)] if A.t else [])
dec=subprocess.Popen(['ffmpeg','-v','error',*cut,'-i',A.src,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{A.W}x{A.H}','-r',fps,'-i','-',*cut,'-i',A.src,'-map','0:v','-map','1:a?','-c:v','libx264','-preset','fast','-crf',str(A.crf),'-pix_fmt','yuv420p','-c:a','copy','-shortest',A.out],stdin=subprocess.PIPE)
MK=np.load(A.masks,mmap_mode='r') if A.masks else None
if MK is not None and MK.ndim==3: MK=MK[:,None]
def gate(i):
    if MK is None: return 1.
    k=i//A.stride;r=(i%A.stride)/A.stride;k1=min(k+1,len(MK)-1);k=min(k,len(MK)-1)
    m=(MK[k][0].astype(np.float32)*(1-r)+MK[k1][0].astype(np.float32)*r)/255
    m=cv2.resize(m,(w,h));return cv2.GaussianBlur(cv2.dilate(m,np.ones((15,15))),(15,15),0)
def ramp(x,a,b): return np.clip((x-a)/(b-a),0,1)
dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST);ys,xs=np.mgrid[0:h,0:w].astype(np.float32)
n=w*h*3;i=0;S=None;prev=None;diffs=[];t0=time.time();mid=(A.h0+A.h1)/2
while True:
    b=dec.stdout.read(n)
    if len(b)<n:break
    fr=np.frombuffer(b,np.uint8).reshape(h,w,3);g=cv2.cvtColor(fr,cv2.COLOR_BGR2GRAY)
    hsv=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV_FULL).astype(np.float32);H=hsv[...,0]*360/256;Ss=hsv[...,1];V=hsv[...,2]
    wt=ramp(H,A.h0,A.h0+15)*ramp(-H,-A.h1,-A.h1+15)*ramp(Ss,A.smin*0.5,A.smin)*ramp(V,15,35)
    wt=cv2.GaussianBlur(wt,(5,5),0)*gate(i)
    if S is None:S=wt
    else:
        fl=dis.calc(g,prev,None);Sw=cv2.remap(S,xs+fl[...,0],ys+fl[...,1],cv2.INTER_LINEAR);Sn=(1-A.alpha)*Sw+A.alpha*wt
        diffs.append(float(np.abs(Sn-S).mean()));S=Sn
    prev=g
    big=cv2.resize(fr,(A.W,A.H),interpolation=cv2.INTER_LANCZOS4)
    hb=cv2.cvtColor(big,cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    Hb=hb[...,0]*360/256;nh=(A.hue+(Hb-mid)*0.5)%360  # rotate, compress spread around target
    hb2=np.dstack([nh*256/360%256,hb[...,1]*A.sat,hb[...,2]])
    gr=cv2.cvtColor(np.clip(hb2,0,255).astype(np.uint8),cv2.COLOR_HSV2BGR_FULL).astype(np.float32)
    # keep luma: scale so Y matches original
    Y0=big.astype(np.float32)@np.array([.114,.587,.299],np.float32);Y1=gr@np.array([.114,.587,.299],np.float32)
    gr=np.clip(gr*(Y0/np.maximum(Y1,1))[...,None]*0.6+gr*0.4,0,255)
    m=np.clip(cv2.resize(S,(A.W,A.H)),0,1)[...,None]
    out=big+(gr-big)*m
    out=cv2.addWeighted(out,1.25,cv2.GaussianBlur(out,(0,0),1.0),-0.25,0)
    enc.stdin.write(np.clip(out,0,255).astype(np.uint8).tobytes());i+=1
enc.stdin.close();enc.wait()
st={'frames':i,'sec':round(time.time()-t0,1),'mask_meandiff':float(np.mean(diffs)),'p99':float(np.percentile(diffs,99))};print(json.dumps(st))
if A.stats: json.dump(st,open(A.stats,'w'))
