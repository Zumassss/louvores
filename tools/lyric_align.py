"""Corrige a letra das cifras da Nível II com a letra oficial (slides), mantendo os acordes na mesma sílaba.

Para cada verso: acha o trecho da letra oficial mais parecido (comparando só as letras, sem acento),
troca o texto pelo oficial (maiúsculas como no livro) e remapeia cada acorde letra a letra.
Uso: python3 lyric_align.py novas/nivel2.json [saida.json]
"""
import json, re, sys, unicodedata, difflib, collections

def base(ch):
    return unicodedata.normalize("NFD", ch.lower())[0] if ch.strip() else ch

def letters(s):
    """letras normalizadas + índice de cada uma no texto original"""
    out, idx = [], []
    for i, ch in enumerate(s):
        if ch.isalnum():
            out.append(base(ch)); idx.append(i)
    return "".join(out), idx

def parse(line):
    """'c:Je[E]sus, ó' -> ('Jesus, ó', [(2, 'E')])"""
    text, chords = "", []
    for part in re.split(r"(\[[^\]]*\])", line):
        if part.startswith("[") and part.endswith("]"): chords.append((len(text), part[1:-1]))
        else: text += part
    return text, chords

def build(text, chords):
    out, last = "", 0
    for pos, ch in sorted(chords, key=lambda c: c[0]):
        out += text[last:pos] + "[" + ch + "]"; last = pos
    return out + text[last:]

CAP = {"deus", "jesus", "cristo", "senhor", "espirito", "salvador", "pai", "rei", "cordeiro", "emanuel", "israel", "jerusalem", "siao", "davi", "abraao", "maranata", "redentor", "consolador", "mestre", "filho", "verbo"}

class Official:
    def __init__(self, slides):
        words = [w for sl in slides for ln in sl for w in ln.split()]
        self.words = words
        self.norm = [letters(w)[0] for w in words]

    def best(self, target, maxspan=None):
        """melhor trecho (i, j) de palavras oficiais para o texto normalizado target"""
        n = len(self.norm); L = len(target)
        if L < 4: return None
        best = (0, None)
        for i in range(n):
            acc = ""
            for j in range(i, min(n, i + 40)):
                acc += self.norm[j]
                if len(acc) > L * 1.35 + 3: break
                if len(acc) < L * 0.65 - 3: continue
                r = difflib.SequenceMatcher(None, target, acc, autojunk=False).ratio()
                if r > best[0]: best = (r, (i, j + 1))
        return best

def recase(new_words, ocr_text, first_upper):
    """maiúsculas: primeira palavra do verso como no livro; nomes de Deus etc. com maiúscula; resto minúsculo"""
    out = []
    ocr_caps = {letters(w)[0] for w in re.findall(r"\w+", ocr_text)[1:] if w[:1].isupper()}
    for k, w in enumerate(new_words):
        lw = w.lower()
        key = letters(w)[0]
        if (k == 0 and first_upper) or key in CAP or (key in ocr_caps and k > 0 and key not in ("o", "a", "e", "os", "as", "de", "do", "da", "em", "eu", "que", "se", "me", "te")):
            # mantém pontuação do começo ("“Es" -> "“Es")
            m = re.match(r"^(\W*)(\w)(.*)$", lw)
            lw = (m.group(1) + m.group(2).upper() + m.group(3)) if m else lw
        out.append(lw)
    return " ".join(out)

def align_line(line, off):
    text, chords = parse(line[2:])
    tnorm, tidx = letters(text)
    core = re.sub(r"\s*\((bis|\d+\s*x)\)\s*$", "", text, flags=re.I)
    b = off.best(letters(core)[0])
    if not b or b[1] is None or b[0] < 0.78: return line, False
    i, j = b[1]
    first_upper = bool(re.match(r"^\W*[A-ZÀ-Ý]", text.strip()))
    new = recase(off.words[i:j], text, first_upper)
    # mantém o que vier antes/depois do verso que não é letra ((bis), *, aspas)
    pre = re.match(r"^[\s*“\"(]*", text).group(0)
    suf = re.search(r"\s*\((bis|\d+x)\)\s*$", text, re.I)
    new = pre.strip() + (" " if pre.strip() else "") + new + (suf.group(0) if suf else "")
    nnorm, nidx = letters(new)
    sm = difflib.SequenceMatcher(None, tnorm, nnorm, autojunk=False)
    amap = {}
    for a, bb, size in sm.get_matching_blocks():
        for k in range(size): amap[a + k] = bb + k
    newch = []
    for pos, ch in chords:
        # primeira letra do texto antigo a partir da posição do acorde
        k = next((q for q, ti in enumerate(tidx) if ti >= pos), None)
        if k is None: newch.append((len(new), ch)); continue
        # a letra pode ter sido trocada: usa a próxima que casou (ou a anterior + 1)
        q = k
        while q < len(tnorm) and q not in amap: q += 1
        if q < len(tnorm):
            tgt = amap[q] - (q - k)
            tgt = max(0, tgt)
            np_ = nidx[tgt] if tgt < len(nidx) else len(new)
        else:
            p = k
            while p >= 0 and p not in amap: p -= 1
            np_ = (nidx[amap[p]] + 1) if p >= 0 else 0
        # acorde no começo de palavra fica no começo da palavra
        if pos == 0 or (pos <= len(text) and pos > 0 and not text[pos - 1].isalnum()):
            ws = np_
            while ws > 0 and new[ws - 1].isalnum(): ws -= 1
            # só volta ao começo da palavra nova se ela não junta letras de palavras antigas anteriores
            inv = {v: u for u, v in amap.items()}
            wl = next((q for q, ni in enumerate(nidx) if ni >= ws), None)
            ok_ = wl is not None and wl in inv and inv[wl] >= k
            if ok_: np_ = ws
        newch.append((np_, ch))
    return line[:2] + build(new, newch), True

_POOL = None
def _pool(S):
    """todas as letras oficiais: slides (todas as listas) + letras oficiais do site"""
    global _POOL
    if _POOL is None:
        _POOL = []
        for L in ("col", "cias", "av", "avcias"):
            for x in S[L]: _POOL.append(x)
        try:
            L0 = open("/home/user/louvores/docs/data.js").read().split("\n")
            LET = json.loads(L0[1][L0[1].index("=") + 1:-1])
            for t in LET:
                ls = [ln for ln in re.sub(r"§.*", "", t).split("\n") if ln.strip()]
                if ls: _POOL.append({"num": "", "title": ls[0], "slides": [ls]})
        except Exception: pass
        for x in _POOL:
            x["_w"] = set(w for w in (letters(w)[0] for w in " ".join(" ".join(sl) for sl in x["slides"]).split()) if len(w) > 3)
    return _POOL

def pick_by_text(song, S):
    sw = set(w for w in (letters(w)[0] for l in song["lines"] if l[:2] in ("c:", "t:") for w in parse(l[2:])[0].split()) if len(w) > 3)
    if len(sw) < 5: return None
    best, br = None, 0
    for x in _pool(S):
        if not x["_w"]: continue
        r = len(sw & x["_w"]) / len(sw)
        if r > br: best, br = x, r
    return best if br >= 0.6 else None

def pick_official(song, S):
    r = _pick_official(song, S)
    return r or pick_by_text(song, S)

def _pick_official(song, S):
    def k(t): return letters(t)[0]
    lst = S["cias"] if song["page"] >= 345 else S["col"]
    num = int(song["num"]) if str(song["num"]).isdigit() else None
    cand = [x for x in lst if x["num"] and num is not None and int(x["num"]) == num]
    tt = k(song["title"])
    for x in cand:
        kt = k(x["title"])
        if difflib.SequenceMatcher(None, tt, kt).ratio() >= 0.55 or kt.startswith(tt[:12]) or (len(kt) >= 5 and tt.startswith(kt)): return x
    # pelo título em todas as listas
    best, br = None, 0
    for L in ("col", "cias", "av", "avcias"):
        for x in S[L]:
            r = difflib.SequenceMatcher(None, tt, k(x["title"])).ratio()
            if r > br: best, br = x, r
    return best if br >= 0.85 else None

SECOES = ["Dedicação", "Louvor", "Grupo de Louvor", "Morte, Ressurreição e Salvação", "Corinhos", "Volta de Jesus e Eternidade",
          "Clamor", "Consolo e Encorajamento", "Invocação e Comunhão", "Salmos de Louvor", "Santificação e Derramamento do Espírito Santo",
          "Crianças e Adolescentes", "Crianças", "e Adolescentes"]
_SEC = [letters(x)[0] for x in SECOES]
def lixo(line):
    """cabeçalho de seção do livro, restos do logotipo, letras soltas: não é letra do louvor"""
    if "[" in line: return False
    t = line[2:].strip()
    n = letters(t)[0]
    if len(n) <= 3 and not re.match(r"(?i)^(bis|ó|oh|ah|ai|amém)$", t): return True
    if n in ("maran", "anata", "ata", "ino", "ibis", "aranata", "nata", "osenh", "orjesusvem", "osenhorj", "osenhorje", "susver", "susem", "mnosam", "valseado", "biis"): return True
    if n in ("maranata", "osenhor", "jesusvem") and sum(ch.isupper() for ch in t) >= 0.7 * sum(ch.isalpha() for ch in t): return True   # logotipo do livro
    if re.match(r"(?i)^\s*\d{3,5}\s*\(?\s*let", t) or re.search(r"\b[A-Z]{2,3}[:.][A-Z.]{2,}", t) and len(t) < 30: return True
    if re.match(r"(?i)^(crian[cç]as e adolescentes|santifica[cç][aã]o e derramam)", t): return True
    if re.search(r"\b(Trad|Adap|Let|M[uú]s|Arr|Harm)\.", t) or re.fullmatch(r"[^a-z]*[A-Z]\.[^a-z]*\)\s*", t): return True   # créditos
    parts = [p for p in re.split(r"\s+[—–-]\s+", t) if p]
    return all(any(difflib.SequenceMatcher(None, letters(p)[0], sx).ratio() >= 0.85 for sx in _SEC) for p in parts)

def split_align(line, off):
    """verso que o livro repete na mesma linha ("arcanjos vos prostrai, arcanjos vos prostrai"): alinha cada pedaço"""
    body = line[2:]
    segs = re.split(r"(?<=[,;!?.])\s+", body)
    if len(segs) < 2: return line, False
    out = []
    for sg in segs:
        nl, ok = align_line("c:" + sg, off)
        if not ok: return line, False
        out.append(nl[2:])
    return line[:2] + " ".join(out), True

import cifra_parse as _cp
def snap_syllables(line):
    """acorde no meio de uma sílaba vai para o começo dela (no livro o '|' marca sempre começo de sílaba)"""
    if not line.startswith("c:"): return line
    text, chords = parse(line[2:])
    out = []
    for pos, ch in chords:
        if 0 < pos < len(text) and text[pos - 1].isalpha() and text[pos].isalpha():
            a = pos
            while a > 0 and (text[a - 1].isalpha() or text[a - 1] in "’'"): a -= 1
            b = pos
            while b < len(text) and (text[b].isalpha() or text[b] in "’'"): b += 1
            st = [a + k for k in _cp.syllable_starts(text[a:b])]
            if pos not in st:
                pos = max([x for x in st if x < pos], default=a)
        out.append((pos, ch))
    return line[:2] + build(text, out)

def restore_split(lines):
    """linha só de acordes + verso sem acordes igual a outro verso da música com os mesmos acordes -> usa aquele"""
    out = list(lines)
    full = {}
    for l in lines:
        if l.startswith("c:") and "[" in l:
            t, ch = parse(l[2:])
            if len(letters(t)[0]) >= 4: full.setdefault(letters(t)[0], []).append((sorted(c for _, c in ch), l))
    k = 0; res = []
    while k < len(out):
        l = out[k]
        if l.startswith("c:") and k + 1 < len(out) and out[k + 1].startswith("c:") and "[" not in out[k + 1]:
            t, ch = parse(l[2:])
            if ch and len(letters(t)[0]) <= 1:
                nxt = letters(parse(out[k + 1][2:])[0])[0]
                m = next((ln for cs, ln in full.get(nxt, []) if cs == sorted(c for _, c in ch)), None)
                if m: res.append(m); k += 2; continue
        res.append(l); k += 1
    return res

if __name__ == "__main__":
    S = json.load(open("letras_slides.json"))
    songs = json.load(open(sys.argv[1]))
    st = collections.Counter()
    LFIX = json.load(open("line_fix.json")) if __import__("os").path.exists("line_fix.json") else {}
    SFIX = json.load(open("song_fix.json")) if __import__("os").path.exists("song_fix.json") else {}
    IFIX = json.load(open("intro_fix.json")) if __import__("os").path.exists("intro_fix.json") else {}
    for s in songs:
        for key, fx in IFIX.items():                       # introduções conferidas na imagem
            num, page, first = key.split("|", 2)
            if num != str(s["num"]) or page != str(s["page"]): continue
            L = s["lines"]; old = fx["old"]
            for p in range(len(L) - len(old) + 1):
                if L[p:p + len(old)] == old:
                    s["lines"] = L[:p] + fx["new"] + L[p + len(old):]; st["introdução corrigida"] += 1; break
        k_ = f"{s['num']}|{s['page']}"
        if k_ in SFIX: s["lines"] = SFIX[k_]; st["música conferida à mão"] += 1; continue
        ref = pick_official(s, S)
        if not ref: st["sem letra oficial"] += 1; continue
        off = Official(ref["slides"])
        st["com letra oficial"] += 1
        out = []
        for l in s["lines"]:
            if l.startswith(("c:", "t:")) and lixo(l): st["lixo removido"] += 1; continue
            if re.match(r"(?i)^[ct]:\s*(cantar|cantam|canta o coro|voltar|repetir|obs:|final\s*[:;]?\s*$|\(?\s*na \d|invertendo as vozes|as vozes\.)", l) and "[" not in l:
                out.append("h:" + l[2:].strip().replace("º", "ª").rstrip(";")); st["instrução como título"] += 1; continue
            if l.startswith("c:") or (l.startswith("t:") and len(l) > 10):
                nl, ok = align_line(l, off)
                if not ok: nl, ok = split_align(l, off)
                if ok and nl.startswith("t:") and "[" not in nl: pass
                st["verso corrigido" if ok and nl != l else ("verso igual" if ok else "verso sem par")] += 1
                out.append(nl)
            else: out.append(l)
        s["lines"] = [snap_syllables(l) for l in restore_split(out)]
        for o_, n_ in LFIX.get(f"{s['num']}|{s['page']}", []):
            if o_ in s["lines"]:
                p_ = s["lines"].index(o_); s["lines"][p_:p_ + 1] = n_; st["verso conferido à mão"] += 1
            else: st["conferido não aplicado"] += 1

    json.dump(songs, open(sys.argv[2] if len(sys.argv) > 2 else sys.argv[1], "w"), ensure_ascii=False, indent=1)
    print(dict(st))
