"""Desenha um acorde no mesmo estilo da coletânea (Helvetica negrito, sustenido/bemol/extensão em sobrescrito)."""
import re, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
BIG = 64
SUP = 0.62
F1 = ImageFont.truetype(FONT, BIG)
F2 = ImageFont.truetype(FONT, int(BIG * SUP))
H, WMAX = 32, 160
PAT = re.compile(r"^([A-G])([#b]?)(m?)([^/]*)(?:/([A-G])([#b]?))?$")

def pieces(ch):
    m = PAT.match(ch)
    if not m: return None
    r, a, q, ext, b, ba = m.groups()
    ps = [(r, 0)]
    if a: ps.append((a, 1))
    if q: ps.append((q, 0))
    if ext:
        ext = ext.replace("0", "o")
        ps.append((ext, 1))
    if b:
        ps.append(("/", 0)); ps.append((b, 0))
        if ba: ps.append((ba, 1))
    return ps

def render(ch):
    ps = pieces(ch)
    if ps is None: return None
    canvas = Image.new("L", (BIG * 10, BIG * 2), 0); dr = ImageDraw.Draw(canvas)
    x = 4; base_top = 20
    cap_top = F1.getbbox("H")[1]
    sup_top = F2.getbbox("7")[1]
    for t, sup in ps:
        if sup:
            dr.text((x, base_top + cap_top - sup_top), t, font=F2, fill=255)
            x += F2.getlength(t) - 1
        else:
            dr.text((x, base_top), t, font=F1, fill=255)
            x += F1.getlength(t) - 2
    from PIL import ImageFilter
    canvas = canvas.filter(ImageFilter.MaxFilter(3))
    a = np.asarray(canvas) > 100
    ys, xs = np.where(a)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = a.shape
    nw = min(WMAX, max(1, int(round(w * H / h))))
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((nw, H), Image.BILINEAR)
    out = np.zeros((H, WMAX), np.uint8); out[:, :nw] = np.asarray(im)
    return out

FW, FH = 96, 24
def feat_img(a, w_px):
    """a: imagem 32x160 com a tinta à esquerda; w_px: largura útil. Devolve vetor normalizado de tamanho fixo + aspecto."""
    w = max(1, min(WMAX, int(w_px)))
    im = Image.fromarray(a[:, :w]).resize((FW, FH), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.0))
    v = np.asarray(im, np.float32).ravel(); v = v - v.mean(); v /= (np.linalg.norm(v) + 1e-6)
    return v, w / H

def width_of(a):
    cols = np.where(a.max(0) > 60)[0]
    return (cols.max() + 1) if len(cols) else 1
