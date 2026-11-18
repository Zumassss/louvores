import json,numpy as np,glob,collections
from PIL import Image, ImageFilter
imgs=np.concatenate([np.load(x)['imgs'] for x in sorted(glob.glob('tk/w*/t.npz'))])
def feat(i):
    a=imgs[i]; cols=np.where((a>80).any(0))[0]; w=cols.max()+1 if len(cols) else 1
    # metade direita (depois da letra): onde ficam acidente e sufixo
    x0=int(w*0.45)
    p=Image.fromarray(a[:18, x0:w]).resize((24,14),Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.5))
    v=np.asarray(p,np.float32).ravel(); v-=v.mean(); v/=np.linalg.norm(v)+1e-6
    return np.concatenate([v,[np.log(w/32)*0.6]])
