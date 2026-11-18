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

## Coletâneas cifradas (pasta CLAUDE do Drive)

- `coletanea_split.py`: separa uma coletânea em PDF com texto (Cifras 2025, CIAS 2024) em louvores e converte cada um.
- Coletânea Cifrada Nível II (escaneada): `scan_build.py` lê cada página (acordes em vermelho com `|` vermelho marcando a sílaba; letra em preto, via Tesseract), e `nivel2_assemble.py` monta as cifras, corrige # e b pelo tom da música e a letra pela letra oficial.
- Os resultados ficam em `coletaneas/*.json` e são lidos pelo `build.py`.

## Leitor de acordes da Coletânea Cifrada Nível II (escaneada)

1. `tokens_extract.py` / `tokens_head.py`: recorta cada acorde vermelho das 450 páginas.
2. `tokens_vote.py` / `tokens_knn.py` / `tokens_fix.py`: agrupa desenhos iguais e corrige o OCR pela maioria.
3. `synth_vocab.py` + `synth_score.py` + `synth_rerank.py`: desenha todos os acordes possíveis na mesma fonte e compara com o recorte.
4. `slot_cls.py`: confere a letra do acorde e o símbolo seguinte (#, b, m, 7, /) com exemplos reais do livro.
5. `final_read.py` + `postfix.py`: leitura final; º/ø/6/9/2 depois de #/b pelos exemplos conferidos à mão (`seeds_sfx.json`).
6. `apply_reads.py`: aplica no OCR das linhas e põe os acordes sem '|' sobre a palavra certa; `nivel2_assemble.py` monta as cifras.
