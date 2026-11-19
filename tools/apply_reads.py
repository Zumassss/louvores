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
part_tok = []
ROWSPLIT = set()   # 2ª linha de uma introdução em duas linhas: vira linha só de acordes
import os
PROP = json.load(open("tk/propagated.json")) if os.path.exists("tk/propagated.json") else {}
MANUAL = json.load(open("tk/manual.json")) if os.path.exists("tk/manual.json") else {}
nsplit = 0
for i in range(N):
    pg, x0, y0, x1, y1 = [int(v) for v in meta[i]]
    a = imgs[i]
    col = (a > 80).any(0); w = np.where(col)[0]
    reading, sc, tag = F[i]
    trusted = ("+sfx" in tag or tag.split("+")[0] in ("ok", "ajustado")) and sc >= 0.55 or "+sfx" in tag
    if str(i) in PROP: reading, trusted = PROP[str(i)][0], True
    if str(i) in MANUAL: reading, trusted = MANUAL[str(i)], True     # conferido à mão na imagem
    part_tok_cur = i
    lab_ = MANUAL.get(str(i), "")
    if lab_.startswith("v:"):                       # acorde de baixo ligado ao '|' do verso de cima: só a parte de baixo
        y0 = max(y0, y1 - 32); MANUAL[str(i)] = lab_ = lab_[2:]
    if "^" in lab_ or " / " in lab_:                # duas linhas de acordes no mesmo recorte
        rows_ = lab_.split(" / ") if " / " in lab_ else lab_.split("^")
        hh = (y1 - y0) / len(rows_)
        for r_, txt in enumerate(rows_):
            labs = txt.split(); ry0 = int(y0 + r_ * hh); ry1 = int(y0 + (r_ + 1) * hh)
            for k_, lb in enumerate(labs):
                parts.append((pg, x0 + int((x1 - x0) * k_ / len(labs)), ry0, x0 + int((x1 - x0) * (k_ + 1) / len(labs)) - 2, ry1, to_site(lb), True)); part_tok.append(i)
                if r_ >= 1: ROWSPLIT.add(len(parts) - 1)
        nsplit += 1
        continue
    if str(i) in MANUAL and " " in MANUAL[str(i)].strip():
        labs = MANUAL[str(i)].split()
        sc_px = (y1 - y0) / 32.0
        wpx = (w.max() + 1) if len(w) else 1
        c2 = col[:wpx]; gaps = []; run = 0; st0 = 0
        for x, c in enumerate(c2):
            if not c:
                if run == 0: st0 = x
                run += 1
            else:
                if run >= 2: gaps.append((run, st0, x))
                run = 0
        cuts = sorted(g[2] for g in sorted(gaps, reverse=True)[:len(labs) - 1])
        if len(cuts) < len(labs) - 1: cuts = [int(wpx * k / len(labs)) for k in range(1, len(labs))]
        edges = [0] + cuts + [wpx]
        for k, lb in enumerate(labs):
            parts.append((pg, x0 + int(edges[k] * sc_px), y0, x0 + int(edges[k + 1] * sc_px) - 2, y1, to_site(lb), True)); part_tok.append(i)
        nsplit += 1
        continue
    split = None
    if len(w):
        col = col[:w.max() + 1]; run = 0; st = 0
        for x, c in enumerate(col):
            if not c:
                if run == 0: st = x
                run += 1
            else:
                if run >= 5 and tag not in ("ok",) and str(i) not in MANUAL:
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
            parts.append((pg, xm, y0, x1, y1, to_site(rb[1]), True)); part_tok += [i, i]
            nsplit += 1
            continue
    parts.append((pg, x0, y0, x1, y1, to_site(reading) if reading else "", trusted)); part_tok.append(i)
print("acordes separados:", nsplit)

SIB = collections.defaultdict(list)
for k, t in enumerate(part_tok): SIB[t].append(k)
SIB = {t: v for t, v in SIB.items() if len(v) > 1}
bypg = collections.defaultdict(list)
for k, p in enumerate(parts): bypg[p[0]].append(k)
out = open("n2/all_fixed.jsonl", "w")
UNC = []
USED_ALL = set()
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
                        same_line = (abs(py1 - row["y1"]) <= 10) if row.get("y1") else (abs(py0 - row["y"]) <= 22)
                        if not (same_line and abs(px0 - x) <= 40): continue
                        d = abs(px0 - x) + abs(row["y"] - py0)
                    if d < bd: best, bd = k, d
                if best is not None and parts[best][5]:
                    used.add(best)
                    if not parts[best][6]: UNC.append([part_tok[best], parts[best][5], pg])
                    rd, tr = parts[best][5], parts[best][6]
                    nt = ("!" if tr else "") + rd
                    st["trocado" if rd != t else "igual"] += 1
                    newl.append([x, nt]); boxof[(id(row), key, len(newl) - 1)] = parts[best]
                else:
                    st["sem leitura nova"] += 1
                    newl.append([x, t])
            # irmãos de um recorte com vários acordes (conferido à mão): entram na mesma linha, pela posição
            matched = [boxof[(id(row), key, j)] for j in range(len(newl)) if (id(row), key, j) in boxof]
            for b in matched:
                tok = part_tok[parts.index(b)]
                for k in SIB.get(tok, []):
                    if k in used: continue
                    _, px0, py0, px1, py1, rd, tr = parts[k]
                    if not rd or abs(py0 - b[2]) > 6: continue      # só irmãos da mesma linha
                    used.add(k)
                    newl = [e for e in newl if not (not str(e[1]).startswith("!") and abs(e[0] - (px0 + 3)) < 25)]
                    newl.append([px0 + 3, "!" + rd]); st["acorde de recorte múltiplo"] += 1
            newl.sort(key=lambda e: e[0])
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
    tok_y = collections.defaultdict(list)
    for (rid, _k, _j), b in boxof.items(): tok_y[rid].append(b[2])
    for k in cand:
        if k in used or not parts[k][5]: continue
        _, px0, py0, px1, py1, rd, tr = parts[k]
        ok_rows = [row for row in lyr if row["col"] == (0 if px0 < (r.get("W", 1838) / 2) else 1) or True]
        # 1) mesma linha de acordes de outro verso (altura igual à dos acordes já ligados a ele)
        same = [row for row in lyr if any(abs(y - py0) <= 14 for y in tok_y.get(id(row), []))
                and min(w[1] for w in row["words"]) - 60 <= px0 <= max(w[2] for w in row["words"]) + 500]
        # 2) senão, o verso logo abaixo do acorde
        rows = same or [row for row in lyr if -12 < row["y"] - py1 < 70
                and min(w[1] for w in row["words"]) - 40 <= px0 <= max(w[2] for w in row["words"]) + 60]
        if k in ROWSPLIT: rows = []
        if tr and rows:
            row = min(rows, key=lambda row: abs(row["y"] - py1))
            row.setdefault("chords", []).append([px0 + 3, "!" + rd])
            row["chords"].sort(key=lambda c: c[0])
            if row.get("chy") is None: row["chy"] = row["y"]
            st["órfão encaixado"] += 1
        elif tr:
            # sem verso: vira uma linha só de acordes naquela altura (introdução, interlúdio, fim de verso)
            col = 0 if px0 < r.get("W", 1838) / 2 else 1
            row = next((rw for rw in r["rows"] if not rw.get("words") and rw.get("col") == col and abs(rw["y"] - py0) <= 15 and rw.get("_orf")), None)
            if row is None:
                row = {"y": py0, "words": [], "text": "", "chords": [], "inline": [], "col": col, "_orf": True}
                r["rows"].append(row)
            row["inline"].append([px0, "!" + rd]); row["inline"].sort(key=lambda e: e[0])
            st["órfão em linha de acordes"] += 1
        else:
            r["orphans"].append(parts[k][1:])
    USED_ALL.update(part_tok[k] for k in used)
    # leituras antigas do OCR sem recorte correspondente: duplicatas de acordes de outros versos -> fora
    for row in r["rows"]:
        for key in ("chords", "inline"):
            if key in row:
                n0 = len(row[key]); row[key] = [e for e in row[key] if str(e[1]).startswith("!")]
                st["leitura antiga descartada"] += n0 - len(row[key])
    out.write(json.dumps(r, ensure_ascii=False) + "\n")
    st["órfãos"] += len(r["orphans"])
out.close()
print(dict(st))

json.dump(UNC, open("tk/uncertain_used.json", "w"))
print("incertos usados nas cifras:", len(UNC))
json.dump(sorted(USED_ALL), open("tk/used_tokens.json", "w"))
