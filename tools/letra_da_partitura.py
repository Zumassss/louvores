import json, re, unicodedata, gzip, os, spellchecker, sys
import score2cifra as sc
L = open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'docs', 'data.js')).read().split('\n')
d = json.loads(L[0][L[0].index('=') + 1:-1]); letras = json.loads(L[1][L[1].index('=') + 1:-1])
def nk(w):
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))
GV = set()
for t in letras: GV |= {nk(w) for w in re.split(r"[\s,.;:!?()§\-]+", t) if nk(w)}
_pt = json.load(gzip.open(os.path.join(os.path.dirname(spellchecker.__file__), "resources", "pt.json.gz")))
PT = {nk(w) for w, f in _pt.items() if f >= 40 and len(nk(w)) >= 3}
V = GV | PT
miss = [s for s in d if not any(x[0].startswith("C:") for x in s["d"]) and not any(x[0].startswith("L") for x in s["d"])]
out = {}
for s in miss:
    pdfs = [x[0] for x in s["d"] if not x[0].startswith(("L", "C:")) and not x[2]]
    best = None
    for fid in pdfs:
        try:
            lines, _, nsyl = sc.to_cifra(sc.convert_lyrics(f"pdf/{fid}.pdf"))
        except Exception as e:
            continue
        lines = [("c:" + sc.fix_words(l[2:], V)) if l.startswith("c:") else l for l in lines if not l.startswith("i:")]
        words = [nk(w) for l in lines for w in re.sub(r"\[[^\]]*\]", "", l[2:]).split() if nk(w)]
        q = sum(1 for w in words if w in V) / max(1, len(words))
        if len(words) >= 15 and (best is None or q > best[0]):
            best = (q, fid, lines, len(words))
    out[s["t"]] = best and {"q": best[0], "fid": best[1], "l": best[2], "nw": best[3]}
json.dump(out, open("lyr_only.json", "w"), ensure_ascii=False)
ok = {k: v for k, v in out.items() if v and v["q"] >= 0.9}
print("sem letra oficial:", len(miss), "letra extraída boa:", len(ok), "fraca:", sum(1 for v in out.values() if v and v["q"] < 0.9), "nenhuma:", sum(1 for v in out.values() if not v))
for k in list(ok)[:3]:
    print("==", k, round(ok[k]["q"], 2)); print("\n".join([x for x in ok[k]["l"] if x][:4]))
