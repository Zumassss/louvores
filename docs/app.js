(function () {
  "use strict";
  var DATA = window.LOUVORES || [];
  var CADS = window.CADERNOS || [];
  var FILES = window.ARQUIVOS || {};
  var LETRAS = window.LETRAS || [];
  var RECORTES = window.RECORTES || {};
  var $ = function (id) { return document.getElementById(id); };

  // ---------- Utilidades ----------
  function norm(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, " ").trim();
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function load(k, def) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch (e) { return def; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  // ---------- Índice de busca ----------
  function prep(d, title, text) {
    d.nt = norm(title);
    d.ct = d.nt.replace(/ /g, "");
    d.tw = d.nt.split(" ").filter(Boolean);
    d.x = text || "";
    d.cx = d.x.replace(/ /g, "");
    var seen = {}, lw = [];
    d.x.split(" ").forEach(function (w) { if (w.length > 2 && !seen[w]) { seen[w] = 1; lw.push(w); } });
    d.lw = lw;
  }
  DATA.forEach(function (d, i) {
    d.i = i; d.f = d.d[0][0];
    d.key = d.d[0][0] + ":" + (d.d[0][2] || 0);
    prep(d, d.t + " " + (d.a || []).join(" "), d.x);
    d.nt = norm(d.t); d.ct = d.nt.replace(/ /g, ""); d.tw = d.nt.split(" ").filter(Boolean);
    d.nums = [d.n].concat(d.m || []).map(function (n) {
      var m = /^(cia\s*)?([a-z]?)0*(\d+)$/i.exec((n || "").replace(/\s+/g, " ").trim());
      return m ? [m[3], (m[1] ? "cia" : "") + m[2].toLowerCase()] : null;
    }).filter(Boolean);
    d.hasCifra = d.d.some(function (x) { return /^(Cifra|Harmonia)/.test(x[1]); });
    d.cs = d.c + (d.g ? " · " + d.g : "");
  });
  var PAGES = []; // páginas dos cadernos, buscáveis
  CADS.forEach(function (c, ci) {
    c.ci = ci;
    c.p.forEach(function (txt, pi) {
      var pg = { cad: c, page: pi + 1 };
      prep(pg, c.t, txt);
      PAGES.push(pg);
    });
  });

  // Distância de edição limitada (erros de digitação)
  function lev(a, b, max) {
    var la = a.length, lb = b.length;
    if (Math.abs(la - lb) > max) return max + 1;
    var prev = [], cur = [], j;
    for (j = 0; j <= lb; j++) prev[j] = j;
    for (var i = 1; i <= la; i++) {
      cur[0] = i; var best = i;
      for (j = 1; j <= lb; j++) {
        var c = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + c);
        if (cur[j] < best) best = cur[j];
      }
      if (best > max) return max + 1;
      var t = prev; prev = cur; cur = t;
    }
    return prev[lb];
  }
  function tolerance(len) { return len >= 8 ? 2 : len >= 4 ? 1 : 0; }
  function wordHit(tok, words, last) {
    var tol = tolerance(tok.length), best = 0;
    for (var k = 0; k < words.length; k++) {
      var w = words[k];
      if (w === tok) return 1;
      if ((last || tok.length >= 3) && w.indexOf(tok) === 0) { best = Math.max(best, 0.95); continue; }
      if (tol && best < 0.8) {
        var cut = last && w.length > tok.length + tol ? w.slice(0, tok.length) : w;
        if (lev(tok, cut, tol) <= tol) best = 0.8;
      }
    }
    return best;
  }
  function lyricScore(d, toks, cq) {
    if (!d.cx) return 0;
    if (cq.length >= 5 && d.cx.indexOf(cq) >= 0) return 600;
    var t2 = 0, n = 0;
    for (var j = 0; j < toks.length; j++) {
      if (toks[j].length < 3) continue;
      n++;
      t2 += d.x.indexOf(toks[j]) >= 0 ? 1 : wordHit(toks[j], d.lw, j === toks.length - 1);
    }
    if (!n) return 0;
    var fl = t2 / n;
    if (fl >= 0.999) return 520 + Math.min(n, 6) * 10;
    if (fl >= 0.7 && n >= 2) return 300 + 200 * fl;
    return 0;
  }
  function score(d, q, toks, cq) {
    var s = 0, why = "t";
    var nm = /^(cia\s*|c\s*)?([a-z]?)\s*0*(\d+)$/.exec(q);
    if (nm) {
      var pre = (nm[1] ? "cia" : "") + (nm[2] || "");
      d.nums.forEach(function (x, k) {
        var dig = x[0], dpre = x[1], bonus = k === 0 ? 0 : -20;
        if (dig === nm[3] && (!pre || pre === dpre)) s = Math.max(s, (!pre && dpre ? 950 : 1000) + bonus);
        else if (dig.indexOf(nm[3]) === 0 && (!pre || pre === dpre)) s = Math.max(s, 300);
      });
    }
    if (!toks.length) return { s: s, why: why };
    if (d.nt === q) s = Math.max(s, 900);
    else if (d.nt.indexOf(q) === 0) s = Math.max(s, 820);
    else if (cq.length >= 3 && d.ct.indexOf(cq) >= 0) s = Math.max(s, 760);
    if (s < 700) {
      var tot = 0;
      for (var i = 0; i < toks.length; i++) tot += wordHit(toks[i], d.tw, i === toks.length - 1);
      var f = tot / toks.length;
      if (f >= 0.999) s = Math.max(s, 700);
      else if (f >= 0.75) s = Math.max(s, 450 + 200 * f);
    }
    if (s < 600) {
      var ls = lyricScore(d, toks, cq);
      if (ls > s) { s = ls; why = "l"; }
    }
    return { s: s, why: why };
  }
  function snippet(d, toks) {
    var x = d.x, pos = -1, k;
    var real = toks.filter(function (t) { return t.length >= 3; });
    for (k = 0; k < real.length && pos < 0; k++) pos = x.indexOf(real[k]);
    if (pos < 0) {
      outer: for (k = 0; k < real.length; k++) {
        var tol = tolerance(real[k].length);
        for (var w = 0; w < d.lw.length; w++) {
          if (lev(real[k], d.lw[w].slice(0, real[k].length + 1), tol) <= tol) { pos = x.indexOf(d.lw[w]); break outer; }
        }
      }
    }
    if (pos < 0) return "";
    var a = Math.max(0, x.lastIndexOf(" ", Math.max(0, pos - 26)));
    var b = x.indexOf(" ", Math.min(x.length, pos + 70)); if (b < 0) b = x.length;
    var s = esc(x.slice(a, b).trim());
    real.forEach(function (t) { s = s.replace(new RegExp("\\b(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "[a-z]*)", "g"), "<mark>$1</mark>"); });
    return (a > 0 ? "… " : "") + s + (b < x.length ? " …" : "");
  }

  // ---------- Estado ----------
  var favs = load("lv.favs", []);
  var recents = load("lv.recents", []);
  var filter = load("lv.filter", "all");
  var lastDoc = load("lv.lastDoc", {});

  var FILTERS = [
    { id: "all", label: "Todos", test: function () { return true; } },
    { id: "fav", label: "Favoritos", test: function (d) { return favs.indexOf(d.key) >= 0; } },
    { id: "cifra", label: "Com cifra", test: function (d) { return d.hasCifra; } },
    { id: "av", label: "Avulsos", test: function (d) { return d.c === "Avulsos"; } },
    { id: "col", label: "Coletânea", test: function (d) { return d.c === "Coletânea"; } },
    { id: "cia", label: "CIAs", test: function (d) { return /CIAs/.test(d.c); } },
    { id: "sem", label: "Seminários", test: function (d) { return /Seminário|Equipe/.test(d.c) || /Seminário/.test(d.g); } },
    { id: "tef", label: "Trombetas e Festas", test: function (d) { return /Trombetas|T&F/.test(d.c + " " + d.g + " " + (d.a || []).join(" ")); } },
    { id: "coro", label: "Coro Masculino", test: function (d) { return d.c === "Coro Masculino" || (d.a || []).indexOf("Coro Masculino") >= 0; } },
    { id: "cad", label: "Cadernos", test: function () { return false; }, cads: true }
  ];
  if (!FILTERS.some(function (f) { return f.id === filter; })) filter = "all";
  function curFilter() { return FILTERS.filter(function (x) { return x.id === filter; })[0]; }

  function renderChips() {
    $("chips").innerHTML = FILTERS.map(function (f) {
      var n = f.cads ? CADS.length : DATA.filter(f.test).length;
      if (f.id === "fav" && !n && filter !== "fav") return "";
      return '<button class="chip" role="tab" data-f="' + f.id + '" aria-selected="' + (f.id === filter) + '">' +
        (f.id === "fav" ? "★ " : "") + esc(f.label) + '<span class="n">' + n + "</span></button>";
    }).join("");
  }
  $("chips").addEventListener("click", function (e) {
    var b = e.target.closest(".chip"); if (!b) return;
    filter = b.getAttribute("data-f"); save("lv.filter", filter);
    renderChips(); run(); window.scrollTo(0, 0);
  });

  // ---------- Lista ----------
  var STAR = '<svg class="star" viewBox="0 0 24 24" aria-label="Favorito"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" fill="currentColor"/></svg>';
  var NOTE = '<svg viewBox="0 0 24 24"><path d="M9 18V6l10-2v12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="7" cy="18" r="2.2" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="17" cy="16" r="2.2" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>';
  var BOOK = '<svg viewBox="0 0 24 24"><path d="M4 5.5C4 4.7 4.7 4 5.5 4H11v16H5.5C4.7 20 4 19.3 4 18.5zM20 5.5c0-.8-.7-1.5-1.5-1.5H13v16h5.5c.8 0 1.5-.7 1.5-1.5z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>';
  function badge(d) {
    if (!d.n) return '<div class="badge none">' + NOTE + "</div>";
    var m = /^(CIA)\s*(\d+)$/i.exec(d.n);
    if (m) return '<div class="badge"><span><small>CIA</small>' + esc(m[2]) + "</span></div>";
    return '<div class="badge">' + esc(d.n) + "</div>";
  }
  function tagOf(d) {
    if (d.hasCifra) return '<span class="tag cifra">Cifra</span>';
    if (d.k === "letra") return '<span class="tag letra">Letra</span>';
    if (d.k === "parte") return '<span class="tag parte">' + esc(d.d[0][1].split(" · ")[0]) + "</span>";
    return '<span class="tag partitura">Partitura</span>';
  }
  function itemHTML(d, snip) {
    return '<li class="item" data-i="' + d.i + '">' + badge(d) +
      '<div class="info"><div class="title">' + esc(d.t) + '</div>' +
      '<div class="line2">' + tagOf(d) + '<span class="col">' + esc(d.cs) + "</span></div>" +
      (snip ? '<div class="snip">' + snip + "</div>" : "") + "</div>" +
      (favs.indexOf(d.key) >= 0 ? STAR : "") + "</li>";
  }
  function cadHTML(pg, snip) {
    var c = pg.cad;
    return '<li class="item" data-c="' + c.ci + '" data-p="' + (pg.page || 1) + '"><div class="badge cad">' + BOOK + "</div>" +
      '<div class="info"><div class="title">' + esc(c.t) + "</div>" +
      '<div class="line2"><span class="tag ' + (c.k === "Cifra" ? "cifra" : c.k === "Letra" ? "letra" : "partitura") + '">' + esc(c.k) + "</span>" +
      '<span class="col">' + (pg.page ? "Página " + pg.page + " de " + c.p.length : c.p.length + " páginas") + "</span></div>" +
      (snip ? '<div class="snip">' + snip + "</div>" : "") + "</div></li>";
  }

  // renderização em blocos (lista longa)
  var queue = [], shown = 0, curToks = [];
  var CHUNK = 60;
  function paint(rows) {
    queue = rows; shown = 0;
    $("list").innerHTML = "";
    more();
  }
  function more() {
    var html = "", end = Math.min(queue.length, shown + CHUNK);
    for (; shown < end; shown++) {
      var r = queue[shown];
      if (r.sec) html += '<li class="sec">' + esc(r.sec) + "</li>";
      else if (r.pg) html += cadHTML(r.pg, r.snip ? snippet(r.pg, curToks) : "");
      else html += itemHTML(r.d, r.why === "l" ? snippet(r.d, curToks) : "");
    }
    $("list").insertAdjacentHTML("beforeend", html);
  }
  window.addEventListener("scroll", function () {
    if (shown < queue.length && window.innerHeight + window.scrollY > document.body.offsetHeight - 1200) more();
    $("searchbar").classList.toggle("stuck", window.scrollY > $("searchbar").offsetTop - 1 && window.scrollY > 40);
  }, { passive: true });

  function run() {
    var raw = $("q").value;
    var q = norm(raw), toks = q ? q.split(" ") : [], cq = toks.join("");
    curToks = toks;
    $("clear").hidden = !raw;
    var f = curFilter();
    var rows = [];

    if (f.cads) {
      if (!q) {
        CADS.forEach(function (c) { rows.push({ pg: { cad: c, page: 0 } }); });
        $("meta").textContent = CADS.length + " cadernos com vários louvores";
      } else {
        PAGES.forEach(function (pg) {
          var s = Math.max(lyricScore(pg, toks, cq), pg.nt.indexOf(q) >= 0 ? 500 : 0);
          if (s > 0) rows.push({ pg: pg, s: s, snip: true });
        });
        rows.sort(function (a, b) { return b.s - a.s; });
        $("meta").textContent = rows.length + (rows.length === 1 ? " página encontrada" : " páginas encontradas");
      }
      $("empty").hidden = rows.length > 0;
      paint(rows); return;
    }

    var pool = DATA.filter(f.test);
    if (!q) {
      if (filter === "all" && recents.length) {
        var rec = recents.map(function (k) { return DATA.filter(function (d) { return d.key === k; })[0]; }).filter(Boolean).slice(0, 5);
        if (rec.length) { rows.push({ sec: "Abertos recentemente" }); rec.forEach(function (d) { rows.push({ d: d }); }); }
      }
      var lastCol = null;
      pool.forEach(function (d) {
        if (d.c !== lastCol) { rows.push({ sec: d.c }); lastCol = d.c; }
        rows.push({ d: d });
      });
      $("meta").textContent = pool.length + " louvores" + (filter === "all" ? "" : " · " + f.label);
      $("empty").hidden = pool.length > 0;
      paint(rows); return;
    }

    var out = [];
    for (var i = 0; i < pool.length; i++) {
      var r = score(pool[i], q, toks, cq);
      if (r.s > 0) out.push({ d: pool[i], s: r.s, why: r.why });
    }
    out.sort(function (a, b) {
      return b.s - a.s || (b.d.hasCifra - a.d.hasCifra) || a.d.nt.localeCompare(b.d.nt);
    });
    rows = out;
    // trechos encontrados dentro dos cadernos (só quando a busca parece letra)
    if (filter === "all" && toks.length >= 2) {
      var cp = [];
      PAGES.forEach(function (pg) { var s = lyricScore(pg, toks, cq); if (s >= 520) cp.push({ pg: pg, s: s, snip: true }); });
      cp.sort(function (a, b) { return b.s - a.s; });
      if (cp.length) rows = rows.concat([{ sec: "Nos cadernos" }], cp.slice(0, 6));
    }
    $("meta").textContent = out.length + (out.length === 1 ? " louvor encontrado" : " louvores encontrados");
    $("empty").hidden = rows.length > 0;
    paint(rows);
  }

  var tmr;
  $("q").addEventListener("input", function () { clearTimeout(tmr); tmr = setTimeout(function () { run(); window.scrollTo(0, 0); }, 70); });
  $("q").addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault(); $("q").blur();
      var first = queue.filter(function (r) { return r.d; })[0];
      if (first && first.s >= 950) open(first.d);
    }
  });
  $("clear").addEventListener("click", function () { $("q").value = ""; run(); $("q").focus(); });
  $("list").addEventListener("click", function (e) {
    var li = e.target.closest(".item"); if (!li) return;
    if (li.hasAttribute("data-c")) {
      var c = CADS[+li.getAttribute("data-c")];
      openCad(c, +li.getAttribute("data-p") || 1);
    } else open(DATA[+li.getAttribute("data-i")]);
  });

  // ---------- Visualizador ----------
  var CIFRAS = window.CIFRAS || {};
  var pdfjsP = null;
  function pdfjs() {
    if (!pdfjsP) pdfjsP = import("./lib/pdf.min.mjs").then(function (m) {
      m.GlobalWorkerOptions.workerSrc = new URL("lib/pdf.worker.min.mjs", location.href).href;
      return m;
    });
    return pdfjsP;
  }
  var cur = null, curDocs = [], curIdx = 0, doc = null, docId = null, observer = null, token = 0, wake = null;
  var zoom = load("lv.zoom", 1);           // PDFs
  var tzoom = load("lv.tzoom", 1);         // cifra e letra (texto)
  var view = "";                           // "pdf" | "cifra" | "letra"
  var curCifra = null;                     // {k, l} da cifra aberta
  var tons = load("lv.tons", {});          // transposição salva por louvor
  var myCifras = load("lv.minhas", {});    // cifras coladas pelo usuário
  var showChords = load("lv.chords", true);
  var cropOn = load("lv.crop", true);

  function showViewer() {
    if ($("viewer").hidden) {
      $("viewer").hidden = false;
      document.documentElement.style.overflow = "hidden";
      history.pushState({ v: 1 }, "");
      keepAwake(true);
    }
  }
  function docsOf(d) {
    var list = d.d.slice();
    if (myCifras[d.key]) list.unshift(["M:" + d.key, "Minha cifra", 0, 0]);
    return list;
  }
  function open(d, idx) {
    cur = d; curDocs = docsOf(d);
    if (idx == null) {
      idx = 0;
      var want = lastDoc[d.key];
      curDocs.forEach(function (x, i) { if (x[1] === want) idx = i; });
      recents = [d.key].concat(recents.filter(function (x) { return x !== d.key; })).slice(0, 15);
      save("lv.recents", recents);
    }
    curIdx = idx;
    $("vName").textContent = (d.n ? d.n + "  " : "") + d.t;
    showViewer();
    stopScroll();
    var di = curDocs[idx];
    $("vSub").textContent = di[1].replace(/ · .*/, "");
    if (/^C:/.test(di[0])) showCifra(CIFRAS[di[0].slice(2)]);
    else if (/^M:/.test(di[0])) showCifra(parsePasted(myCifras[d.key]));
    else if (/^L\d+$/.test(di[0])) showLyrics(+di[0].slice(1));
    else loadPdf(di[0], di[2], di[3]);
    drawer();
  }
  function openCad(c, page) {
    cur = null; curDocs = [[c.id, c.k, 0, 0]]; curIdx = 0;
    $("vName").textContent = c.t; $("vSub").textContent = c.k + (page > 1 ? " · pág. " + page : "");
    showViewer(); stopScroll(); loadPdf(c.id, 0, 0, page); drawer();
  }
  function reset() {
    token++;
    if (doc) { doc.destroy(); doc = null; docId = null; }
    if (observer) observer.disconnect();
    $("pageInd").hidden = true;
  }

  // ---------- Acordes: leitura e transposição ----------
  var SH = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  var FL = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"];
  var IDX = { C: 0, "B#": 0, "C#": 1, Db: 1, D: 2, "D#": 3, Eb: 3, E: 4, Fb: 4, F: 5, "E#": 5, "F#": 6, Gb: 6, G: 7, "G#": 8, Ab: 8, A: 9, "A#": 10, Bb: 10, B: 11, Cb: 11 };
  var CHORD_RE = /^([A-G])(#|b)?([^/]*?)(?:\/([A-G])(#|b)?)?$/;
  var MAJ_KEYS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
  var MIN_KEYS = ["Cm", "C#m", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "Bbm", "Bm"];
  function keyInfo(k) {
    var m = /^([A-G])(#|b)?(m?)/.exec(k || "");
    if (!m) return null;
    return { i: IDX[m[1] + (m[2] || "")], minor: !!m[3] };
  }
  function keyName(i, minor) { i = ((i % 12) + 12) % 12; return minor ? MIN_KEYS[i] : MAJ_KEYS[i]; }
  function useFlats(i, minor) {
    var n = keyName(i, minor);
    return /b/.test(n) || /^(F|Dm|Gm|Cm|Fm)$/.test(n);
  }
  function trNote(n, shift, flats) {
    var i = IDX[n]; if (i == null) return n;
    i = ((i + shift) % 12 + 12) % 12;
    return (flats ? FL : SH)[i];
  }
  function trChord(ch, shift, flats) {
    if (!shift) return ch;
    var m = CHORD_RE.exec(ch);
    if (!m) return ch;
    var out = trNote(m[1] + (m[2] || ""), shift, flats) + m[3];
    if (m[4]) out += "/" + trNote(m[4] + (m[5] || ""), shift, flats);
    return out;
  }
  function origKey(c) {
    if (c.k && keyInfo(c.k)) return c.k;
    for (var i = 0; i < c.l.length; i++) {
      var m = /\[([A-G](?:#|b)?m?)/.exec(c.l[i]);
      if (m && c.l[i].indexOf("i:") !== 0) return m[1].replace(/m$/, "") + (/^\[[A-G](#|b)?m(?!aj)/.test(c.l[i].slice(m.index)) ? "m" : "");
    }
    return "C";
  }

  // ---------- Cifra (estilo Cifra Club) ----------
  function cifraShift() { return (cur && tons[cur.key]) || 0; }
  function showCifra(c) {
    reset(); view = "cifra"; curCifra = c;
    if (!c) { $("pages").innerHTML = '<div class="vmsg">Cifra não encontrada.</div>'; return; }
    renderCifra();
    $("pages").scrollTop = 0;
  }
  function renderCifra() {
    var c = curCifra; if (!c) return;
    var ok = keyInfo(origKey(c)), shift = cifraShift();
    var flats = ok ? useFlats(ok.i + shift, ok.minor) : false;
    var html = "", stanza = [];
    function chordHTML(ch) { return '<b class="ch">' + esc(trChord(ch, shift, flats)) + "</b>"; }
    function flush() { if (stanza.length) { html += '<div class="cs">' + stanza.join("") + "</div>"; stanza = []; } }
    c.l.forEach(function (line) {
      if (!line) { flush(); return; }
      var t = line.slice(0, 2), s = line.slice(2);
      if (t === "h:") { flush(); stanza.push('<div class="ch-h">' + esc(s) + "</div>"); return; }
      if (t === "t:") { stanza.push('<div class="cl">' + (esc(s) || "&nbsp;") + "</div>"); return; }
      if (t === "p:") { stanza.push('<pre class="cp">' + esc(s) + "</pre>"); return; }
      if (t === "i:" || t === "a:") {
        if (!showChords) return;
        stanza.push('<div class="ci">' + s.split(/(\[[^\]]+\])/).map(function (p) {
          return /^\[.+\]$/.test(p) ? chordHTML(p.slice(1, -1)) : esc(p);
        }).join("") + "</div>");
        return;
      }
      // linha cantada: cada palavra é um bloco (acorde em cima, sílaba embaixo)
      if (!showChords) { stanza.push('<div class="cl">' + esc(s.replace(/\[[^\]]+\]/g, "")) + "</div>"); return; }
      var parts = s.split(/(\[[^\]]+\])/), out = "", pend = null;
      function seg(ch, txt) {
        return '<span class="sg"><b class="ch">' + (ch ? esc(trChord(ch, shift, flats)) : "") + '</b><span class="sy">' + (txt ? esc(txt) : "&nbsp;") + "</span></span>";
      }
      function words(txt, ch) {
        var ws = txt.match(/\S+\s*|\s+/g) || [];
        if (!ws.length && ch) { out += seg(ch, "\u00a0\u00a0"); return; }
        ws.forEach(function (w, k) { out += seg(k === 0 ? ch : null, w); });
      }
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i];
        if (/^\[.+\]$/.test(p)) {
          if (pend !== null) out += seg(pend, "\u00a0\u00a0");
          pend = p.slice(1, -1);
        } else if (p) { words(p, pend); pend = null; }
      }
      if (pend !== null) out += seg(pend, "\u00a0\u00a0");
      stanza.push('<div class="cl has">' + out + "</div>");
    });
    flush();
    $("pages").innerHTML = '<article class="cifra" style="font-size:' + (17 * tzoom).toFixed(1) + 'px">' + html + "</article>";
    tomUI();
  }
  function setTom(shift) {
    if (!cur) return;
    shift = ((shift % 12) + 18) % 12 - 6;   // entre -6 e +5
    if (shift) tons[cur.key] = shift; else delete tons[cur.key];
    save("lv.tons", tons);
    var y = $("pages").scrollTop; renderCifra(); $("pages").scrollTop = y;
  }
  function tomUI() {
    if (view !== "cifra" || !curCifra) return;
    var ok = keyInfo(origKey(curCifra)), shift = cifraShift();
    if (!ok) return;
    $("keyV").textContent = keyName(ok.i + shift, ok.minor);
    $("tomOrig").textContent = "original: " + keyName(ok.i, ok.minor);
    $("keyGrid").innerHTML = (ok.minor ? MIN_KEYS : MAJ_KEYS).map(function (k, i) {
      var sel = ((ok.i + shift) % 12 + 12) % 12 === i;
      return '<button type="button" data-k="' + i + '" class="' + (sel ? "on" : "") + (i === ok.i ? " orig" : "") + '">' + k + "</button>";
    }).join("");
    $("tomReset").hidden = !shift;
  }
  $("tomUp").addEventListener("click", function () { setTom(cifraShift() + 1); });
  $("tomDown").addEventListener("click", function () { setTom(cifraShift() - 1); });
  $("tomReset").addEventListener("click", function () { setTom(0); });
  $("keyGrid").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-k]"); if (!b || !curCifra) return;
    var ok = keyInfo(origKey(curCifra)); setTom(+b.getAttribute("data-k") - ok.i);
  });
  $("optChords").addEventListener("change", function () {
    showChords = this.checked; save("lv.chords", showChords);
    if (view === "cifra") renderCifra();
  });

  // Cifra colada (texto do Cifra Club ou de qualquer site): acordes em cima, letra embaixo
  var TOK_CHORD = /^\(?[A-G](#|b)?(maj|min|m|M|dim|aug|sus|add|º|°|ø|\+)?[0-9]*(\([^)\s]{1,12}\))?(maj|sus|add|m)?[0-9]*(\/[A-G](#|b)?)?\)?$/;
  function isChordTok(t) { return TOK_CHORD.test(t) || /^(\||%|-|\(?\d+x\)?|x\d+)$/i.test(t); }
  function isChordLineTxt(l) {
    var toks = l.trim().split(/\s+/);
    return toks[0] !== "" && toks.every(isChordTok) && toks.some(function (t) { return TOK_CHORD.test(t); });
  }
  function parsePasted(text) {
    var src = String(text || "").replace(/\r/g, "").replace(/\t/g, "    ").split("\n"), out = [], key = "";
    for (var i = 0; i < src.length; i++) {
      var l = src[i].replace(/\s+$/, "");
      var km = /^\s*tom:\s*([A-G](#|b)?m?)/i.exec(l);
      if (km) { key = km[1]; continue; }
      if (!l.trim()) { if (out.length && out[out.length - 1] !== "") out.push(""); continue; }
      if (/^\s*[eEADGBb]\s*\|[-\d|hpbr~\/\\x ]*\|?\s*$/.test(l)) { out.push("p:" + l); continue; }      // tablatura
      var tag = /^\s*\[([^\]]+)\]\s*(.*)$/.exec(l);                                                    // [Intro] A B C
      if (tag && !TOK_CHORD.test(tag[1])) {
        var rest = tag[2].trim();
        if (rest && rest.split(/\s+/).some(function (t) { return TOK_CHORD.test(t); }))
          out.push("i:" + tag[1] + ": " + rest.split(/(\s+)/).map(function (t) { return TOK_CHORD.test(t) ? "[" + t + "]" : t; }).join(""));
        else out.push("h:" + tag[1] + (rest ? " " + rest : ""));
        continue;
      }
      if (isChordLineTxt(l)) {
        var nx = src[i + 1] != null ? src[i + 1].replace(/\s+$/, "") : "";
        var chords = [], re = /\S+/g, m;
        while ((m = re.exec(l))) chords.push([m.index, m[0]]);
        if (nx.trim() && !isChordLineTxt(nx) && !/^\s*\[/.test(nx)) {
          var lyr = nx, res = "", last = 0;
          chords.forEach(function (c) {
            if (!TOK_CHORD.test(c[1])) return;
            var pos = Math.min(c[0], lyr.length);
            res += lyr.slice(last, pos) + "[" + c[1].replace(/^\(|\)$/g, "") + "]"; last = pos;
          });
          res += lyr.slice(last);
          out.push("c:" + res.replace(/^\s+/, "").replace(/ {2,}/g, " "));
          i++;
        } else {
          out.push("a:" + chords.map(function (c) { return TOK_CHORD.test(c[1]) ? "[" + c[1].replace(/^\(|\)$/g, "") + "]" : c[1]; }).join("  "));
        }
        continue;
      }
      out.push("t:" + l.trim());
    }
    while (out.length && out[out.length - 1] === "") out.pop();
    return { k: key, l: out };
  }
  function pasteSheet() {
    if (!cur) return;
    closeDrawer();
    var bg = document.createElement("div"); bg.className = "sheet-bg";
    bg.innerHTML = '<div class="sheet" role="dialog" aria-label="Colar cifra"><h2>Colar uma cifra</h2>' +
      "<p>Copie a cifra (por exemplo, do app do Cifra Club) e cole aqui, com os acordes em cima da letra. Ela fica salva neste aparelho e muda de tom sozinha.</p>" +
      '<textarea id="pasteTxt" spellcheck="false" placeholder="Tom: G&#10;&#10;[Intro] G D Em C&#10;&#10;G          D&#10;Letra da música..."></textarea>' +
      '<div class="act">' + (myCifras[cur.key] ? '<button class="btn ghost" data-a="del">Apagar</button>' : "") +
      '<button class="btn ghost" data-a="x">Cancelar</button><button class="btn" data-a="ok">Salvar</button></div></div>';
    document.body.appendChild(bg);
    var ta = bg.querySelector("#pasteTxt"); ta.value = myCifras[cur.key] || "";
    setTimeout(function () { ta.focus(); }, 50);
    bg.addEventListener("click", function (e) {
      var a = e.target.getAttribute("data-a");
      if (e.target === bg || a === "x") bg.remove();
      if (a === "del") { delete myCifras[cur.key]; save("lv.minhas", myCifras); bg.remove(); open(cur, 0); }
      if (a === "ok") {
        var v = ta.value.trim();
        if (!v) { bg.remove(); return; }
        myCifras[cur.key] = v; save("lv.minhas", myCifras); bg.remove();
        lastDoc[cur.key] = "Minha cifra"; save("lv.lastDoc", lastDoc);
        open(cur, 0);
      }
    });
  }
  $("pasteBtn").addEventListener("click", pasteSheet);

  // ---------- Letra em texto ----------
  function showLyrics(n) {
    reset(); view = "letra";
    var html = "", txt = LETRAS[n] || "";
    txt.split(/\n{2,}/).forEach(function (st) {
      html += '<div class="stanza">' + st.split("\n").map(function (ln) {
        return ln.charAt(0) === "§" ? '<div class="lmark">' + esc(ln.slice(1)) + "</div>" : '<div class="ln">' + (esc(ln) || "&nbsp;") + "</div>";
      }).join("") + "</div>";
    });
    $("pages").innerHTML = '<article class="lyrics" style="font-size:' + (19 * tzoom).toFixed(1) + 'px">' + html + "</article>";
    $("pages").scrollTop = 0;
  }

  // ---------- Menu lateral ----------
  function drawer() {
    var d = cur;
    $("dNum").textContent = d && d.n ? d.n : "";
    $("dTitle").textContent = d ? d.t : $("vName").textContent;
    $("dCol").textContent = (d ? d.cs : "Caderno") + (view === "cifra" && curCifra && curCifra.g ? (curCifra.g === 2 ? " · cifra montada da partitura — confira, pode ter palavras quebradas" : " · cifra montada a partir da partitura") : "");
    $("dDocs").innerHTML = curDocs.map(function (x, i) {
      var ic = /^(C:|M:)/.test(x[0]) ? "♪" : /^L\d/.test(x[0]) ? "¶" : "▤";
      return '<button type="button" role="tab" data-i="' + i + '" aria-selected="' + (i === curIdx) + '"><span class="di">' + ic + "</span>" + esc(x[1]) + "</button>";
    }).join("");
    $("secDocs").hidden = curDocs.length < 2;
    $("secTom").hidden = view !== "cifra";
    $("secChords").hidden = view !== "cifra";
    $("optChords").checked = showChords;
    $("secMode").hidden = !(view === "pdf" && docId && RECORTES[docId]);
    $("secMode").querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", (b.getAttribute("data-m") === "1") === cropOn); });
    $("zVal").textContent = Math.round((view === "pdf" ? zoom : tzoom) * 100) + "%";
    $("vStar").hidden = !d;
    $("pasteBtn").hidden = !d;
    if (d) $("vStar").textContent = favs.indexOf(d.key) >= 0 ? "★ Nos favoritos" : "☆ Favoritar";
    $("pasteBtn").textContent = d && myCifras[d.key] ? "Editar minha cifra" : "Colar uma cifra";
    tomUI();
  }
  function openDrawer() {
    drawer();
    $("drawerBg").hidden = false;
    $("drawer").classList.add("open"); $("drawer").setAttribute("aria-hidden", "false");
    $("vMenu").setAttribute("aria-expanded", "true");
  }
  function closeDrawer() {
    $("drawerBg").hidden = true;
    $("drawer").classList.remove("open"); $("drawer").setAttribute("aria-hidden", "true");
    $("vMenu").setAttribute("aria-expanded", "false");
  }
  $("vMenu").addEventListener("click", function () { $("drawer").classList.contains("open") ? closeDrawer() : openDrawer(); });
  $("vTitleBtn").addEventListener("click", openDrawer);
  $("drawerBg").addEventListener("click", closeDrawer);
  $("dDocs").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-i]"); if (!b) return;
    var i = +b.getAttribute("data-i");
    if (cur) { lastDoc[cur.key] = curDocs[i][1]; save("lv.lastDoc", lastDoc); open(cur, i); }
    closeDrawer();
  });
  $("secMode").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-m]"); if (!b) return;
    cropOn = b.getAttribute("data-m") === "1"; save("lv.crop", cropOn);
    drawer(); if (doc) layout();
  });
  // deslizar da borda direita abre o menu; deslizar para a direita fecha
  (function swipe() {
    var sx = 0, sy = 0, from = null;
    $("viewer").addEventListener("touchstart", function (e) {
      if (e.touches.length !== 1) { from = null; return; }
      sx = e.touches[0].clientX; sy = e.touches[0].clientY;
      from = $("drawer").classList.contains("open") ? "open" : (sx > window.innerWidth - 24 ? "edge" : null);
    }, { passive: true });
    $("viewer").addEventListener("touchend", function (e) {
      if (!from) return;
      var dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
      if (Math.abs(dx) > 50 && Math.abs(dy) < 60) {
        if (from === "edge" && dx < 0) openDrawer();
        if (from === "open" && dx > 0) closeDrawer();
      }
      from = null;
    }, { passive: true });
  })();

  function closeViewer() {
    closeDrawer(); stopScroll();
    $("viewer").hidden = true; document.documentElement.style.overflow = "";
    reset(); view = ""; curCifra = null;
    $("pages").innerHTML = "";
    keepAwake(false);
    renderChips(); run();
  }
  $("vBack").addEventListener("click", function () { history.back(); });
  window.addEventListener("popstate", function () { if (!$("viewer").hidden) closeViewer(); });
  document.addEventListener("keydown", function (e) {
    if ($("viewer").hidden) return;
    if (e.key === "Escape") { if ($("drawer").classList.contains("open")) closeDrawer(); else history.back(); }
  });
  $("vStar").addEventListener("click", function () {
    if (!cur) return;
    var i = favs.indexOf(cur.key);
    if (i >= 0) favs.splice(i, 1); else favs.unshift(cur.key);
    save("lv.favs", favs); drawer();
  });

  // Tela sempre acesa enquanto o louvor está aberto
  function keepAwake(on) {
    try {
      if (on && "wakeLock" in navigator) navigator.wakeLock.request("screen").then(function (l) { wake = l; }).catch(function () {});
      else if (!on && wake) { wake.release(); wake = null; }
    } catch (e) {}
  }
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible" && !$("viewer").hidden) keepAwake(true); });

  // ---------- Rolagem automática ----------
  var scrollSpeed = load("lv.speed", 3), rolling = false, rollLast = 0, rollAcc = 0;
  $("scrollSpeed").value = scrollSpeed;
  function rollFrame(ts) {
    if (!rolling) return;
    if (rollLast) {
      var box = $("pages");
      rollAcc += (ts - rollLast) / 1000 * (6 + scrollSpeed * 7) * (view === "pdf" ? zoom : tzoom);
      var step = Math.floor(rollAcc);
      if (step) { box.scrollTop += step; rollAcc -= step; }
      if (box.scrollTop + box.clientHeight >= box.scrollHeight - 2) { stopScroll(); return; }
    }
    rollLast = ts; requestAnimationFrame(rollFrame);
  }
  function startScroll() { rolling = true; rollLast = 0; rollAcc = 0; $("scrollFab").hidden = false; $("scrollBtn").textContent = "❚❚ Parar"; requestAnimationFrame(rollFrame); }
  function stopScroll() { rolling = false; $("scrollFab").hidden = true; $("scrollBtn").textContent = "▶ Rolar"; }
  $("scrollBtn").addEventListener("click", function () { if (rolling) stopScroll(); else { startScroll(); closeDrawer(); } });
  $("scrollFab").addEventListener("click", stopScroll);
  $("scrollSpeed").addEventListener("input", function () { scrollSpeed = +this.value; save("lv.speed", scrollSpeed); });

  // ---------- Tamanho / zoom ----------
  function setZoom(z, anchor) {
    var box = $("pages");
    if (view !== "pdf") {
      var y = box.scrollTop / Math.max(1, box.scrollHeight);
      tzoom = Math.max(0.6, Math.min(2.6, Math.round(z * 100) / 100)); save("lv.tzoom", tzoom);
      var a = box.querySelector(".cifra"); if (a) a.style.fontSize = (17 * tzoom).toFixed(1) + "px";
      var l = box.querySelector(".lyrics"); if (l) l.style.fontSize = (19 * tzoom).toFixed(1) + "px";
      box.scrollTop = y * box.scrollHeight;
      $("zVal").textContent = Math.round(tzoom * 100) + "%";
      return;
    }
    zoom = Math.max(0.5, Math.min(4, Math.round(z * 100) / 100));
    $("zVal").textContent = Math.round(zoom * 100) + "%";
    save("lv.zoom", zoom);
    if (!doc) return;
    var rel = anchor || { x: box.clientWidth / 2, y: box.clientHeight / 2 };
    var fx = (box.scrollLeft + rel.x) / Math.max(1, box.scrollWidth), fy = (box.scrollTop + rel.y) / Math.max(1, box.scrollHeight);
    layout(function () {
      box.scrollLeft = fx * box.scrollWidth - rel.x;
      box.scrollTop = fy * box.scrollHeight - rel.y;
    });
  }
  function curZ() { return view === "pdf" ? zoom : tzoom; }
  $("zIn").addEventListener("click", function () { setZoom(curZ() * (view === "pdf" ? 1.25 : 1.1)); });
  $("zOut").addEventListener("click", function () { setZoom(curZ() / (view === "pdf" ? 1.25 : 1.1)); });
  $("zVal").addEventListener("click", function () { setZoom(1); });
  (function pinch() {
    var box = $("pages"), start = 0, z0 = 1, mid = null, ratio = 1;
    function dist(t) { var dx = t[0].clientX - t[1].clientX, dy = t[0].clientY - t[1].clientY; return Math.sqrt(dx * dx + dy * dy); }
    box.addEventListener("touchstart", function (e) {
      if (e.touches.length === 2 && view) {
        start = dist(e.touches); z0 = curZ(); ratio = 1;
        var r = box.getBoundingClientRect();
        mid = { x: (e.touches[0].clientX + e.touches[1].clientX) / 2 - r.left, y: (e.touches[0].clientY + e.touches[1].clientY) / 2 - r.top };
      }
    }, { passive: true });
    box.addEventListener("touchmove", function (e) {
      if (start && e.touches.length === 2) {
        e.preventDefault();
        ratio = Math.max(0.5 / z0, Math.min(4 / z0, dist(e.touches) / start));
        Array.prototype.forEach.call(box.children, function (p) { p.style.transform = "scale(" + ratio + ")"; p.style.transformOrigin = "50% 0"; });
      }
    }, { passive: false });
    function end() {
      if (!start) return;
      start = 0;
      Array.prototype.forEach.call(box.children, function (p) { p.style.transform = ""; });
      if (Math.abs(ratio - 1) > 0.04) setZoom(z0 * ratio, mid);
    }
    box.addEventListener("touchend", end); box.addEventListener("touchcancel", end);
    document.addEventListener("gesturestart", function (e) { if (!$("viewer").hidden) e.preventDefault(); });
  })();

  // ---------- PDF ----------
  var range = [1, 0];
  function loadPdf(id, from, to, jump) {
    view = "pdf";
    var t = ++token;
    var nr = [from || 1, to || (from ? from : 0)];
    if (doc && docId === id) {
      if (nr[0] !== range[0] || nr[1] !== range[1]) { range = nr; layout(function () { scrollToPage(jump); }); }
      else { layout(function () { scrollToPage(jump); }); }
      return;
    }
    range = nr;
    if (doc) { doc.destroy(); doc = null; docId = null; }
    $("pages").innerHTML = '<div class="vmsg"><div class="spinner"></div>Abrindo…</div>';
    Promise.all([pdfjs(), fetch("pdf/" + id + ".pdf").then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.arrayBuffer(); })])
      .then(function (res) {
        if (t !== token) return;
        return res[0].getDocument({ data: new Uint8Array(res[1]), standardFontDataUrl: new URL("lib/standard_fonts/", location.href).href, isEvalSupported: false }).promise;
      })
      .then(function (pdf) {
        if (!pdf || t !== token) return;
        doc = pdf; docId = id; drawer();
        layout(function () { scrollToPage(jump); });
      })
      .catch(function (err) {
        if (t !== token) return;
        $("pages").innerHTML = '<div class="vmsg">Não foi possível abrir este arquivo' +
          (navigator.onLine ? "." : " sem internet.<br>Ele ainda não foi salvo no aparelho.") +
          '<br><br><a href="pdf/' + id + '.pdf" target="_blank" rel="noopener">Abrir o PDF direto</a></div>';
        if (window.console) console.error(err);
      });
  }
  function scrollToPage(p) {
    var el = p && $("pages").querySelector('.page[data-p="' + p + '"]');
    $("pages").scrollTop = el ? el.offsetTop - 10 : 0;
  }
  function layout(after) {
    var t = token, pdf = doc, box = $("pages");
    if (!pdf) return;
    if (observer) observer.disconnect();
    var avail = Math.min(box.clientWidth - 16, 1000);
    var width = Math.round(avail * zoom);
    var dpr = Math.min(window.devicePixelRatio || 1, 3);
    pdf.getPage(1).then(function (p1) {
      if (t !== token) return;
      var vp = p1.getViewport({ scale: 1 }), ratio = vp.height / vp.width;
      box.innerHTML = "";
      observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting && !en.target.dataset.done) { en.target.dataset.done = 1; draw(en.target); }
        });
      }, { root: box, rootMargin: "1500px 200px" });
      var last = Math.min(range[1] || pdf.numPages, pdf.numPages), first = Math.min(range[0], last);
      box.dataset.n = last - first + 1; box.dataset.first = first;
      var crops = cropOn && RECORTES[docId];
      for (var i = first; i <= last; i++) {
        var bands = crops && crops[i - 1] && crops[i - 1].length ? crops[i - 1] : [[0, 1]];
        bands.forEach(function (b) {
          var el = document.createElement("div");
          el.className = "page" + (bands.length > 1 || b[1] - b[0] < 1 ? " strip" : "");
          el.dataset.p = i; el.dataset.b0 = b[0]; el.dataset.b1 = b[1];
          el.style.width = width + "px"; el.style.height = Math.round(width * ratio * (b[1] - b[0])) + "px";
          if (width > box.clientWidth) el.style.margin = "0 8px 10px";
          box.appendChild(el); observer.observe(el);
        });
      }
      if (after) after();
    });
    var rendered = {};
    function pageCanvas(n) {
      if (!rendered[n]) rendered[n] = pdf.getPage(n).then(function (page) {
        var vp1 = page.getViewport({ scale: 1 });
        var scale = (width / vp1.width) * dpr;
        var maxPx = 14e6; if (vp1.width * vp1.height * scale * scale > maxPx) scale = Math.sqrt(maxPx / (vp1.width * vp1.height));
        var vp = page.getViewport({ scale: scale });
        var c = document.createElement("canvas");
        c.width = Math.floor(vp.width); c.height = Math.floor(vp.height);
        return page.render({ canvasContext: c.getContext("2d", { alpha: false }), viewport: vp }).promise.then(function () { return { c: c, ratio: vp1.height / vp1.width }; });
      });
      return rendered[n];
    }
    function draw(el) {
      var b0 = +el.dataset.b0, b1 = +el.dataset.b1;
      pageCanvas(+el.dataset.p).then(function (r) {
        if (t !== token) return;
        el.style.height = Math.round(width * r.ratio * (b1 - b0)) + "px";
        var full = r.c, y0 = Math.floor(b0 * full.height), h = Math.max(1, Math.ceil((b1 - b0) * full.height));
        if (b0 === 0 && b1 === 1) { el.appendChild(full); return; }
        var c = document.createElement("canvas");
        c.width = full.width; c.height = h;
        c.getContext("2d", { alpha: false }).drawImage(full, 0, y0, full.width, h, 0, 0, full.width, h);
        el.appendChild(c);
      });
    }
  }
  var rz; window.addEventListener("resize", function () { clearTimeout(rz); rz = setTimeout(function () { if (doc && view === "pdf" && !$("viewer").hidden) setZoom(zoom); }, 250); });
  var indT;
  $("pages").addEventListener("scroll", function () {
    var box = $("pages"), total = +box.dataset.n || 0;
    if (view !== "pdf" || !doc || total < 2) return;
    var ps = box.querySelectorAll(".page"), mid = box.scrollTop + box.clientHeight / 3, n = 1, f0 = +box.dataset.first || 1;
    for (var i = 0; i < ps.length; i++) { if (ps[i].offsetTop <= mid) n = +ps[i].dataset.p - f0 + 1; else break; }
    var ind = $("pageInd"); ind.textContent = n + " / " + total; ind.hidden = false; ind.style.opacity = 1;
    clearTimeout(indT); indT = setTimeout(function () { ind.style.opacity = 0; }, 1200);
  }, { passive: true });

  // ---------- Offline ----------
  var PDF_CACHE = "louvores-pdf-v1";
  var allFiles = Object.keys(FILES);
  var totalBytes = allFiles.reduce(function (a, k) { return a + FILES[k]; }, 0);
  var state = { done: 0, total: allFiles.length, running: false, error: false };
  var supported = "caches" in window && "serviceWorker" in navigator;

  function pill() {
    var b = $("offlineBtn"), t = $("offlineTxt");
    b.classList.remove("ok", "err");
    if (!supported) { t.textContent = "Online"; b.classList.add("err"); return; }
    if (state.done >= state.total) { t.textContent = "Pronto offline"; b.classList.add("ok"); }
    else if (state.running) t.textContent = "Salvando " + Math.floor(100 * state.done / state.total) + "%";
    else if (state.error) { t.textContent = "Salvar offline"; b.classList.add("err"); }
    else t.textContent = Math.floor(100 * state.done / state.total) + "% offline";
    var bar = document.querySelector(".sheet .bar > i"); if (bar) bar.style.width = (100 * state.done / state.total) + "%";
    var st = document.querySelector(".sheet .st");
    if (st) st.textContent = state.done >= state.total ? "Tudo salvo. Pode usar sem internet." : state.done + " de " + state.total + " arquivos salvos no aparelho" + (state.error && !state.running ? " — conecte-se à internet para terminar." : "");
  }

  function syncAll() {
    if (state.running || !supported) return;
    state.running = true; state.error = false; pill();
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {});
    caches.open(PDF_CACHE).then(function (cache) {
      return cache.keys().then(function (keys) {
        var have = {};
        keys.forEach(function (r) {
          var m = /pdf\/([^/?]+)\.pdf/.exec(r.url);
          if (m && FILES[m[1]]) have[m[1]] = 1; else cache.delete(r); // remove arquivos antigos
        });
        var todo = allFiles.filter(function (id) { return !have[id]; });
        state.done = state.total - todo.length; pill();
        var idx = 0, fails = 0;
        function worker() {
          if (idx >= todo.length) return Promise.resolve();
          var id = todo[idx++], url = "pdf/" + id + ".pdf";
          return fetch(url, { cache: "no-cache" }).then(function (r) {
            if (!r.ok) throw new Error(r.status);
            return cache.put(url, r);
          }).then(function () { state.done++; if (state.done % 5 === 0 || state.done === state.total) pill(); }, function () { fails++; })
            .then(worker);
        }
        return Promise.all([worker(), worker(), worker(), worker(), worker()]).then(function () { if (fails) state.error = true; });
      });
    }).catch(function () { state.error = true; })
      .then(function () { state.running = false; pill(); });
  }

  var theme = load("lv.theme", "auto");
  function applyTheme() {
    if (theme === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
  }
  applyTheme();

  function sheet() {
    var standalone = window.navigator.standalone || (window.matchMedia && matchMedia("(display-mode: standalone)").matches);
    var bg = document.createElement("div"); bg.className = "sheet-bg";
    bg.innerHTML = '<div class="sheet" role="dialog" aria-label="Uso offline"><h2>Usar sem internet</h2>' +
      "<p>" + DATA.length + " louvores e " + CADS.length + " cadernos (" + Math.round(totalBytes / 1e6) + " MB) ficam salvos no aparelho. Depois disso tudo funciona sem internet.</p>" +
      '<div class="bar"><i></i></div><p class="st"></p>' +
      (standalone ? "" : '<div class="howto"><b>No iPhone (Safari):</b> toque em <b>Compartilhar</b> → <b>Adicionar à Tela de Início</b> e abra sempre pelo ícone. Assim o iPhone não apaga os arquivos salvos.</div>') +
      '<div class="opts" role="group" aria-label="Tema">' +
      ["auto", "light", "dark"].map(function (t) { return '<button type="button" data-t="' + t + '" aria-pressed="' + (theme === t) + '">' + { auto: "Automático", light: "Claro", dark: "Escuro" }[t] + "</button>"; }).join("") + "</div>" +
      '<div class="act"><button class="btn ghost" data-a="x">Fechar</button><button class="btn" data-a="go">' + (state.done >= state.total ? "Verificar de novo" : "Salvar agora") + "</button></div></div>";
    document.body.appendChild(bg);
    bg.addEventListener("click", function (e) {
      var a = e.target.getAttribute("data-a"), t = e.target.getAttribute("data-t");
      if (e.target === bg || a === "x") bg.remove();
      if (a === "go") syncAll();
      if (t) {
        theme = t; save("lv.theme", t); applyTheme();
        bg.querySelectorAll("[data-t]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-t") === t); });
      }
    });
    pill();
  }
  $("offlineBtn").addEventListener("click", sheet);

  if (supported) {
    navigator.serviceWorker.register("sw.js").then(function () { return navigator.serviceWorker.ready; })
      .then(function () { syncAll(); })
      .catch(function () { state.error = true; pill(); });
    window.addEventListener("online", function () { if (state.done < state.total) syncAll(); });
  } else pill();

  // ---------- Início ----------
  $("ver").textContent = "v" + (window.DATA_VERSION || "").slice(0, 6);
  renderChips();
  run();
})();
