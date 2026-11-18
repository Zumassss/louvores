"""Separa uma coletânea cifrada (PDF com texto) em louvores e converte cada um para o formato de cifra.

Uso: python3 coletanea_split.py arquivo.pdf saida.json [primeira_pagina]
Cada louvor começa num título "NN - TÍTULO" (ou "NN – TÍTULO").
"""
import json, re, sys
import cifra_parse as cp

HEAD = re.compile(r"^\s*(\d{1,3})\s*[-–—.]\s*([A-ZÀ-Ý0-9][^a-zà-ÿ]{2,}[A-ZÀ-Ý!?)\.]?)\s*$")
META = re.compile(r"(?i)^(let\.?|letra|m[uú]s\.?|m[uú]sica|arr\.?|arranjo|ritmo|tonalidade|tom|autor|comp\.|trad\.|vers[aã]o|\(let|\(m[uú]s)")

def all_lines(path, first=1):
    out = []
    for pi, (W, H, ws) in enumerate(cp.pages_words(path, first), start=first):
        for col in cp.columns(W, H, ws):
            for l in cp.lines_of(col):
                out.append((pi, l))
    return out

def split(path, first=1):
    rows = all_lines(path, first)
    songs, cur = [], None
    for pi, l in rows:
        txt = " ".join(w["t"] for w in l).strip()
        m = HEAD.match(txt)
        if m and not cp.is_chord_line(l) and not re.search(r"\.{4,}", txt):
            cur = {"num": m.group(1), "title": m.group(2).strip(" -–"), "page": pi, "rows": []}
            songs.append(cur); continue
        if cur is not None:
            # título que continua na linha de baixo (tudo maiúsculo, sem acordes)
            letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", txt)
            if not cur["rows"] and letters and letters.upper() == letters and len(letters) >= 3 and not cp.is_chord_line(l) and not META.match(txt) and not re.search(r"\d", txt):
                cur["title"] = (cur["title"] + " " + txt).strip(); continue
            cur["rows"].append(l)
    out = []
    for s in songs:
        head, body = [], []
        started = False
        for l in s["rows"]:
            t = " ".join(w["t"] for w in l).strip()
            if not started and (META.match(t) or (not cp.is_chord_line(l) and len(body) == 0 and len(head) < 3 and not cp.INLINE.match(t) and not cp.LABEL.match(t) and not re.search(r"\|", t))):
                head.append(t)
                if not META.match(t) and len(head) >= 3: started = True
                continue
            started = True
            body.append(l)
        lines = cp.to_lines(body)
        lines = [x for x in lines if not re.match(r"(?i)^t:(ritmo|tonalidade|tom)\b", x)]
        key = cp.detect_key(lines, "\n".join(head))
        nc = sum(1 for x in lines if x.startswith("c:"))
        out.append({"num": s["num"], "title": s["title"], "page": s["page"], "key": key, "lines": lines, "nc": nc,
                    "head": head})
    return out

if __name__ == "__main__":
    first = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    res = split(sys.argv[1], first)
    json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(len(res), "louvores;", sum(1 for r in res if r["nc"] >= 4), "com cifra boa")
