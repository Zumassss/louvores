"""Classifica o símbolo logo depois da letra do acorde (#, b, m, 7, 9, 6, °, sus, /, nada...) com exemplos reais da coletânea."""
import numpy as np, glob, json, collections, re
from PIL import Image, ImageFilter
import nivel2_assemble as na

meta = np.concatenate([np.load(f)["meta"] for f in sorted(glob.glob("hd/w*/t.npz"))])
head = np.concatenate([np.load(f)["imgs"] for f in sorted(glob.glob("hd/w*/t.npz"))])
fixed = np.load("tk/fixed.npz")["fixed"]
RR = json.load(open("tk/rr_all.json"))
top = [x["c"][0][1] if x["c"] else "" for x in RR]
N = len(meta)
h = meta[:, 4] - meta[:, 2]; w = meta[:, 3] - meta[:, 1]

def nxt(lab):
    if not lab: return None
    m = re.match(r"^[A-G](.?)", lab)
    c = m.group(1)
    if c == "0": c = "o"
    if c.isdigit(): return c
    if c in ("#", "b", "m", "s", "(", "/", "+", "o", "ø", ""): return c
    return None

agree = [i for i in range(N) if top[i] and top[i] == fixed[i]]
# largura da letra: acordes só com a letra
kl = {}
for L in "ABCDEFG":
    r = [w[i] / h[i] for i in agree if top[i] == L and h[i] > 20]
    kl[L] = float(np.median(r)) if r else 0.75
print({k: round(v, 3) for k, v in kl.items()})

def patch(i, L):
    x0 = int(round(kl[L] * 48)) - 4
    p = head[i][:30, max(0, x0):x0 + 30].astype(np.float32)
    if p.shape[1] < 30: p = np.pad(p, ((0, 0), (0, 30 - p.shape[1])))
    p = np.asarray(Image.fromarray(p.astype(np.uint8)).resize((20, 20), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.6)), np.float32)
    v = p.ravel() - p.mean(); return v / (np.linalg.norm(v) + 1e-6)

ex_i = [i for i in agree if nxt(top[i]) is not None]
X = np.stack([patch(i, top[i][0]) for i in ex_i]); Y = np.array([nxt(top[i]) for i in ex_i]); EL = np.array([top[i][0] for i in ex_i])
print("exemplos", len(ex_i), collections.Counter(Y).most_common())

res = {}
B = 2048
allv = {}
for a in range(0, N, B):
    idx = list(range(a, min(N, a + B)))
    roots = [(top[i] or fixed[i] or "C")[0] for i in idx]
    P = np.stack([patch(i, r) for i, r in zip(idx, roots)])
    S = P @ X.T
    for k, i in enumerate(idx):
        if np.abs(P[k]).sum() < 1e-3: res[i] = ("", 1.0); continue
        s = S[k]
        nn = np.argpartition(-s, 8)[:8]
        nn = [j for j in nn if ex_i[j] != i]
        c = collections.Counter()
        for j in nn: c[Y[j]] += s[j]
        lab, sc = c.most_common(1)[0]
        tot = float(sum(c.values())); res[i] = (str(lab), round(float(sc) / tot, 3) if tot > 0 else 0.0)
json.dump({str(k): v for k, v in res.items()}, open("tk/slot.json", "w"))
# acerto nos próprios exemplos (deixando o próprio de fora)
ok = sum(1 for i, y in zip(ex_i, Y) if res[i][0] == y)
print("acerto nos exemplos", ok / len(ex_i))
cm = collections.Counter((y, res[i][0]) for i, y in zip(ex_i, Y) if res[i][0] != y)
print(cm.most_common(20))

# ---- letra do acorde (A..G) ----
def rpatch(i):
    p = head[i][:, :46]
    p = np.asarray(Image.fromarray(p).resize((24, 24), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.6)), np.float32)
    v = p.ravel() - p.mean(); return v / (np.linalg.norm(v) + 1e-6)
rex = [i for i in agree]
RX = np.stack([rpatch(i) for i in rex]); RY = np.array([top[i][0] for i in rex])
rres = {}
for a in range(0, N, B):
    idx = list(range(a, min(N, a + B)))
    P = np.stack([rpatch(i) for i in idx]); S = P @ RX.T
    for k, i in enumerate(idx):
        s = S[k]; nn = [j for j in np.argpartition(-s, 9)[:9] if rex[j] != i][:8]
        c = collections.Counter()
        for j in nn: c[RY[j]] += s[j]
        lab, sc = c.most_common(1)[0]; tot = float(sum(c.values()))
        rres[i] = (str(lab), round(float(sc) / tot, 3) if tot > 0 else 0.0, round(float(s[nn[0]]), 3))
json.dump({str(k): v for k, v in rres.items()}, open("tk/root.json", "w"))
ok = sum(1 for i in rex if rres[i][0] == top[i][0]); print("letra: acerto nos exemplos", ok / len(rex))

# ---- símbolo do começo da extensão (depois de 'm', '#' ou 'b') ----
PRE = re.compile(r"^([A-G])([#b]?)(m?)(.?)")
def pre_of(lab):
    m = PRE.match(lab); r, a, q, c = m.groups()
    if not (a or q): return None, None
    if c == "0": c = "o"
    return r + a + q, c
wpre = {}
for i in agree:
    p, c = pre_of(top[i])
    if p and c == "" and h[i] > 20: wpre.setdefault(p, []).append(w[i] / h[i])
wpre = {k: float(np.median(v)) for k, v in wpre.items() if len(v) >= 3}
def pwidth(p):
    if p in wpre: return wpre[p]
    r = p[0]; extra = (0.33 if any(x in p[1:] for x in "#b") else 0) + (0.85 if p.endswith("m") else 0)
    return kl[r] + extra
def epatch(i, p):
    x0 = int(round(pwidth(p) * 48)) - 4
    q = head[i][:30, max(0, x0):x0 + 30].astype(np.float32)
    if q.shape[1] < 30: q = np.pad(q, ((0, 0), (0, 30 - q.shape[1])))
    q = np.asarray(Image.fromarray(q.astype(np.uint8)).resize((20, 20), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.6)), np.float32)
    v = q.ravel() - q.mean(); n = np.linalg.norm(v)
    return v / n if n > 1e-3 else v * 0
eex = [(i,) + pre_of(top[i]) for i in agree]
eex = [(i, p, c) for i, p, c in eex if p and c is not None and (c in "#b/(+os" or c.isdigit() or c == "")]
EX = np.stack([epatch(i, p) for i, p, c in eex]); EY = np.array([c for _, _, c in eex])
print("exemplos extensão", len(eex), collections.Counter(EY).most_common())
json.dump({"wpre": wpre, "kl": kl}, open("tk/widths.json", "w"))
np.savez_compressed("tk/ext_ex.npz", EX=EX, EY=EY, EI=np.array([i for i, _, _ in eex]))
