import json, re, unicodedata, collections, sys

def n(s):
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()

files = json.load(open("files.json")) + json.load(open("files2.json"))
files = [x for x in files if "pdf" in x["kind"] or x["name"].lower().endswith(".pdf")]

CADERNOS = {"1Z9Cu7MZ2ih9jZadnHVu76Tbx-mgMD10R": "Letras — Seminário de Louvor Abril 2026",
            "1PouOFtKRLZFjzXdKx48oq1JFSzO1C9ca": "Cifras — Seminário de Louvor Setembro 2026",
            "1BSfeiw7Uwt53-qTSBJ5zWMN7OtAdBQU-": "Letras — Seminário de Louvor Setembro 2026",
            "1XyejoSGFYXG2O8ICdulTzxD7WXivrJyg": "Caderno de Partituras — Evangelização das CIAs (Out/2026)",
            "13jaR1jpGE07qkouAz9mcbcTHsPXD5GKZ": "Louvores Cifrados — Evangelização das CIAs (Out/2026)",
            "1s3VlCddRfQ_OWJR5zyLRWPZWTuOT_E5M": "Folha de Louvores Oficial — Trombetas e Festas 2024",
            "12sRv_ui7nwCuL_V948JAtUrHImE8Y0YV": "Cifras — Trombetas e Festas 2023"}

GROUP_DIRS = re.compile(r"^(sopro|sopros|cordas|base|vocal|vozes|madeiras|metais|percuss|arr\b|arranjo|partes|pdf|partituras|instrumentos|grade|audio|audios|playback|kit)")

def stem(name):
    s = re.sub(r"\.pdf$", "", name, flags=re.I).strip()
    m = re.match(r"^((?:CIA\s*)?[A-Z]?\d{1,3})\s*-\s*(.+)$", s)
    if m:
        return m.group(1) + " - " + re.split(r"\s+-\s+|_|\s*\[", m.group(2))[0].strip()
    s = re.split(r"\s+-\s+|_|\s*\[", s)[0].strip()
    s = re.sub(r"^\d{3,5}\s*-\s*", "", s)  # "7805-Comigo habitas"
    return s

def song_key(x):
    p = list(x["path"])
    while len(p) > 2 and (GROUP_DIRS.match(n(p[-1])) or re.fullmatch(r"[A-G][#b]?m?\d?", p[-1]) or "modula" in n(p[-1])):
        p.pop()
    last = p[-1]
    if len(p) == 1 or len(last) <= 2 or n(last).startswith(("seminario", "equipe de louvor", "trombetas e festas")):
        p = p + [stem(x["name"])]
    return tuple(p)

INSTR = [  # (regex, preferência como parte substituta, rótulo)
    (r"cordas", 9, "Cordas"), (r"violino ?i\b|violino ?1|violin ?i\b|violin ?1|violino\b|violin\b", 8, "Violino"),
    (r"flaut|flute|piccolo|flautim", 7, "Flauta"), (r"viola\b", 6, "Viola"), (r"violonc|cello", 6, "Violoncelo"),
    (r"sax", 5, "Saxofone"), (r"clarin", 5, "Clarinete"), (r"oboe", 5, "Oboé"), (r"trompet|trumpet|flugel", 4, "Trompete"),
    (r"trombon", 3, "Trombone"), (r"trompa|horn", 3, "Trompa"), (r"fagot|bassoon", 2, "Fagote"),
    (r"bombard|eufon|euphon", 2, "Bombardino"), (r"tuba|contrabai|contrabass|baixo|bass\b", 1, "Baixo"),
    (r"timpan|carrilh|harpa|bateria|percus|glock|xilof|marimba", 0, "Percussão"),
]

def classify(x):
    nm = n(x["name"][:-4] if x["name"].lower().endswith(".pdf") else x["name"])
    tail = nm.split(" - ", 1)[1] if " - " in nm else nm
    if re.search(r"cifr|violao|guitar|acorde|chord", nm): return ("cifra", 100, "Cifra")
    if re.search(r"harmonia", tail): return ("cifra", 90, "Harmonia")
    if re.search(r"letra|lyrics", tail): return ("letra", 50, "Letra")
    if re.search(r"teclad|keyboard", tail): return ("partitura", 80, "Teclado")
    if re.search(r"piano", tail): return ("partitura", 75, "Piano")
    if re.search(r"partitura|full ?score|grade|score|regencia|maestro", tail): return ("partitura", 60, "Grade")
    if re.search(r"\bbase\b", tail): return ("partitura", 55, "Base")
    for rx, pref, lab in INSTR:
        if re.search(rx, tail): return ("parte", pref, lab)
    if re.search(r"coro|coral|choir|vocal|voz|vozes|melodia|soprano|tenor\b|alto\b|masculin", tail): return ("partitura", 40, "Coro")
    for rx, pref, lab in INSTR:
        if re.search(rx, nm): return ("parte", pref, lab)
    return ("partitura", 45, "Partitura")

songs = collections.defaultdict(list)
cadernos = []
for x in files:
    if x["id"] in CADERNOS:
        cadernos.append({"id": x["id"], "title": CADERNOS[x["id"]], "collection": x["path"][0]}); continue
    songs[song_key(x)].append(x)

PRIO = {"Louvores Avulsos": 0, "Louvores Coletânea": 1, "Louvores Coletânea CIAs": 2, "Louvores Avulsos CIAs": 3,
        "Evangelização CIAs - Outubro/2026": 4, "Seminário de Louvor Ago/25": 5,
        "Equipe de Louvor - Maanaim de Domingos Martins/ES": 6, "Louvores para Coro Masculino e Quarteto": 7}

out = []
for key, fs in songs.items():
    seen, uniq = set(), []
    for f in fs:
        k = n(f["name"])
        if k in seen: continue
        seen.add(k); uniq.append((f, classify(f)))
    by = lambda kind: sorted([u for u in uniq if u[1][0] == kind], key=lambda u: -u[1][1])
    docs = []
    cif, par, let, parte = by("cifra"), by("partitura"), by("letra"), by("parte")
    if cif: docs.append({"id": cif[0][0]["id"], "label": cif[0][1][2]})
    if par: docs.append({"id": par[0][0]["id"], "label": "Partitura" if par[0][1][2] in ("Grade", "Partitura") else par[0][1][2]})
    for u in par[1:]:
        mm = re.search(r"\((com|sem) modula", n(u[0]["name"]))
        if mm and u[1][1] == par[0][1][1]:
            docs[-1]["label"] = "Partitura (" + ("sem" if mm.group(1) == "com" else "com") + " modulação)" if "modula" in n(par[0][0]["name"]) else docs[-1]["label"]
            docs.append({"id": u[0]["id"], "label": "Partitura (" + mm.group(1) + " modulação)"})
    if let: docs.append({"id": let[0][0]["id"], "label": "Letra"})
    if not cif and not par and parte:
        docs.append({"id": parte[0][0]["id"], "label": parte[0][1][2]})
    if not docs: continue
    kind = "cifra" if cif else ("partitura" if par else ("parte" if parte else "letra"))

    raw = key[-1]
    m = re.match(r"^\s*((?:CIA\s*)?[A-Z]?\d{1,4})\s*[-–.]\s*(.+)$", raw)
    num, title = (m.group(1).strip(), m.group(2).strip()) if m else ("", raw.strip())
    if re.fullmatch(r"\d{1,4}", title):            # pasta só com número
        num = num or title
        best = (cif or par or let or parte)[0][0]
        title = stem(best["name"])
    title = re.sub(r"\s+", " ", re.sub(r"\.pdf$", "", title, flags=re.I)).strip(" -")
    if title and title == title.upper() and len(title) > 4:  # TUDO MAIÚSCULO -> Capitalizado
        title = title.capitalize()
    group = [g for g in key[1:-1] if len(g) > 2]
    out.append({"collection": key[0], "num": num, "title": title, "docs": docs, "type": kind,
                "group": group, "prio": PRIO.get(key[0], 9)})

json.dump({"songs": out, "cadernos": cadernos}, open("songs2.json", "w"), ensure_ascii=False, indent=1)
print("songs", len(out), collections.Counter(o["type"] for o in out))
print(collections.Counter(o["collection"] for o in out))
print("docs", sum(len(o["docs"]) for o in out))
