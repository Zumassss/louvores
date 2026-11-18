"""Segunda passada: tira vírgula/ponto do recorte e decide entre os melhores candidatos comparando em resolução maior."""
import numpy as np, glob, json, re, sys
from PIL import Image, ImageFilter
from scipy import ndimage
import synth

PAT = synth.PAT
H, WMAX = 32, 160

def clean(img):
    m = img > 80
    lab, n = ndimage.label(m)
    if n > 1:
        objs = ndimage.find_objects(lab)
        xs = np.where(m.any(0))[0]; wtot = xs.max() + 1
        for k, o in enumerate(objs, 1):
            y0, y1 = o[0].start, o[0].stop; x0, x1 = o[1].start, o[1].stop
            if y0 >= 0.55 * H and x0 >= 0.5 * wtot and (y1 - y0) <= 0.5 * H and (x1 - x0) <= 0.25 * H:
                m[lab == k] = False
    ys, xs = np.where(m)
    if not len(ys): return img, False
    if ys.min() == 0 and ys.max() == H - 1: return img, False
    a = img[ys.min():ys.max() + 1, :xs.max() + 1].copy(); a[~m[ys.min():ys.max() + 1, :xs.max() + 1]] = 0
    h, w = a.shape
    nw = min(WMAX, max(1, int(round(w * H / h))))
    out = np.zeros((H, WMAX), np.uint8); out[:, :nw] = np.asarray(Image.fromarray(a).resize((nw, H), Image.BILINEAR))
    return out, True

def fine(a, w):
    im = Image.fromarray(a[:, :max(1, w)]).resize((max(8, w), H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.7))
    v = np.asarray(im, np.float32).ravel(); v = v - v.mean(); return v / (np.linalg.norm(v) + 1e-6)

def variants(s):
    m = PAT.match(s)
    if not m: return []
    r, a, q, e, b, ba = m.groups(); e = e or ""; b = b or ""; ba = ba or ""
    out = []
    for a2 in ("", "#", "b"):
        for ba2 in (("", "#", "b") if b else ("",)):
            out.append(r + a2 + q + e + ("/" + b + ba2 if b else ""))
    for e2 in ("", "0", "07", "6", "9", "7", "7M", "sus4", "+", "7(9)", "(9)", "2", "4"):
        out.append(r + a + q + e2 + ("/" + b + ba if b else ""))
    return out

cache = {}
def rend(s):
    if s not in cache:
        r = synth.render(s); cache[s] = (r, synth.width_of(r)) if r is not None else None
    return cache[s]

R = json.load(open("tk/syn_all.json"))
imgs = np.concatenate([np.load(x)["imgs"] for x in sorted(glob.glob("tk/w*/t.npz"))])
a0, a1 = int(sys.argv[1]), int(sys.argv[2])
res = []
for x in R[a0:a1]:
    i = x["i"]
    img, cleaned = clean(imgs[i])
    tw = synth.width_of(img)
    tv = fine(img, tw)
    top = x["r"][0][1]
    cands = [s for s, sc in x["r"] if sc >= top - 0.06] + [s for s, sc in x["g"] if sc >= top - 0.03]
    for s in list(cands[:3]): cands += variants(s)
    seen, scored = set(), []
    for s in cands:
        if s in seen: continue
        seen.add(s)
        rr = rend(s)
        if rr is None: continue
        r, cw = rr
        rim = np.asarray(Image.fromarray(r[:, :cw]).resize((tw, H), Image.BILINEAR))
        out = np.zeros((H, WMAX), np.uint8); out[:, :tw] = rim
        sc = float(fine(out, tw) @ tv) - 0.35 * abs(np.log(cw / tw))
        scored.append((round(sc, 4), s))
    scored.sort(reverse=True)
    res.append({"i": i, "c": scored[:5], "cl": cleaned})
json.dump(res, open(f"tk/rr_{a0}.json", "w"))
print("ok", a0, len(res))
