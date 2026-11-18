"""Monta as cifras da Coletânea Cifrada Nível II a partir das páginas lidas por scan_build.py.

Uso: python3 nivel2_assemble.py saida.json pagina1.jsonl [pagina2.jsonl ...]
"""
import json, re, sys, collections, unicodedata
import cifra_parse as cp
import scan_build as sb
import score2cifra as sc

HEAD = re.compile(r"^\s*(\d{1,3})\s*[-–—.]+\s*([A-ZÀ-Ý0-9][^a-zà-ÿ]{2,})$")
META = re.compile(r"(?i)^\(?\s*(let|letra|m[uú]s|arr|trad|vers)|tonalidade|ritmo|\(\s*let|/\s*m[uú]s")
LABEL = re.compile(r"(?i)^(coro|instrumentos?|instrumental|repetir.*|bis|final|ponte|solo|interl[uú]dio|todos|varões|varoas|vozes.*|\d+\s*x)\s*:?$")
INLINE = re.compile(r"(?i)^(introdu[cç][aã]o|final|instrumental|interl[uú]dio|solo|ponte)\s*:")
CH = re.compile(r"^[A-G](#|b)?(maj|m|M|dim|aug|sus|add|º|ø|\+)?[0-9]*(\([^)\s]{1,10}\))?(maj|sus|add|m)?[0-9]*(/[A-G](#|b)?)?$")

def nk(w):
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))

def load_rows(paths):
    pages = []
    for p in paths:
        for line in open(p):
            line = line.strip()
            if line: pages.append(json.loads(line))
    pages.sort(key=lambda r: r["page"])
    items = []
    for pg in pages:
        H = pg.get("H", 3500)
        for it in sorted(pg["rows"], key=lambda it: (it["col"], it["y"])):
            it["page"] = pg["page"]; it["H"] = H
            items.append(it)
    return items

def song_key(chords):
    roots = collections.Counter(re.match(r"^[A-G](#|b)?m?", c).group(0) for c in chords if re.match(r"^[A-G]", c))
    return roots

def clean_chords(lines):
    """Corrige leituras duvidosas usando os outros acordes da música (A6 x Ab, Abb, letras soltas)."""
    allc = [c for l in lines for c in re.findall(r"\[([^\]]+)\]", l)]
    cnt = collections.Counter(allc)
    def fixc(c):
        c = c.replace("bb", "b")
        m = re.match(r"^([A-G])6(.*)$", c)
        if m and cnt.get(m.group(1) + "b" + m.group(2), 0) >= cnt.get(c, 0): c = m.group(1) + "b" + m.group(2)
        m = re.match(r"^([A-G])(m?)9$", c)
        return c if CH.match(c) else None
    out = []
    for l in lines:
        def rep(m):
            f = fixc(m.group(1)); return "[" + f + "]" if f else ""
        out.append(re.sub(r"\[([^\]]+)\]", rep, l))
    return out

def assemble(items):
    songs, cur, skipbox = [], None, False
    for i, it in enumerate(items):
        txt = it["text"].strip()
        # cabeçalho/rodapé da página (categoria, número da página)
        if it["words"] and (re.fullmatch(r"\d{1,3}", txt) or (it["y"] < it["H"] * 0.035 and len(txt.split()) <= 3 and not HEAD.match(txt))):
            continue
        m = HEAD.match(txt) if it["words"] and not it["chords"] else None
        if m:
            cur = {"num": m.group(1), "title": m.group(2).strip(" -–"), "page": it["page"], "lines": [], "head": [], "cont": True}
            songs.append(cur); continue
        if cur is None: continue
        if cur["cont"] and it["words"] and not it["chords"] and not it["inline"]:
            letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", txt)
            if letters and letters.upper() == letters and len(letters) >= 3 and not META.search(txt):
                cur["title"] += " " + txt; continue
        cur["cont"] = False
        # quadro com versículo ("SALMO 150:6 - ...") no meio da página
        if re.match(r"^[A-ZÇÃÉÍÓÚ]+\s+\d+[:.]\d+", txt): skipbox = True
        if skipbox:
            if re.search(r"[”\"]\s*$|\.\s*[”\"]?$", txt): skipbox = False
            continue
        if it["words"] and META.search(txt) and not it["chords"]:
            cur["head"].append(txt); continue
        ch_inline = [c for _, c in it["inline"]]
        if it["words"] and INLINE.match(txt):
            lab = INLINE.match(txt).group(1).capitalize()
            if ch_inline: cur["lines"].append("i:" + lab + ": " + " ".join("[" + c + "]" for c in ch_inline))
            else: cur["lines"].append("h:" + txt.rstrip(":"))
            continue
        if not it["words"]:
            # acordes sem '|': no fim da linha de letra seguinte (mesma altura dos outros acordes dela)?
            nxt = items[i + 1] if i + 1 < len(items) else None
            near = nxt and nxt["words"] and nxt["col"] == it["col"] and (
                (nxt.get("chy") is not None and -10 <= nxt["chy"] - it["y"] <= 60) or
                (nxt.get("chy") is None and nxt["chords"] and 15 <= nxt["y"] - it["y"] <= 80))
            if near:
                nxt.setdefault("tail", []).extend(ch_inline); continue
            if ch_inline: cur["lines"].append("a:" + " ".join("[" + c + "]" for c in ch_inline))
            continue
        if LABEL.match(txt):
            if re.match(r"(?i)^bis$", txt): continue
            cur["lines"].append("h:" + txt.rstrip(":")); continue
        line = sb.lyric_with_chords(it)
        tail = it.get("tail", []) + [c for _, c in it["inline"]]
        if tail: line += "".join("[" + c + "]" for c in tail)
        line = re.sub(r"\s*\b(bis|BIS)\s*$", " (bis)", line)
        cur["lines"].append("c:" + line)
    return songs

def fix_lyrics(lines, letra_words, gv):
    """Corrige a letra com a letra oficial: junta sílabas cortadas pelo '|' e troca palavras com 1-2 letras erradas."""
    voc = set(letra_words) or gv
    seq = " ".join(letra_words)
    out = []
    for l in lines:
        if not l.startswith("c:"): out.append(l); continue
        s = l[2:]
        # 1) junta pares "vi tória" quando a palavra inteira existe na letra e o par não aparece separado
        if letra_words:
            parts = re.split(r"(\s+)", s)
            changed = True
            while changed:
                changed = False
                toks = [(m.start(), m.end()) for m in re.finditer(r"\S+", s)]
                for (a0, a1), (b0, b1) in zip(toks, toks[1:]):
                    w1 = re.sub(r"\[[^\]]*\]", "", s[a0:a1]); w2 = re.sub(r"\[[^\]]*\]", "", s[b0:b1])
                    if re.search(r"[,.;:!?]$", w1): continue
                    j = nk(w1 + w2)
                    if j in voc and (nk(w1) + " " + nk(w2)) not in seq and not (nk(w1) in voc and nk(w2) in voc and (nk(w1) + " " + nk(w2)) in seq):
                        s = s[:a1] + s[b0:]; changed = True; break
        if letra_words:
            def jh(m):
                a, b = m.group(1), m.group(2)
                return (a + b) if nk(re.sub(r"\[[^\]]*\]", "", a + b)) in voc else m.group(0)
            for _ in range(3):
                s = re.sub(r"(\S+)\s+-\s+(\S+)", jh, s)
        # 2) palavra com erro de leitura -> palavra da letra oficial mais parecida
        def fixw(m):
            w = m.group(0)
            core = re.sub(r"\[[^\]]*\]", "", w)
            k = nk(core)
            if not k or not letra_words: return w
            if k in voc:
                # mesma palavra: usa a grafia da letra oficial (acentos), se a palavra não tem acorde no meio
                if re.search(r"\w\[", w): return w
                orig = [x for x in letra_orig if nk(x) == k]
                if not orig: return w
                forms = {x.strip(",.;:!?\"“”()").lower() for x in orig}
                if len(forms) > 1: return w     # "e"/"é", "o"/"ó": ambíguo, deixa como está
                o = orig[0].strip(",.;:!?\"“”()")
                lead = re.match(r"^(\[[^\]]*\])*", w).group(0)
                body = w[len(lead):]
                m2 = re.match(r"^([\"“(]*)(.*?)([,.;:!?\"”)]*)$", body)
                if not m2 or nk(m2.group(2)) != k or "[" in m2.group(2): return w
                word = m2.group(2)
                if word[:1].isupper(): o = o[:1].upper() + o[1:]
                elif word.islower(): o = o.lower()
                return lead + m2.group(1) + o + m2.group(3)
            if len(k) < 3 or re.search(r"\w\[", w): return w
            tol = 1 if len(k) < 7 else 2
            best = None
            for c in voc:
                if abs(len(c) - len(k)) <= tol and sc_lev(c, k, tol) <= tol:
                    best = c; break
            if not best: return w
            # troca só as letras (mantém acordes e pontuação no lugar)
            orig = [x for x in letra_orig if nk(x) == best]
            if not orig: return w
            rep = orig[0]
            if core[:1].isupper(): rep = rep[:1].upper() + rep[1:]
            chords = re.findall(r"\[[^\]]*\]", w)
            lead = re.match(r"^(\[[^\]]*\])*", w).group(0)
            punct = re.search(r"[,.;:!?”\"]*$", core).group(0)
            return lead + rep.strip(",.;:!?") + punct + "".join(c for c in chords if c not in lead)
        s = re.sub(r"\S+", fixw, s)
        out.append("c:" + s)
    return out

def sc_lev(a, b, mx):
    if abs(len(a) - len(b)) > mx: return mx + 1
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b); best = i
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            best = min(best, cur[j])
        if best > mx: return mx + 1
        prev = cur
    return prev[-1]

letra_orig = []
if __name__ == "__main__":
    items = load_rows(sys.argv[2:])
    songs = assemble(items)
    slides = json.load(open("letras_slides.json"))
    by_num = {int(x["num"]): x for x in slides["col"] if x["num"]}
    gv = set()
    for x in slides["col"]:
        for sl_ in x["slides"]:
            for ln in sl_: gv |= {nk(w) for w in ln.split() if nk(w)}
    out = []
    for s in songs:
        ref = by_num.get(int(s["num"]))
        lw, letra_orig[:] = [], []
        if ref:
            words = [w for sl_ in ref["slides"] for ln in sl_ for w in re.split(r"\s+", ln) if nk(w)]
            letra_orig.extend(w.lower() if w.isupper() else w for w in words)
            lw = [nk(w) for w in words]
        lines = clean_chords(s["lines"])
        lines = fix_lyrics(lines, lw, gv)
        lines = [x for x in lines if x != "c:" and x.strip() not in ("a:", "i:")]
        head = " ".join(s["head"])
        km = re.search(r"(?i)tonalidade:?\s*([A-G](?:#|b)?m?)", head.replace("Dim", "Dm"))
        key = km.group(1) if km else cp.detect_key(lines, "")
        nc = sum(1 for x in lines if x.startswith("c:") and "[" in x)
        out.append({"num": s["num"], "title": s["title"], "page": s["page"], "key": key, "lines": lines, "nc": nc, "head": s["head"]})
    json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    print(len(out), "louvores;", sum(1 for x in out if x["nc"] >= 3), "com cifra")
