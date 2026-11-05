#!/usr/bin/env python
"""Dual recolor from silver_v3 mask logic: SAM coat -> dark green; sequin/sparkle (+optional obj2) -> dark red."""
import argparse,subprocess,json,time,numpy as np,cv2
a=argparse.ArgumentParser();a.add_argument('src');a.add_argument('masks');a.add_argument('out')
a.add_argument('--stride',type=int,default=3);a.add_argument('--ss',type=float,default=0);a.add_argument('--t',type=float,default=0)
a.add_argument('--W',type=int,default=1080);a.add_argument('--H',type=int,default=1920);a.add_argument('--crf',type=int,default=16)
a.add_argument('--alpha',type=float,default=0.7);a.add_argument('--ystrip',type=int,default=920);a.add_argument('--stats',default='')
a.add_argument('--hue',type=float,default=140);a.add_argument('--dhue',type=float,default=0)
a.add_argument('--sat',type=float,default=0.88);a.add_argument('--dsat',type=float,default=1.05)
a.add_argument('--vscale',type=float,default=0.5);a.add_argument('--dvscale',type=float,default=0.5)
a.add_argument('--seqsd',type=float,default=8.)
a.add_argument('--noskin',type=int,default=1)
A=a.parse_args()
MK=np.load(A.masks,mmap_mode='r')
if MK.ndim==3: MK=MK[:,None]
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',A.src]))['streams'][0]
w,h,fps=info['width'],info['height'],info['r_frame_rate']
cut=(['-ss',str(A.ss)] if A.ss else [])+(['-t',str(A.t)] if A.t else [])
dec=subprocess.Popen(['ffmpeg','-v','error',*cut,'-i',A.src,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{A.W}x{A.H}','-r',fps,'-i','-',*cut,'-i',A.src,'-map','0:v','-map','1:a?','-c:v','libx264','-preset','fast','-crf',str(A.crf),'-pix_fmt','yuv420p','-c:a','copy','-shortest',A.out],stdin=subprocess.PIPE)
def getm(i):
    k=(i+ss_off)//A.stride;r=(i%A.stride)/A.stride;k1=min(k+1,len(MK)-1);k=min(k,len(MK)-1)
    raw=MK[k].astype(np.float32)*(1-r)+MK[k1].astype(np.float32)*r
    raw=raw/255
    if raw.shape[1:]!=(h,w): raw=np.stack([cv2.resize(x,(w,h),interpolation=cv2.INTER_LINEAR) for x in raw])
    return raw  # [C,h,w] C>=1
dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)
ys,xs=np.mgrid[0:h,0:w].astype(np.float32)
has_obj2 = MK.shape[1]>1 and float(MK[:,1].max())>0
try:
    _n,_d=map(int,str(fps).split('/')); _fpv=_n/float(_d)
except Exception:
    _fpv=float(fps)
ss_off=int(round(A.ss*_fpv))
fbig=np.zeros((A.H,A.W),np.float32);cv2.ellipse(fbig,(int(A.W*0.55),int(A.H*0.22)),(int(A.W*0.14),int(A.H*0.14)),0,0,360,1.,-1)
prev=None;S=None;n=w*h*3;i=0;t0=time.time();diffs=[]
while True:
    b=dec.stdout.read(n)
    if len(b)<n:break
    fr=np.frombuffer(b,np.uint8).reshape(h,w,3);g=cv2.cvtColor(fr,cv2.COLOR_BGR2GRAY)
    mm=getm(i);hsv=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV);Hh=hsv[...,0].astype(np.float32)*2;Ss=hsv[...,1].astype(np.float32);Vv=hsv[...,2].astype(np.float32)
    skin=((Hh>=14)&(Hh<=40)&(Ss>45)&(Vv>120)).astype(np.float32);skin=cv2.GaussianBlur(cv2.dilate(skin,np.ones((5,5))),(7,7),0)
    # also bright hands
    hand=0*((Ss<80)&(Vv>150)&((fr[...,1].astype(np.int16)-fr[...,0])>=4)&(Hh<=40)&(mm[0]>0.4)).astype(np.float32);hand=cv2.GaussianBlur(cv2.dilate(hand,np.ones((5,5))),(7,7),0)
    skin=np.clip(skin+hand,0,1)
    pink=(((Hh>=300)|(Hh<=30))&(Ss>12)).astype(np.float32)
    core=cv2.morphologyEx(mm[0],cv2.MORPH_CLOSE,np.ones((61,3)));reg=cv2.dilate(core,np.ones((9,9)))
    rim=(((Hh>=300)|(Hh<=18))&(Ss>25)).astype(np.float32)
    coat=np.where(core>0.5,pink*(1-skin*(core<0.9)),reg*rim)
    near=cv2.dilate((core>0.5).astype(np.uint8),np.ones((41,41)))
    coat=np.maximum(coat,near*((Hh>=305)&(Ss>35)).astype(np.float32)*(1-skin))
    # fuller fill + soft core to kill pink edge holes/halos
    coat=np.maximum(coat,core*(1-skin)*0.95)
    face=np.zeros((h,w),np.float32);cv2.ellipse(face,(int(w*0.55),int(h*0.22)),(int(w*0.14),int(h*0.14)),0,0,360,1.,-1);face=cv2.GaussianBlur(face,(31,31),0)
    skin2=((Hh>=8)&(Hh<=42)&(Ss>28)&(Vv>85)).astype(np.float32)
    coat=coat*(1.0-np.clip(face*skin2*1.35,0,1))
    band=((Hh>=315)|((Hh<11)&(Ss<140)&(Vv>140)))&(Ss>10)
    hdist=np.minimum(np.abs(Hh-345),360-np.abs(Hh-345))
    bs=np.clip((45-hdist)/25,0,1)*np.clip((Ss-8)/25,0,1)*np.clip((Vv-50)/40,0,1)
    coat[A.ystrip:]=cv2.GaussianBlur(bs,(0,0),4)[A.ystrip:]
    # decorations = sequin texture (local V std) inside SAM coat, minus burned-in text
    hp=Vv-cv2.GaussianBlur(Vv,(0,0),1.5);sd=np.sqrt(np.maximum(cv2.blur(hp*hp,(7,7)),0))
    ec=cv2.erode((core>0.5).astype(np.uint8),np.ones((13,13)))
    txt=(((Hh>=35)&(Hh<=75)&(Ss>90)&(Vv>140))|(Vv<45)).astype(np.uint8)
    txt=cv2.dilate(txt,np.ones((11,11)))
    dd=((sd>13)&(ec>0)&(txt==0)).astype(np.uint8)
    dd=cv2.morphologyEx(dd,cv2.MORPH_CLOSE,np.ones((7,7)));dd=cv2.morphologyEx(dd,cv2.MORPH_OPEN,np.ones((7,7)))
    hsf=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV_FULL).astype(np.float32);Hf=hsf[...,0]*360/256
    # hands only near coat (not face/wood)
    near_coat=cv2.dilate((core>0.4).astype(np.uint8),np.ones((51,51)))
    facep=np.zeros((h,w),np.uint8);cv2.ellipse(facep,(int(w*0.55),int(h*0.22)),(int(w*0.16),int(h*0.16)),0,0,360,1,-1)
    hd=((Hf>=6)&(Hf<=32)&(Ss>70)&(Ss<170)&(Vv>120)&(near_coat>0)&(facep==0)).astype(np.uint8)
    hd=cv2.morphologyEx(hd,cv2.MORPH_OPEN,np.ones((5,5)))
    hin=cv2.erode(hd,np.ones((3,3))); hout=cv2.dilate(hd,np.ones((23,23)))
    cz=((hout>0)&(hin==0)).astype(np.uint8)
    cz[:int(h*0.38)]=0;cz[int(h*0.62):]=0
    hp2=Vv-cv2.GaussianBlur(Vv,(0,0),0.8);sd2=np.sqrt(np.maximum(cv2.blur(hp2*hp2,(3,3)),0))
    ec2=((core>0.4)).astype(np.uint8)
    # in cuff annulus: sequin sparkle OR non-matte (any texture/darker) fabric
    dd2=(((sd2>6)|(Vv<180))&(Ss>50)&(ec2>0)&(cz>0)&(txt==0)).astype(np.uint8)
    dd2=cv2.morphologyEx(dd2,cv2.MORPH_CLOSE,np.ones((9,9)))
    dd2=cv2.morphologyEx(dd2,cv2.MORPH_OPEN,np.ones((3,3)))
    # keep dd2 inside cz (no streak up sleeve)
    dd2=dd2*cz
    dd=np.maximum(dd,dd2)
    dd[A.ystrip:]=0
    deco=cv2.GaussianBlur(dd.astype(np.float32),(7,7),0)*coat
    cloth=np.clip(coat*(1.0-0.9*deco),0,1)
    st=np.stack([cloth,deco])
    if S is None:S=st
    else:
        fl=dis.calc(g,prev,None);mx,my=xs+fl[...,0],ys+fl[...,1]
        Sw=np.stack([cv2.remap(x,mx,my,cv2.INTER_LINEAR) for x in S]);Sn=(1-A.alpha)*Sw+A.alpha*st
        diffs.append(float(np.abs(Sn[0]-S[0]).mean()));S=Sn
    prev=g
    big=cv2.resize(fr,(A.W,A.H),interpolation=cv2.INTER_LANCZOS4)
    upm=cv2.resize(np.dstack([S[0],S[1]]),(A.W,A.H),interpolation=cv2.INTER_LINEAR)
    try:
        mb=np.clip(cv2.ximgproc.guidedFilter(big,np.ascontiguousarray(upm[...,0]),6,1e-3),0,1)
        db=np.clip(cv2.ximgproc.guidedFilter(big,np.ascontiguousarray(upm[...,1]),4,1e-3),0,1)
    except Exception:
        mb=np.clip(cv2.GaussianBlur(upm[...,0],(5,5),0),0,1);db=np.clip(cv2.GaussianBlur(upm[...,1],(5,5),0),0,1)
    db=np.clip(db,0,1);mb=np.clip(np.maximum(mb,db*0.3),0,1)
    hb=cv2.cvtColor(big,cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    Hd=hb[...,0]*360/256;Sb,Vb=hb[...,1],hb[...,2]
    # hard skin protect at output res (hands: bright low-S; face: warm hue)
    gb=big[...,1].astype(np.float32)-big[...,0].astype(np.float32)
    sk=((Hd>=0)&(Hd<=40)&(Sb<80)&(Vb>150)&(gb>=4))|((Hd>=8)&(Hd<=40)&(Sb>=62)&(Sb<175)&(Vb>110)&(fbig>0.3))
    sk=np.zeros(Vb.shape,np.float32) if A.noskin else cv2.GaussianBlur(cv2.dilate(sk.astype(np.uint8),np.ones((5,5))).astype(np.float32),(5,5),0)
    # harden blend (no half-blends on rims) + rim pink clamp
    sy=int(A.ystrip*A.H/h)
    soft=mb[sy:].copy()
    mb=np.clip((mb-0.08)/0.35,0,1)
    hd0=np.minimum(np.abs(Hd-345),360-np.abs(Hd-345))
    pkk=np.clip((40-hd0)/20,0,1)*np.clip((Sb-10)/20,0,1)
    # 1-2px AA/pale fringe on coat silhouette: recolor pale edge, never wood/skin
    face_sk=((Hd>=6)&(Hd<=35)&(Sb>70)&(Vb>100)&(fbig>0.25)).astype(np.float32)
    wood=((Hd>=10)&(Hd<=48)&(Sb>170)&(Vb<135)).astype(np.float32)
    piano=((Vb<55)&(Sb<60)).astype(np.float32)
    cbig=cv2.resize(core,(A.W,A.H),interpolation=cv2.INTER_LINEAR)
    cbig=np.clip(cbig,0,1)
    coat_bin=(mb>0.4).astype(np.uint8)
    grow=cv2.dilate(coat_bin,np.ones((5,5))).astype(np.float32)  # ~2px
    safe=(1-np.clip(sk+face_sk+wood+piano,0,1))
    # AA fringe: mid-S edge blend (not solid high-S wood); pale/pink/desat OK
    fringe=(((Sb<165)&(Vb>85))|(((Hd>=280)|(Hd<=55))&(Sb>8)&(Vb>75))).astype(np.float32)
    mb=np.clip(np.maximum(mb,grow*fringe*safe),0,1)
    mb[sy:]=np.clip(soft*1.3,0,1)
    # harden so pale AA can't show through; tiny blur only
    mb=np.clip((mb-0.02)/0.20,0,1)
    mb=cv2.GaussianBlur(mb,(3,3),0)*(1-sk)
    db=np.clip((db-0.15)/0.45,0,1)*(1-sk)*np.clip(cv2.erode(mb,np.ones((3,3)))*1.5,0,1)
    g_hsv=np.dstack([np.full(Vb.shape,A.hue*256/360.0,np.float32),np.maximum(Sb*0.85,170),Vb*A.vscale])
    r_hsv=np.dstack([np.full(Vb.shape,A.dhue*256/360.0,np.float32),np.maximum(Sb,185),np.minimum(Vb*A.dvscale,105)])
    gr=cv2.cvtColor(np.clip(g_hsv,0,255).astype(np.uint8),cv2.COLOR_HSV2BGR_FULL).astype(np.float32)
    rd=cv2.cvtColor(np.clip(r_hsv,0,255).astype(np.uint8),cv2.COLOR_HSV2BGR_FULL).astype(np.float32)
    out=big.astype(np.float32)
    out=out+(gr-out)*mb[...,None]
    out=out+(rd-out)*db[...,None]
    out=cv2.addWeighted(out,1.25,cv2.GaussianBlur(out,(0,0),1.0),-0.25,0)
    enc.stdin.write(np.clip(out,0,255).astype(np.uint8).tobytes());i+=1
enc.stdin.close();enc.wait()
st={'frames':i,'sec':round(time.time()-t0,1),'mask_meandiff':float(np.mean(diffs) if diffs else 0),'p99':float(np.percentile(diffs,99) if diffs else 0),'has_obj2':has_obj2}
print(json.dumps(st))
if A.stats: json.dump(st,open(A.stats,'w'))
