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
# letras oficiais: baixe os .pptx da pasta "Arquivos / Slides - Projeção" para slides/ (col, cias, avcias, av) e rode:
for f in col cias avcias av; do python3 -I ../tools/pptx_text.py slides/$f.pptx slides_$f.json; done
python3 ../tools/parse_slides.py           # separa as letras por louvor -> letras_slides.json
python3 ../tools/build.py                  # gera docs/data.js (com letras e recortes), docs/pdf/ e docs/sw.js
```

O `build.py` também troca a versão do `sw.js`; assim os aparelhos baixam a atualização sozinhos na próxima vez que abrirem com internet.

`crop.py` (usado pelo `build.py`) procura nas grades a linha de cifras e a pauta do coro e grava as faixas de cada página em `window.RECORTES`. No site, o botão **Melodia / Grade** alterna entre o recorte e a página inteira.
