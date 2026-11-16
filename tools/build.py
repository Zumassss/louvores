"""Gera docs/data.js + copia PDFs. Entrada: songs2.json, cadernos.json, pdf/, txt/."""
import json, re, os, shutil, unicodedata, hashlib, subprocess, collections

# Rode a partir da pasta de trabalho (com files.json, songs2.json, cadernos.json, pdf/ e txt/).
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

# ---- 3. ordena documentos de cada louvor: Cifra > Harmonia > Partitura... e remove repetidos ----
ORDER = {"Cifra": 0, "Harmonia": 1, "Teclado": 2, "Piano": 3, "Partitura": 4, "Base": 5, "Coro": 6, "Letra": 8}
def dorder(d):
    base = d["label"].split(" (")[0]
    return (ORDER.get(base, 7), 1 if d.get("page") else 0)

os.makedirs(f"{OUT}/pdf", exist_ok=True)
keep = set()
txt_cache = {}
def text_of(d):
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
        if not os.path.exists(f"pdf/{d['id']}.pdf"): continue
        if has_main and d["label"].split(" (")[0] not in ORDER: continue   # parte de instrumento: só se não houver nada melhor
        h = (md5(d["id"]), d.get("page", 0))
        if h in hashes: continue
        hashes.add(h); docs.append(d)
    if not docs: continue
    # rótulos únicos: quando há 2 "Partitura", mostra a origem
    cnt = collections.Counter(d["label"] for d in docs)
    for d in docs:
        if cnt[d["label"]] > 1 or d.get("page"):
            d["show"] = d["label"] + " · " + d["src"]
        else:
            d["show"] = d["label"]
    docs = docs[:6]
    kind = "cifra" if any(d["label"] in ("Cifra", "Harmonia") for d in docs) else \
           ("parte" if all(d["label"] not in ORDER for d in docs) else "partitura")
    text = "\n".join(text_of(d) for d in docs)
    for d in docs: keep.add(d["id"])
    num = s["num"]
    data.append({
        "n": num, "t": s["title"], "c": s["col"], "g": s["group"], "a": sorted(set(s["also"]) - {s["col"]}),
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

ver = hashlib.sha1(json.dumps([data, cad_out], sort_keys=True).encode()).hexdigest()[:10]
with open(f"{OUT}/data.js", "w") as f:
    f.write("window.LOUVORES=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    f.write("window.CADERNOS=" + json.dumps(cad_out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    f.write("window.ARQUIVOS=" + json.dumps(sizes, separators=(",", ":")) + ";\n")
    f.write(f"window.DATA_VERSION={json.dumps(ver)};\n")
print("louvores", len(data), "novos de cadernos", added_new, "arquivos", len(keep), "MB", round(total / 1e6, 1), "versão", ver)
print(collections.Counter(d["c"] for d in data))
print(collections.Counter(d["k"] for d in data))

# ---- service worker (lista de arquivos do app + versão) ----
shell = ["./", "index.html", "style.css", "app.js", "data.js", "manifest.webmanifest", "lib/pdf.min.mjs", "lib/pdf.worker.min.mjs"]
for sub in ["icons", "img", "fonts", "lib/standard_fonts"]:
    for fn in sorted(os.listdir(f"{OUT}/{sub}")):
        if not fn.endswith(".txt"): shell.append(f"{sub}/{fn}")
code_ver = hashlib.sha1(b"".join(open(f"{OUT}/{p}", "rb").read() for p in shell if p != "./")).hexdigest()[:10]
tpl = open(os.path.join(TOOLS, "sw.template.js")).read().replace("__VERSION__", code_ver).replace("__FILES__", json.dumps(shell))
open(f"{OUT}/sw.js", "w").write(tpl)
print("sw versão", code_ver, len(shell), "arquivos do app")
