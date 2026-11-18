import json,numpy as np,glob,collections
from PIL import Image
from scipy import ndimage
head=np.concatenate([np.load(f)["imgs"] for f in sorted(glob.glob("hd/w*/t.npz"))])
def glyph(i):
    m=head[i]>110
    lab,n=ndimage.label(m)
    objs=ndimage.find_objects(lab)
    comps=[(o[1].start,o[1].stop,o[0].start,o[0].stop,k+1) for k,o in enumerate(objs) if o is not None and (lab[o]==k+1).sum()>=6]
    comps.sort()
    if len(comps)<2: return None
    # raiz: primeiro componente alto
    r=next((c for c in comps if c[3]-c[2]>=30),None)
    if r is None: return None
    nxt=[c for c in comps if c[0]>=r[0]+3 and c is not r and c[2]<=12 and (c[3]-c[2])<=34]
    if not nxt: return None
    g=min(nxt,key=lambda c:c[0])
    x0,x1,y0,y1,k=g
    crop=(lab[y0:y1,x0:x1]==k).astype(np.uint8)
    h,w=crop.shape; s=max(h,w)
    pad=np.zeros((s,s),np.uint8); pad[(s-h)//2:(s-h)//2+h,(s-w)//2:(s-w)//2+w]=crop*255
    v=np.asarray(Image.fromarray(pad).resize((16,16),Image.BILINEAR),np.float32).ravel()/255
    # buraco no meio?
    filled=ndimage.binary_fill_holes(crop); hole=(filled&~crop.astype(bool)).sum()/max(1,filled.sum())
    extra=np.array([h/48*3, w/max(1,h), hole*4, y1/48*3],np.float32)
    f=np.concatenate([v/ (np.linalg.norm(v)+1e-6), extra*0.5])
    return f,(h,w,round(float(hole),2),y1)

W=json.load(open('tk/widths.json')); KL=W['kl']
def hole_in_slot(i, L, x_extra=0):
    m=head[i]>110
    filled=ndimage.binary_fill_holes(m)
    holes=filled&~m
    x0=max(0,int(round(KL[L]*48))-5+x_extra); x1=x0+24
    return int(holes[:26, x0:x1].sum())

def ring_after(i, L):
    """componentes com buraco depois da letra, na parte de cima: (x0, altura, largura, área do buraco)"""
    m = head[i] > 110
    lab, n = ndimage.label(m)
    filled = ndimage.binary_fill_holes(m); holes = filled & ~m
    out = []
    xr = int(round(KL[L] * 48)) - 3
    for k, o in enumerate(ndimage.find_objects(lab), 1):
        if o is None or o[1].start < xr or o[0].start > 14: continue
        comp = lab[o] == k
        hcomp = ndimage.binary_fill_holes(comp) & ~comp
        if hcomp.sum() >= 3:
            out.append((o[1].start, o[0].stop - o[0].start, o[1].stop - o[1].start, int(hcomp.sum()), o[0].stop))
    return sorted(out)
