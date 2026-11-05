#!/usr/bin/env python
"""Black/dark garment -> dark green (SAM2 masks obj1+obj2), sequins/shirt -> dark red, bottom blurred band soft dark-pixel tint.
usage: recolor_black_v1.py SRC MASKS.npy OUT [--stride 3 --ss --t --band 0.879]"""
import argparse,subprocess,json,time,numpy as np,cv2
a=argparse.ArgumentParser();a.add_argument('src');a.add_argument('masks');a.add_argument('out')
a.add_argument('--stride',type=int,default=3);a.add_argument('--ss',type=float,default=0);a.add_argument('--t',type=float,default=0)
a.add_argument('--W',type=int,default=1080);a.add_argument('--H',type=int,default=1920);a.add_argument('--crf',type=int,default=16)
a.add_argument('--band',type=float,default=0.879);a.add_argument('--stats',default='');a.add_argument('--alpha',type=float,default=0.7)
a.add_argument('--hue',type=float,default=140);a.add_argument('--dhue',type=float,default=0)
A=a.parse_args()
MK=np.load(A.masks,mmap_mode='r')
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',A.src]))['streams'][0]
w,h,fps=info['width'],info['height'],info['r_frame_rate'];n_,d_=map(int,fps.split('/'));off=int(round(A.ss*n_/d_))
cut=(['-ss',str(A.ss)] if A.ss else [])+(['-t',str(A.t)] if A.t else [])
dec=subprocess.Popen(['ffmpeg','-v','error',*cut,'-i',A.src,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{A.W}x{A.H}','-r',fps,'-i','-',*cut,'-i',A.src,'-map','0:v','-map','1:a?','-c:v','libx264','-preset','fast','-crf',str(A.crf),'-pix_fmt','yuv420p','-c:a','copy','-shortest',A.out],stdin=subprocess.PIPE)
def getm(i):
    j=i+off;k=j//A.stride;r=(j%A.stride)/A.stride;k1=min(k+1,len(MK)-1);k=min(k,len(MK)-1)
    m=(MK[k].astype(np.float32)*(1-r)+MK[k1].astype(np.float32)*r)/255
    return m[0].copy(),m[1].copy()
dis=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST);ys,xs=np.mgrid[0:h,0:w].astype(np.float32)
by=int(h*A.band)
def rp(x,a,b): return np.clip((x-a)/(b-a),0,1)
S=None;prev=None;n=w*h*3;i=0;t0=time.time();diffs=[]
while True:
    b=dec.stdout.read(n)
    if len(b)<n:break
    fr=np.frombuffer(b,np.uint8).reshape(h,w,3);g=cv2.cvtColor(fr,cv2.COLOR_BGR2GRAY)
    hs=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV).astype(np.float32);H=hs[...,0]*2;Sa=hs[...,1];V=hs[...,2]
    m,m2=getm(i);m[by:]=0;m2[by:]=0
    wood=((H>=8)&(H<=48)&(Sa>60)&(V>110)).astype(np.float32)
    sk2=((H<=45)&(Sa>30)&(V>80)).astype(np.uint8)
    # pianist: cut above collar = below lowest face/skin row in his upper region
    m2b=(m2>0.5)
    if m2b.any():
        rows=np.where(m2b.any(1))[0];top=rows.min()
        fs=sk2[top:top+260]*m2b[top:top+260]
        cut=top+ (np.where(fs.any(1))[0].max()+12 if fs.any() else 150)
        m2[:cut]=0
    m2=m2*(1-wood)
    # singer hem: grow down over grey/dark low-sat garment pixels, not wood
    g_ok=((Sa<55)&(V<240)).astype(np.uint8)*(wood<0.5).astype(np.uint8)
    gr_=(m>0.5).astype(np.uint8);lo=int(h*0.55)
    for _ in range(30):
        gr_[lo:by]=np.maximum(gr_[lo:by],cv2.dilate(gr_,np.ones((7,3)))[lo:by]*g_ok[lo:by])
    m=np.maximum(m,cv2.GaussianBlur(gr_.astype(np.float32),(5,5),0))
    m=np.maximum(m,m2)
    skin=((H<=45)&(Sa>35)&(V>95)).astype(np.uint8);skin[int(h*0.6):]=0
    dk=cv2.erode(V,np.ones((7,7)))<70
    txt=((((H>=35)&(H<=75)&(Sa>90)&(V>120))|((Sa<45)&(V>185)))&dk).astype(np.uint8)
    nl,lab,stt,_=cv2.connectedComponentsWithStats(txt,8)
    big_ids=np.where(stt[:,4]>=60)[0];big_ids=big_ids[big_ids>0]
    txt=np.isin(lab,big_ids).astype(np.uint8)
    txt=cv2.dilate(txt,np.ones((7,7)))
    prot=cv2.dilate(np.maximum(skin,txt),np.ones((5,5))).astype(np.float32)
    cloth=m*(1-prot)
    # pianist shirt (white) -> red lining
    shirt=m2*((Sa<50)&(V>140)).astype(np.float32)
    cloth=np.maximum(cloth,m2*0)  # keep
    # sequins: sparkle inside robe
    hp=V-cv2.GaussianBlur(V,(0,0),1.2);sd=np.sqrt(cv2.blur(hp*hp,(5,5)).clip(0))
    sq=((sd>14)&(cv2.erode((m>0.5).astype(np.uint8),np.ones((7,7)))>0)).astype(np.uint8)
    sq=cv2.morphologyEx(sq,cv2.MORPH_CLOSE,np.ones((9,9)));sq=cv2.morphologyEx(sq,cv2.MORPH_OPEN,np.ones((5,5)))
    deco=np.maximum(sq.astype(np.float32)*m,shirt)*(1-cv2.dilate(txt,np.ones((9,9))).astype(np.float32))
    # band: soft dark pixels
    bw=rp(V,115,60)*rp(Sa,95,50);bw=cv2.GaussianBlur(bw,(0,0),6)
    colm=(m[by-40:by]>0.5).any(0).astype(np.float32)
    colm=cv2.GaussianBlur(cv2.dilate(colm[None],np.ones((1,61))),(0,0),15)[0]
    cloth[by:]=bw[by:]*np.clip(colm*1.5,0,1)[None]
    st=np.stack([cloth,deco])
    if S is None:S=st
    else:
        fl=dis.calc(g,prev,None);Sw=np.stack([cv2.remap(x,xs+fl[...,0],ys+fl[...,1],cv2.INTER_LINEAR) for x in S]);Sn=(1-A.alpha)*Sw+A.alpha*st
        diffs.append(float(np.abs(Sn[0]-S[0]).mean()));S=Sn
    prev=g
    big=cv2.resize(fr,(A.W,A.H),interpolation=cv2.INTER_LANCZOS4)
    up=cv2.resize(np.dstack([S[0],S[1]]),(A.W,A.H),interpolation=cv2.INTER_LINEAR)
    mb=np.clip(cv2.ximgproc.guidedFilter(big,np.ascontiguousarray(up[...,0]),4,1e-3),0,1)
    db=np.clip(cv2.ximgproc.guidedFilter(big,np.ascontiguousarray(up[...,1]),3,1e-3),0,1)
    hb=cv2.cvtColor(big,cv2.COLOR_BGR2HSV_FULL).astype(np.float32);Vb=hb[...,2]
    gr=cv2.cvtColor(np.dstack([np.full_like(Vb,A.hue*256/360),np.full_like(Vb,175),np.clip(26+Vb*0.95,0,150)]).astype(np.uint8),cv2.COLOR_HSV2BGR_FULL).astype(np.float32)
    rd=cv2.cvtColor(np.dstack([np.full_like(Vb,A.dhue*256/360),np.full_like(Vb,200),np.clip(35+Vb*0.5,0,140)]).astype(np.uint8),cv2.COLOR_HSV2BGR_FULL).astype(np.float32)
    out=big.astype(np.float32);out+= (gr-out)*mb[...,None];out+=(rd-out)*db[...,None]
    out=cv2.addWeighted(out,1.2,cv2.GaussianBlur(out,(0,0),1.0),-0.2,0)
    enc.stdin.write(np.clip(out,0,255).astype(np.uint8).tobytes());i+=1
enc.stdin.close();enc.wait()
st={'frames':i,'sec':round(time.time()-t0,1),'mask_meandiff':float(np.mean(diffs)),'p99':float(np.percentile(diffs,99))};print(json.dumps(st))
if A.stats: json.dump(st,open(A.stats,'w'))
