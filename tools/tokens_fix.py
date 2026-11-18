"""Combina a leitura do OCR com a maioria dos acordes de desenho igual.
Regras (conferidas olhando os recortes):
- letra do acorde, 'm', extensão e letra do baixo: vale a maioria dos vizinhos;
- extensão só cresce (A -> A7), nunca perde números lidos;
- '#' e 'b' (pequenos, o desenho quase não muda): ficam os do OCR; se o OCR não leu nada,
  só entram se os vizinhos concordarem quase todos.
"""
import numpy as np, collections, re, json
import nivel2_assemble as na

PAT = re.compile(r"^([A-G])([#b]?)([^/]*)(?:/([A-G])([#b]?))?$")

def norm(t):
    if not t: return None
    t = t.replace("7M", "7M")
    n = na.norm_chord(t)
    return n if n and PAT.match(n) else None

def parts(t):
    m = PAT.match(t); return m.groups() if m else None

d = np.load("tk/vote.npz"); meta = d["meta"]; ocr = list(d["ocr"])
k = np.load("tk/knn.npz"); nn, ns = k["nn"], k["ns"]
N = len(meta)
lab = [norm(o) for o in ocr]
P = [parts(l) if l else None for l in lab]

out, why = [], collections.Counter()
for i in range(N):
    nb = [(j, s) for j, s in zip(nn[i], ns[i]) if s >= 0.955 and P[j]]
    own = P[i]
    if not nb:
        out.append(lab[i] or ""); why["sem vizinhos"] += 1; continue
    def vote(f, w_own=1.0):
        c = collections.Counter()
        for j, s in nb: c[f(P[j])] += s
        if own: c[f(own)] += w_own
        tot = sum(c.values()); v, sc = c.most_common(1)[0]
        return v, sc / tot
    root, pr = vote(lambda p: p[0])
    qual, pq = vote(lambda p: p[2])
    bass, pb = vote(lambda p: p[3] or "")
    acc, pa = vote(lambda p: p[1])
    bacc, pba = vote(lambda p: p[4] or "")
    if own:
        r0, a0, q0, b0, ba0 = own
        R = root if pr >= 0.6 else r0
        Q = q0
        if pq >= 0.6 and qual != q0:
            # extensão só cresce; 'm' pode aparecer/sumir conforme os vizinhos
            if qual.startswith(q0) or (q0 in ("", "m") and qual in ("m", "")) or not na.CH.match("C" + q0): Q = qual
        B = bass if pb >= 0.6 else (b0 or "")
        A = a0; BA = ba0 or ""
        if B and not b0: BA = bacc if pba >= 0.9 else ""
        if not B: BA = ""
    else:
        if pr < 0.6: out.append(""); why["incerto"] += 1; continue
        R, Q = root, (qual if pq >= 0.6 else "")
        B = bass if pb >= 0.6 else ""
        A = acc if pa >= 0.9 else ""
        BA = bacc if (B and pba >= 0.9) else ""
    new = R + A + Q + ("/" + B + BA if B else "")
    if not na.CH.match(new): new = lab[i] or ""
    if new != (lab[i] or ""): why["corrigido" if lab[i] else "preenchido"] += 1
    out.append(new)
np.savez_compressed("tk/fixed.npz", meta=meta, ocr=np.array(ocr), fixed=np.array(out))
print(dict(why), "vazios", sum(1 for x in out if not x))
c = collections.Counter((a, b) for a, b in zip(lab, out) if a and a != b)
for kk, v in c.most_common(45): print(kk, v)
