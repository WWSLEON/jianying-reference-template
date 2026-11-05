#!/usr/bin/env python
"""SAM2.1-tiny CPU video tracking. usage: sam2_track.py FRAMES_DIR PROMPTS.json OUT.npy [IMAGE_SIZE=1024, e.g. 512]
prompts: {"objs":{"1":{"pos":[[x,y]..],"neg":[..]},"2":{...}},"frame":0}. Saves uint8 [N,2,H,W] masks (obj1, obj2)."""
import sys,json,time,numpy as np,torch
torch.set_num_threads(8)
from sam2.build_sam import build_sam2_video_predictor
d,pj,out=sys.argv[1:4];SZ=int(sys.argv[4]) if len(sys.argv)>4 else 1024;P=json.load(open(pj))
pred=build_sam2_video_predictor('configs/sam2.1/sam2.1_hiera_t.yaml','/workspace/sam2/ck/t.pt',device='cpu',hydra_overrides_extra=[f'++model.image_size={SZ}'])
t0=time.time()
with torch.inference_mode():
    st=pred.init_state(d,offload_video_to_cpu=True,offload_state_to_cpu=True)
    for k,o in P['objs'].items():
        pts=o['pos']+o['neg'];lb=[1]*len(o['pos'])+[0]*len(o['neg'])
        pred.add_new_points_or_box(st,frame_idx=P.get('frame',0),obj_id=int(k),points=np.array(pts,np.float32),labels=np.array(lb,np.int32))
    N=st['num_frames'];H,W=st['video_height'],st['video_width'];M=np.zeros((N,2,H,W),np.uint8)
    for fi,ids,lg in pred.propagate_in_video(st):
        for j,i in enumerate(ids): M[fi,i-1]=(torch.sigmoid(lg[j,0])*255).byte().numpy()
        if fi%50==0: print(fi,round(time.time()-t0,1),flush=True)
np.save(out,M);print('done',N,round(time.time()-t0,1))
