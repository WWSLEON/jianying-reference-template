#!/usr/bin/env python
"""SAM2-masked garment recolor. Coat mask (obj1) + inner strip/brooch (obj2) from sam2_track.py (uint8 [K,2,h,w], every --stride frames),
interpolated per frame, flow-EMA stabilized, guided-filter upsampled; inside coat: luminance->silver gradient; obj2 -> dark gray.
Bottom blurred strip (y>=--strip of src) uses HSV band mask. usage: silver_swap_v3.py SRC MASKS.npy OUT [--ss --t --stride]"""
import argparse,subprocess,json,time,numpy as np,cv2
a=argparse.ArgumentParser();a.add_argument('src');a.add_argument('masks');a.add_argument('out')
a.add_argument('--stride',type=int,default=1);a.add_argument('--ss',type=float,default=0);a.add_argument('--t',type=float,default=0)
a.add_argument('--W',type=int,default=1080);a.add_argument('--H',type=int,default=1920);a.add_argument('--crf',type=int,default=16)
a.add_argument('--alpha',type=float,default=0.7);a.add_argument('--strip',type=int,default=920);a.add_argument('--stats',default='');a.add_argument('--dark',type=float,default=0,help='1=sequin strip/brooch dark gray (can look patchy)');a.add_argument('--seqsd',type=float,default=9)
A=a.parse_args()
MK=np.load(A.masks,mmap_mode='r')
if MK.ndim==3: MK=MK[:,None]
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',A.src]))['streams'][0]
w,h,fps=info['width'],info['height'],info['r_frame_rate']
cut=(['-ss',str(A.ss)] if A.ss else [])+(['-t',str(A.t)] if A.t else [])
dec=subprocess.Popen(['ffmpeg','-v','error',*cut,'-i',A.src,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{A.W}x{A.H}','-r',fps,'-i','-',*cut,'-i',A.src,'-map','0:v','-map','1:a?','-c:v','libx264','-preset','fast','-crf',str(A.crf),'-pix_fmt','yuv420p','-c:a','copy','-shortest',A.out],stdin=subprocess.PIPE)
def getm(i):
    k=i//A.stride;r=(i%A.stride)/A.stride;k1=min(k+1,len(MK)-1);k=min(k,len(MK)-1)
    m=(MK[k][:1].astype(np.float32)*(1-r)+MK[k1][:1].astype(np.float32)*r)/255
    if m.shape[1:]!=(h,w): m=np.stack([cv2.resize(x,(w,h),interpolation=cv2.INTER_LINEAR) for x in m])
    return m
dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)
ys,xs=np.mgrid[0:h,0:w].astype(np.float32)
gy=np.linspace(1.05,0.78,A.H,dtype=np.float32)[:,None];gx=(1+0.05*np.sin(np.linspace(0,3.14,A.W,dtype=np.float32)))[None,:]
sy=int(A.strip*A.H/h);prev=None;S=None;n=w*h*3;i=0;t0=time.time();diffs=[]
while True:
    b=dec.stdout.read(n)
    if len(b)<n:break
    fr=np.frombuffer(b,np.uint8).reshape(h,w,3);g=cv2.cvtColor(fr,cv2.COLOR_BGR2GRAY)
    m=getm(i);hsv=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV);Hh=hsv[...,0].astype(np.float32)*2;Ss=hsv[...,1].astype(np.float32);Vv=hsv[...,2].astype(np.float32)
    skin=((Hh>=14)&(Hh<=40)&(Ss>45)&(Vv>120)).astype(np.float32);skin=cv2.GaussianBlur(cv2.dilate(skin,np.ones((5,5))),(7,7),0)
    pink=(((Hh>=300)|(Hh<=30))&(Ss>12)).astype(np.float32)  # coat colours (incl. shaded orange-pink)
    core=cv2.morphologyEx(m[0],cv2.MORPH_CLOSE,np.ones((61,3)));reg=cv2.dilate(core,np.ones((9,9)))  # grown 4px to kill pink edge halo
    rim=(((Hh>=300)|(Hh<=18))&(Ss>25)).astype(np.float32)
    coat=np.where(core>0.5,pink*(1-skin*(core<0.9)),reg*rim)
    near=cv2.dilate((core>0.5).astype(np.uint8),np.ones((41,41)))  # pink inner layer SAM left out (chest)
    coat=np.maximum(coat,near*((Hh>=305)&(Ss>35)).astype(np.float32))
    hf=cv2.blur(np.abs(Vv-cv2.GaussianBlur(Vv,(0,0),1.0)),(5,5))  # pixel-level sparkle = sequins; smooth folds ~<1
    inner=cv2.erode((reg>0.5).astype(np.uint8),np.ones((15,15)))
    sq=((hf>A.seqsd)&(inner>0)).astype(np.uint8);sq=cv2.morphologyEx(sq,cv2.MORPH_OPEN,np.ones((5,5)))
    seq=cv2.GaussianBlur(sq.astype(np.float32),(5,5),0)
    # bottom blurred strip: no SAM there -> colour band
    band=((Hh>=315)|((Hh<11)&(Ss<140)&(Vv>140)))&(Ss>10);coat[A.strip:]=cv2.GaussianBlur(band.astype(np.float32),(9,9),0)[A.strip:]
    dk=A.dark*seq*coat;dk[A.strip:]=0
    st=np.stack([coat,dk])
    if S is None:S=st
    else:
        fl=dis.calc(g,prev,None);mx,my=xs+fl[...,0],ys+fl[...,1]
        Sw=np.stack([cv2.remap(x,mx,my,cv2.INTER_LINEAR) for x in S]);Sn=(1-A.alpha)*Sw+A.alpha*st
        diffs.append(float(np.abs(Sn[0]-S[0]).mean()));S=Sn
    prev=g
    big=cv2.resize(fr,(A.W,A.H),interpolation=cv2.INTER_LANCZOS4)
    up=cv2.resize(np.dstack([S[0],S[1]]),(A.W,A.H),interpolation=cv2.INTER_LINEAR)
    mb=np.clip(cv2.ximgproc.guidedFilter(big,np.ascontiguousarray(up[...,0]),6,1e-3),0,1);db=np.clip(up[...,1]/np.maximum(up[...,0],1e-3),0,1)
    V=big.max(2).astype(np.float32)
    sil=np.clip(V*0.5*gy*gx+78*gy,0,255);dg=np.clip(V*0.25+20,0,90);L=sil*(1-db)+dg*db
    out=big.astype(np.float32)+(np.stack([L*1.03,L,L*0.97],-1)-big)*mb[...,None]
    out=cv2.addWeighted(out,1.3,cv2.GaussianBlur(out,(0,0),1.0),-0.3,0)
    enc.stdin.write(np.clip(out,0,255).astype(np.uint8).tobytes());i+=1
enc.stdin.close();enc.wait()
st={'frames':i,'sec':round(time.time()-t0,1),'mask_meandiff':float(np.mean(diffs)),'p99':float(np.percentile(diffs,99))};print(json.dumps(st))
if A.stats: json.dump(st,open(A.stats,'w'))
