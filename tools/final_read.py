"""Leitura final de cada acorde.
O melhor candidato desenhado precisa respeitar três verificações feitas com exemplos reais do livro:
letra do acorde, símbolo logo depois da letra (#, b, m, 7, /...) e começo da extensão (depois de m/#/b)."""
import numpy as np, glob, json, re, sys, collections
from PIL import Image, ImageFilter
import synth

src = open("synth_rerank.py").read().split("R = json.load")[0]
rr = {}; exec(src, rr)

PAT = synth.PAT
d = np.load("tk/fixed.npz"); meta = d["meta"]; fixed = d["fixed"]
imgs = np.concatenate([np.load(x)["imgs"] for x in sorted(glob.glob("tk/w*/t.npz"))])
head = np.concatenate([np.load(f)["imgs"] for f in sorted(glob.glob("hd/w*/t.npz"))])
RR = json.load(open("tk/rr_all.json"))
slot = json.load(open("tk/slot.json")); root = json.load(open("tk/root.json"))
W = json.load(open("tk/widths.json")); wpre, kl = W["wpre"], W["kl"]
E = np.load("tk/ext_ex.npz"); EX, EY, EI = E["EX"], E["EY"], E["EI"]
N = len(meta)

def first_after_root(s):
    m = re.match(r"^[A-G](.?)", s); c = m.group(1)
    return "o" if c == "0" else c

PRE = re.compile(r"^([A-G])([#b]?)(m?)(.?)")
def pre_of(s):
    r, a, q, c = PRE.match(s).groups()
    if not (a or q): return None, None
    return r + a + q, ("o" if c == "0" else c)

def pwidth(p):
    if p in wpre: return wpre[p]
    return kl[p[0]] + (0.33 if any(x in p[1:] for x in "#b") else 0) + (0.85 if p.endswith("m") else 0)

ecache = {}
def ext_cls(i, p):
    if (i, p) in ecache: return ecache[(i, p)]
    x0 = int(round(pwidth(p) * 48)) - 4
    q = head[i][:30, max(0, x0):x0 + 30].astype(np.float32)
    if q.shape[1] < 30: q = np.pad(q, ((0, 0), (0, 30 - q.shape[1])))
    q = np.asarray(Image.fromarray(q.astype(np.uint8)).resize((20, 20), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.6)), np.float32)
    v = q.ravel() - q.mean(); n = np.linalg.norm(v)
    if n < 1e-3: r = ("", 1.0)
    else:
        v /= n; s = EX @ v
        nn = [j for j in np.argsort(-s)[:9] if EI[j] != i][:8]
        c = collections.Counter()
        for j in nn: c[EY[j]] += s[j]
        lab, sc = c.most_common(1)[0]
        r = (str(lab), float(sc) / float(sum(c.values())))
    ecache[(i, p)] = r
    return r

EXT = ["", "7", "7M", "9", "6", "4", "2", "sus4", "0", "07", "7(9)", "(9)", "+", "7(4)", "7(b9)", "6(9)", "7(b13)", "(b13)", "(#5)", "7(#5)", "5+", "11", "13", "7sus4", "(sus4)", "7M(9)", "7(11)", "9(11)"]
def pool(c, roots):
    out = set(s for s, _ in c)
    for s, _ in c[:2]:
        m = PAT.match(s)
        if not m: continue
        r, a, q, e, b, ba = m.groups(); b = b or ""; ba = ba or ""
        for r2 in roots | {r}:
            for a2 in ("", "#", "b"):
                for q2 in ("", "m"):
                    for e2 in EXT:
                        if q2 == "m" and e2 in ("0", "07"): continue
                        for ba2 in (("", "#", "b") if b else ("",)):
                            out.add(r2 + a2 + q2 + e2 + ("/" + b + ba2 if b else ""))
    return out

def fine_score(img, tw, tv, s):
    x = rr["rend"](s)
    if x is None: return -9
    r, cw = x
    rim = np.asarray(Image.fromarray(r[:, :cw]).resize((tw, 32), Image.BILINEAR))
    out = np.zeros((32, 160), np.uint8); out[:, :tw] = rim
    return float(rr["fine"](out, tw) @ tv) - 0.35 * abs(np.log(cw / tw))

a0, a1 = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (0, len(RR))
final = []; stats = collections.Counter()
for x in RR[a0:a1]:
    i = x["i"]
    c = [(s, sc) for sc, s in x["c"]]
    if not c: final.append((str(fixed[i]), 0.0, "vazio")); continue
    s0, sc0 = c[0]
    if sc0 < 0.45: final.append((str(fixed[i]), sc0, "fraco")); stats["fraco"] += 1; continue
    rl, rc, _ = root[str(i)]; sl, scf = slot[str(i)]
    need_root = rl if rc >= 0.8 else None
    need_slot = sl if scf >= 0.75 else None
    fb = re.search(r"/([A-G])", str(fixed[i])); need_bass = fb.group(1) if fb else None
    def ok(s, use_ext=False):
        if need_root and s[0] != need_root: return False
        if need_slot is not None and first_after_root(s) != need_slot: return False
        if re.match(r"^[A-G][#b]?m0", s): return False
        if re.search(r"^(Fb|Cb|E#|B#)|/(Fb|Cb|E#|B#)$", s): return False
        if need_bass and "/" in s and s.split("/")[1][0] != need_bass: return False
        if use_ext:
            p, e = pre_of(s)
            if p:
                el, ec = ext_cls(i, p)
                if ec >= 0.75 and e != el: return False
        return True
    if ok(s0):
        final.append((s0, sc0, "ok")); stats["ok"] += 1; continue
    img, _ = rr["clean"](imgs[i]); tw = synth.width_of(img); tv = rr["fine"](img, tw)
    P = pool(c, {need_root} if need_root else set())
    scored = sorted(((fine_score(img, tw, tv, s), s) for s in P), reverse=True)
    pick = next(((sc, s) for sc, s in scored if ok(s)), None)
    tag = "ajustado"
    if pick is None:
        pick = next(((sc, s) for sc, s in scored if ok(s, False)), None); tag = "ajustado-sem-ext"
    if pick is None:
        final.append((s0, sc0, "conflito")); stats["conflito"] += 1
    elif pick[0] < sc0 - 0.12:
        final.append((pick[1], pick[0], "forte")); stats["forte"] += 1
    else:
        final.append((pick[1], pick[0], tag)); stats[tag] += 1
json.dump(final, open(f"tk/fr_{a0}.json", "w"))
print(a0, dict(stats))
