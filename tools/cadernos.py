"""Descobre que música está em que página de cada caderno (PDF com vários louvores)."""
import json, re, subprocess, unicodedata

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", s).split()

def key(s):
    s = re.sub(r"\(.*?\)", " ", s)
    return " ".join(norm(s))

def pages(fid):
    out = subprocess.run(["pdftotext", "-q", "-layout", f"pdf/{fid}.pdf", "-"], capture_output=True, text=True).stdout
    return out.split("\f")

def columns(line):
    return [c.strip() for c in re.split(r"\s{3,}|​", line) if c.strip()]

KIND = lambda t: "Cifra" if re.search(r"cifr", t, re.I) else ("Letra" if re.search(r"letra|folha", t, re.I) else "Partitura")

def analyse(cad):
    pg = pages(cad["id"])
    titles = []  # (title, printed page or None)
    for p, txt in enumerate(pg[:3]):
        if "NDICE" not in txt.upper(): continue
        for line in txt.splitlines():
            for m in re.finditer(r"([A-Za-zÀ-ÿ!?¡¿][^\d]{3,80}?)[\s.​…]{2,}(\d{1,3})(?=\s{2,}|\s*$)", line):
                t = m.group(1).strip(" .​…")
                if not re.search(r"ndice", t, re.I): titles.append((t, int(m.group(2))))
    if not titles:
        for p, txt in enumerate(pg):
            for line in txt.splitlines():
                for c in columns(line):
                    m = re.match(r"^\d{2}\s*[-–]\s*([A-Za-zÀ-ÿ].{3,90})$", c)
                    if m:
                        t = re.sub(r"\s*\((Let|Avulso|Mús|Coletânea|\d).*$", "", m.group(1)).strip()
                        titles.append((t, None))
    # tira duplicados (mesmo título)
    seen, uniq = set(), []
    for t, pp in titles:
        k = key(t)
        if len(k) < 4 or k in seen: continue
        seen.add(k); uniq.append((t, pp))
    keys = [key(t) for t, _ in uniq]
    ptxt = [" ".join(norm(x)) for x in pg]
    listy = [sum(1 for k in keys if k in pt) >= 4 for pt in ptxt]  # páginas de índice/lista
    res = []
    for (t, printed), k in zip(uniq, keys):
        cands = [i for i, pt in enumerate(ptxt) if k in pt and not listy[i]]
        if printed and (printed - 1) in cands: page = printed
        elif printed and printed - 1 < len(pg) and not cands: page = printed
        elif cands: page = cands[0] + 1
        else:
            alls = [i for i, pt in enumerate(ptxt) if k in pt]
            page = (printed or (alls[-1] + 1 if alls else None))
        if page: res.append({"title": t, "page": page})
    return res, [re.sub(r"\s+", " ", x) for x in pg]

if __name__ == "__main__":
    d = json.load(open("songs2.json"))
    out = []
    for c in d["cadernos"]:
        entries, texts = analyse(c)
        c = dict(c, kind=KIND(c["title"]), entries=entries, pages=len(texts))
        out.append(c)
        print("==", c["title"], c["pages"], "pág;", len(entries), "músicas")
        for e in entries[:60]: print("   ", e["page"], e["title"])
    json.dump(out, open("cadernos.json", "w"), ensure_ascii=False, indent=1)
