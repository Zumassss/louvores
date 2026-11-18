"""Agrupa acordes com a mesma imagem e decide a leitura de cada grupo pela maioria das leituras do OCR."""
import numpy as np, glob, json, collections
from PIL import Image

metas, imgs = [], []
for f in sorted(glob.glob("tk/w*/t.npz")):
    d = np.load(f); metas.append(d["meta"]); imgs.append(d["imgs"])
meta = np.concatenate(metas); im = np.concatenate(imgs)
N = len(meta)
small = np.stack([np.asarray(Image.fromarray(x).resize((120, 24), Image.BILINEAR)) for x in im]).astype(np.float32) / 255
w = (meta[:, 3] - meta[:, 1]).astype(np.float32); h = (meta[:, 4] - meta[:, 2]).astype(np.float32)
v = small.reshape(N, -1); v /= (np.linalg.norm(v, axis=1, keepdims=True) + 1e-6)
feat = np.concatenate([v, (np.log(w / h + 0.1))[:, None] * 1.5, (np.log(h) / 4)[:, None]], 1)
feat /= np.linalg.norm(feat, axis=1, keepdims=True)
feat = feat.astype(np.float32)

# leitura do OCR para cada recorte
ocr = [None] * N
bypg = collections.defaultdict(list)
for i, m in enumerate(meta): bypg[int(m[0])].append(i)
for l in open("n2/all.jsonl"):
    r = json.loads(l); pg = r["page"]
    toks = bypg.get(pg, [])
    for row in r["rows"]:
        ent = [(x, t, row.get("chy")) for x, t in row.get("chords", [])] + [(x, t, None) for x, t in row.get("inline", [])]
        for x, t, chy in ent:
            best, bd = None, 1e9
            for i in toks:
                _, x0, y0, x1, y1 = meta[i]
                if chy is not None:
                    if not (-8 <= chy - y1 <= 50 and abs(x0 - x) <= 30): continue
                    d = abs(x0 - x) + abs(chy - y1)
                else:
                    if not (y0 - 25 <= row["y"] <= y1 + 25 and abs(x0 - x) <= 40): continue
                    d = abs(x0 - x) + abs(row["y"] - y0)
                if d < bd: best, bd = i, d
            if best is not None and (ocr[best] is None or ocr[best] == ""): ocr[best] = t

THR = 0.985
C = np.zeros((0, feat.shape[1]), np.float32); cnt = []; lab = np.zeros(N, np.int32)
order = np.argsort(-(w * h))
for k, idx in enumerate(order):
    f = feat[idx]
    if len(C):
        s = C @ f; j = int(np.argmax(s))
        if s[j] >= THR:
            lab[idx] = j; cnt[j] += 1; C[j] += (f - C[j]) / cnt[j]; C[j] /= np.linalg.norm(C[j]); continue
    C = np.vstack([C, f[None]]); cnt.append(1); lab[idx] = len(cnt) - 1
cnt = np.array(cnt)
votes = [collections.Counter() for _ in cnt]
for i in range(N):
    if ocr[i]: votes[lab[i]][ocr[i]] += 1
np.savez_compressed("tk/vote.npz", lab=lab, cnt=cnt, meta=meta, ocr=np.array([o or "" for o in ocr]))
json.dump([dict(v) for v in votes], open("tk/votes.json", "w"))
print("acordes", N, "com ocr", sum(1 for o in ocr if o), "grupos", len(cnt), ">=5:", (cnt >= 5).sum(), "cobrem", cnt[cnt >= 5].sum())
