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
python3 ../tools/build.py                  # 1ª passada: gera docs/data.js
python3 ../tools/cifras.py                 # converte as cifras em PDF para texto (acordes + letra) -> cifras.json
python3 ../tools/build.py                  # 2ª passada: inclui as cifras interativas (troca de tom no app)
```

O `build.py` também troca a versão do `sw.js`; assim os aparelhos baixam a atualização sozinhos na próxima vez que abrirem com internet.

`crop.py` (usado pelo `build.py`) procura nas grades a linha de cifras e a pauta do coro e grava as faixas de cada página em `window.RECORTES`. No site, o botão **Melodia / Grade** alterna entre o recorte e a página inteira.

`cifra_parse.py` lê as cifras no formato da ICM (acordes em cima, `|` na letra marcando onde entra cada acorde), separa colunas dos cadernos e gera linhas no formato `c:Por[Bb]que ele é o [F]Rei`. No app, a cifra muda de tom pelo menu lateral, e qualquer cifra pode ser colada pelo próprio app ("Colar uma cifra"), ficando salva no aparelho.

Louvores cuja partitura não tem acordes ganham uma "Cifra (sem acordes)" com a letra (oficial dos slides, `letras_por_titulo.json`, ou extraída da partitura por `letra_da_partitura.py`). No app, o menu lateral tem **✎ Adicionar/Editar acordes**: toca-se na palavra e escolhe-se o acorde; as alterações ficam salvas no aparelho (no tom original) e valem para a troca de tom.
