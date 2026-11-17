import zipfile, re, sys, json, html
def slides(path):
    z = zipfile.ZipFile(path)
    names = sorted([n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)], key=lambda n: int(re.findall(r"\d+", n)[0]))
    # ordem real das slides vem de presentation.xml + rels
    pres = z.read("ppt/presentation.xml").decode("utf8")
    rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf8")
    rid2t = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(slides/slide\d+\.xml)"', rels)) or {}
    rid2t.update({a: b for b, a in re.findall(r'Target="(slides/slide\d+\.xml)"[^>]*Id="(rId\d+)"', rels)})
    order = [rid2t[r] for r in re.findall(r'<p:sldId [^>]*r:id="(rId\d+)"', pres) if r in rid2t]
    out = []
    for t in order:
        x = z.read("ppt/" + t).decode("utf8")
        hidden = 'show="0"' in x[:600]
        shapes = []
        for sp in re.findall(r"<p:sp>.*?</p:sp>|<p:sp .*?</p:sp>", x, re.S):
            paras = []
            for p in re.findall(r"<a:p>.*?</a:p>|<a:p .*?</a:p>", sp, re.S):
                p = re.sub(r"<a:br/>", "<a:t>\n</a:t>", p)
                paras.append("".join(html.unescape(s) for s in re.findall(r"<a:t>([^<]*)</a:t>", p)))
            name = (re.search(r'<p:cNvPr [^>]*name="([^"]*)"', sp) or [None, ""])[1]
            ph = (re.search(r'<p:ph[^>]*type="([^"]*)"', sp) or [None, "body" if "<p:ph" in sp else ""])[1]
            sz = re.findall(r'sz="(\d+)"', sp)
            off = re.search(r'<a:off x="(\d+)" y="(\d+)"', sp)
            if any(q.strip() for q in paras): shapes.append({"t": paras, "name": html.unescape(name), "ph": ph, "sz": max(map(int, sz)) if sz else 0, "y": int(off.group(2)) if off else -1})
        out.append({"slide": t, "hidden": hidden, "shapes": shapes})
    return out
if __name__ == "__main__":
    s = slides(sys.argv[1])
    json.dump(s, open(sys.argv[2], "w"), ensure_ascii=False)
    print(len(s), "slides")
