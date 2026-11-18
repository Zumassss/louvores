"""Aplica as leituras novas dos acordes (final_read) nas linhas do OCR da Nível II -> n2/all_fixed.jsonl.
Acordes conferidos ganham '!' na frente (o montador não mexe neles pelo tom)."""
import numpy as np, glob, json, re, collections
from PIL import Image
import synth

src = open("final_read.py").read()
ns = {}
exec(src.split("a0, a1 =")[0], ns)          # funções e dados do leitor final
fine_score, rr, POOL_EXT = ns["fine_score"], ns["rr"], ns["EXT"]
POOL_EXT = POOL_EXT + ["sus4(9)", "sus4(7)", "9(sus4)", "sus4(6)", "9(#11)"]

meta = ns["meta"]; imgs = ns["imgs"]; fixed = ns["fixed"]
F = json.load(open("tk/final_read.json"))
N = len(meta)

def to_site(s):
    s = re.sub(r"^([A-G][#b]?)07", r"\1°7", s)
    s = re.sub(r"^([A-G][#b]?)0", r"\1°", s)
    return s

def read_free(img):
    """lê um pedaço sem ajuda do OCR: todas as letras, acidentes e extensões comuns"""
    tw = synth.width_of(img); tv = rr["fine"](img, tw)
    best = (-9, "")
    for r in "ABCDEFG":
        for a in ("", "#", "b"):
            for q in ("", "m"):
                for e in POOL_EXT[:16]:
                    if q == "m" and e in ("0", "07"): continue
                    s = r + a + q + e
                    sc = fine_score(img, tw, tv, s)
                    if sc > best[0]: best = (sc, s)
    return best

# pedaços: acordes grudados ("G/B C") viram dois
parts = []   # (pg, x0, y0, x1, y1, leitura, confiável)
nsplit = 0
for i in range(N):
    pg, x0, y0, x1, y1 = [int(v) for v in meta[i]]
    a = imgs[i]
    col = (a > 80).any(0); w = np.where(col)[0]
    reading, sc, tag = F[i]
    trusted = tag in ("ok", "ajustado", "ok+dim", "ajustado+dim") and sc >= 0.55
    split = None
    if len(w):
        col = col[:w.max() + 1]; run = 0; st = 0
        for x, c in enumerate(col):
            if not c:
                if run == 0: st = x
                run += 1
            else:
                if run >= 5 and tag not in ("ok",):
                    nxt = a[:, x:x + 6] > 80; rows = np.where(nxt.any(1))[0]
                    if len(rows) and rows.max() >= 28 and rows.min() <= 6: split = (st, x); break
                run = 0
    if split:
        sc_px = (y1 - y0) / 32.0
        A = np.zeros_like(a); A[:, :split[0]] = a[:, :split[0]]
        B = np.zeros_like(a); B[:, :a.shape[1] - split[1]] = a[:, split[1]:]
        ra, rb = read_free(A), read_free(B)
        if ra[0] > 0.6 and rb[0] > 0.6:
            xm = x0 + int(split[1] * sc_px)
            parts.append((pg, x0, y0, xm - 2, y1, to_site(ra[1]), True))
            parts.append((pg, xm, y0, x1, y1, to_site(rb[1]), True))
            nsplit += 1
            continue
    parts.append((pg, x0, y0, x1, y1, to_site(reading) if reading else "", trusted))
print("acordes separados:", nsplit)

bypg = collections.defaultdict(list)
for k, p in enumerate(parts): bypg[p[0]].append(k)
out = open("n2/all_fixed.jsonl", "w")
st = collections.Counter()
for l in open("n2/all.jsonl"):
    r = json.loads(l); pg = r["page"]; cand = bypg.get(pg, [])
    used = set(); boxof = {}
    for row in r["rows"]:
        for key in ("chords", "inline"):
            newl = []
            for x, t in row.get(key, []):
                chy = row.get("chy") if key == "chords" else None
                best, bd = None, 1e9
                for k in cand:
                    if k in used: continue
                    _, px0, py0, px1, py1, rd, tr = parts[k]
                    if chy is not None:
                        if not (-8 <= chy - py1 <= 50 and abs(px0 - x) <= 30): continue
                        d = abs(px0 - x) + abs(chy - py1)
                    else:
                        if not (py0 - 25 <= row["y"] <= py1 + 25 and abs(px0 - x) <= 40): continue
                        d = abs(px0 - x) + abs(row["y"] - py0)
                    if d < bd: best, bd = k, d
                if best is not None and parts[best][5]:
                    used.add(best)
                    rd, tr = parts[best][5], parts[best][6]
                    nt = ("!" if tr else "") + rd
                    st["trocado" if rd != t else "igual"] += 1
                    newl.append([x, nt]); boxof[(id(row), key, len(newl) - 1)] = parts[best]
                else:
                    st["sem leitura nova"] += 1
                    newl.append([x, t])
            if key in row: row[key] = newl
    # acordes do livro que nenhum '|' pegou (o OCR perdeu): ficam registrados para conferência
    # acordes numa linha só de acordes (sem '|' embaixo): vão para o verso da mesma altura dos outros acordes, ou para o verso logo abaixo
    HEADM = re.compile(r"^\s*\d{1,3}\s*[-–—.]+\s*[A-ZÀ-Ý0-9]|(?i:tonalidade|ritmo|\(?\s*let\b|m[uú]s\.)")
    lyr = [row for row in r["rows"] if row.get("words") and not HEADM.search(row["text"])]
    for row in r["rows"]:
        if row.get("words") or not row.get("inline"): continue
        keep = []
        for j, (x, t) in enumerate(row["inline"]):
            b = boxof.get((id(row), "inline", j))
            if b is None or not t or not re.match(r"^!?[A-G]", t): keep.append([x, t]); continue
            _, px0, py0, px1, py1, rd, tr = b
            same = None
            for lr in lyr:
                if lr["col"] != row["col"]: continue
                for jj in range(len(lr.get("chords", []))):
                    bb = boxof.get((id(lr), "chords", jj))
                    if bb and abs(bb[2] - py0) <= 14: same = lr; break
                if same: break
            if same is None:
                below = [lr for lr in lyr if lr["col"] == row["col"] and 0 < lr["y"] - py1 < 75]
                if below: same = min(below, key=lambda lr: lr["y"])
            if same is None: keep.append([x, t]); continue
            same.setdefault("chords", []).append([px0 + 3, t]); same["chords"].sort(key=lambda c: c[0])
            if same.get("chy") is None: same["chy"] = same["y"]
            st["acorde sem | posicionado"] += 1
        row["inline"] = keep
    r["orphans"] = []
    for k in cand:
        if k in used or not parts[k][5]: continue
        _, px0, py0, px1, py1, rd, tr = parts[k]
        # verso logo abaixo do acorde
        rows = [row for row in r["rows"] if row.get("words") and not re.search(r"^\s*\d{1,3}\s*[-–—.]+\s*[A-ZÀ-Ý0-9]|(?i:tonalidade|ritmo|\(?\s*let\b|m[uú]s\.)", row["text"]) and 0 < row["y"] - py1 < 70
                and min(w[1] for w in row["words"]) - 40 <= px0 <= max(w[2] for w in row["words"]) + 60]
        if tr and rows:
            row = min(rows, key=lambda row: row["y"] - py1)
            row.setdefault("chords", []).append([px0 + 3, "!" + rd])
            row["chords"].sort(key=lambda c: c[0])
            if row.get("chy") is None: row["chy"] = row["y"]
            st["órfão encaixado"] += 1
        else:
            r["orphans"].append(parts[k][1:])
    out.write(json.dumps(r, ensure_ascii=False) + "\n")
    st["órfãos"] += len(r["orphans"])
out.close()
print(dict(st))
