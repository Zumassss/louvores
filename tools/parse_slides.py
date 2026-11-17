"""Separa os slides oficiais em louvores (número, título, letra)."""
import json, re, sys

SKIP = re.compile(r"^(í|i)ndice$|^b ?i ?s$|^instrumentos?$", re.I)
TITLE_NUM = re.compile(r"^\s*(\d{1,3})\s*(AV)?\s*[-–—]\s*(.+)$", re.S)

def shape_text(sh):
    return re.sub(r"[ \t]+", " ", " ".join(p.strip() for p in sh["t"] if p.strip())).strip()

def is_title(sh, mode):
    t = shape_text(sh)
    if not t or SKIP.match(t.replace(" ", "") if len(t) < 8 else t): return None
    m = TITLE_NUM.match(t)
    if m and len(t) < 120 and mode != "av":
        return (m.group(1).zfill(3 if mode == "col" else 2), m.group(3).strip(" -–"))
    if mode == "av" and sh["sz"] >= 4400 and len(t) < 90 and len(sh["t"]) <= 3:
        return ("", t)
    return None

def clean_lines(sh):
    out = []
    for p in sh["t"]:
        for line in p.split("\n"):
            line = re.sub(r"[ \t]+", " ", line).strip()
            out.append(line)
    # remove linhas vazias no começo/fim
    while out and not out[0]: out.pop(0)
    while out and not out[-1]: out.pop()
    return out

def parse(path, mode):
    slides = json.load(open(path))
    songs, cur = [], None
    for sl in slides:
        if sl["hidden"]: continue
        shapes = sl["shapes"]
        if any(re.fullmatch(r"\d{1,3}", shape_text(s)) for s in shapes) and len(shapes) > 50: continue  # índice
        title = None
        for s in shapes:
            t = is_title(s, mode)
            if t: title = t; title_shape = s; break
        if title:
            cur = {"num": title[0], "title": title[1], "slides": []}
            songs.append(cur)
        if cur is None: continue
        lines = []
        for s in shapes:
            if title and s is title_shape: continue
            t = shape_text(s)
            if not t or SKIP.match(t.replace(" ", "")) or SKIP.match(t): continue
            if re.search(r"COLETÂNEA DE|ATUALIZAÇÃO|EDIÇÃO 20", t): continue
            if len(t) < 6 and re.fullmatch(r"[\dA-Z]{1,4}", t.replace(" ", "")): continue
            ls = clean_lines(s)
            if lines and ls: lines.append("")
            lines += ls
        if lines: cur["slides"].append(lines)
    return songs

if __name__ == "__main__":
    allsongs = {}
    for f, mode in [("col", "col"), ("cias", "cias"), ("avcias", "avcias"), ("av", "av")]:
        s = parse(f"slides_{f}.json", mode)
        allsongs[f] = s
        nums = [x["num"] for x in s]
        print(f, len(s), "louvores; sem letra:", sum(1 for x in s if not x["slides"]), "; ex:", [(x["num"], x["title"]) for x in s[:3]], "...", [(x["num"], x["title"]) for x in s[-2:]])
    json.dump(allsongs, open("letras_slides.json", "w"), ensure_ascii=False, indent=1)
