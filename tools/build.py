"""Gera docs/data.js + copia PDFs. Entrada: songs2.json, cadernos.json, pdf/, txt/."""
import json, re, os, shutil, unicodedata, hashlib, subprocess, collections

# Rode a partir da pasta de trabalho (files.json, songs2.json, cadernos.json, letras_slides.json, cifras.json, s2c.json, lyr_only.json, pdf/ e txt/).
TOOLS = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(TOOLS, "..", "docs")

def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()

def tkey(s):
    core = re.sub(r"\(.*?\)", " ", s)
    if len(norm(core).split()) >= 2 or norm(core) == norm(s): s = core
    s = re.sub(r"^(o|a|os|as)\s+", "", norm(s))
    return s

WORD = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ]+$")
CHORD = re.compile(r"^[A-G](b|#)?(m|maj|min|dim|aug|sus)?\d*$")
def lyrics(text):
    words = []
    for line in text.splitlines():
        line = line.replace("_", " ").replace("‿", " ")
        line = re.sub(r"^\s*\d+\s*[.)]\s*", "", line)
        line = re.sub(r"(?<=\w)\s*[-–]\s*(?=\w)", "", line)
        for tok in re.split(r"[\s,.;:!?\"“”'()«»¡¿|]+", line):
            if WORD.match(tok) and not (CHORD.match(tok) and len(tok) <= 3) and (len(tok) > 1 or tok.lower() in "aeoéóàô"):
                words.append(tok)
    return norm(" ".join(words))

_md5 = {}
def md5(fid):
    if fid not in _md5: _md5[fid] = hashlib.md5(open(f"pdf/{fid}.pdf", "rb").read()).hexdigest()
    return _md5[fid]

def page_texts(fid):
    out = subprocess.run(["pdftotext", "-q", f"pdf/{fid}.pdf", "-"], capture_output=True, text=True).stdout
    return out.split("\f")

COL_SHORT = {
    "Louvores Avulsos": "Avulsos", "Louvores Coletânea": "Coletânea",
    "Louvores Coletânea CIAs": "Coletânea CIAs", "Louvores Avulsos CIAs": "Avulsos CIAs",
    "Evangelização CIAs - Outubro/2026": "Evangelização CIAs",
    "Seminário de Louvor Ago/25": "Seminário Ago/25",
    "Equipe de Louvor - Maanaim de Domingos Martins/ES": "Equipe Maanaim",
    "Louvores para Coro Masculino e Quarteto": "Coro Masculino",
    "Trombetas e Festas 2023": "Trombetas e Festas", "Folheto Trombetas e Festas 2024": "Trombetas e Festas",
}
PRIO = {"Avulsos": 0, "Coletânea": 1, "Coletânea CIAs": 2, "Avulsos CIAs": 3, "Evangelização CIAs": 4,
        "Seminário Ago/25": 5, "Equipe Maanaim": 6, "Coro Masculino": 7, "Trombetas e Festas": 8}
CAD_SHORT = {
    "1Z9Cu7MZ2ih9jZadnHVu76Tbx-mgMD10R": "Seminário Abr/26", "1PouOFtKRLZFjzXdKx48oq1JFSzO1C9ca": "Seminário Set/26",
    "1BSfeiw7Uwt53-qTSBJ5zWMN7OtAdBQU-": "Seminário Set/26", "1XyejoSGFYXG2O8ICdulTzxD7WXivrJyg": "Evangelização",
    "13jaR1jpGE07qkouAz9mcbcTHsPXD5GKZ": "Evangelização", "1s3VlCddRfQ_OWJR5zyLRWPZWTuOT_E5M": "T&F 2024",
    "12sRv_ui7nwCuL_V948JAtUrHImE8Y0YV": "T&F 2023",
}
CAD_COL = {"12sRv_ui7nwCuL_V948JAtUrHImE8Y0YV": "Trombetas e Festas", "1s3VlCddRfQ_OWJR5zyLRWPZWTuOT_E5M": "Trombetas e Festas",
           "1XyejoSGFYXG2O8ICdulTzxD7WXivrJyg": "Evangelização CIAs", "13jaR1jpGE07qkouAz9mcbcTHsPXD5GKZ": "Evangelização CIAs"}

def short_group(g):
    g = re.sub(r"Seminário de Louvor\s*-\s*", "Seminário ", g)
    for a, b in [("Janeiro","Jan"),("Fevereiro","Fev"),("Março","Mar"),("Abril","Abr"),("Maio","Mai"),("Junho","Jun"),("Julho","Jul"),("Agosto","Ago"),("Setembro","Set"),("Outubro","Out"),("Novembro","Nov"),("Dezembro","Dez")]:
        g = re.sub(a + r"\s+20(\d\d)", b + r"/\1", g)
    g = re.sub(r"Trombetas e Festas\s+(\d{4})", r"T&F \1", g)
    return g

def nice_title(t):
    t = re.sub(r"\s+", " ", t).strip(" -–")
    if t == t.upper() and len(t) > 3:
        t = t.lower().capitalize()
        t = re.sub(r"\b(deus|jesus|cristo|senhor|pai|israel|canaã|jordão|egito|salvador|cordeiro|barnabé|davi)\b", lambda m: m.group(1).capitalize(), t)
    return t

src = json.load(open("songs2.json"))["songs"]
cads = json.load(open("cadernos.json"))

# ---- 1. junta louvores repetidos (mesmo título) ----
merged = collections.OrderedDict()
for s in sorted(src, key=lambda s: PRIO.get(COL_SHORT.get(s["collection"], ""), 9)):
    col = COL_SHORT.get(s["collection"], s["collection"])
    k = tkey(s["title"])
    grp = short_group(s["group"][-1]) if s["group"] else ""
    docs = [{"id": d["id"], "label": d["label"], "src": grp or col} for d in s["docs"]]
    if k in merged:
        m = merged[k]
        if not m["num"] and s["num"]: m["num"] = s["num"]
        m["also"].append(grp or col)
        m["docs"] += docs
    else:
        merged[k] = {"num": s["num"], "title": s["title"], "col": col, "group": grp,
                     "docs": docs, "also": []}

# ---- 2. páginas dos cadernos ----
added_new = 0
shared_page = set()
for c in cads:
    cnt = collections.Counter(e["page"] for e in c["entries"])
    shared_page |= {(c["id"], p) for p, k in cnt.items() if k > 1}
    starts = sorted({e["page"] for e in c["entries"]})
    for e in c["entries"]:
        nxt = [p for p in starts if p > e["page"]]
        e["end"] = (nxt[0] - 1) if nxt else c["pages"]
for c in cads:
    for e in c["entries"]:
        k = tkey(e["title"])
        if len(k) < 4: continue
        target = merged.get(k)
        if not target:
            for kk, v in merged.items():
                if len(k.split()) >= 3 and (kk.startswith(k) or k.startswith(kk)) and len(kk.split()) >= 3:
                    target = v; break
        doc = {"id": c["id"], "label": c["kind"], "page": e["page"], "end": e["end"], "src": CAD_SHORT.get(c["id"], "Caderno")}
        if target:
            if not any(d["id"] == c["id"] for d in target["docs"]):
                target["docs"].append(doc)
        else:
            merged[k] = {"num": "", "title": nice_title(e["title"]), "col": CAD_COL.get(c["id"], "Trombetas e Festas"),
                         "group": "", "docs": [doc], "also": []}
            added_new += 1

# ---- 2b. letras oficiais (slides de projeção): todos os louvores da Coletânea, CIAs e Avulsos ----
PROPER = ["deus", "jesus", "cristo", "senhor", "espírito santo", "espírito", "israel", "sião", "jerusalém", "canaã", "jordão",
          "egito", "salvador", "cordeiro", "davi", "moisés", "abraão", "jacó", "maranata", "aleluia", "hosana", "rei", "emanuel",
          "calvário", "getsêmani", "gólgota", "belém", "nazaré", "golias", "sansão", "daniel", "elias", "pedro", "paulo",
          "barnabé", "lázaro", "marta", "maria", "noé", "josé", "gideão", "salomão", "jeová", "shekinah", "messias", "pai", "filho",
          "eliseu", "jericó", "babilônia", "sinai", "betel", "isaque", "josué", "samuel", "saul", "jonas", "zaqueu", "bartimeu"]
PROPER_RE = re.compile(r"(?<![\wÀ-ÿ])(" + "|".join(sorted(PROPER, key=len, reverse=True)) + r")(?![\wÀ-ÿ])")
def sentence(line):
    if not line or line != line.upper(): return line
    t = line.lower()
    t = PROPER_RE.sub(lambda m: " ".join(w.capitalize() for w in m.group(1).split()), t)
    t = re.sub(r"^([^\wÀ-ÿ]*)([\wÀ-ÿ])", lambda m: m.group(1) + m.group(2).upper(), t)
    t = re.sub(r"([.!?]\s+)([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t
MARK = re.compile(r"^(coro|bis|final:?|repetir.*|instrumentos?|\(?\d+x\)?|varões|varoas|todos|introdução.*)$", re.I)
def lyric_text(sl):
    out = []
    for slide in sl["slides"]:
        if out: out.append("")
        for ln in slide:
            if MARK.match(ln.strip()): out.append("§" + ln.strip().capitalize())  # marcação (Coro, Bis...)
            else: out.append(sentence(ln))
    txt = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()

LETRAS = []
slides = json.load(open("letras_slides.json"))
# corrige número repetido (ex.: 174 duas vezes e falta 175)
col_nums = [x["num"] for x in slides["col"]]
for i in range(1, len(slides["col"])):
    a, b = slides["col"][i - 1], slides["col"][i]
    if b["num"] == a["num"] and str(int(a["num"]) + 1).zfill(3) not in col_nums: b["num"] = str(int(a["num"]) + 1).zfill(3)

by_num = collections.defaultdict(list)
for v in merged.values():
    m = re.match(r"^(CIA\s*)?([A-Z]?)0*(\d+)$", v["num"] or "")
    if m: by_num[("cia" if m.group(1) else m.group(2).lower(), int(m.group(3)))].append(v)
letras_new = 0
for kind, lst in slides.items():
    for sl in lst:
        text = lyric_text(sl)
        if not text: continue
        title = sentence(re.sub(r"\s+", " ", sl["title"]).strip(" -–"))
        title = re.sub(r"\s*\((bis|2x)\)\s*$", "", title, flags=re.I)
        k = tkey(title)
        target = None
        if kind == "col" and sl["num"]:
            cands = [v for v in by_num.get(("", int(sl["num"])), []) if v["col"] in ("Coletânea", "Equipe Maanaim", "Coro Masculino", "Seminário Ago/25", "Trombetas e Festas")]
            target = cands[0] if cands else None
        elif kind == "cias" and sl["num"]:
            cands = by_num.get(("cia", int(sl["num"])), [])
            target = cands[0] if cands else None
        if not target:
            target = merged.get(k)
            if target and kind in ("col", "cias") and target["num"]:
                mine = sl["num"] if kind == "col" else "CIA " + sl["num"].zfill(3)
                if re.sub(r"\D", "", target["num"]).lstrip("0") != sl["num"].lstrip("0") and not re.match(r"^A\d", target["num"]):
                    target = None   # mesmo título, outro número: é outro louvor
            if target is None and kind in ("col", "cias"):
                k = tkey(sl["title"]) if "(" in sl["title"] else k   # mantém o subtítulo para diferenciar
        LETRAS.append(text)
        doc = {"id": "L%d" % (len(LETRAS) - 1), "label": "Letra", "text": True, "src": "Oficial"}
        if target:
            if not any(d.get("text") for d in target["docs"]):
                target["docs"].append(doc)
            if kind in ("col", "cias") and re.match(r"^A\d", target["num"] or ""):
                target.setdefault("alt", []).append(sl["num"] if kind == "col" else "CIA " + sl["num"].zfill(3))
            if kind in ("col", "cias") and (not target["num"] or target["col"] in ("Equipe Maanaim", "Seminário Ago/25", "Trombetas e Festas", "Evangelização CIAs", "Coro Masculino")) and not re.match(r"^A\d", target["num"] or ""):
                target["num"] = sl["num"] if kind == "col" else "CIA " + sl["num"].zfill(3)
                newcol = "Coletânea" if kind == "col" else "Coletânea CIAs"
                if target["col"] != newcol:
                    target["also"].append(target["group"] or target["col"])
                    target["col"], target["group"] = newcol, ""
        else:
            col = {"col": "Coletânea", "cias": "Coletânea CIAs", "avcias": "Avulsos CIAs", "av": "Avulsos"}[kind]
            num = sl["num"] if kind == "col" else ("CIA " + sl["num"].zfill(3) if kind == "cias" else "")
            key = k if k not in merged else norm(title) + " #" + kind + sl["num"]
            merged[key] = {"num": num, "title": title, "col": col, "group": "", "docs": [doc], "also": []}
            letras_new += 1
print("letras oficiais:", len(LETRAS), "louvores novos só com letra:", letras_new)

# ---- 3. ordena documentos de cada louvor: Cifra > Harmonia > Partitura... e remove repetidos ----
ORDER = {"Cifra": 0, "Harmonia": 1, "Teclado": 2, "Piano": 3, "Partitura": 4, "Base": 5, "Coro": 6, "Letra": 8}
def dorder(d):
    base = d["label"].split(" (")[0]
    return (ORDER.get(base, 7), 1 if d.get("page") else 0)

os.makedirs(f"{OUT}/pdf", exist_ok=True)
keep = set()
txt_cache = {}
def text_of(d):
    if d.get("text"): return re.sub(r"§.*", "", LETRAS[int(d["id"][1:])])
    if d.get("page"):
        if (d["id"], d["page"]) in shared_page: return ""  # página com várias músicas
        if d["id"] not in txt_cache: txt_cache[d["id"]] = page_texts(d["id"])
        pg = txt_cache[d["id"]]
        return "\n".join(pg[d["page"] - 1:d.get("end", d["page"])])
    p = f"txt/{d['id']}.pdf.txt"
    return open(p, errors="ignore").read() if os.path.exists(p) else ""

data = []
for k, s in merged.items():
    docs, hashes = [], set()
    has_main = any(d["label"].split(" (")[0] in ORDER for d in s["docs"])
    for d in sorted(s["docs"], key=dorder):
        if d.get("text"):
            docs.append(d); continue
        if not os.path.exists(f"pdf/{d['id']}.pdf"): continue
        if has_main and d["label"].split(" (")[0] not in ORDER: continue   # parte de instrumento: só se não houver nada melhor
        h = (md5(d["id"]), d.get("page", 0))
        if h in hashes: continue
        hashes.add(h); docs.append(d)
    if not docs: continue
    if any(d.get("text") for d in docs):   # letra oficial em texto substitui as letras em PDF
        docs = [d for d in docs if d.get("text") or d["label"] != "Letra"]
    # rótulos únicos: quando há 2 "Partitura", mostra a origem
    cnt = collections.Counter(d["label"] for d in docs)
    for d in docs:
        if cnt[d["label"]] > 1 or d.get("page"):
            d["show"] = d["label"] + " · " + d["src"]
        else:
            d["show"] = d["label"]
    docs = docs[:6]
    kind = "cifra" if any(d["label"] in ("Cifra", "Harmonia") for d in docs) else \
           ("letra" if all(d["label"] == "Letra" for d in docs) else
            ("parte" if all(d["label"] not in ORDER for d in docs) else "partitura"))
    text = "\n".join(text_of(d) for d in docs)
    for d in docs:
        if not d.get("text"): keep.add(d["id"])
    num = s["num"]
    data.append({
        "n": num, "m": s.get("alt", []), "t": s["title"], "c": s["col"], "g": s["group"], "a": sorted(set(s["also"]) - {s["col"]}),
        "k": kind, "d": [[d["id"], d["show"], d.get("page", 0), d.get("end", 0)] for d in docs],
        "x": lyrics(text)[:5000],
    })

# Cadernos inteiros (busca página a página)
cad_out = []
for c in cads:
    keep.add(c["id"])
    pg = page_texts(c["id"])
    ptxt = [("" if (i < 3 and re.search(r"ndice", t, re.I)) else lyrics(t)[:3000]) for i, t in enumerate(pg)]
    cad_out.append({"id": c["id"], "t": c["title"], "k": c["kind"], "p": ptxt})

def num_sort(n):
    m = re.match(r"(CIA\s*)?([A-Z]?)(\d+)", n or "")
    return (0, (m.group(1) or "") + m.group(2), int(m.group(3))) if m else (1, "", 0)
data.sort(key=lambda d: (PRIO.get(d["c"], 9), num_sort(d["n"]), norm(d["t"])))

# copia PDFs (e apaga os que não são mais usados)
total = 0
for fid in keep:
    dst = f"{OUT}/pdf/{fid}.pdf"
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(f"pdf/{fid}.pdf"):
        shutil.copy(f"pdf/{fid}.pdf", dst)
    total += os.path.getsize(dst)
for fn in os.listdir(f"{OUT}/pdf"):
    if fn[:-4] not in keep: os.remove(f"{OUT}/pdf/{fn}")
sizes = {fid: os.path.getsize(f"{OUT}/pdf/{fid}.pdf") for fid in keep}

# ---- remove louvores que só têm letra (sem cifra nem partitura) ----
antes = len(data)
# (louvores só com letra agora ficam: viram "Cifra (sem acordes)" com a letra oficial)
print("louvores só com letra (mantidos como cifra sem acordes):", sum(1 for s_ in data if all(x[1].startswith("Letra") for x in s_["d"])))
keep = {x[0] for s_ in data for x in s_["d"] if not x[0].startswith(("L", "C:"))} | {c["id"] for c in cads}

# ---- letras para as cifras sem acordes ----
def letra_lines(txt):
    out = []
    for ln in txt.split("\n"):
        if not ln.strip(): out.append("") if out and out[-1] != "" else None; continue
        out.append(("h:" + ln[1:]) if ln.startswith("§") else ("c:" + ln.strip()))
    while out and out[-1] == "": out.pop()
    return out
FUZZY = json.load(open(os.path.join(TOOLS, "letras_por_titulo.json"))) if os.path.exists(os.path.join(TOOLS, "letras_por_titulo.json")) else {}
LYR = json.load(open("lyr_only.json")) if os.path.exists("lyr_only.json") else {}

# ---- coletâneas cifradas novas (pasta CLAUDE do Drive) ----
import difflib as _dl
NEWSRC = []   # (fonte, coleção esperada, número, título, tom, linhas)
def _add_new(path, src, colfn):
    if not os.path.exists(path): return
    for x in json.load(open(path)):
        if x.get("nc", 0) < 3: continue
        col, num = colfn(x)
        NEWSRC.append({"src": src, "col": col, "num": num, "title": x["title"], "k": x.get("key", ""), "l": x["lines"], "page": x.get("page"), "pdf": path.replace(".json", ".pdf")})
_add_new(os.path.join(TOOLS, "coletaneas", "cifras2025.json"), "Coletânea Cifras 2025", lambda x: (None, None))
_add_new(os.path.join(TOOLS, "coletaneas", "cias2024.json"), "Coletânea CIAs 2024",
         lambda x: ("Coletânea CIAs", "CIA " + x["num"].zfill(3)) if x["page"] < 192 else ("Avulsos CIAs", None))
_add_new(os.path.join(TOOLS, "coletaneas", "nivel2.json"), "Coletânea Cifrada Nível II",
         lambda x: ("Coletânea", x["num"].zfill(3)) if x["page"] < 345 else ("Coletânea CIAs", "CIA " + x["num"].zfill(3)))
def _numkey(n):
    m = re.match(r"^(CIA\s*)?([A-Z]?)0*(\d+)$", n or "")
    return ((m.group(1) and "cia") or m.group(2).lower(), int(m.group(3))) if m else None
_by_num = collections.defaultdict(list)
for s_ in data:
    for n in [s_["n"]] + list(s_.get("m", [])):
        k = _numkey(n)
        if k: _by_num[k].append(s_)
_by_title = collections.defaultdict(list)
for s_ in data: _by_title[tkey(s_["t"])].append(s_)
NEW_MATCH, NEW_NEW = 0, 0
RETITLE = {"SALMO 91": "Salmo 91 (Seguro estou nos braços de Deus)"}
NOMATCH = {("Coletânea Cifras 2025", "SALMO 91"), ("Coletânea Cifras 2025", "GRAÇAS TE DOU, Ó SENHOR"),
           ("Coletânea Cifrada Nível II", "LOUVAI AO SENHOR TODAS AS NAÇÕES")}
for x in NEWSRC:
    target = None
    if x["num"]:
        cands = [s_ for s_ in _by_num.get(_numkey(x["num"]), []) if s_["c"] == x["col"] or x["col"] == "Coletânea"]
        # confere o título (a numeração pode mudar entre edições)
        for s_ in cands:
            r = _dl.SequenceMatcher(None, tkey(s_["t"]), tkey(sentence(x["title"]))).ratio()
            if r >= 0.6: target = s_; break
    if target is None:
        c2 = _by_title.get(tkey(sentence(x["title"])), [])
        if c2: target = c2[0]
    if target is None:   # um título é o começo do outro (título cortado ou com subtítulo)
        k0 = tkey(sentence(x["title"]))
        if len(k0.split()) >= 3:
            pref = [lst[0] for k_, lst in _by_title.items() if (k_.startswith(k0 + " ") or k0.startswith(k_ + " ")) and len(k_.split()) >= 3]
            if pref: target = pref[0]
    if target is None:
        best, br = None, 0
        k0 = tkey(sentence(x["title"]))
        for k_, lst in _by_title.items():
            r = _dl.SequenceMatcher(None, k_, k0).ratio()
            if r > br: best, br = lst[0], r
        if br >= 0.9: target = best
    if (x["src"], x["title"]) in NOMATCH:    # título parecido, música diferente (conferido pela letra): só título igual
        target = None if x["title"] in RETITLE else next(iter(_by_title.get(tkey(sentence(x["title"])), [])), None)
    if target is not None:
        lst = target.setdefault("_news", [])
        if not any(y["src"] == x["src"] for y in lst):
            lst.append(x); NEW_MATCH += 1
            continue
        # a mesma coletânea já deu cifra a este louvor: é outra música -> louvor próprio
        same = next((s2 for s2 in _by_title.get(tkey(sentence(x["title"])), []) if s2 is not target), None)
        if same is not None:
            same.setdefault("_news", []).append(x); NEW_MATCH += 1; continue
    # louvor que ainda não existe no site
    col = x["col"] or "Cifras 2025"
    num = x["num"] or ""
    s_ = {"n": num, "m": [], "t": RETITLE.get(x["title"]) or sentence(x["title"]).replace(" ,", ","), "c": col, "g": "", "a": [], "k": "cifra", "d": [], "x": "", "_news": [x]}
    data.append(s_); _by_title[tkey(s_["t"])].append(s_); NEW_NEW += 1
# louvores repetidos no site (mesma música em outra pasta) também usam a cifra
_extra = 0
for s_ in data:
    if s_.get("_news"): continue
    k0 = tkey(s_["t"])
    best, br = None, 0
    for x in NEWSRC:
        if (x["src"], x["title"]) in NOMATCH: continue
        kx = tkey(sentence(x["title"]))
        r = _dl.SequenceMatcher(None, kx, k0).ratio()
        if len(k0.split()) >= 3 and (kx.startswith(k0 + " ") or k0.startswith(kx + " ")) and len(kx.split()) >= 3: r = max(r, 0.93)
        if r > br: best, br = x, r
    if best is not None and br >= 0.92:
        s_["_news"] = [best]; _extra += 1
json.dump([[s_["n"], s_["t"], x["src"], x["num"], x["title"]] for s_ in data for x in s_.get("_news", [])], open("matches.json", "w"), ensure_ascii=False)
print("coletâneas novas:", len(NEWSRC), "cifras;", NEW_MATCH, "em louvores existentes;", NEW_NEW, "louvores novos;", _extra, "repetidos com a mesma cifra")

# ---- cifras em texto (acordes + letra, com troca de tom no app) ----
CIFRAS = {}
_PIPE = {}
if os.path.exists("cifras.json"):
    allc = json.load(open("cifras.json"))
    for s_ in data:
        got = False
        for doc in list(s_["d"]):
            if not doc[1].startswith(("Cifra", "Harmonia")) or doc[0].startswith(("L", "C:")): continue
            key = doc[0] + (":%d" % doc[2] if doc[2] else "")
            if key in allc and not got:
                CIFRAS[key] = {"k": allc[key]["key"], "l": allc[key]["lines"]}
                _PIPE[key] = (f"pdf/{doc[0]}.pdf", list(range(doc[2], (doc[3] or doc[2]) + 1)) if doc[2] else None, not doc[2])
                s_["d"].insert(0, ["C:" + key, "Cifra", 0, 0])
                got = True
            if key in allc:
                doc[1] = doc[1].replace("Cifra", "Cifra (PDF)", 1).replace("Harmonia", "Harmonia (PDF)", 1)
        # cifras das coletâneas (todas viram versões do louvor; a primeira é a principal se não houver outra)
        _PRI = {"Coletânea Cifras 2025": 0, "Coletânea CIAs 2024": 1, "Coletânea Cifrada Nível II": 2}
        _SHORT = {"Coletânea Cifras 2025": "Cifras 2025", "Coletânea CIAs 2024": "CIAs 2024", "Coletânea Cifrada Nível II": "Nível II"}
        _pos = 1 if got else 0
        for x in sorted(s_.get("_news", []), key=lambda y: _PRI.get(y["src"], 9)):
            kk = "N:" + str(int(hashlib.md5((x["src"] + x["title"] + str(x["num"])).encode()).hexdigest(), 16) % 10**10)
            CIFRAS[kk] = {"k": x["k"], "l": x["l"], "src": x["src"]}
            if x.get("page") and "nivel2" not in x["pdf"]: _PIPE[kk] = (x["pdf"], [x["page"], x["page"] + 1], False)
            s_["d"].insert(_pos, ["C:" + kk, "Cifra" if not got else "Cifra · " + _SHORT.get(x["src"], x["src"]), 0, 0]); _pos += 1
            if not s_["x"]: s_["x"] = lyrics("\n".join(re.sub(r"\[[^\]]*\]", "", l[2:]) for l in x["l"] if l[:2] in ("c:", "t:")))[:5000]
            got = True
        # cifra gerada a partir da partitura (acordes da partitura sobre as sílabas)
        if not got and os.path.exists("s2c.json"):
            if "_s2c" not in globals():
                globals()["_s2c"] = json.load(open("s2c.json"))
            for doc in s_["d"]:
                r = _s2c.get(doc[0])
                if not r or r["nch"] < 6 or not any(l.startswith("c:") for l in r["l"]): continue
                good = r["nw"] >= 25 and ((r["hit"] is not None and r["hit"] >= 0.75) or (r["hit"] is None and r.get("gh", 0) >= 0.97))
                fair = r["nw"] >= 12 and ((r["hit"] is not None and r["hit"] >= 0.5) or (r["hit"] is None and r.get("gh", 0) >= 0.85))
                if good or fair:
                    CIFRAS[doc[0]] = {"k": r["k"], "l": r["l"], "g": 1 if good else 2}
                    s_["d"].insert(0, ["C:" + doc[0], "Cifra" if good else "Cifra (revisar)", 0, 0])
                    got = True
                    break
        # sem acordes na partitura: cifra só com a letra (o usuário adiciona os acordes no app)
        if not got:
            lines, src = None, ""
            lid = next((x[0] for x in s_["d"] if re.match(r"^L\d+$", x[0])), None)
            if lid:
                lines, src = letra_lines(LETRAS[int(lid[1:])]), "oficial"
            elif s_["t"] in FUZZY:
                k_, i_ = FUZZY[s_["t"]]
                lines, src = letra_lines(lyric_text(slides[k_][i_])), "oficial"
            elif any(x[1].startswith("Letra") and x[2] for x in s_["d"]):
                x = next(x for x in s_["d"] if x[1].startswith("Letra") and x[2])
                try:
                    import cifra_parse as _cp
                    r_ = _cp.caderno_song(f"pdf/{x[0]}.pdf", x[2], x[3] or x[2], s_["t"]) or _cp.page_doc(f"pdf/{x[0]}.pdf", x[2], x[3] or x[2])
                    ls_ = [("c:" + l[2:]) if l.startswith("t:") else l for l in r_["l" if "l" in r_ else "lines"]]
                    if sum(1 for l in ls_ if l.startswith("c:")) >= 4: lines, src = ls_, "caderno"
                except Exception as e:
                    print("letra caderno falhou", s_["t"], e)
            if not lines and LYR.get(s_["t"]) and LYR[s_["t"]]["q"] >= 0.75:
                lines, src = LYR[s_["t"]]["l"], ("partitura" if LYR[s_["t"]]["q"] >= 0.9 else "revisar")
            if lines:
                CIFRAS["T:" + s_["d"][0][0]] = {"k": "", "l": lines, "g": 3, "s": src}
                s_["d"].insert(0, ["C:T:" + s_["d"][0][0], "Cifra (sem acordes)", 0, 0])
                got = "sem"
        if got:
            s_["k"] = "cifra" if got is True else s_["k"]
            s_["x"] = s_["x"]  # texto de busca já inclui a cifra
print("cifras em texto:", len(CIFRAS))

# ---- recorte das grades: só a parte principal (cifras + melodia + letra) ----
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crop as _crop
from concurrent.futures import ThreadPoolExecutor as _TPE
grade_ids = sorted({x[0] for s_ in data for x in s_["d"] if not x[0].startswith(("L", "C:")) and not x[2] and not x[1].startswith(("Cifra", "Harmonia", "Letra"))})
with _TPE(8) as _ex:
    RECORTES = {fid: r for fid, r in _ex.map(_crop.analyse, grade_ids) if r}
print("grades recortadas:", len(RECORTES), "de", len(grade_ids))

# ---- posições exatas pelos '|' do PDF ----
import pipe_fix as _pf, pdfplumber as _plb
_pst = collections.Counter()
for _k, (_path, _pages, _whole) in _PIPE.items():
    if not os.path.exists(_path): continue
    if _pages is None:
        with _plb.open(_path) as _d: _pages = list(range(1, len(_d.pages) + 1))
    _new, _how = _pf.fix(CIFRAS[_k]["l"], _path, tuple(_pages), _whole)
    _pst[_how.split(":")[0]] += 1
    CIFRAS[_k]["l"] = _new
print("marcas |:", dict(_pst))

# ---- correções conferidas no PDF (casos que a leitura automática não resolve) ----
if os.path.exists(os.path.join(TOOLS, "overrides.json")):
    for _k, _rules in json.load(open(os.path.join(TOOLS, "overrides.json"))).items():
        if _k not in CIFRAS: print("override sem cifra:", _k); continue
        _l = CIFRAS[_k]["l"]
        for _old, _new in _rules:
            _i = 0; _hit = 0
            while _i <= len(_l) - len(_old):
                if _l[_i:_i + len(_old)] == _old: _l[_i:_i + len(_old)] = _new; _hit += 1; _i += len(_new)
                else: _i += 1
            if not _hit: print("override não aplicado:", _k, _old)

# ---- acabamento das cifras: sequências de acordes soltas viram linha de acordes; 7 9 -> 7(9) ----
import cifra_parse as _cp
def _fixch(ch):
    return re.sub(r"^([A-G](?:#|b)?m?)7(9|11|13)(?=\(|$|/)", r"\g<1>7(\2)", ch)
def _post(lines):
    out = []
    for l in lines:
        if l.startswith("h:"):
            toks = [t.strip("(),.:") for t in l[2:].split()]
            if sum(1 for t in toks if t and _cp.CHORD.match(t)) >= 2:
                l = "t:" + l[2:]
        if l.startswith(("c:", "a:", "i:")):
            l = re.sub(r"\[([^\]]+)\]", lambda m: "[" + _fixch(m.group(1)) + "]", l)
        elif l.startswith("t:"):
            toks = l[2:].split()
            core = [t.strip("(),.[]:") for t in toks]
            nch = sum(1 for t in core if t and _cp.CHORD.match(t))
            words = [t for t in core if t and not _cp.CHORD.match(t)]
            lead = next((j for j, t in enumerate(core) if not (t and _cp.CHORD.match(t))), len(core))
            if lead >= 3 or nch and nch >= 2 * len(words) or (nch >= 2 and re.match(r"(?i)^\(?(instr|final|intro)", l[2:])):
                def br(m):
                    t = m.group(0); c = t.strip("(),.[]:")
                    return t.replace(c, "[" + _fixch(c) + "]") if c and _cp.CHORD.match(c) else t
                l = "i:" + re.sub(r"\S+", br, l[2:])
        out.append(l)
    return out
_np = 0
for _k, _c in CIFRAS.items():
    _new = _post(_c["l"])
    if _new != _c["l"]: _np += 1
    _c["l"] = _new
print("cifras com acabamento:", _np)

ver = hashlib.sha1(json.dumps([data, cad_out, RECORTES, CIFRAS], sort_keys=True).encode()).hexdigest()[:10]
# dados divididos: lista (leve, carrega na hora), busca na letra e conteúdo (carregam depois)
for d_ in data:
    for k_ in [k_ for k_ in d_ if k_.startswith("_")]: del d_[k_]
BUSCA = [d_.pop("x", "") for d_ in data]
J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
with open(f"{OUT}/data.js", "w") as f:
    f.write("window.LOUVORES=" + J(data) + ";\n")
    f.write("window.RECORTES=" + json.dumps(RECORTES, separators=(",", ":")) + ";\n")
    f.write("window.CADERNOS=" + J([dict({k: v for k, v in c.items() if k != "p"}, n=len(c["p"])) for c in cad_out]) + ";\n")
    f.write("window.ARQUIVOS=" + json.dumps(sizes, separators=(",", ":")) + ";\n")
    f.write(f"window.DATA_VERSION={json.dumps(ver)};\n")
with open(f"{OUT}/busca.js", "w") as f:
    f.write("window.BUSCA=" + J(BUSCA) + ";\n")
    f.write("window.BUSCA_CAD=" + J([c["p"] for c in cad_out]) + ";\n")
    f.write("window.__lv&&__lv('busca');\n")
with open(f"{OUT}/conteudo.js", "w") as f:
    f.write("window.LETRAS=" + J(LETRAS) + ";\n")
    f.write("window.CIFRAS=" + J(CIFRAS) + ";\n")
    f.write("window.__lv&&__lv('conteudo');\n")
for fn_ in ("data.js", "busca.js", "conteudo.js"):
    print(fn_, round(os.path.getsize(f"{OUT}/{fn_}") / 1e6, 2), "MB")
print("louvores", len(data), "novos de cadernos", added_new, "arquivos", len(keep), "MB", round(total / 1e6, 1), "versão", ver)
print(collections.Counter(d["c"] for d in data))
print(collections.Counter(d["k"] for d in data))

# ---- service worker (lista de arquivos do app + versão) ----
shell = ["./", "index.html", "style.css", "app.js", "data.js", "busca.js", "conteudo.js", "manifest.webmanifest", "lib/pdf.min.mjs", "lib/pdf.worker.min.mjs"]
for sub in ["icons", "img", "fonts", "lib/standard_fonts"]:
    for fn in sorted(os.listdir(f"{OUT}/{sub}")):
        if not fn.endswith(".txt"): shell.append(f"{sub}/{fn}")
code_ver = hashlib.sha1(b"".join(open(f"{OUT}/{p}", "rb").read() for p in shell if p != "./")).hexdigest()[:10]
tpl = open("sw.template.js").read().replace("__VERSION__", code_ver).replace("__FILES__", json.dumps(shell))
open(f"{OUT}/sw.js", "w").write(tpl)
print("sw versão", code_ver, len(shell), "arquivos do app")
