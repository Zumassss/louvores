"""Leituras incertas: usa a leitura de acordes de desenho quase idêntico que foram lidos com segurança."""
import json, numpy as np, collections, glob
from PIL import Image, ImageFilter
F = json.load(open("tk/final_read.json"))
imgs = np.concatenate([np.load(x)["imgs"] for x in sorted(glob.glob("tk/w*/t.npz"))])
meta = np.load("tk/vote.npz")["meta"]
N = len(F)
def trusted(f):
    r, sc, tag = f
    base = tag.split("+")[0]
    if "+sfx" in tag: return True
    return base in ("ok", "ajustado") and sc >= 0.55
T = np.array([trusted(f) and bool(f[0]) for f in F])
# vetor fino: largura real, 24x96, desfocado
def vec(i):
    a = imgs[i]; cols = np.where((a > 80).any(0))[0]; w = cols.max() + 1 if len(cols) else 1
    im = Image.fromarray(a[:, :w]).resize((96, 24), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.6))
    v = np.asarray(im, np.float32).ravel(); v -= v.mean(); v /= np.linalg.norm(v) + 1e-6
    return v, w / 32
V = np.zeros((N, 96 * 24), np.float32); A = np.zeros(N, np.float32)
for i in range(N): V[i], A[i] = vec(i)
ti = np.where(T)[0]; VT = V[ti]; AT = np.log(A[ti])
unc = np.where(~T)[0]
res = {}; st = collections.Counter()
for a in range(0, len(unc), 512):
    idx = unc[a:a + 512]
    S = V[idx] @ VT.T - 0.5 * np.abs(np.log(A[idx])[:, None] - AT[None, :])
    for k, i in enumerate(idx):
        o = np.argsort(-S[k])[:5]
        labs = [F[ti[j]][0] for j in o if S[k][j] >= 0.93]
        if len(labs) >= 3:
            lab, n = collections.Counter(labs).most_common(1)[0]
            if n >= 3 and n == len(labs) or n >= 4:
                res[int(i)] = (lab, float(S[k][o[0]])); st["propagado"] += 1
                if lab != F[i][0]: st["mudou"] += 1
                continue
        st["continua incerto"] += 1
json.dump(res, open("tk/propagated.json", "w"))
print(dict(st))
