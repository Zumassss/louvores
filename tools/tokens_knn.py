"""Para cada acorde, olha os 12 acordes de desenho mais parecido e decide a leitura pela maioria (corrige erros isolados do OCR)."""
import numpy as np, glob, json, collections
from PIL import Image

d = np.load("tk/vote.npz"); meta = d["meta"]; ocr = list(d["ocr"])
imgs = np.concatenate([np.load(f)["imgs"] for f in sorted(glob.glob("tk/w*/t.npz"))])
N = len(meta)
small = np.stack([np.asarray(Image.fromarray(x).resize((120, 24), Image.BILINEAR)) for x in imgs]).astype(np.float32) / 255
w = (meta[:, 3] - meta[:, 1]).astype(np.float32); h = (meta[:, 4] - meta[:, 2]).astype(np.float32)
v = small.reshape(N, -1); v /= (np.linalg.norm(v, axis=1, keepdims=True) + 1e-6)
feat = np.concatenate([v, (np.log(w / h + 0.1))[:, None] * 1.5, (np.log(h) / 4)[:, None]], 1)
feat = (feat / np.linalg.norm(feat, axis=1, keepdims=True)).astype(np.float32)
K = 12
nn = np.zeros((N, K), np.int32); ns = np.zeros((N, K), np.float32)
B = 2048
for a in range(0, N, B):
    S = feat[a:a + B] @ feat.T
    for i in range(S.shape[0]): S[i, a + i] = -1
    idx = np.argpartition(-S, K, axis=1)[:, :K]
    sv = np.take_along_axis(S, idx, 1)
    o = np.argsort(-sv, 1)
    nn[a:a + B] = np.take_along_axis(idx, o, 1); ns[a:a + B] = np.take_along_axis(sv, o, 1)
np.savez_compressed("tk/knn.npz", nn=nn, ns=ns)

final, conf, changed, filled, unsure = [], [], 0, 0, 0
for i in range(N):
    c = collections.Counter()
    for j, s in zip(nn[i], ns[i]):
        if s >= 0.95 and ocr[j]: c[ocr[j]] += s
    if ocr[i]: c[ocr[i]] += 1.0
    tot = sum(c.values())
    if not tot:
        final.append(ocr[i]); conf.append(0.0); unsure += 1; continue
    lab, sc = c.most_common(1)[0]
    p = sc / tot
    if p >= 0.6 and lab != ocr[i]:
        if ocr[i]: changed += 1
        else: filled += 1
        final.append(lab)
    else:
        final.append(ocr[i] if ocr[i] else lab)
        if p < 0.6: unsure += 1
    conf.append(p)
np.savez_compressed("tk/final.npz", final=np.array(final), conf=np.array(conf), meta=meta, ocr=np.array(ocr))
print("acordes", N, "corrigidos", changed, "preenchidos", filled, "incertos", unsure)
