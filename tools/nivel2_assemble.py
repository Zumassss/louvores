"""Monta as cifras da Coletânea Cifrada Nível II a partir das páginas lidas por scan_build.py.

Uso: python3 nivel2_assemble.py saida.json pagina1.jsonl [pagina2.jsonl ...]
"""
import json, re, sys, collections, unicodedata
import cifra_parse as cp
import scan_build as sb
import score2cifra as sc

HEAD = re.compile(r"^\s*(\d{1,3})\s*[-–—.]+\s*([A-ZÀ-Ý0-9][^a-zà-ÿ]{2,})$")
META = re.compile(r"(?i)^\(?\s*(let|letra|m[uú]s|arr|trad|vers)|tonalidade|ritmo|\(\s*let|/\s*m[uú]s")
LABEL = re.compile(r"(?i)^(coro|instrumentos?|instrumental|repetir.*|bis|final|ponte|solo|interl[uú]dio|todos|varões|varoas|vozes.*|\d+\s*x)(\s+(\d+\s*x|final|no\s.{0,20}))?\s*(\([^)]*\))?\s*:?$")
INLINE = re.compile(r"(?i)^(introdu[cç][aã]o|final|instrumentos?|instrumental|interl[uú]dio|solo|ponte)\s*:")
CH = re.compile(r"^" + cp.CH + r"$")

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

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "Fb": 4, "E#": 5, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11, "Cb": 11, "B#": 0}
MAJOR = [0, 2, 4, 5, 7, 9, 11]
def scale_names(key):
    """Notas do tom escritas como na partitura (com # ou b)."""
    m = re.match(r"^([A-G])(#|b)?(m?)", key or "")
    if not m: return None
    root = NOTE[m.group(1) + (m.group(2) or "")]
    minor = bool(m.group(3))
    steps = [0, 2, 3, 5, 7, 8, 10, 11] if minor else MAJOR   # menor harmônica inclui a sensível
    letters = "CDEFGAB"
    li = letters.index(m.group(1))
    names = set()
    degs = [0, 2, 3, 5, 7, 8, 10] if minor else MAJOR
    for k, st in enumerate(degs):
        L = letters[(li + k) % 7]; pc = (root + st) % 12
        diff = (pc - NOTE[L]) % 12
        names.add(L + {0: "", 1: "#", 11: "b", 2: "##", 10: "bb"}.get(diff, ""))
    if minor:   # sensível (V maior)
        L = letters[(li + 6) % 7]; pc = (root + 11) % 12; diff = (pc - NOTE[L]) % 12
        names.add(L + {0: "", 1: "#", 11: "b"}.get(diff, ""))
    return names

def norm_chord(t):
    if t.startswith("!"):
        n = norm_chord(t[1:]); return ("!" + n) if n else None
    t = t.replace("bb", "b")
    t = re.sub(r"^([A-G][#b]?)([A-G][#b]?)$", r"\1/\2", t)                 # AG -> A/G
    t = re.sub(r"^([A-G][#b]?m?\d*)[il1|I]([A-G][#b]?)$", r"\1/\2", t)       # DiF -> D/F
    if CH.match(t): return t
    for k in range(len(t) - 1, 0, -1):                                        # maior pedaço válido do começo
        if CH.match(t[:k]): return t[:k]
    return None

def chord_pcs(root, rest):
    r = NOTE.get(root)
    if r is None: return None, None
    minor = bool(re.match(r"^m(?!aj)", rest))
    dim = bool(re.search(r"dim|º|°", rest))
    third = 3 if (minor or dim) else 4
    fifth = 6 if dim else (8 if "aug" in rest or "+" in rest else 7)
    tones = {0, third, fifth}
    if re.search(r"maj7", rest): tones.add(11)
    elif re.search(r"7", rest): tones.add(10)
    return r, tones

def fits(root, rest, sc_pcs):
    """Acorde cabe no tom: tríade do campo harmônico, ou dominante (X7) com fundamental no tom."""
    r, tones = chord_pcs(root, rest)
    if r is None: return False
    tri = {(r + t) % 12 for t in tones if t in (0, 3, 4, 6, 7, 8)}
    if tri <= sc_pcs: return True
    if r in sc_pcs and re.match(r"^7", rest) and not re.match(r"^m", rest): return True
    return False

def key_fix(c, sc_names):
    """Acerta # e b que o OCR perdeu, usando o tom.
    - tom com sustenidos: só acrescenta '#'; tom com bemóis: só acrescenta 'b';
    - acidente lido de verdade fica (exceto E#/B#, que viram F#/C#);
    - só troca se o original não cabe no tom e o corrigido cabe."""
    if not sc_names: return c
    sc_pcs = {NOTE[n] for n in sc_names if n in NOTE}
    sharp_key = any(n.endswith("#") for n in sc_names) and not any(n.endswith("b") for n in sc_names)
    flat_key = any(n.endswith("b") for n in sc_names) and not any(n.endswith("#") for n in sc_names)
    m = re.match(r"^([A-G][#b]?)([^/]*)(?:/([A-G][#b]?))?$", c)
    if not m: return c
    root, rest, bass = m.group(1), m.group(2), m.group(3)
    if root in ("E#", "B#", "Fb", "Cb"):
        root = {"E#": "F#", "B#": "C#", "Fb": "E", "Cb": "B"}[root]
    elif len(root) == 1 and not fits(root, rest, sc_pcs):
        alt = root + ("#" if sharp_key else "b" if flat_key else "")
        if alt != root and alt in NOTE and fits(alt, rest, sc_pcs): root = alt
    out = root + rest
    if bass:
        if bass in ("E#", "B#", "Fb", "Cb"): bass = {"E#": "F", "B#": "C", "Fb": "E", "Cb": "B"}[bass]
        r, tones = chord_pcs(root, rest)
        def is_tone(n): return r is not None and NOTE.get(n) is not None and (NOTE[n] - r) % 12 in tones
        if len(bass) == 1 and not is_tone(bass):
            alt = bass + ("#" if sharp_key else "b" if flat_key else "")
            if alt in NOTE and is_tone(alt): bass = alt
        out += "/" + bass
    return out

def best_key(chords, header):
    """Tom pelos acordes; o do cabeçalho vale se combinar quase tão bem."""
    keys = [r + q for r in ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"] for q in ("", "m")]
    def score(k):
        sc_names = scale_names(k); pcs = {NOTE[n] for n in sc_names if n in NOTE}
        tot = 0
        for c in chords:
            m = re.match(r"^([A-G][#b]?)([^/]*)", c)
            if m and fits(m.group(1), m.group(2), pcs): tot += 1
        first_last = [re.match(r"^([A-G][#b]?m?)", x).group(1) for x in (chords[:1] + chords[-1:]) if re.match(r"^[A-G]", x)]
        return tot + 0.5 * sum(1 for f in first_last if f == k)
    if not chords: return header
    scored = {k: score(k) for k in keys}
    sharps = sum(c.count("#") for c in chords); flats = sum(1 for c in chords if re.match(r"^[A-G]b", c))
    pref = "#" if sharps >= flats else "b"
    best = max(scored, key=lambda k: (scored[k], (pref in k) or (len(k.rstrip("m")) == 1)))
    if header in scored and scored[header] >= scored[best] * 0.9: return header
    return best

def clean_chords(lines, key=""):
    """Corrige leituras duvidosas: formato, acidentes pelo tom e A6 x Ab."""
    sc_names = scale_names(key)
    def fixc(c):
        c = norm_chord(c)
        if not c: return None
        if c.startswith("!"): return c          # conferido no desenho: não mexe
        return key_fix(c, sc_names)
    stage = [re.sub(r"\[([^\]]+)\]", lambda m: "[" + (fixc(m.group(1)) or "") + "]", l).replace("[]", "") for l in lines]
    allc = [c for l in stage for c in re.findall(r"\[([^\]]+)\]", l)]
    cnt = collections.Counter(allc)
    def fix6(m):
        c = m.group(1)
        if c.startswith("!"): return "[" + c[1:] + "]"
        mm = re.match(r"^([A-G])6(.*)$", c)
        if mm and cnt.get(mm.group(1) + "b" + mm.group(2), 0) >= 1: c = mm.group(1) + "b" + mm.group(2)
        return "[" + c + "]"
    return [re.sub(r"\[([^\]]+)\]", fix6, l) for l in stage]

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
            rest = [w for w in it["words"] if not INLINE.match(w[0] + ":") and not re.match(r"(?i)^(introdu|final|instrument)", w[0])]
            if it["chords"] and rest:      # "Final: |Para tua |glória..." -> título + verso com acordes
                cur["lines"].append("h:" + lab)
                cur["lines"].append("c:" + sb.lyric_with_chords(dict(it, words=rest)))
                continue
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
            # '|' preto: a linha de acordes fica logo acima da letra, que ficou sem acordes -> liga pela posição x
            if nxt and nxt["words"] and nxt["col"] == it["col"] and not nxt["chords"] and not nxt.get("tail") and 15 <= nxt["y"] - it["y"] <= 90 \
                    and not INLINE.match(nxt["text"]) and not LABEL.match(nxt["text"].strip()):
                nxt["chords"] = [(x, c) for x, c in it["inline"]]
                continue
            if ch_inline: cur["lines"].append("a:" + " ".join("[" + c + "]" for c in ch_inline))
            continue
        if LABEL.match(txt):
            if re.match(r"(?i)^bis$", txt): continue
            cur["lines"].append("h:" + txt.rstrip(":")); continue
        if txt.startswith("(") and not it["chords"] and it["inline"]:     # "(D para repetir)"
            cur["lines"].append("i:" + sb.lyric_with_chords(dict(it, chords=it["inline"]))); continue
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
        # 0) restos do '|' lidos como apóstrofo/aspas no meio da palavra ("encon't[E]rei")
        s = re.sub(r"(?<=[A-Za-zÀ-ÿ\]])['’‘`´“”\"](?=[A-Za-zÀ-ÿ\[])", "", s)
        s = re.sub(r"(?<=\s)['’‘`´](?=[A-Za-zÀ-ÿ\[])", "", s)
        s = re.sub(r"^['’‘`´](?=[A-Za-zÀ-ÿ\[])", "", s)
        # 0b) sequência de sílabas separadas por hífen ("A - le lui- a" -> "Aleluia")
        if voc:
            toks = s.split(" ")
            out_t, i = [], 0
            while i < len(toks):
                best = None
                for j in range(min(len(toks), i + 8), i + 1, -1):
                    seg = toks[i:j]
                    if not any("-" in t for t in seg): continue
                    joined = "".join(t for t in seg if t not in ("-", "–", "="))
                    core = re.sub(r"\[[^\]]*\]", "", joined).replace("-", "")
                    if len(nk(core)) >= 4 and nk(core) in voc and re.search(r"[A-Za-zÀ-ÿ]", core):
                        best = (j, joined.replace("-", "") if "-" not in "".join(letra_orig_forms.get(nk(core), [""])) else joined); break
                if best:
                    out_t.append(best[1].replace("=", "")); i = best[0]
                else:
                    out_t.append(toks[i]); i += 1
            s = " ".join(out_t)
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
letra_orig_forms = {}
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
            letra_orig_forms.clear()
            for w in words: letra_orig_forms.setdefault(nk(w), []).append(w)
            lw = [nk(w) for w in words]
        head = " ".join(s["head"])
        km = re.search(r"(?i)tonalidade:?\s*([A-G](?:#|b|♯|♭)?\s?m?)", head.replace("Dim", "Dm").replace("Em ", "Em"))
        key = km.group(1).replace(" ", "").replace("♯", "#").replace("♭", "b") if km else ""
        raw = [(norm_chord(c) or "").lstrip("!") for l in s["lines"] for c in re.findall(r"\[([^\]]+)\]", l)]
        key = best_key([c for c in raw if c], key)
        lines = clean_chords(s["lines"], key)
        if not key: key = cp.detect_key(lines, "")
        lines = fix_lyrics(lines, lw, gv)
        lines = [x for x in lines if x != "c:" and x.strip() not in ("a:", "i:")]
        nc = sum(1 for x in lines if x.startswith("c:") and "[" in x)
        out.append({"num": s["num"], "title": s["title"], "page": s["page"], "key": key, "lines": lines, "nc": nc, "head": s["head"]})
    json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    print(len(out), "louvores;", sum(1 for x in out if x["nc"] >= 3), "com cifra")
