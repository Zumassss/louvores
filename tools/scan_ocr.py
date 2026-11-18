"""OCR da coletânea escaneada: separa acordes (vermelho) da letra (preto) e reconhece cada camada.

Uso: python3 scan_ocr.py arquivo.pdf pagina saida_prefixo
Gera <prefixo>.json com palavras {t, x0, y0, x1, y1, red} em pontos (1/72 pol).
"""
import sys, json, subprocess, os
import numpy as np
from PIL import Image

def page_image(pdf, page, outdir):
    base = os.path.join(outdir, f"p{page:04d}")
    if not os.path.exists(base + ".png"):
        subprocess.run(["pdftoppm", "-r", "300", "-f", str(page), "-l", str(page), "-png", "-singlefile", pdf, base], check=True)
    return base + ".png"

def layers(png):
    im = np.asarray(Image.open(png).convert("RGB")).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    red = (r > 120) & (r - g > 60) & (r - b > 50)
    dark = (r + g + b < 330) & ~red
    H, W = red.shape
    red_img = np.full((H, W), 255, np.uint8); red_img[red] = 0
    blk_img = np.full((H, W), 255, np.uint8); blk_img[dark] = 0
    return red_img, blk_img, W, H

def tess(img_arr, psm, lang, whitelist=None, tmp="/tmp"):
    path = os.path.join(tmp, f"tess_{os.getpid()}.png")
    Image.fromarray(img_arr).save(path)
    cmd = ["tesseract", path, "stdout", "--psm", str(psm), "-l", lang, "tsv"]
    if whitelist: cmd[5:5] = ["-c", "tessedit_char_whitelist=" + whitelist]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    words = []
    for line in out.splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 12 or not f[11].strip(): continue
        words.append((f[11], int(f[6]), int(f[7]), int(f[8]), int(f[9]), float(f[10]), (int(f[2]), int(f[3]), int(f[4]))))
    return words

def ocr_page(pdf, page, outdir):
    png = page_image(pdf, page, outdir)
    red_img, blk_img, W, H = layers(png)
    sc = 72.0 / 300.0
    res = []
    # duas colunas: reconhece cada metade separado (o layout é em 2 colunas)
    mid = W // 2
    for x0c, x1c in ((0, mid), (mid, W)):
        for img, red in ((red_img[:, x0c:x1c], True), (blk_img[:, x0c:x1c], False)):
            if red:
                ws = tess(img, 11, "eng", "ABCDEFGmajsudi#b0123456789/()+º°Ø-:,.", outdir)
            else:
                ws = tess(img, 4, "por", None, outdir)
            for t, x, y, w, h, conf, blk in ws:
                res.append({"t": t, "x0": (x + x0c) * sc, "y0": y * sc, "x1": (x + x0c + w) * sc, "y1": (y + h) * sc,
                            "red": red, "conf": conf, "col": 0 if x0c == 0 else 1})
    return {"W": W * sc, "H": H * sc, "words": res}

if __name__ == "__main__":
    r = ocr_page(sys.argv[1], int(sys.argv[2]), os.path.dirname(sys.argv[3]) or ".")
    json.dump(r, open(sys.argv[3] + ".json", "w"), ensure_ascii=False)
    for w in sorted(r["words"], key=lambda w: (w["col"], round(w["y0"] / 4), w["x0"]))[:120]:
        print(w["col"], "R" if w["red"] else " ", round(w["x0"]), round(w["y0"]), w["t"])
