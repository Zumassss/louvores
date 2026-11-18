"""Monta as cifras da coletânea escaneada: OCR da letra (preto) + acordes e '|' (vermelho).

Uso: python3 scan_build.py arquivo.pdf pag_ini pag_fim saida.jsonl
Cada linha da saída: {"page", "rows": [...]} com as linhas da página em ordem de leitura.
"""
import os, re, sys, json
import numpy as np
import scan_ocr as so
import scan_chords as sch

def group_rows(words, tol):
    rows = []
    for w in sorted(words, key=lambda w: ((w["y0"] + w["y1"]) / 2, w["x0"])):
        cy = (w["y0"] + w["y1"]) / 2
        if rows and abs(rows[-1]["cy"] - cy) < tol:
            rows[-1]["w"].append(w); rows[-1]["cy"] = (rows[-1]["cy"] * (len(rows[-1]["w"]) - 1) + cy) / len(rows[-1]["w"])
        else: rows.append({"cy": cy, "w": [w]})
    for r in rows: r["w"].sort(key=lambda w: w["x0"])
    return rows

def process_page(pdf, page, tmp):
    png = so.page_image(pdf, page, tmp)
    red_img, blk_img, W, H = so.layers(png)
    chords, pipes, _, _ = sch.page_chords(png, tmp)
    out = []
    # divisão entre as colunas: a faixa vertical com menos tinta perto do meio
    ink = ((blk_img == 0) | (red_img == 0)).sum(axis=0)
    a, b = int(W * 0.38), int(W * 0.62)
    win = 15
    sm = np.convolve(ink, np.ones(win), "same")
    mid = a + int(np.argmin(sm[a:b]))
    for ci, (x0c, x1c) in enumerate(((0, mid), (mid, W))):
        bw = so.tess(blk_img[:, x0c:x1c], 4, "por", None, tmp)
        words = [{"t": t, "x0": x + x0c, "y0": y, "x1": x + x0c + w, "y1": y + h, "conf": c} for t, x, y, w, h, c, _ in bw]
        words = [w for w in words if not re.fullmatch(r"[|Il!\[\]¡]", w["t"])]   # restos de '|' preto (colchete de bis)
        col_ch = [c for c in chords if x0c <= c["x0"] < x1c]
        col_pp = [p for p in pipes if x0c <= p[0] < x1c]
        rows = group_rows(words, 18)
        used_ch = set()
        # '|' -> acorde logo acima
        pipe_ch = []
        for p in col_pp:
            px0, py0, px1, py1 = p
            cand = [i for i, c in enumerate(col_ch) if i not in used_ch and 0 <= py0 - c["y1"] <= 40 and abs(c["x0"] - px0) <= 30]
            if not cand: continue
            i = min(cand, key=lambda i: (py0 - col_ch[i]["y1"]) + abs(col_ch[i]["x0"] - px0))
            used_ch.add(i)
            pipe_ch.append({"x": (px0 + px1) / 2, "y0": py0, "y1": py1, "t": col_ch[i]["t"]})
        items = []
        for r in rows:
            ry0 = min(w["y0"] for w in r["w"]); ry1 = max(w["y1"] for w in r["w"])
            text = " ".join(w["t"] for w in r["w"])
            # acordes desta linha de letra (pelos '|' que tocam a linha)
            mine = [pc for pc in pipe_ch if pc["y1"] >= ry0 - 6 and pc["y0"] <= ry1 and not pc.get("used")]
            for pc in mine: pc["used"] = True
            # acordes na mesma altura do texto (Introdução: D, G...)
            inline = [i for i, c in enumerate(col_ch) if i not in used_ch and c["y0"] < ry1 and c["y1"] > ry0]
            for i in inline: used_ch.add(i)
            items.append({"y": ry0, "y1": ry1, "chy": min([pc["y0"] for pc in mine], default=None), "words": [(w["t"], w["x0"], w["x1"]) for w in r["w"]], "text": text,
                          "chords": [(pc["x"], pc["t"]) for pc in sorted(mine, key=lambda p: p["x"])],
                          "inline": [(col_ch[i]["x0"], col_ch[i]["t"]) for i in sorted(inline, key=lambda i: col_ch[i]["x0"])]})
        # acordes que sobraram (linhas só de acordes)
        rest = [c for i, c in enumerate(col_ch) if i not in used_ch]
        for r in group_rows([dict(c) for c in rest], 14):
            items.append({"y": min(c["y0"] for c in r["w"]), "words": [], "text": "", "chords": [],
                          "inline": [(c["x0"], c["t"]) for c in r["w"]]})
        # '|' que sobraram sem letra: o acorde vai como linha só de acordes
        for pc in pipe_ch:
            if not pc.get("used"):
                items.append({"y": pc["y0"], "words": [], "text": "", "chords": [], "inline": [(pc["x"], pc["t"])]})
        items.sort(key=lambda it: it["y"])
        for it in items: it["col"] = ci
        out += items
    return {"page": page, "W": W, "H": H, "rows": out}

def lyric_with_chords(it):
    """Texto da linha com [acorde] antes da palavra que começa logo depois de cada '|'."""
    ws = it["words"]
    text, starts = "", []
    for i, (t, x0, x1) in enumerate(ws):
        if i: text += " "
        starts.append((len(text), x0, x1, t)); text += t
    ins = []
    for x, ch in it["chords"]:
        pos = None
        for st, x0, x1, t in starts:
            if x0 >= x - 6: pos = st; break
            if x0 < x < x1:   # o '|' caiu dentro da palavra (OCR não separou): posição proporcional
                k = int(round((x - x0) / max(1, (x1 - x0)) * len(t)))
                pos = st + max(0, min(len(t), k)); break
        if pos is None: pos = len(text)
        ins.append((pos, ch))
    out, last = "", 0
    for pos, ch in sorted(ins, key=lambda a: a[0]):
        out += text[last:pos] + "[" + ch + "]"; last = pos
    return out + text[last:]

if __name__ == "__main__":
    pdf, a, b, outp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    tmp = os.path.join(os.path.dirname(outp) or ".", "img"); os.makedirs(tmp, exist_ok=True)
    with open(outp, "a") as f:
        for pg in range(a, b + 1):
            try:
                r = process_page(pdf, pg, tmp)
            except Exception as e:
                r = {"page": pg, "error": str(e), "rows": []}
            f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
            png = os.path.join(tmp, f"p{pg:04d}.png")
            if os.path.exists(png): os.remove(png)
