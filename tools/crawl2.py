import re, json, sys, html, urllib.request, concurrent.futures as cf

ROOTS = {
    "Louvores para Coro Masculino e Quarteto": "1Lz6hEyThp91gPvBOQX3PfHPF_BGtshRw",
    "Evangelização CIAs - Outubro/2026": "1Rzugylr4S4JL4656hgc21zh7Daq9bbgY",
    "Folheto Trombetas e Festas 2024": "1mUQLYyiYWUowEZPWk40Gv1b5wEoUhALV",
    "Trombetas e Festas 2023": "1UtPsPkHtfMC91RGCPuVGaJ6dbEnmx3K4",
}
OLD = {
    "Louvores Avulsos": "1GkbI-RFAQ0q2SdsGSpNxcwfq_leVGnr5",
    "Louvores Coletânea CIAs": "1IPwjC905-4yfCds4vbTZVtmlvOjKILvu",
    "Louvores Avulsos CIAs": "19km1-DofXLxe2whgV5bzKSbVZv6wM0kW",
    "Seminário de Louvor Ago/25": "1F9nlNgSmmISWsjctu9lWBrgAqQlNo4HG",
    "Equipe de Louvor - Maanaim de Domingos Martins/ES": "1n1Afj4bKHrur3SQNc-PgiACV9NaufPKw",
    "Louvores Coletânea": "11rp2619vTyRyClw5qyd2DbrcU2bQ7xGS",
}
ENTRY = re.compile(r'<div class="flip-entry" id="entry-([^"]+)".*?<a href="([^"]+)".*?aria-label="([^"]*)".*?<div class="flip-entry-title">([^<]*)</div>', re.S)

def fetch(fid):
    for _ in range(4):
        try:
            with urllib.request.urlopen(f"https://drive.google.com/embeddedfolderview?id={fid}", timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            err = e
    print("FAIL", fid, err, file=sys.stderr); return ""

files = []
def walk(level):
    nxt = []
    with cf.ThreadPoolExecutor(16) as ex:
        for (fid, path), page in zip(level, ex.map(lambda x: fetch(x[0]), level)):
            for chunk in page.split('<div class="flip-entry" id="entry-')[1:]:
                eid = chunk.split('"', 1)[0]
                href = re.search(r'<a href="([^"]+)"', chunk).group(1)
                title = html.unescape(re.search(r'flip-entry-title">([^<]*)<', chunk).group(1))
                m = re.search(r'/type/([^"]+)"', chunk); kind = m.group(1) if m else ""
                if "/folders/" in href:
                    nxt.append((eid, path + [title]))
                else:
                    files.append({"id": eid, "name": title, "kind": kind, "path": path})
    return nxt

level = [(fid, [name]) for name, fid in ROOTS.items()]
depth = 0
while level:
    print("depth", depth, "folders", len(level), "files so far", len(files), file=sys.stderr)
    level = walk(level); depth += 1
json.dump(files, open(sys.argv[1], "w"), ensure_ascii=False, indent=0)
print("total files", len(files))
