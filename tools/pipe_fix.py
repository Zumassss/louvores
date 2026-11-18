"""Corrige cifras já montadas usando a leitura exata pelos '|' do PDF."""
import re, unicodedata, functools
import pdfplumber
import cifra_parse as cp
import pipe_parse as pp

def norm(s):
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if ch.isalpha())

_pdfs = {}
@functools.lru_cache(maxsize=None)
def page_lines(path, pg):
    if path not in _pdfs: _pdfs[path] = pdfplumber.open(path)
    pdf = _pdfs[path]
    if pg < 1 or pg > len(pdf.pages): return [], {"pipes": 0, "sem_acorde": 0, "acordes_soltos": 0, "flags": []}
    try: return pp.page(pdf, pg)
    except Exception: return [], {"pipes": 0, "sem_acorde": 0, "acordes_soltos": 0, "flags": []}

META = re.compile(r"(?i)^(let(ra)?\.?|m[uú]s(ica)?\.?|harm\.?|trad\.?|arr\.?|vers[aã]o|adapt\.?|tom|tonalidade|ritmo|compasso|andamento|autor)\b")

def chords_of(l): return re.findall(r"\[([^\]]+)\]", l)

def fix(lines, path, pages, whole):
    pl, st, fl = [], {"pipes": 0, "sem_acorde": 0, "acordes_soltos": 0, "sem_marca": 0}, []
    for pg in pages:
        a, s = page_lines(path, pg); pl += a; fl += s.get("flags", [False] * len(a))
        for k in st: st[k] += s.get(k, 0)
    if st["pipes"] < 4: return lines, "sem-marcas"
    good = {}
    for l in pl:
        if l.startswith("c:") and "|" not in l:
            n = norm(l[2:])
            if len(n) >= 4: good.setdefault(n, l)
    if whole and st["sem_acorde"] == 0 and st["acordes_soltos"] == 0 and st["sem_marca"] == 0:
        out, started = [], False
        for l in pl:
            if not started:
                if l.startswith("t:"):
                    t = l[2:].strip()
                    toks = [x.strip("(),.:") for x in t.split()]
                    chordish = sum(1 for x in toks if x and cp.CHORD.match(x)) >= 2
                    if not (cp.INLINE.match(t) or re.match(r"(?i)^introd", t) or chordish): continue
                else: started = l.startswith(("c:", "a:"))
            if l.startswith("t:") and cp.LABEL.match(l[2:].strip()): l = "h:" + l[2:].strip()
            out.append(l)
        return out, "inteira"
    # troca linha a linha, na ordem (o mesmo verso pode repetir com acordes diferentes)
    import difflib
    A = [norm(l[2:]) if l.startswith(("c:", "t:")) else "\x00%d" % k for k, l in enumerate(lines)]
    PL = [l for l, f in zip(pl, fl) if l.startswith("c:") and f]
    B = [norm(l[2:]) for l in PL]
    out = list(lines); nrep = 0
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal": continue
        for a_, b_ in zip(range(i1, i2), range(j1, j2)):
            g = PL[b_]
            if len(B[b_]) >= 4 and g != lines[a_] and chords_of(g) and len(chords_of(g)) >= len(chords_of(lines[a_])) - 1:
                out[a_] = g; nrep += 1
    return out, ("linhas:%d" % nrep) if nrep else "igual"
