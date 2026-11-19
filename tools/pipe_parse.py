"""Leitura exata pelas marcas '|': cada acorde fica na sílaba marcada com '|' na letra logo abaixo.

page_lines(pdf, pg) -> linhas (por coluna, de cima para baixo) já com acordes, e a checagem:
todos os '|' receberam acorde e todos os acordes acharam um '|'.
"""
import re, sys, json
import pdfplumber
import cifra_parse as cp

def gutter(chars, W):
    import numpy as np
    cov = np.zeros(int(W) + 2, bool)
    for c in chars:
        if c["text"].isspace(): continue
        cov[int(c["x0"]):int(c["x1"]) + 1] = True
    a, b = int(W * 0.3), int(W * 0.7)
    best, bl, run, st = None, 0, 0, a
    for x in range(a, b):
        if not cov[x]:
            if run == 0: st = x
            run += 1
            if run > bl: bl, best = run, st + run // 2
        else: run = 0
    return best if bl >= 6 else W + 1

def segs_of(chars, mid):
    """linhas por coluna; sobrescritos (letra menor) entram na linha logo abaixo."""
    cs = [c for c in chars if not c["text"].isspace()]
    if not cs: return []
    big = sorted(c["size"] for c in cs)[len(cs) // 2]
    rows = []
    for c in sorted(cs, key=lambda c: (c["size"] < 0.8 * big, round(c["top"]), c["x0"])):
        col = 0 if c["x0"] < mid else 1
        small = c["size"] < 0.8 * big
        for r in rows:
            if r["col"] != col: continue
            if (not small and abs(r["top"] - c["top"]) < 2.2) or (small and -0.3 * big < r["top"] - c["top"] < 0.9 * big):
                r["c"].append(c); break
        else: rows.append({"top": c["top"], "col": col, "c": [c]})
    return [sorted(r["c"], key=lambda c: c["x0"]) for r in rows]

def tokens(seg):
    toks, cur = [], [seg[0]]
    for a, b in zip(seg, seg[1:]):
        if b["x0"] - a["x1"] > 0.18 * a["size"]: toks.append(cur); cur = [b]
        else: cur.append(b)
    toks.append(cur)
    out = [{"t": "".join(c["text"] for c in t), "x0": t[0]["x0"], "x1": t[-1]["x1"]} for t in toks]
    j = []   # "G7(4" "9)" -> "G7(4 9)"
    for t in out:
        if j and j[-1]["t"].count("(") > j[-1]["t"].count(")"):
            j[-1]["t"] += " " + t["t"]; j[-1]["x1"] = t["x1"]
        else: j.append(dict(t))
    return j

def is_chords(seg):
    ts = [dict(t, t=t["t"].strip("|")) for t in tokens(seg)]
    ts = [t for t in ts if t["t"]]
    return ts and all(cp.CHORD.match(t["t"]) or cp.SEP.match(t["t"]) for t in ts) and any(cp.CHORD.match(t["t"]) for t in ts)

def page(pdf, pg):
    p = pdf.pages[pg - 1]
    W = p.width
    mid = gutter(p.chars, W)
    segs = segs_of(p.chars, mid)
    S = [{"top": s[0]["top"], "bot": max(c["bottom"] for c in s), "x0": s[0]["x0"], "x1": s[-1]["x1"], "c": s, "size": s[0]["size"],
          "chord": is_chords(s)} for s in segs]
    for s in S: s["col"] = 0 if s["x0"] < mid else 1
    chords = []
    for s in S:
        if s["chord"]:
            for t in tokens(s["c"]):
                if t["t"].startswith("|"): t = dict(t, t=t["t"].lstrip("|"), x0=t["x0"] + 2)
                t["t"] = t["t"].rstrip("|")
                if cp.CHORD.match(t["t"]): chords.append({"t": t["t"], "x": t["x0"], "top": s["top"], "col": s["col"], "used": False, "seg": id(s)})
    out_lines, ok, npipe, nmiss = [], True, 0, 0
    for s in sorted(S, key=lambda s: (s["col"], s["top"])):
        if s["chord"]:
            continue
        cs = s["c"]
        if s["chord"]: continue
        for k, c in enumerate(cs):
            nx = cs[k + 1] if k + 1 < len(cs) else None
            c["pipe"] = c["text"] == "|" or (c["text"] in "Il" and "Bold" in c.get("fontname", "") and nx is not None and "Bold" not in nx.get("fontname", "") and nx["x0"] - c["x1"] < 0.15 * c["size"])
        pipes = [c for c in cs if c["pipe"]]
        # linha de acordes logo acima: se o número de acordes = número de '|', liga em ordem (exato)
        rowsab = sorted({h["seg"]: h["top"] for h in chords if not h["used"] and h["col"] == s["col"] and 0 < s["top"] - h["top"] < 2.6 * s["size"]}.items(), key=lambda kv: -kv[1])
        assign = {}
        if pipes and rowsab:
            row = sorted([h for h in chords if h["seg"] == rowsab[0][0] and not h["used"]], key=lambda h: h["x"])
            if len(row) == len(pipes):
                for pc, h in zip(pipes, row): assign[id(pc)] = h
        text, ins, xs = "", [], []
        prev = None
        for c in cs:
            if prev is not None and c["x0"] - prev["x1"] > 0.18 * c["size"] and not prev["pipe"]: text += " "; xs.append(prev["x1"])
            if c["pipe"]:
                if id(c) in assign:
                    h = assign[id(c)]; h["used"] = True; ins.append((len(text), h["t"])); npipe += 1; prev = c; continue
                above = [h for h in chords if not h["used"] and h["col"] == s["col"] and 0 < s["top"] - h["top"] < 2.6 * s["size"] and abs(h["x"] - c["x0"]) < 2.5 * s["size"]]
                npipe += 1
                if above:
                    h = min(above, key=lambda h: (s["top"] - h["top"], abs(h["x"] - c["x0"])))
                    h["used"] = True; ins.append((len(text), h["t"]))
                else:
                    nmiss += 1; ok = False
            else:
                text += c["text"]; xs.append(c["x0"])
            prev = c
        if rowsab and (pipes or text.strip()):   # acordes da mesma linha sem '|' (fim de verso etc.): pela posição
            for h in chords:
                if h["seg"] == rowsab[0][0] and not h["used"]:
                    pos = next((k for k, x in enumerate(xs) if x >= h["x"] - 1.5), len(text))
                    # sem '|': nunca no meio de uma palavra que já tem acorde -> vai para o fim da palavra
                    if 0 < pos < len(text) and text[pos - 1].isalpha() and text[pos].isalpha():
                        ws = pos
                        while ws > 0 and text[ws - 1].isalpha(): ws -= 1
                        if any(ws <= p0 < pos for p0, _ in ins):
                            while pos < len(text) and (text[pos].isalpha() or text[pos] in ".,;:!?"): pos += 1
                    h["used"] = True; ins.append((pos, h["t"]))
            ins.sort(key=lambda t: t[0])
        if ins:
            line = ""; last = 0
            for pos, ch in ins: line += text[last:pos] + "[" + ch + "]"; last = pos
            out_lines.append((s["col"], s["top"], "c:" + line + text[last:], bool(pipes) and all(id(pc) in assign or True for pc in pipes)))
        else:
            out_lines.append((s["col"], s["top"], "t:" + text, False))
    # acordes sem '|' embaixo: linha só de acordes (introdução etc.)
    left = [h for h in chords if not h["used"]]
    bysg = {}
    for h in left: bysg.setdefault((h["col"], h["top"]), []).append(h)
    for (col, top), hs in bysg.items():
        out_lines.append((col, top, "a:" + " ".join("[" + h["t"] + "]" for h in sorted(hs, key=lambda h: h["x"])), False))
    out_lines.sort(key=lambda x: (x[0], x[1]))
    st = {"pipes": npipe, "sem_acorde": nmiss, "acordes_soltos": len(left)}
    st["flags"] = [f for *_, f in out_lines]
    st["sem_marca"] = sum(1 for _, _, l, f in out_lines if l.startswith("c:") and not f)
    return [l for _, _, l, _ in out_lines], st

if __name__ == "__main__":
    pdf = pdfplumber.open(sys.argv[1])
    a, b = int(sys.argv[2]), int(sys.argv[3])
    for pg in range(a, b + 1):
        lines, st = page(pdf, pg)
        print("== página", pg, st)
        for l in lines: print("  ", l)
