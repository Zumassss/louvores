"""Compara todos os recortes com todo o vocabulário de acordes desenhados (em lote)."""
import numpy as np, glob, json, re
import synth, nivel2_assemble as na

vs = [np.load(f"tk/voc{k}.npz") for k in range(4)]
V = np.concatenate([v["V"] for v in vs]); F = np.concatenate([v["F"] for v in vs]).astype(np.float32); A = np.concatenate([v["A"] for v in vs])
logA = np.log(A)
PAT = synth.PAT
root = np.array([s[0] for s in V]); bass = np.array([(PAT.match(s).group(5) or "") for s in V])

d = np.load("tk/fixed.npz"); meta = d["meta"]; ocr = d["ocr"]; fixed = d["fixed"]
imgs = np.concatenate([np.load(x)["imgs"] for x in sorted(glob.glob("tk/w*/t.npz"))])
nn = np.load("tk/knn.npz")["nn"]
N = len(meta)
T = np.zeros((N, F.shape[1]), np.float32); tasp = np.zeros(N, np.float32)
for i in range(N):
    T[i], tasp[i] = synth.feat_img(imgs[i], synth.width_of(imgs[i]))

def parts(t):
    t = na.norm_chord(t) if t else None
    m = PAT.match(t) if t else None
    return m.groups() if m else None

out = []
B = 256
for a in range(0, N, B):
    S = T[a:a + B] @ F.T - 0.35 * np.abs(logA[None, :] - np.log(tasp[a:a + B])[:, None])
    for k in range(S.shape[0]):
        i = a + k
        labels = [ocr[i], fixed[i]] + [fixed[j] for j in nn[i][:3]]
        P = [p for p in (parts(x) for x in labels) if p]
        roots = {p[0] for p in P}; basses = {p[4] or "" for p in P} | {""}
        s = S[k]
        g = np.argsort(-s)[:3]
        if roots:
            m = np.isin(root, list(roots)) & np.isin(bass, list(basses))
            sm = np.where(m, s, -9)
            r = np.argsort(-sm)[:6]
        else:
            r = g
        out.append({"i": i, "r": [[str(V[j]), round(float(s[j]), 4)] for j in r], "g": [[str(V[j]), round(float(s[j]), 4)] for j in g]})
json.dump(out, open("tk/syn_all.json", "w"))
print("ok", len(out))
