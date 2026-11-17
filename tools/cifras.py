import json, re, sys
import cifra_parse as cp
L = open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'docs', 'data.js')).read().split('\n')
d = json.loads(L[0][L[0].index('=') + 1:-1])
cads = {c["id"]: c for c in json.load(open('cadernos.json'))}
out, stats = {}, []
for s in d:
    for doc in s['d']:
        fid, lab, page, end = doc
        if not lab.startswith(('Cifra', 'Harmonia')): continue
        key = fid + (":%d" % page if page else "")
        if key in out: continue
        try:
            if page:
                ent = next((e for e in cads[fid]["entries"] if e["page"] == page and cp.norm(e["title"])[:2] == cp.norm(e["title"])[:2]), None)
                titles = [e["title"] for e in cads[fid]["entries"] if e["page"] == page]
                r = None
                # tenta o título do caderno que corresponde a este louvor
                cand = sorted(titles, key=lambda t: -len(set(cp.norm(t)) & set(cp.norm(s['t']))))
                for t in cand:
                    r = cp.caderno_song(f"pdf/{fid}.pdf", page, end or page, t)
                    if r: break
                if not r: r = cp.page_doc(f"pdf/{fid}.pdf", page, end or page)
            else:
                r = cp.whole_doc(f"pdf/{fid}.pdf")
        except Exception as e:
            print("ERRO", s['t'], e); r = None
        if not r or not r["lines"]: print("VAZIO", s['t'], key); continue
        nc = sum(1 for l in r["lines"] if l.startswith("c:"))
        na = sum(1 for l in r["lines"] if l.startswith("a:"))
        nt = sum(1 for l in r["lines"] if l.startswith("t:"))
        if nc < 4 or nc / max(1, nc + na + nt) < 0.4:
            print("FORA (não é cifra em texto)", s['t'], key, nc, na, nt); continue
        out[key] = r
        stats.append((s['t'], key, r["key"], nc, na, nt))
json.dump(out, open('cifras.json', 'w'), ensure_ascii=False)
print(len(out), "cifras")
for st in sorted(stats, key=lambda x: x[3] / max(1, x[3] + x[4] + x[5])):
    print(st)
