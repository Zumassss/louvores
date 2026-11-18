"""Conta quantos louvores da lista 'sem partitura e sem acordes' ganharam cifra de verdade."""
import json, csv, re, collections, sys
L = open('/home/user/louvores/docs/data.js').read().split('\n')
d = json.loads(L[0][L[0].index('=') + 1:-1])
C = json.loads(L[2][L[2].index('=') + 1:-1])
def key(c, n, t): return (c, (n or "").strip(), t.strip().lower())
idx = {}
for s in d:
    idx[key(s["c"], s["n"], s["t"])] = s
rows = list(csv.reader(open('/home/user/louvores/listas/louvores_sem_partitura_e_sem_acordes.csv', encoding='utf-8-sig'), delimiter=';'))[1:]
com, sem = [], []
for col, num, tit in rows:
    s = idx.get(key(col, num, tit))
    if not s:
        cand = [x for x in d if x["c"] == col and x["n"] == num and num] or [x for x in d if x["t"].lower() == tit.lower()]
        s = cand[0] if cand else None
    ok = False
    if s:
        for doc in s["d"]:
            if doc[0].startswith("C:") and doc[1].startswith("Cifra") and "sem acordes" not in doc[1]:
                c = C.get(doc[0][2:])
                if c and any("[" in l for l in c["l"] if l.startswith("c:")): ok = True; break
    (com if ok else sem).append((col, num, tit))
print("da lista de", len(rows), ":", len(com), "ganharam cifra;", len(sem), "continuam sem")
print(collections.Counter(c for c, _, _ in sem))
if len(sys.argv) > 1:
    json.dump(sem, open(sys.argv[1], "w"), ensure_ascii=False)
