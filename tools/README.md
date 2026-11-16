# Ferramentas de atualização

Scripts que geram o site em `docs/` a partir das pastas públicas do Drive "Material para ensaio".
Rode tudo de dentro de uma pasta de trabalho (ex.: `work/`, ignorada pelo git):

```bash
mkdir -p work && cd work
python3 ../tools/crawl.py files.json       # lista as 6 pastas principais
python3 ../tools/crawl2.py files2.json     # lista as pastas extras (Coro Masculino, Evangelização, T&F)
python3 ../tools/select.py                 # escolhe cifra / partitura / letra de cada louvor -> songs2.json
# baixa os PDFs escolhidos para pdf/<id>.pdf e extrai o texto:
#   pdftotext pdf/<id>.pdf txt/<id>.pdf.txt
python3 ../tools/cadernos.py               # mapeia músicas -> páginas dos cadernos
python3 ../tools/build.py                  # gera docs/data.js, docs/pdf/ e docs/sw.js
```

O `build.py` também troca a versão do `sw.js`; assim os aparelhos baixam a atualização sozinhos na próxima vez que abrirem com internet.
