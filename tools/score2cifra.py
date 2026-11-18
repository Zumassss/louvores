"""Gera cifra (acordes sobre a letra) a partir de partitura em PDF.

Em cada sistema da partitura, a linha de cifras fica acima da pauta principal e a letra
fica abaixo em sílabas, cada uma centralizada na nota. O acorde vai para a sílaba
que está embaixo dele (pela coordenada x).
"""
import re, json, sys, unicodedata
import cifra_parse as cp

def fix_chord(t):
    t = t.replace("Œ„Š", "maj").replace("„ˆˆ", "").replace("(“", "(").replace("“", "sus")
    t = t.replace("‹", "m").replace("¨", "b").replace("♭", "b").replace("©", "#").replace("♯", "#").replace("™", "")
    t = t.replace("°", "º")
    return t

CH = re.compile(r"^[A-G](#|b)?(maj|m|M|dim|aug|sus|add|º|ø|\+)?[0-9]*(\([^)\s]{1,10}\))?(maj|sus|add|m)?[0-9]*(\([^)\s]{1,10}\))?(/[A-G](#|b)?)?$")
NOISE = re.compile(r"^(p|pp|ppp|mp|mf|f|ff|fff|sfz|rit\.?|ritard\.?|rall\.?|cresc\.?|dim\.?|a tempo|tutti|solo|unis\.?|div\.?|fine|d\.s\.?|d\.c\.?|al|coda|v\.s\.?|bis|x|\d+x|\(\d+x\)|[A-Z]\.|\d+\.?)$", re.I)
SYL = re.compile(r"[A-Za-zÀ-ÿ]")

def page_rows(ws, W):
    ws = [dict(w, t=fix_chord(w["t"]) if re.match(r"^[A-G]", w["t"]) and len(w["t"]) <= 18 else w["t"]) for w in ws]
    ws = cp.glue(ws)
    for w in ws:
        if re.match(r"^[A-G]", w["t"]): w["t"] = fix_chord(w["t"])
    rows = []
    for w in sorted(ws, key=lambda w: (w["y0"], w["x0"])):
        if rows and abs(rows[-1][0]["y0"] - w["y0"]) < 2.6: rows[-1].append(w)
        else: rows.append([w])
    for r in rows: r.sort(key=lambda w: w["x0"])
    return rows

import collections
def mode_y(ws):
    c = collections.Counter(round(w["y0"] * 2) / 2 for w in ws)
    return c.most_common(1)[0][0] if c else 0

def chord_row(r, W):
    body = [w for w in r if w["x0"] > W * 0.10 and not (len(w["t"]) == 1 and w["x0"] < W * 0.15)]
    if not body: return None
    ch = [w for w in body if CH.match(w["t"])]
    if not ch: return None
    # linha de notas da fonte musical ("e e E e"): só letras soltas no meio de símbolos
    if all(len(w["t"]) == 1 for w in ch) and sum(1 for w in body if junk(w["t"])) >= 2: return None
    if len(ch) >= 2:   # acordes de verdade ficam todos na mesma altura
        my = mode_y(ch)
        ch = [w for w in ch if abs(w["y0"] - my) <= 0.8]
        if len(ch) == 1 and len(ch[0]["t"]) == 1: return None
        # símbolos musicais com tamanho diferente dos acordes (ex.: nota "E" da fonte da partitura)
        hs = sorted(w["y1"] - w["y0"] for w in ch if len(w["t"]) > 1) or sorted(w["y1"] - w["y0"] for w in ch)
        mh = hs[len(hs) // 2]
        ch = [w for w in ch if abs((w["y1"] - w["y0"]) - mh) <= max(1.0, mh * 0.18)]
    other = [w for w in body if not CH.match(w["t"]) and not junk(w["t"])]
    if other: return None
    return ch

def junk(t):
    """Símbolos musicais soltos (notas, pausas, quiálteras) que caem na mesma altura."""
    return (not re.search(r"[A-Za-zÀ-ÿ0-9]", t)) or len(t) <= 2 and not re.match(r"^[A-G]", t) or re.fullmatch(r"[\d.()|%]+", t) is not None

LABELW = re.compile(r"(?i)^(mulheres|homens|vozes|voz|baixo|el[eé]trico|coro|piano|teclado|guitarra|viol[aã]o|bateria|soprano|contralto|tenor|todos|solo|un[ií]s\.?|tutti|cordas|sopros|metais|madeiras|flauta|violino|violoncelo|viola|trompete|trombone|sax|clarinete|fagote|obo[eé]|harpa|orquestra[cç][aã]o|arranjo|arr\.|let\.|m[uú]s\.|letra|m[uú]sica|adapt\.|trad\.|vers[aã]o|revis[aã]o)$")
GLYPH = re.compile(r"^[ewæœ˙Œ‰Ó∑»«ˆ˘]+™?$|^[a-z]$")
CREDIT = re.compile(r"(?i)\b(letra|m[uú]sica|arranjo|arr\.|orquestra[cç][aã]o|trans\.|transcri|adapta|adapt\.|trad\.|tradu[cç][aã]o|harmoniza|vers[aã]o|revis[aã]o|composi[cç][aã]o|editora[cç][aã]o|copyright|©)")
def lyric_row(r, W):
    if CREDIT.search(" ".join(w["t"] for w in r)): return None
    body = [w for w in r if w["x0"] > W * 0.04 and not NOISE.match(w["t"]) and not LABELW.match(w["t"])]
    syl = [w for w in body if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2}", w["t"].replace("æ", "").replace("œ", "")) and not CH.match(w["t"])]
    glyphs = [w for w in body if GLYPH.match(w["t"]) or not re.search(r"[A-Za-zÀ-ÿ]", w["t"])]
    hy = [w for w in r if w["t"] in ("-", "–", "_")]
    if len(syl) >= 3 and len(glyphs) <= len(syl) or (len(syl) >= 2 and hy):
        my = mode_y(syl)
        return [w for w in r if abs(w["y0"] - my) <= 1.2 and w["x0"] > W * 0.04 and not LABELW.match(w["t"])]
    return None

def build_line(row, chords):
    """Junta sílabas em palavras e coloca os acordes. Devolve (texto ChordPro, n_acordes, n_silabas)."""
    toks = [w for w in row if not NOISE.match(w["t"]) or w["t"] in ("-", "–")]
    # tira número de estrofe no começo ("1.", "2.")
    while toks and re.fullmatch(r"\d+\.?|\(\d+\)", toks[0]["t"]): toks.pop(0)
    if toks and re.match(r"^\d+\.\S", toks[0]["t"]): toks[0] = dict(toks[0], t=re.sub(r"^\d+\.", "", toks[0]["t"]))
    syl = []  # (texto, x_centro, junta_com_proxima)
    join_next = False
    for w in toks:
        t = w["t"]
        if t in ("-", "–", "—"):
            if syl: syl[-1][2] = True
            continue
        if re.fullmatch(r"_+", t) or not re.search(r"[A-Za-zÀ-ÿ]", t): continue
        t = t.replace("™", "")
        t = t.replace("_", " ").replace("‿", " ").replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
        lead = t.startswith("-"); trail = t.endswith("-")
        t = t.strip("-–")
        if not t: continue
        if lead and syl: syl[-1][2] = True
        syl.append([t, (w["x0"] + w["x1"]) / 2, trail, w["x0"]])
    if not syl: return None
    # texto e posição de início de cada sílaba
    text, starts = "", []
    for i, (t, cx, j, x0) in enumerate(syl):
        starts.append(len(text)); text += t
        if i < len(syl) - 1 and not j: text += " "
    ins = []
    for c in chords:
        target = c["x0"] + 3.5
        best = min(range(len(syl)), key=lambda i: abs(syl[i][1] - target))
        if abs(syl[best][1] - target) > 22:
            nxt = [i for i in range(len(syl)) if syl[i][1] > target]
            pos = starts[nxt[0]] if nxt else len(text)
        else:
            pos = starts[best]
        ins.append((pos, c["x0"], c["t"]))
    ins.sort(key=lambda x: (x[0], x[1]))
    out, last = "", 0
    for pos, _, ch in ins:
        out += text[last:pos] + "[" + ch + "]"; last = pos
    out += text[last:]
    return re.sub(r"\s+", " ", out).strip(), len(chords), len(syl), bool(syl[-1][2])

def convert(path):
    systems = []  # (chords, [verse rows])
    for W, H, ws in cp.pages_words(path):
        rows = page_rows(ws, W)
        allw = [w for r in rows for w in r]
        kinds = []
        for r in rows:
            if r[0]["y0"] < H * 0.045 or r[0]["y0"] > H * 0.94: continue
            c = chord_row(r, W)
            if c: kinds.append(("c", r[0]["y0"], c)); continue
            l = lyric_row(r, W)
            if l: kinds.append(("l", r[0]["y0"], l)); continue
            # linha curta (anacruse: "Qual foi o", "Oh!"): 1-2 palavras de verdade
            body = [w for w in r if w["x0"] > W * 0.15 and not NOISE.match(w["t"])]
            if any(LABELW.match(w["t"]) for w in r): continue
            sy = [w for w in body if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2}|^[AEOÓÉÀaeoóé][,!]?$", w["t"]) and not CH.match(w["t"]) and not GLYPH.match(w["t"])]
            if sy and len(sy) >= len(body) - sum(1 for w in body if w["t"] in ("-", "–")) and len(sy) <= 4:
                my = mode_y(sy)
                kinds.append(("w", r[0]["y0"], [w for w in r if abs(w["y0"] - my) <= 1.2 and w["x0"] > W * 0.08]))
        # cada hífen solto pertence à linha de letra mais próxima (estrofes ficam bem juntas)
        lys = [mode_y([w for w in k[2] if len(w["t"]) > 1] or k[2]) for k in kinds if k[0] in ("l", "w")]
        inrow = {id(w) for k in kinds if k[0] in ("l", "w") for w in k[2]}
        stray = {}
        lrows = [(mode_y([w for w in k[2] if len(w["t"]) > 1] or k[2]), k[2]) for k in kinds if k[0] in ("l", "w")]
        for w in allw:
            if w["t"] in ("-", "–") and id(w) not in inrow and lrows:
                hx = (w["x0"] + w["x1"]) / 2
                def brackets(row):   # há sílaba logo à esquerda e logo à direita do hífen?
                    L = any(0 <= hx - x["x1"] < 24 for x in row if len(x["t"]) and x["t"] not in ("-", "–"))
                    R = any(0 <= x["x0"] - hx < 24 for x in row if len(x["t"]) and x["t"] not in ("-", "–"))
                    return L and R
                cands = [(abs(w["y0"] - y), y) for y, row in lrows if -4 <= w["y0"] - y <= 9 and brackets(row)]
                if cands: stray[id(w)] = min(cands)[1]
        i = 0
        while i < len(kinds):
            k, y, data = kinds[i]
            if k != "c": i += 1; continue
            # junta linhas de acordes muito próximas (acordes com alturas diferentes)
            chords = list(data); j = i + 1
            while j < len(kinds) and kinds[j][0] == "c" and kinds[j][1] - y < 9:
                chords += kinds[j][2]; j += 1
            chords.sort(key=lambda w: w["x0"])
            # estrofes logo abaixo
            verses = []
            while j < len(kinds) and (kinds[j][0] == "l" or (kinds[j][0] == "w" and kinds[j][1] - y < 75)) and kinds[j][1] - y < 120:
                if verses and kinds[j][1] - verses[-1][0]["y0"] > 22: break
                row = list(kinds[j][2]); ry = mode_y([w for w in row if len(w["t"]) > 1] or row)
                # hífens que ficaram um pouco fora da linha: só os que estão mais perto DESTA linha de letra
                have = {id(w) for w in row}
                for w in allw:
                    if w["t"] in ("-", "–") and id(w) not in have and stray.get(id(w)) == ry:
                        row.append(w)
                row.sort(key=lambda w: w["x0"])
                verses.append(row); j += 1
            # outras vozes (mais abaixo, sem acorde) são ignoradas
            while j < len(kinds) and kinds[j][0] in ("l", "w"): j += 1
            if not verses and len(chords) == 1 and len(chords[0]["t"]) <= 2:
                i = j; continue   # letra de ensaio (A, B, C...) e não acorde
            systems.append((chords, verses))
            i = j
    return systems

def to_cifra(systems):
    lines, n_ch, n_syl = [], 0, 0
    blocks = []  # agrupa sistemas seguidos com o mesmo número de estrofes
    for chords, verses in systems:
        k = len(verses)
        if blocks and blocks[-1][0] == k and k > 0: blocks[-1][1].append((chords, verses))
        else: blocks.append([k, [(chords, verses)]])
    first = True
    for k, sysl in blocks:
        if k == 0:
            chs = [c["t"] for chords, _ in sysl for c in chords]
            lab = "Introdução" if first else "Instrumental"
            if lines and lines[-1] != "": lines.append("")
            lines.append("i:" + lab + ": " + " ".join("[" + c + "]" for c in chs))
            lines.append("")
            first = False
            continue
        first = False
        for v in range(k):
            carry = ""
            for chords, verses in sysl:
                r = build_line(verses[v], chords)
                if not r: continue
                txt = carry + r[0]; carry = ""
                if r[3]:   # termina no meio de uma palavra ("trans-"): o pedaço vai para a próxima linha
                    cut = txt.rfind(" ")
                    if cut > 0: carry, txt = txt[cut + 1:], txt[:cut]
                lines.append("c:" + txt); n_ch += r[1] if v == 0 else 0; n_syl += r[2]
            if carry: lines.append("c:" + carry)
            lines.append("")
    # muitos acordes seguidos antes de uma única palavra (anacruse): vira linha de introdução
    fixed = []
    for i, x in enumerate(lines):
        m = re.match(r"^c:((?:\[[^\]]+\]){3,})([^\[]*)$", x)
        if m and len(m.group(2).split()) <= 2:
            fixed.append("i:" + ("Introdução" if not any(l.startswith("c:") for l in fixed) else "Instrumental") + ": " + " ".join(re.findall(r"\[[^\]]+\]", m.group(1))))
            word = m.group(2).strip()
            if word and i + 1 < len(lines) and lines[i + 1].startswith("c:"):
                lines[i + 1] = "c:" + word + " " + lines[i + 1][2:]
            elif word: fixed.append("c:" + word)
            continue
        fixed.append(x)
    lines = fixed
    # anacruse: palavra curta depois do fim da frase ("fé. Ó") vai para o começo da próxima linha cantada
    for i in range(len(lines)):
        if not lines[i].startswith("c:"): continue
        m = re.search(r"([.!?;])\s*((?:\[[^\]]+\])*[^\s\[\]]{1,4})$", lines[i])
        if not m or not re.search(r"[A-Za-zÀ-ÿ]", re.sub(r"\[[^\]]*\]", "", m.group(2))): continue
        nxt = next((k for k in range(i + 1, min(i + 4, len(lines))) if lines[k].startswith("c:")), None)
        if nxt is None: continue
        lines[i] = lines[i][:m.start(2)].rstrip()
        lines[nxt] = "c:" + m.group(2) + " " + lines[nxt][2:]
    while lines and lines[-1] == "": lines.pop()
    clean = []
    for x in lines:
        if x == "" and clean and clean[-1] == "": continue
        clean.append(x)
    return clean, n_ch, n_syl

def key_of(lines):
    chs = re.findall(r"\[([A-G](?:#|b)?)(m(?!aj))?", " ".join(l for l in lines if l.startswith("c:")))
    if not chs: return ""
    root, minor = chs[-1]
    return root + ("m" if minor else "")

if __name__ == "__main__":
    sy = convert(sys.argv[1])
    lines, a, b = to_cifra(sy)
    print("key", key_of(lines), "chords", a, "syl", b)
    print("\n".join(lines))


def fix_words(line, vocab):
    """Usa o vocabulário da letra oficial para juntar sílabas soltas e separar palavras grudadas."""
    import unicodedata
    def nk(w):
        w = unicodedata.normalize("NFD", w.lower())
        return re.sub(r"[^a-z]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))
    plain, chords = "", []
    for m in re.finditer(r"\[([^\]]+)\]|([^\[]+)", line):
        if m.group(1): chords.append([len(plain), m.group(1)])
        else: plain += m.group(2)
    ok1 = {"a", "e", "o", "u", "y"}
    def good(w): k = nk(w); return k in vocab or (len(k) == 1 and k in ok1)
    changed = True
    while changed:
        changed = False
        words = [(m.start(), m.end()) for m in re.finditer(r"\S+", plain)]
        # sequências de 3 a 5 sílabas soltas que formam uma palavra ("Se gu ro" -> "Seguro")
        for i in range(len(words)):
            for n in (5, 4, 3):
                if i + n > len(words): continue
                seg = words[i:i + n]
                if any(seg[k + 1][0] != seg[k][1] + 1 for k in range(n - 1)): continue
                parts = [plain[a:b] for a, b in seg]
                if any(re.search(r"[,.;:!?]$", p) for p in parts[:-1]): continue
                if nk("".join(parts)) in vocab and sum(1 for p in parts if good(p)) < n:
                    for k in range(n - 1, 0, -1):
                        cut = seg[k][0] - 1
                        plain = plain[:cut] + plain[cut + 1:]
                        for c in chords:
                            if c[0] > cut: c[0] -= 1
                    changed = True; break
            if changed: break
        if changed: continue
        for (a0, a1), (b0, b1) in zip(words, words[1:]):
            w1, w2 = plain[a0:a1], plain[b0:b1]
            if b0 == a1 + 1 and not re.search(r"[,.;:!?]$", w1) and nk(w1 + w2) in vocab and (not good(w1) or not good(w2)):
                plain = plain[:a1] + plain[b0:]
                for c in chords:
                    if c[0] > a1: c[0] -= 1
                changed = True; break
        if changed: continue
        for a0, a1 in words:
            w = plain[a0:a1]; core = nk(w)
            if len(core) < 4 or core in vocab: continue
            letters = [i for i, ch in enumerate(w) if ch.isalpha()]
            for k in range(1, len(letters)):
                cut = letters[k]
                p1, p2 = w[:cut], w[cut:]
                if good(p1) and good(p2) and min(len(nk(p1)), len(nk(p2))) >= 1:
                    pos = a0 + cut
                    plain = plain[:pos] + " " + plain[pos:]
                    for c in chords:
                        if c[0] >= pos: c[0] += 1
                    changed = True; break
            if changed: break
    out, last = "", 0
    for pos, ch in sorted(chords, key=lambda c: c[0]):
        out += plain[last:pos] + "[" + ch + "]"; last = pos
    return out + plain[last:]

def convert_lyrics(path):
    """Só a letra (partitura sem acordes): cada grupo de linhas de sílabas vira um sistema sem acordes."""
    systems = []
    for W, H, ws in cp.pages_words(path):
        rows = page_rows(ws, W)
        allw = [w for r in rows for w in r]
        ls = []
        for r in rows:
            if r[0]["y0"] < H * 0.045 or r[0]["y0"] > H * 0.94: continue
            if any(LABELW.match(w["t"]) for w in r if w["x0"] > W * 0.15): continue
            l = lyric_row(r, W)
            if l:
                txt = " ".join(w["t"] for w in l)
                letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", txt)
                if re.search(r"\b1[5-9]\d\d|20\d\d\b", txt) or (letters and letters.upper() == letters and len(letters) > 8):
                    continue   # créditos ("PHILIP PAUL BLISS, 1874")
                ls.append((mode_y([w for w in l if len(w["t"]) > 1] or l), l))
        # hífens soltos -> linha mais próxima com sílabas dos dois lados
        inrow = {id(w) for _, l in ls for w in l}
        for w in allw:
            if w["t"] in ("-", "–") and id(w) not in inrow:
                hx = (w["x0"] + w["x1"]) / 2
                c = [(abs(w["y0"] - y), k) for k, (y, l) in enumerate(ls) if -4 <= w["y0"] - y <= 9
                     and any(0 <= hx - x["x1"] < 24 for x in l) and any(0 <= x["x0"] - hx < 24 for x in l)]
                if c: ls[min(c)[1]][1].append(w)
        for _, l in ls: l.sort(key=lambda w: w["x0"])
        stack, last = [], None
        for y, l in ls:
            if stack and y - last > 22:
                systems.append(([], stack)); stack = []
            stack.append(l); last = y
        if stack: systems.append(([], stack))
    return systems
