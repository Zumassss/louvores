import json, re, sys, collections, unicodedata
import score2cifra as sc
from concurrent.futures import ProcessPoolExecutor
targets = json.load(open("targets.json"))
L = open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'docs', 'data.js')).read().split('\n')
d = json.loads(L[0][L[0].index('=') + 1:-1])
letras = json.loads(L[1][L[1].index('=') + 1:-1])
by_t = {s["t"]: s for s in d}
def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z ]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).split()
def nk(w):
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))
def vocab_of(title):
    s = by_t.get(title)
    if not s: return set()
    for x in s["d"]:
        if re.match(r"^L\d+$", x[0]): return {nk(w) for w in re.split(r"[\s,.;:!?()]+", letras[int(x[0][1:])]) if nk(w)}
    return set()
GV = set()
for txt in letras:
    GV |= {nk(w) for w in re.split(r"[\s,.;:!?()§\-]+", txt) if nk(w)}
def job(t):
    title, fid, lab = t
    try:
        lines, nch, nsyl = sc.to_cifra(sc.convert(f"pdf/{fid}.pdf"))
        voc = vocab_of(title) or GV
        if voc: lines = [("c:" + sc.fix_words(l[2:], voc)) if l.startswith("c:") else l for l in lines]
    except Exception as e:
        return title, fid, None, str(e)
    return title, fid, {"k": sc.key_of(lines), "l": lines, "nch": nch, "nsyl": nsyl}, None
out, rep = {}, []
with ProcessPoolExecutor(8) as ex:
    for title, fid, r, err in ex.map(job, targets):
        if not r: rep.append((title, "ERRO", err)); continue
        words = norm(" ".join(re.sub(r"\[[^\]]*\]", "", l[2:]) for l in r["l"] if l.startswith("c:")))
        s = by_t.get(title)
        lw = []
        if s:
            for x in s["d"]:
                if re.match(r"^L\d+$", x[0]): lw = norm(letras[int(x[0][1:])])
        ref = set(lw) if lw else None
        hit = (sum(1 for w in words if w in ref) / max(1, len(words))) if ref else None
        gh = sum(1 for w in words if "".join(w) in GV) / max(1, len(words))
        r["hit"] = hit; r["nw"] = len(words); r["gh"] = gh
        out[fid] = r
        rep.append((title, r["nch"], r["nsyl"], len(words), None if hit is None else round(hit, 2)))
json.dump(out, open("s2c.json", "w"), ensure_ascii=False)
for fid, r in out.items():
    r["ok"] = r["nch"] >= 8 and r["nw"] >= 25 and ((r["hit"] is not None and r["hit"] >= 0.75) or (r["hit"] is None and r["gh"] >= 0.9))
json.dump(out, open("s2c.json", "w"), ensure_ascii=False)
ok = [r for r in out.values() if r["ok"]]
print("sem referência aprovadas:", sum(1 for r in ok if r["hit"] is None), "de", sum(1 for r in out.values() if r["hit"] is None))
print("total", len(rep), "aprovadas", len(ok))
print("sem acordes/letra:", sum(1 for x in rep if x[1] != "ERRO" and (x[1] < 8 or x[3] < 25)))
print("letra divergente:", [x for x in rep if x[1] != "ERRO" and x[1] >= 8 and x[3] >= 25 and x[4] is not None and x[4] < 0.7][:15])
print("erros:", [x for x in rep if x[1] == "ERRO"][:5])
