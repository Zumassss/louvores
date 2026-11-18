"""Recorta cada acorde inteiro (vermelho) de páginas da coletânea escaneada.

Uso: python3 tokens_extract.py pag_ini pag_fim saida.npz
Para cada acorde: página, caixa (x0,y0,x1,y1 a 300dpi) e imagem com altura 32 (largura até 160, alinhada à esquerda).
Também guarda os '|' vermelhos (página, x0,y0,x1,y1).
"""
import sys, os, subprocess
import numpy as np
from PIL import Image
from scipy import ndimage

PDF = "novas/nivel2.pdf"
H, WMAX = 32, 160

def red_mask(png):
    im = np.asarray(Image.open(png).convert("RGB")).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    return (r > 120) & (r - g > 60) & (r - b > 50)

def token_img(mask):
    h, w = mask.shape
    sc = H / max(1, h)
    nw = min(WMAX, max(1, int(round(w * sc))))
    im = Image.fromarray((mask * 255).astype(np.uint8)).resize((nw, H), Image.BILINEAR)
    out = np.zeros((H, WMAX), np.uint8); out[:, :nw] = np.asarray(im)
    return out

HH, HW = 48, 88
def head_img(mask):
    """começo do acorde (até 1,8x a altura), altura 48"""
    h, w = mask.shape
    cw = min(w, int(1.8 * h))
    sc = HH / h
    nw = min(HW, max(1, int(round(cw * sc))))
    im = Image.fromarray((mask[:, :cw] * 255).astype(np.uint8)).resize((nw, HH), Image.BILINEAR)
    out = np.zeros((HH, HW), np.uint8); out[:, :nw] = np.asarray(im)
    return out

def page_tokens(pg, tmp):
    base = os.path.join(tmp, f"t{pg:04d}")
    subprocess.run(["pdftoppm", "-r", "300", "-f", str(pg), "-l", str(pg), "-png", "-singlefile", PDF, base], check=True)
    m = red_mask(base + ".png"); os.remove(base + ".png")
    lab, n = ndimage.label(m)
    objs = ndimage.find_objects(lab)
    pipes, comps = [], []
    for i, o in enumerate(objs, start=1):
        if o is None: continue
        h = o[0].stop - o[0].start; w = o[1].stop - o[1].start
        if (lab[o] == i).sum() < 6: continue
        if w <= 9 and h >= 28 and h / max(1, w) >= 4: pipes.append((pg, o[1].start, o[0].start, o[1].stop, o[0].stop)); continue
        if h > 120 or w > 260: continue
        comps.append((o[0].start, o[0].stop, o[1].start, o[1].stop))
    groups = []
    for c in sorted(comps, key=lambda c: c[2]):
        cy = (c[0] + c[1]) / 2; placed = False
        for G in groups:
            gy0, gy1, gx0, gx1 = G
            if gy0 - 12 <= cy <= gy1 + 12 and c[2] - gx1 <= 7 and c[2] >= gx0 - 2:
                G[0], G[1], G[2], G[3] = min(gy0, c[0]), max(gy1, c[1]), min(gx0, c[2]), max(gx1, c[3]); placed = True; break
        if not placed: groups.append([c[0], c[1], c[2], c[3]])
    toks = []
    for y0, y1, x0, x1 in groups:
        if y1 - y0 < 12: continue
        toks.append(((pg, x0, y0, x1, y1), head_img(m[y0:y1, x0:x1])))
    return toks, pipes

if __name__ == "__main__":
    a, b, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    tmp = os.path.dirname(out) or "."
    T, P = [], []
    for pg in range(a, b + 1):
        try:
            t, p = page_tokens(pg, tmp); T += t; P += p
        except Exception as e:
            print("erro", pg, e, flush=True)
    np.savez_compressed(out, meta=np.array([t[0] for t in T], np.int32), imgs=np.stack([t[1] for t in T]), pipes=np.array(P, np.int32))
    print("acordes", len(T), "traços", len(P))
