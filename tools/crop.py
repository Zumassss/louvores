"""Descobre, em cada página de uma grade, a faixa vertical com a pauta principal (cifras + melodia + letra).

Saída: {file_id: [[ [y0, y1], ... ] por página]} com y em fração da altura da página.
Lista vazia numa página = mostrar a página inteira.
"""
import json, re, subprocess, sys, os, html, collections
from concurrent.futures import ThreadPoolExecutor

WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')
PAGE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)
CHORD = re.compile(r"^[A-G](b|#|♭|♯|©|¨)?(m|‹|maj|min|M|dim|aug|sus|add|º|°|ø|\+)?[0-9]*(\(.*\))?(/[A-G](b|#|♭|♯|©|¨)?)?$")
CLEF = {"&", "?", "B", "V"}
CLEF_RE = re.compile(r"^[&?BV][b#n¨©]*$")
VOICE = re.compile(r"^(coro|vozes|voz|canto|melodia|vocal|soprano|s\.|choir|coral|sop|contralto|tenor|bar[ií]tono)", re.I)
KEYS = re.compile(r"^(piano|pno|pn\.|teclado|keyboard|org)", re.I)

def words_of(path):
    out = subprocess.run(["pdftotext", "-q", "-bbox", path, "-"], capture_output=True, text=True).stdout
    pages = []
    for w, h, body in PAGE.findall(out):
        ws = [(float(a), float(b), float(c), float(d), html.unescape(t)) for a, b, c, d, t in WORD.findall(body)]
        pages.append((float(w), float(h), ws))
    return pages

def analyse_page(W, H, ws, first):
    # 1) claves no começo dos sistemas (coluna mais à esquerda onde aparecem claves)
    clefs = [w for w in ws if CLEF_RE.match(w[4]) and w[0] < W * 0.25]
    if len(clefs) < 5: return None
    xs = collections.Counter(round(w[0]) for w in clefs)
    cx = min(x for x, n in xs.items() if n >= 2) if any(n >= 2 for n in xs.values()) else None
    if cx is None: return None
    clefx = {}
    for w in clefs:
        if cx - 3 <= w[0] <= cx + 70: clefx[round(w[1])] = w[0]
    staves = sorted(clefx)
    # junta claves muito próximas (mesma pauta)
    st = []
    for y in staves:
        if not st or y - st[-1] > 12: st.append(y)
    staves = st
    if len(staves) < 5: return None   # não é grade (poucas pautas por página)
    labels = [w for w in ws if w[2] < cx + 66 and not CLEF_RE.match(w[4]) and not re.fullmatch(r"[b#n¨©]+", w[4]) and re.search(r"[A-Za-zÀ-ÿ]", w[4]) and not CHORD.match(w[4])]

    other = {round(l[1]) for l in labels if len(re.sub(r"[^A-Za-zÀ-ÿ]", "", l[4])) >= 2 and not (VOICE.match(l[4]) or KEYS.match(l[4]))}
    if len(other) < 3: return None   # não há outros instrumentos para esconder

    def labelled(y):  # nome de instrumento próprio (ignora coro/vozes/piano, que fazem parte da parte principal)
        ls = [l for l in labels if -8 <= ((l[1] + l[3]) / 2) - y <= 26 and l[2] < clefx.get(y, cx) - 1]
        return bool(ls) and not any(VOICE.match(l[4]) or KEYS.match(l[4]) for l in ls)

    # 2) linhas de cifras (>= 2 acordes na mesma altura, depois da coluna das claves)
    rows = collections.defaultdict(list)
    for w in ws:
        if w[0] > cx + 15 and len(w[4]) <= 9 and CHORD.match(w[4]) and not any(abs(w[1] - l[1]) < 2 and abs(w[0] - l[0]) < 1 for l in labels):
            rows[round(w[1] / 4)].append(w)
    chord_rows = sorted({min(x[1] for x in v) for v in rows.values() if len(v) >= 2})
    # junta linhas muito próximas
    cr = []
    for y in chord_rows:
        if not cr or y - cr[-1] > 10: cr.append(y)
    chord_rows = cr

    targets = []
    if chord_rows:
        for yc in chord_rows:
            nxt = [s for s in staves if s > yc - 2]
            if nxt and not labelled(nxt[0]): targets.append((yc, nxt[0]))   # cifras de baixo/guitarra: ignora
    else:
        # sem cifras: usa a pauta do coro/vozes, senão a do piano
        for rx in (VOICE, KEYS):
            ls = [l for l in labels if rx.match(l[4])]
            if ls:
                for l in ls:
                    ly = (l[1] + l[3]) / 2
                    # primeira pauta do grupo: a pauta mais próxima acima/na altura do rótulo
                    cand = [s for s in staves if s <= ly + 4]
                    s0 = cand[-1] if cand else staves[0]
                    # se o rótulo está centrado num grupo, começa na pauta acima também
                    targets.append((s0 - 18, s0))
                break
    if not targets: return None

    bands = []
    inst = [y for y in staves if labelled(y)]          # pautas de outros instrumentos (limites)
    if len(inst) < 3: return None
    tops = sorted(t[0] for t in targets)
    for yc, s0 in targets:
        top = min(yc, s0) - 10
        prev_inst = [y for y in inst if y < s0]
        if prev_inst: top = max(top, prev_inst[-1] + 30)
        nxt_inst = [y for y in inst if y > s0]
        nxt_tgt = [t for t in tops if t > yc + 20]
        bottom = min([H - 14] + ([nxt_inst[0] - 10] if nxt_inst else []) + ([nxt_tgt[0] - 12] if nxt_tgt else []))
        i = staves.index(s0)
        if i + 3 < len(staves):   # no máximo 3 pautas (melodia/coro + piano)
            bottom = min(bottom, (staves[i + 2] + staves[i + 3]) / 2 + 4)
        if bottom - top > 30: bands.append([max(0, top), min(H, bottom)])
    if not bands: return None
    if first:  # cabeçalho (título, autor, andamento) na primeira página
        bands.insert(0, [0, max(0, staves[0] - 14)])
    # une faixas sobrepostas
    bands.sort(); merged = []
    for b in bands:
        if merged and b[0] <= merged[-1][1] + 2: merged[-1][1] = max(merged[-1][1], b[1])
        else: merged.append(b)
    covered = sum(b[1] - b[0] for b in merged)
    if covered > 0.6 * H: return None   # recorte não economiza nada
    return [[round(a / H, 4), round(b / H, 4)] for a, b in merged]

def analyse(fid):
    try:
        pages = words_of(f"pdf/{fid}.pdf")
    except Exception:
        return fid, None
    res, any_crop = [], False
    for i, (W, H, ws) in enumerate(pages):
        r = analyse_page(W, H, ws, i == 0)
        res.append(r or [])
        any_crop |= bool(r)
    return fid, (res if any_crop else None)

if __name__ == "__main__":
    ids = json.load(open(sys.argv[1]))
    with ThreadPoolExecutor(8) as ex:
        out = {fid: r for fid, r in ex.map(analyse, ids) if r}
    json.dump(out, open(sys.argv[2], "w"))
    print("grades recortadas:", len(out), "de", len(ids))
