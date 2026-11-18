"""Ajustes finais da leitura: º no lugar de # (buraco no sinal) e sufixo depois de #/b (º, ø, 6, 9, 7, 2) por exemplos conferidos."""
import json, re, collections, numpy as np
from oslot import hole_in_slot
from accsfx import feat
F = []
for k in range(4): F += json.load(open(f"tk/fr_{k*14316}.json"))
n = collections.Counter()
for i, f in enumerate(F):
    s = f[0]
    if s and re.match(r"^[A-G]#(?!m)", s) and hole_in_slot(i, s[0]) >= 10:
        F[i] = [s[0] + "0" + s[2:], f[1], f[2] + "+dim"]; n["#->º"] += 1
    s = F[i][0]
    s2 = re.sub(r"/Fb$", "/F#", re.sub(r"/Cb$", "/C#", s))
    if s2 != s: F[i] = [s2] + list(F[i][1:]); n["baixo b->#"] += 1
S = json.load(open("seeds_sfx.json"))
X, Y = [], []
for k, ids in S.items():
    for i in ids: X.append(feat(i)); Y.append(k)
X = np.stack(X)
PAT = re.compile(r"^([A-G][#b])(\d+|0|07|ø)?$")
for i, f in enumerate(F):
    m = PAT.match(f[0] or "")
    if not m: continue
    v = feat(i); s = X @ v; o = np.argsort(-s)[:3]
    c = collections.Counter(Y[t] for t in o); p, cnt = c.most_common(1)[0]
    if cnt >= 2 and s[o[0]] > 0.75:
        new = m.group(1) + p
        if new != f[0]: n[(f[0][2:], p)] += 1; F[i] = [new, f[1], f[2] + "+sfx"]
print(n.most_common(30))
json.dump(F, open("tk/final_read.json", "w"))
