"""Recortes altos demais (duas linhas de acordes juntas): separa por linha e depois por acorde."""
import json, os, subprocess, numpy as np
from PIL import Image
from scipy import ndimage
import tokens_extract as te

meta = np.load("tk/vote.npz")["meta"]
h = meta[:, 4] - meta[:, 2]
tall = [i for i in range(len(meta)) if h[i] > 44]
bypg = {}
for i in tall: bypg.setdefault(int(meta[i][0]), []).append(i)
out_meta, out_img, out_par = [], [], []
for pg, ids in sorted(bypg.items()):
    base = f"tk/orf/m{pg}"
    if not os.path.exists(base + ".png"):
        subprocess.run(["pdftoppm", "-r", "300", "-f", str(pg), "-l", str(pg), "-png", "-singlefile", te.PDF, base], check=True)
    m = te.red_mask(base + ".png")
    for i in ids:
        _, x0, y0, x1, y1 = [int(v) for v in meta[i]]
        sub = m[y0:y1, x0:x1]
        lab, n = ndimage.label(sub)
        comps = []
        for k, o in enumerate(ndimage.find_objects(lab), 1):
            if o is None or (lab[o] == k).sum() < 6: continue
            hh = o[0].stop - o[0].start; ww = o[1].stop - o[1].start
            if ww <= 9 and hh >= 10 and hh / max(1, ww) >= 2.5: continue      # '|' (inteiro ou pedaço)
            comps.append((o[0].start, o[0].stop, o[1].start, o[1].stop))
        if not comps: continue
        # faixas de texto (linhas) pela projeção vertical
        prof = np.zeros(sub.shape[0], bool)
        for c in comps: prof[c[0]:c[1]] = True
        bands = []; yy = 0
        while yy < len(prof):
            if prof[yy]:
                st = yy
                while yy < len(prof) and prof[yy]: yy += 1
                if bands and st - bands[-1][1] < 3: bands[-1][1] = yy
                else: bands.append([st, yy])
            else: yy += 1
        bands = [b for b in bands if b[1] - b[0] >= 15] or [[min(c[0] for c in comps), max(c[1] for c in comps)]]
        rows = [[c for c in comps if b[0] <= (c[0] + c[1]) / 2 <= b[1]] for b in bands]
        for rw in rows:
            if not rw: continue
            groups = []
            for c in sorted(rw, key=lambda c: c[2]):
                if groups and c[2] - groups[-1][3] <= 7:
                    G = groups[-1]; G[0], G[1], G[3] = min(G[0], c[0]), max(G[1], c[1]), max(G[3], c[3])
                else: groups.append([c[0], c[1], c[2], c[3]])
            for a0, a1, b0, b1 in groups:
                if a1 - a0 < 12: continue
                box = (pg, x0 + b0, y0 + a0, x0 + b1, y0 + a1)
                out_meta.append(box); out_img.append(te.token_img(sub[a0:a1, b0:b1])); out_par.append(i)
np.savez_compressed("tk/extra.npz", meta=np.array(out_meta, np.int32), imgs=np.stack(out_img), par=np.array(out_par))
print("altos", len(tall), "novos recortes", len(out_meta))
