"""Converte cifras em PDF (formato ICM: acordes em cima, '|' na letra) em linhas ChordPro.

Formato de saída de cada linha:
  "c:<letra com [Acorde] embutido>"   linha cantada com acordes
  "a:[A] [B] [C]"                      só acordes (introdução/instrumental na pauta)
  "i:Introdução: [Bb], [Eb]"           texto com acordes no meio (mostrados em linha)
  "h:Coro"                             rótulo de seção
  "t:texto"                            texto comum
  ""                                   linha em branco (separa estrofes)
"""
import re, subprocess, html, json, sys, unicodedata

WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')
PAGE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)
CH = r"[A-G](?:#|b)?(?:maj|min|m|M|dim|aug|sus|add|º|°|ø|Ø|\+)?[0-9]*(?:b5|#5)?(?:\([^)\s]{1,12}\))?(?:maj|sus|add|m)?[0-9]*(?:\([^)\s]{1,12}\))?(?:/[A-G](?:#|b)?)?"
CHORD = re.compile(r"^" + CH + r"$")
SEP = re.compile(r"^(\||\|\||%|-|–|\(?\d+x\)?|x\d+|\(bis\)|bis)$", re.I)

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).split()

def pages_words(path, first=None, last=None):
    cmd = ["pdftotext", "-q", "-bbox"]
    if first: cmd += ["-f", str(first)]
    if last: cmd += ["-l", str(last)]
    out = subprocess.run(cmd + [path, "-"], capture_output=True, text=True).stdout
    res = []
    for w, h, body in PAGE.findall(out):
        ws = [dict(x0=float(a), y0=float(b), x1=float(c), y1=float(d), t=html.unescape(t).replace("​", ""))
              for a, b, c, d, t in WORD.findall(body)]
        res.append((float(w), float(h), [x for x in ws if x["t"].strip()]))
    return res

def columns(W, H, ws):
    """Divide a página em colunas pela margem esquerda onde começam as linhas de letra."""
    body = [w for w in ws if w["y0"] > H * 0.05]
    rows = []
    for w in sorted(body, key=lambda w: (w["y0"], w["x0"])):
        if rows and abs(rows[-1][0]["y0"] - w["y0"]) < 2.5: rows[-1].append(w)
        else: rows.append([w])
    starts = []
    for r in rows:
        r.sort(key=lambda w: w["x0"])
        seg = [r[0]]
        for w in r[1:]:
            if w["x0"] - seg[-1]["x1"] > 22:
                starts.append(seg); seg = [w]
            else: seg.append(w)
        starts.append(seg)
    xs = []
    for seg in starts:
        t = " ".join(w["t"] for w in seg)
        if CHORD.match(seg[0]["t"]) or re.fullmatch(r"(?i)[|\s]*(bis|\d+x|x\d+)?[|\s]*", t) or len(t) < 6: continue
        xs.append(seg[0]["x0"])
    xs.sort()
    clusters = []
    for x in xs:
        if clusters and x - clusters[-1][-1] < 8: clusters[-1].append(x)
        else: clusters.append([x])
    lefts = [min(c) for c in clusters if len(c) >= 4]
    # colunas precisam estar afastadas (pelo menos 25% da largura)
    cols_x = []
    for x in lefts:
        if not cols_x or x - cols_x[-1] > W * 0.22: cols_x.append(x)
    if len(cols_x) <= 1: return [ws]
    out = [[] for _ in cols_x]
    for w in ws:
        k = 0
        for i, x in enumerate(cols_x):
            if w["x0"] >= x - 6: k = i
        out[k].append(w)
    return [c for c in out if c]

SUP = re.compile(r"^(?:[0-9]+|\([^)]*\)|maj[0-9]*|sus[0-9]*|add[0-9]*|dim|aug|º|°|ø|\+|M[0-9]*|/[A-G](?:#|b)?)+$")
def glue(ws):
    ws = sorted(ws, key=lambda w: (w["x0"], w["y0"]))
    out = []
    for w in sorted(ws, key=lambda w: (round(w["y0"] / 8), w["x0"])):
        out.append(dict(w))
    # acordes com parênteses quebrados em pedaços: "F9" "(" "#11" ")" -> "F9(#11)"
    CHORDISH = re.compile(r"^[A-G](#|b)?[0-9mMajsudi+º°()#b/A-G]*$")
    FRAG = re.compile(r"^[()#b0-9+º°Øø]+$|^\(?(sus|add|maj|dim|aug)[0-9]*\)?$|^/[A-G](#|b)?$|^[0-9]*\([^ ]*$|^\)(/[A-G](#|b)?)?$")
    rows = sorted(out, key=lambda w: w["x0"])
    for i, a in enumerate(rows):
        if a.get("del") or not CHORDISH.match(a["t"]): continue
        for b in rows[i + 1:]:
            if b.get("del") or abs(b["y0"] - a["y0"]) > 3.5: continue
            if not (-0.5 <= b["x0"] - a["x1"] < 4.6): continue
            gap = b["x0"] - a["x1"]
            if FRAG.match(b["t"]) and (gap < 1.2 or (gap < 4.6 and (a["t"].count("(") > a["t"].count(")") or b["t"][0] in "(/Øø" or re.match(r"^[0-9]", b["t"]) and len(a["t"]) <= 2))):
                a["t"] += b["t"]; a["x1"] = b["x1"]; b["del"] = True
    changed = True
    while changed:
        changed = False
        for w in out:
            if w.get("del") or not SUP.match(w["t"]): continue
            for p in out:
                if p is w or p.get("del"): continue
                if -0.5 <= w["x0"] - p["x1"] < 2.6 and abs(p["y0"] - w["y0"]) < 7 and CHORD.match(p["t"] + w["t"]) and re.match(r"^[A-G]", p["t"]):
                    p["t"] += w["t"]; p["x1"] = w["x1"]; w["del"] = True; changed = True; break
    return [w for w in out if not w.get("del")]

def lines_of(ws):
    ws = sorted(glue(ws), key=lambda w: (w["y0"], w["x0"]))
    lines = []
    for w in ws:
        if lines and abs(lines[-1][0]["y0"] - w["y0"]) < 2.5: lines[-1].append(w)
        else: lines.append([w])
    for l in lines: l.sort(key=lambda w: w["x0"])
    return lines

def is_chord_line(l):
    toks = [w["t"] for w in l]
    ch = [t for t in toks if CHORD.match(t)]
    if not ch: return False
    other = [t for t in toks if not (CHORD.match(t) or SEP.match(t))]
    # tolera erro de digitação curto ("BB") se quase tudo for acorde
    return not other or (len(ch) >= 2 * len(other) and all((len(t) <= 3 or re.match(r"^[A-G](#|b)?[^ ]{0,9}$", t)) and not re.search(r"[aeiouáéíóú]{1}[a-z]", t) for t in other))

def build_lyric(l):
    """Texto da linha + posição x de cada caractere."""
    text, xs = "", []
    for i, w in enumerate(l):
        if i:
            gap = w["x0"] - l[i - 1]["x1"]
            n = 1 if gap < 6 else max(1, round(gap / 4.5))
            n = min(n, 1) if gap < 12 else n
            text += " " * n; xs += [l[i - 1]["x1"] + gap * (k + 1) / (n + 1) for k in range(n)]
        t = w["t"]; step = (w["x1"] - w["x0"]) / max(1, len(t))
        text += t; xs += [w["x0"] + step * k for k in range(len(t))]
    return text, xs

VOW = set("aeiouáéíóúâêôãõàüyAEIOUÁÉÍÓÚÂÊÔÃÕÀÜY")
def syllable_starts(word):
    """Começos de sílaba numa palavra (regras simples do português)."""
    w = word.lower(); n = len(w); starts = [0]
    i = 0
    letters = [c.isalpha() for c in w]
    while i < n:
        if w[i] in VOW:
            j = i + 1
            while j < n and w[j] in VOW and not (w[j - 1] in "aeo" and w[j] in "aeo"):  # ditongos ficam juntos; hiato "oe/ea" separa
                j += 1
            k = j
            while k < n and letters[k] and w[k] not in VOW: k += 1
            cons = w[j:k]
            if k >= n or not cons:
                if k < n and not cons and j < n and w[j] in VOW: starts.append(j)
                i = k; continue
            if len(cons) == 1: b = j
            elif cons[-2:] in ("nh", "lh", "ch", "qu", "gu") or cons[-2:] in ("br", "cr", "dr", "fr", "gr", "pr", "tr", "vr", "bl", "cl", "fl", "gl", "pl", "tl"):
                b = k - 2
            else: b = k - 1
            if 0 < b < n and letters[b]: starts.append(b)
            i = k
        else:
            i += 1
    return sorted(set(starts))

def snap_syllable(text, pos):
    if pos >= len(text) or not text[pos].isalpha(): return pos
    a = pos
    while a > 0 and text[a - 1].isalpha(): a -= 1
    b = pos
    while b < len(text) and text[b].isalpha(): b += 1
    cands = [a + x for x in syllable_starts(text[a:b])]
    return min(cands, key=lambda c: (abs(c - pos), c > pos))

def merge(chords, lyric_words):
    """Coloca cada acorde no lugar certo da letra."""
    # tira colchetes de 'bis' (| sozinho no fim) e guarda a anotação
    tail = ""
    lw = list(lyric_words)
    while lw and (lw[-1]["t"] in ("|", "||") or re.fullmatch(r"(?i)\|?\s*(bis|\d+x|x\d+)", lw[-1]["t"])):
        t = lw.pop()["t"]
        if re.search(r"(?i)bis|\dx|x\d", t): tail = " (" + re.sub(r"[|\s]", "", t).lower() + ")" + tail
    text, xs = build_lyric(lw) if lw else ("", [])
    chs = [c for c in chords if CHORD.match(c["t"])]
    pipes = [i for i, ch in enumerate(text) if ch == "|"]
    ins = []  # (posição no texto sem '|', acorde)
    clean_xs = [x for ch, x in zip(text, xs) if ch != "|"]
    cpipes = [p - k for k, p in enumerate(pipes)]
    if pipes and len(pipes) == len(chs):
        ins = [(p, c["t"]) for p, c in zip(cpipes, chs)]
    else:
        used = set()
        for c in chs:
            cx = c["x0"] + 0.5
            pos = len(clean_xs)
            for i, x in enumerate(clean_xs):
                if x >= cx - 1.5: pos = i; break
            near = [p for p in cpipes if p not in used and abs(p - pos) <= 3]
            if near:
                pos = min(near, key=lambda p: abs(p - pos)); used.add(pos)
            elif pos < len(clean_xs):
                # sem '|': encaixa no começo da sílaba mais próxima (Se·nhor, In·vo·cai)
                cl = text.replace("|", "")
                if pos < len(cl) and cl[pos] == " ": pos += 1
                pos = snap_syllable(cl, pos)
            ins.append((pos, c["t"]))
    clean = text.replace("|", "")
    # se a letra começa com espaços demais por causa do recuo, mantém só os acordes nas posições
    out, last = "", 0
    for pos, c in sorted(ins, key=lambda x: x[0]):
        pos = min(pos, len(clean))
        out += clean[last:pos] + "[" + c + "]"; last = pos
    out += clean[last:]
    if len(clean) < (max([p for p, _ in ins]) if ins else 0):
        out += ""
    return re.sub(r"\s{2,}", " ", out).strip() + tail

HEAD_SKIP = re.compile(r"(?i)^(www\.|louvoricm|cifra atualizada|material passando|atualizado em|p[aá]gina|\d{1,3}$)")
LABEL = re.compile(r"(?i)^(coro|final|ponte|refr[aã]o|estrofe|verso|parte|solo|interl[uú]dio|pr[eé]-?refr[aã]o|instrumental)\b[^:]*:?$")
INLINE = re.compile(r"(?i)^(introdu[cç][aã]o|instrumental|intro|interl[uú]dio|final|solo|ponte)\s*:")

def to_lines(raw):
    """raw: lista de linhas (cada uma lista de palavras) já em ordem de leitura."""
    out, i = [], 0
    prev_y = None
    while i < len(raw):
        l = raw[i]
        txt = " ".join(w["t"] for w in l).strip()
        lh = max(8, l[0]["y1"] - l[0]["y0"])
        if prev_y is not None and l[0]["y0"] - prev_y > max(22, 3.2 * lh) and out and out[-1] != "": out.append("")
        prev_y = l[0]["y0"]
        if HEAD_SKIP.match(txt): i += 1; continue
        if is_chord_line(l):
            nxt = raw[i + 1] if i + 1 < len(raw) else None
            if nxt and not is_chord_line(nxt) and nxt[0]["y0"] - l[0]["y0"] < max(18, 2.3 * (l[0]["y1"] - l[0]["y0"])) and not LABEL.match(" ".join(w["t"] for w in nxt)) and not INLINE.match(" ".join(w["t"] for w in nxt)):
                out.append("c:" + merge(l, nxt)); prev_y = nxt[0]["y0"]; i += 2; continue
            out.append("a:" + " ".join("[" + w["t"] + "]" if CHORD.match(w["t"]) else w["t"] for w in l)); i += 1; continue
        if INLINE.match(txt) and not any(CHORD.match(p) for p in re.split(r"[\s,|]+", txt)):
            out.append("h:" + txt.rstrip(":")); i += 1; continue
        if INLINE.match(txt):
            parts = re.split(r"(\s+|,|\|)", txt)
            out.append("i:" + "".join("[" + p + "]" if CHORD.match(p) else p for p in parts)); i += 1; continue
        if LABEL.match(txt):
            out.append("h:" + txt.rstrip(":")); i += 1; continue
        out.append("t:" + re.sub(r"\s{2,}", " ", txt.replace("|", "")).strip())
        i += 1
    while out and out[-1] == "": out.pop()
    while out and out[0] == "": out.pop(0)
    # continuação de introdução/instrumental na linha seguinte (ex.: "E, B")
    merged = []
    for x in out:
        body = x[2:] if x[:2] in ("t:", "a:") else None
        if body and merged and merged[-1].startswith("i:") and all(CHORD.match(t) or SEP.match(t) for t in re.split(r"[\s,]+", body.strip()) if t):
            merged[-1] += " " + "".join("[" + p + "]" if CHORD.match(p) else p for p in re.split(r"(\s+|,)", body.replace("[", "").replace("]", "")))
            continue
        merged.append(x)
    out = merged
    # remove brancos repetidos
    res = []
    for x in out:
        if x == "" and res and res[-1] == "": continue
        res.append(x)
    return res

def detect_key(lines, header_text):
    m = re.search(r"(?i)tonalidade:?\s*([A-G](?:#|b)?m?)", header_text) or re.search(r"\(([A-G](?:#|b)?m?)\)\s*$", header_text.splitlines()[0] if header_text else "")
    if m: return m.group(1)
    for l in lines:
        m = re.search(r"\[([A-G](?:#|b)?m?)", l)
        if m and not l.startswith("i:"): return m.group(1)
    return ""

def whole_doc(path):
    """PDF de uma música só (Site Louvor ICM)."""
    raw, header = [], []
    for W, H, ws in pages_words(path):
        for col in columns(W, H, ws):
            for l in lines_of(col): raw.append(l)
    # cabeçalho: tudo antes da primeira linha de acordes que não seja título/autoria/tonalidade
    start = 0
    for k, l in enumerate(raw):
        t = " ".join(w["t"] for w in l)
        if is_chord_line(l) or INLINE.match(t) or LABEL.match(t): start = k; break
        header.append(t)
    head = "\n".join(header)
    lines = to_lines(raw[start:])
    return {"key": detect_key(lines, head), "lines": lines}

def caderno_song(path, page, end, title):
    """Uma música dentro de um caderno: lê as colunas das páginas e corta a partir do título."""
    raw = []
    for W, H, ws in pages_words(path, page, end):
        for col in columns(W, H, ws):
            raw += lines_of(col)
    k = " ".join(norm(re.sub(r"\(.*?\)", "", title)))
    start, stop = None, len(raw)
    for i, l in enumerate(raw):
        t = " ".join(norm(re.sub(r"^\d{1,2}\s*[-–]\s*", "", " ".join(w["t"] for w in l))))
        if start is None and k and (t == k or t.startswith(k)) and not is_chord_line(l) and not re.search(r"\s\d{1,3}$", " ".join(w["t"] for w in l)):
            near = raw[i + 1:i + 5]
            if any(is_chord_line(x) or INLINE.match(" ".join(w["t"] for w in x)) for x in near):
                start = i; continue
        if start is not None and i > start + 2:
            txt = " ".join(w["t"] for w in l)
            # próximo título (MAIÚSCULAS, curto, sem '|') encerra a música
            if (re.match(r"^\d{2}\s*[-–]\s*\S", txt) or (txt.upper() == txt and len(txt) > 6 and re.search(r"[A-ZÀ-Ý]{4}", txt) and "|" not in txt and not is_chord_line(l) and not INLINE.match(txt) and not LABEL.match(txt) and not re.search(r"\b(BIS|CORO|FINAL)\b", txt))):
                stop = i; break
    if start is None: return None
    head = " ".join(w["t"] for w in raw[start])
    body = raw[start + 1:stop]
    # linhas de cabeçalho (ritmo, tonalidade) viram texto comum no topo
    lines = to_lines(body)
    lines = [l for l in lines if not re.match(r"(?i)^t:(ritmo|tonalidade|tom)\b", l)] if lines else lines
    return {"key": detect_key(lines, head), "lines": lines}

def render(c):
    """Visualização em texto (para conferir)."""
    out = []
    for l in c["lines"]:
        if l.startswith("c:"):
            s = l[2:]; top, bot = "", ""
            for m in re.finditer(r"\[([^\]]+)\]|([^\[]+)", s):
                if m.group(1):
                    pad = max(len(bot), len(top)); top = top.ljust(len(bot)) + m.group(1) + " ";
                else: bot += m.group(2)
                if len(top) > len(bot): pass
            out += [top.rstrip(), bot]
        else: out.append(l)
    return "\n".join(out)

if __name__ == "__main__":
    print(render(whole_doc(sys.argv[1])))

def page_doc(path, page, end):
    """Alternativa: a página inteira (pula a 1ª linha, que é o título)."""
    raw = []
    for W, H, ws in pages_words(path, page, end):
        for col in columns(W, H, ws):
            raw += lines_of(col)
    k = 0
    while k < len(raw) and not (is_chord_line(raw[k]) or INLINE.match(" ".join(w["t"] for w in raw[k]))): k += 1
    head = " ".join(w["t"] for w in raw[max(0, k - 1)]) if raw else ""
    lines = to_lines(raw[k:])
    return {"key": detect_key(lines, head), "lines": lines}
