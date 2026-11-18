"""Acordes da coletânea escaneada: componentes vermelhos -> traços '|' (posição) + acordes (texto)."""
import os, re, subprocess, json, sys
import numpy as np
from PIL import Image
from scipy import ndimage
import scan_ocr as so

CHORD = re.compile(r"^[A-G](#|b)?(maj|m|M|dim|aug|sus|add|º|ø|\+)?[0-9]*(\([^)\s]{1,10}\))?(maj|sus|add|m)?[0-9]*(/[A-G](#|b)?)?$")

def tess_token(img, tmp, psm=7):
    path = os.path.join(tmp, f"tok_{os.getpid()}.png")
    Image.fromarray(img).save(path)
    out = subprocess.run(["tesseract", path, "stdout", "--psm", str(psm), "-l", "eng", "-c",
                          "tessedit_char_whitelist=ABCDEFGmajsudi#b0123456789/()+-º"], capture_output=True, text=True).stdout
    return out.strip().replace(" ", "")

def tess_best(img, tmp, single=False):
    """Tenta alguns modos do Tesseract e fica com a primeira leitura que pareça acorde/pedaço válido."""
    tries = (10, 8, 7) if single else (7, 8, 13)
    first = ""
    for psm in tries:
        t = tess_token(img, tmp, psm)
        if not first: first = t
        if t and (CHORD.match(fix(t)) or re.fullmatch(r"[0-9#b()susadjm+º/]+", t)): return t
    return first

def read_chord(mask, box, tmp):
    """Lê um acorde. Partes pequenas e altas (expoente: 7, b, #, sus4) são lidas à parte."""
    y0, y1, x0, x1 = box
    sub = mask[y0:y1, x0:x1]
    lab, n = ndimage.label(sub)
    objs = ndimage.find_objects(lab)
    if not objs: return ""
    hs = [o[0].stop - o[0].start for o in objs]
    big = max(hs)
    base_bottom = max(o[0].stop for o, h in zip(objs, hs) if h >= big * 0.75)
    main = np.zeros_like(sub); sup = np.zeros_like(sub)
    for i, (o, h) in enumerate(zip(objs, hs), start=1):
        small_high = h < big * 0.75 and o[0].stop < base_bottom - big * 0.25
        (sup if small_high else main)[lab == i] = 1
    def ocr(m):
        if not m.any(): return ""
        ys, xs = np.nonzero(m)
        crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        scale = max(1, int(60 / max(1, crop.shape[0])))
        img = np.pad((1 - crop) * 255, 12, constant_values=255).astype(np.uint8)
        img = np.asarray(Image.fromarray(img).resize((img.shape[1] * scale, img.shape[0] * scale), Image.NEAREST))
        return tess_best(img, tmp, single=crop.shape[1] < crop.shape[0] * 1.15)
    m = ocr(main); s = ocr(sup)
    # expoente: b/# logo depois da nota viram acidente; números/sus/add viram extensão
    if s:
        s = s.replace("-", "")
        if s[:1] in ("b", "#") and len(m) >= 1 and not re.match(r"^[A-G][#b]", m):
            m = m[0] + s[0] + m[1:]; s = s[1:]
        if s:
            if "/" in m: a, bb = m.split("/", 1); m = a + s + "/" + bb
            else: m = m + s
    return fix(m)

def fix(t):
    t = t.replace("-", "")
    if not t: return t
    first = {"8": "B", "0": "D", "O": "D", "6": "G", "3": "B", "a": "A", "d": "D", "b": "B"}.get(t[0], t[0])
    t = first + t[1:]
    t = re.sub(r"^([A-G])8", r"\1b", t)
    t = re.sub(r"/8", "/B", t); t = re.sub(r"/0", "/D", t); t = re.sub(r"/6", "/G", t)
    t = t.replace("CCuus", "C#sus").replace("uus", "sus")
    t = re.sub(r"sus4\d+", "sus4", t)
    if not CHORD.match(t):
        t2 = re.sub(r"^([A-G])[asg](?=$|m|[0-9]|/|sus)", r"\1#", t)     # '#' lido como a/s/g
        t2 = re.sub(r"^([A-G])i?b", r"\1b", t2)
        if CHORD.match(t2): t = t2
    return t

def components(mask):
    lab, n = ndimage.label(mask)
    objs = ndimage.find_objects(lab)
    return lab, objs

def page_chords(png, tmp):
    red_img, blk_img, W, H = so.layers(png)
    mask = (red_img == 0).astype(np.uint8)
    lab, objs = components(mask)
    pipes, glyphs = [], []
    for i, o in enumerate(objs, start=1):
        h = o[0].stop - o[0].start; w = o[1].stop - o[1].start
        if (lab[o] == i).sum() < 6: continue
        if w <= 9 and h >= 28 and h / max(1, w) >= 4: pipes.append((o[1].start, o[0].start, o[1].stop, o[0].stop))
        else: glyphs.append((o[0].start, o[0].stop, o[1].start, o[1].stop))
    # agrupa glifos em acordes (mesma linha, perto na horizontal)
    glyphs.sort(key=lambda g: (g[0], g[2]))
    groups = []
    for g in sorted(glyphs, key=lambda g: g[2]):
        placed = False
        for G in groups:
            gy0, gy1, gx0, gx1 = G["box"]
            cy = (g[0] + g[1]) / 2
            if gy0 - 12 <= cy <= gy1 + 12 and g[2] - gx1 <= 7 and g[2] >= gx0 - 2:
                G["box"] = (min(gy0, g[0]), max(gy1, g[1]), min(gx0, g[2]), max(gx1, g[3])); placed = True; break
        if not placed: groups.append({"box": g})
    chords = []
    for G in groups:
        y0, y1, x0, x1 = G["box"]
        if (y1 - y0) < 12: continue
        t = read_chord(mask, (y0, y1, x0, x1), tmp)
        chords.append({"t": t, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return chords, pipes, W, H

if __name__ == "__main__":
    ch, pp, W, H = page_chords(sys.argv[1], os.path.dirname(sys.argv[1]))
    for c in sorted(ch, key=lambda c: (c["x0"] > W / 2, c["y0"], c["x0"]))[:60]:
        print(c["x0"] > W / 2, c["y0"], c["x0"], repr(c["t"]), "OK" if CHORD.match(c["t"]) else "??")
    print("pipes", len(pp), "chords", len(ch), "válidos", sum(1 for c in ch if CHORD.match(c["t"])))
