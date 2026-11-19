(function () {
  "use strict";
  var DATA = window.LOUVORES || [];
  var CADS = window.CADERNOS || [];
  var FILES = window.ARQUIVOS || {};
  var LETRAS = [];
  var CIFRAS = {};
  // carregamento sob demanda: busca na letra e conteúdo das cifras/letras
  var LOADS = {}, WAIT = {};
  window.__lv = function (name) { (WAIT[name] || []).forEach(function (f) { f(); }); WAIT[name] = null; LOADS[name] = true; };
  function need(name, cb) {
    if (LOADS[name] === true) { if (cb) cb(); return; }
    if (cb) (WAIT[name] = WAIT[name] || []).push(cb);
    if (LOADS[name]) return;
    LOADS[name] = "loading";
    var sc = document.createElement("script"); sc.src = name + ".js?v=" + (window.DATA_VERSION || ""); sc.async = true;
    sc.onerror = function () { LOADS[name] = false; setTimeout(function () { need(name); }, 3000); };
    document.head.appendChild(sc);
  }
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
    d.sk = d.key + "|" + d.c + "|" + d.n + "|" + d.t;   // único (louvores repetidos dividem o mesmo arquivo)
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
  CADS.forEach(function (c, ci) { c.ci = ci; });
  var searchReady = false;
  function onBusca() {
    var B = window.BUSCA || [], BC = window.BUSCA_CAD || [];
    DATA.forEach(function (d, i) {
      var nt = d.nt, ct = d.ct, tw = d.tw;
      prep(d, d.t, B[i] || ""); d.nt = nt; d.ct = ct; d.tw = tw;
    });
    CADS.forEach(function (c, ci) {
      (BC[ci] || []).forEach(function (txt, pi) { var pg = { cad: c, page: pi + 1 }; prep(pg, c.t, txt); PAGES.push(pg); });
    });
    window.BUSCA = window.BUSCA_CAD = null;
    searchReady = true;
    if ($("q").value) run();
  }
  function onConteudo() {
    LETRAS = window.LETRAS || []; CIFRAS = window.CIFRAS || {};
    window.LETRAS = window.CIFRAS = null;
  }

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
    if (typeof curTab !== "undefined") { curTab = filter === "fav" ? "fav" : "songs"; document.querySelectorAll("#tabbar [data-tab]").forEach(function (x) { x.setAttribute("aria-selected", x.getAttribute("data-tab") === curTab); }); }
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
    return '<div class="badge' + (d.n.length > 3 ? " long" : "") + '">' + esc(d.n) + "</div>";
  }
  function tagOf(d) {
    if (d.hasCifra) return '<span class="tag t-cifra">Cifra</span>';
    if (d.k === "letra") return '<span class="tag t-letra">Letra</span>';
    if (d.k === "parte") return '<span class="tag t-parte">' + esc(d.d[0][1].split(" · ")[0]) + "</span>";
    return '<span class="tag t-partitura">Partitura</span>';
  }
  function itemHTML(d, snip) {
    return '<li class="item" data-i="' + d.i + '">' + badge(d) +
      '<div class="info"><div class="title">' + esc(d.t) + '</div>' +
      '<div class="line2">' + tagOf(d) + '<span class="col">' + esc(d.cs) + "</span></div>" +
      (snip ? '<div class="snip">' + snip + "</div>" : "") + "</div>" +
      (favs.indexOf(d.key) >= 0 ? STAR : "") + addBtn(d) + "</li>";
  }
  var PLUS = '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.8" stroke-linecap="round"/></svg>';
  var CHECK = '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function addBtn(d) {
    var on = inSet(d);
    return '<button class="add' + (on ? " on" : "") + '" type="button" data-add="' + d.i + '" aria-label="' + (on ? "Tirar da lista do culto" : "Adicionar à lista do culto") + '"><i>' + (on ? CHECK : PLUS) + "</i></button>";
  }
  function cadHTML(pg, snip) {
    var c = pg.cad;
    return '<li class="item" data-c="' + c.ci + '" data-p="' + (pg.page || 1) + '"><div class="badge cad">' + BOOK + "</div>" +
      '<div class="info"><div class="title">' + esc(c.t) + "</div>" +
      '<div class="line2"><span class="tag t-' + (c.k === "Cifra" ? "cifra" : c.k === "Letra" ? "letra" : "partitura") + '">' + esc(c.k) + "</span>" +
      '<span class="col">' + (pg.page ? "Página " + pg.page + " de " + c.n : c.n + " páginas") + "</span></div>" +
      (snip ? '<div class="snip">' + snip + "</div>" : "") + "</div></li>";
  }

  // renderização em blocos (lista longa)
  var queue = [], shown = 0, curToks = [];
  var CHUNK = 60;
  function paint(rows) {
    queue = rows; shown = 0;
    var L = $("list"); L.classList.remove("fresh"); void L.offsetWidth; L.classList.add("fresh");
    L.innerHTML = "";
    more();
  }
  function more() {
    var html = "", end = Math.min(queue.length, shown + CHUNK);
    for (; shown < end; shown++) {
      var r = queue[shown];
      var prev = queue[shown - 1], next = queue[shown + 1];
      var g = (!prev || prev.sec ? " gf" : "") + (!next || next.sec ? " gl" : "");
      if (r.sec) html += '<li class="sec">' + esc(r.sec) + "</li>";
      else if (r.pg) html += cadHTML(r.pg, r.snip ? snippet(r.pg, curToks) : "").replace('class="item"', 'class="item' + g + '"');
      else html += itemHTML(r.d, r.why === "l" ? snippet(r.d, curToks) : "").replace('class="item"', 'class="item' + g + '"');
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
      $("empty").querySelector("p").textContent = filter === "fav" ? "Nenhum favorito ainda" : "Nenhum louvor encontrado";
      $("empty").querySelector("span").textContent = filter === "fav" ? "Abra um louvor e toque em ☆ Favoritar no menu ⋮ para guardar aqui." : "Tente outra palavra, o número ou um trecho diferente da letra.";
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
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && $("viewer").hidden && document.activeElement !== $("q") && !document.querySelector(".sheet-bg")) { e.preventDefault(); if (curTab === "set") showTab("songs"); $("q").focus(); }
  });
  $("q").addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault(); $("q").blur();
      var first = queue.filter(function (r) { return r.d; })[0];
      if (first && first.s >= 950) open(first.d);
    }
  });
  $("clear").addEventListener("click", function () { $("q").value = ""; run(); $("q").focus(); });
  $("list").addEventListener("click", function (e) {
    var ab = e.target.closest("[data-add]");
    if (ab) { e.stopPropagation(); toggleSet(DATA[+ab.getAttribute("data-add")]); return; }
    var li = e.target.closest(".item"); if (!li) return;
    if (li.hasAttribute("data-c")) {
      var c = CADS[+li.getAttribute("data-c")];
      openCad(c, +li.getAttribute("data-p") || 1);
    } else { setPos = -1; open(DATA[+li.getAttribute("data-i")]); }
  });

  // ---------- Visualizador ----------
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
    if (closing) { closing = false; $("viewer").classList.remove("out"); }
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
    if (/^(C:|L\d)/.test(di[0]) && LOADS.conteudo !== true) {
      reset(); $("pages").innerHTML = '<div class="vmsg"><div class="spinner"></div>Carregando…</div>';
      drawer(); dockUI();
      need("conteudo", function () { if (cur === d && curIdx === idx) open(d, idx); });
      return;
    }
    if (/^C:/.test(di[0])) {
      var K = di[0].slice(2), base = CIFRAS[K];
      showCifra(base && edits[K] ? { k: base.k, l: edits[K], g: base.g, ed: 1 } : base, K);
      subLabel();
    }
    else if (/^M:/.test(di[0])) showCifra(parsePasted(myCifras[d.key]), null);
    else if (/^L\d+$/.test(di[0])) showLyrics(+di[0].slice(1));
    else loadPdf(di[0], di[2], di[3]);
    drawer();
    $("vdock").classList.remove("hide");
    dockUI();
  }
  function openCad(c, page) {
    cur = null; curDocs = [[c.id, c.k, 0, 0]]; curIdx = 0;
    $("vName").textContent = c.t; $("vSub").textContent = c.k + (page > 1 ? " · pág. " + page : "");
    setPos = -1; showViewer(); stopScroll(); loadPdf(c.id, 0, 0, page); drawer(); dockUI();
  }
  function reset() {
    token++;
    $("pages").classList.remove("txt");
    if (doc) { doc.destroy(); doc = null; docId = null; }
    if (observer) observer.disconnect();
    $("pageInd").hidden = true;
  }

  // ---------- Acordes: leitura e transposição ----------
  var SH = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  var FL = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"];
  var IDX = { C: 0, "B#": 0, "C#": 1, Db: 1, D: 2, "D#": 3, Eb: 3, E: 4, Fb: 4, F: 5, "E#": 5, "F#": 6, Gb: 6, G: 7, "G#": 8, Ab: 8, A: 9, "A#": 10, Bb: 10, B: 11, Cb: 11 };
  var CHORD_RE = /^([A-G])(#|b)?(.*?)(?:\/([A-G])(#|b)?)?$/;
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
    return "";
  }

  // ---------- Cifra (estilo Cifra Club) ----------
  function cifraShift() { return (cur && tons[cur.key]) || 0; }
  var edits = load("lv.edits", {}), editing = false, cifraKey = null;
  function showCifra(c, key) {
    reset(); view = "cifra"; curCifra = c; cifraKey = key || null; editing = false; editBar();
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
    var sc = showChords || editing;
    c.l.forEach(function (line, li) {
      if (!line) { flush(); return; }
      var t = line.slice(0, 2), s = line.slice(2);
      if (t === "h:") { flush(); stanza.push('<div class="ch-h">' + esc(s) + "</div>"); return; }
      if (t === "t:") { stanza.push('<div class="cl">' + (esc(s) || "&nbsp;") + "</div>"); return; }
      if (t === "p:") { stanza.push('<pre class="cp">' + esc(s) + "</pre>"); return; }
      if (t === "i:" || t === "a:") {
        if (!sc) return;
        stanza.push('<div class="ci">' + s.split(/(\[[^\]]+\])/).map(function (p) {
          return /^\[.+\]$/.test(p) ? chordHTML(p.slice(1, -1)) : esc(p);
        }).join("") + "</div>");
        return;
      }
      // linha cantada: cada palavra é um bloco (acorde em cima, sílaba embaixo)
      if (!sc || (!editing && s.indexOf("[") < 0)) { stanza.push('<div class="cl">' + (esc(s.replace(/\[[^\]]+\]/g, "")) || "&nbsp;") + "</div>"); return; }
      var parts = s.split(/(\[[^\]]+\])/), out = "", pend = null, po = 0, kc = {};
      function seg(ch, txt, pos) {
        var k = kc[pos] || 0;
        if (ch) kc[pos] = k + 1;
        var at = editing && t === "c:" ? ' data-l="' + li + '" data-o="' + pos + '" data-k="' + k + '"' : "";
        return '<span class="sg"' + at + '><b class="ch">' + (ch ? esc(trChord(ch, shift, flats)) : "") + '</b><span class="sy">' + (txt ? esc(txt) : "&nbsp;") + "</span></span>";
      }
      function words(txt, ch) {
        var ws = txt.match(/\S+\s*|\s+/g) || [];
        if (!ws.length && ch) { out += seg(ch, "\u00a0\u00a0", po); return; }
        ws.forEach(function (w, k) { out += seg(k === 0 ? ch : null, w, po); po += w.length; });
      }
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i];
        if (/^\[.+\]$/.test(p)) {
          if (pend !== null) out += seg(pend, "\u00a0\u00a0", po);
          pend = p.slice(1, -1);
        } else if (p) { words(p, pend); pend = null; }
      }
      if (pend !== null) out += seg(pend, "\u00a0\u00a0", po);
      if (editing && t === "c:") out += seg(null, "\u00a0+\u00a0", po);
      stanza.push('<div class="cl has">' + out + "</div>");
    });
    flush();
    $("pages").classList.add("txt");
    $("pages").innerHTML = '<article class="cifra' + (editing ? " editing" : "") + '" style="font-size:' + (17 * tzoom).toFixed(1) + 'px">' + html + "</article>";
    var art = $("pages").firstChild;
    if (art && window.innerWidth >= 1024 && window.innerWidth > window.innerHeight && art.scrollHeight > $("pages").clientHeight * 1.05) art.classList.add("cols");
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
    if (!$("viewer").hidden) dockUI();
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


  // ---------- Editor de acordes ----------
  function splitLine(s) {
    var plain = "", chords = [];
    s.split(/(\[[^\]]+\])/).forEach(function (p) {
      if (/^\[.+\]$/.test(p)) chords.push([plain.length, p.slice(1, -1)]); else plain += p;
    });
    return { plain: plain, chords: chords };
  }
  function joinLine(o) {
    var out = "", last = 0;
    o.chords.forEach(function (c) { out += o.plain.slice(last, c[0]) + "[" + c[1] + "]"; last = c[0]; });
    return out + o.plain.slice(last);
  }
  function subLabel() {
    if (view === "cifra" && curCifra && curCifra.g === 3 && curCifra.l.some(function (l) { return l.indexOf("[") >= 0; })) $("vSub").textContent = "Cifra";
  }
  function setChordAt(li, pos, k, chord) {
    var lines = curCifra.l.slice(), line = lines[li];
    if (!line || line.slice(0, 2) !== "c:") return;
    var o = splitLine(line.slice(2)), same = o.chords.filter(function (c) { return c[0] === pos; });
    var others = o.chords.filter(function (c) { return c[0] !== pos; });
    if (k < same.length) { if (chord) same[k][1] = chord; else same.splice(k, 1); }
    else if (chord) same.push([pos, chord]);
    o.chords = others.concat(same).sort(function (a, b) { return a[0] - b[0]; });
    lines[li] = "c:" + joinLine(o);
    curCifra = { k: curCifra.k, l: lines, g: curCifra.g, ed: 1 };
    if (cifraKey) { edits[cifraKey] = lines; save("lv.edits", edits); }
    var y = $("pages").scrollTop; renderCifra(); $("pages").scrollTop = y; subLabel();
  }
  function chordAt(li, pos, k) {
    var line = curCifra.l[li]; if (!line) return null;
    var c = splitLine(line.slice(2)).chords.filter(function (c) { return c[0] === pos; })[k];
    return c ? c[1] : null;
  }
  function editBar() {
    var b = $("editBar");
    if (!b) {
      b = document.createElement("div"); b.id = "editBar"; b.className = "editbar";
      b.innerHTML = '<span>Toque numa palavra para pôr ou trocar o acorde</span><button type="button" id="editDone">Concluir</button>';
      $("viewer").appendChild(b);
      $("editDone").addEventListener("click", function () { editing = false; editBar(); renderCifra(); });
    }
    b.hidden = !editing;
    $("viewer").classList.toggle("editing", editing);
  }
  $("editBtn").addEventListener("click", function () {
    if (view !== "cifra" || !curCifra || !cifraKey) return;
    editing = !editing; closeDrawer(); editBar(); stopScroll(); renderCifra();
  });
  $("editUndo").addEventListener("click", function () {
    if (!cifraKey || !edits[cifraKey]) return;
    if (!confirm("Desfazer todas as suas alterações de acordes nesta cifra?")) return;
    delete edits[cifraKey]; save("lv.edits", edits);
    closeDrawer(); open(cur, curIdx);
  });
  $("pages").addEventListener("click", function (e) {
    if (!editing) return;
    var sg = e.target.closest(".sg[data-l]"); if (!sg) return;
    chordPicker(+sg.getAttribute("data-l"), +sg.getAttribute("data-o"), +sg.getAttribute("data-k"));
  });
  var ROOTS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
  var QUALS = ["", "m", "7", "m7", "maj7", "sus4", "4", "9", "6", "dim", "º", "7(9)", "m7(b5)", "add9"];
  function chordPicker(li, pos, k) {
    var ok = keyInfo(origKey(curCifra)), shift = ok ? cifraShift() : 0;
    var flats = ok ? useFlats(ok.i + shift, ok.minor) : false;
    var curCh = chordAt(li, pos, k), shown = curCh ? trChord(curCh, shift, flats) : "";
    var m = /^([A-G](?:#|b)?)([^/]*)(?:\/([A-G](?:#|b)?))?$/.exec(shown) || [];
    var st = { r: m[1] || "", q: m[2] || "", b: m[3] || "" };
    var used = {};
    curCifra.l.forEach(function (l) { (l.match(/\[([^\]]+)\]/g) || []).forEach(function (x) { used[trChord(x.slice(1, -1), shift, flats)] = 1; }); });
    var bg = document.createElement("div"); bg.className = "sheet-bg";
    var word = (splitLine(curCifra.l[li].slice(2)).plain.slice(pos).match(/^\S*/) || [""])[0] || "fim da linha";
    bg.innerHTML = '<div class="sheet picker" role="dialog" aria-label="Escolher acorde"><h2>Acorde em “' + esc(word) + '”</h2>' +
      '<div class="pv"><input id="pkIn" type="text" autocapitalize="off" autocorrect="off" spellcheck="false" value="' + esc(shown) + '" placeholder="ex.: G, Em7, D/F#"></div>' +
      (Object.keys(used).length ? '<div class="dlab">Desta música</div><div class="pk used">' + Object.keys(used).map(function (c) { return '<button type="button" data-c="' + esc(c) + '">' + esc(c) + "</button>"; }).join("") + "</div>" : "") +
      '<div class="dlab">Nota</div><div class="pk roots">' + ROOTS.map(function (r) { return '<button type="button" data-r="' + r + '">' + r + "</button>"; }).join("") + "</div>" +
      '<div class="dlab">Tipo</div><div class="pk quals">' + QUALS.map(function (q) { return '<button type="button" data-q="' + q + '">' + (q || "maior") + "</button>"; }).join("") + "</div>" +
      '<div class="dlab">Baixo</div><div class="pk bass"><button type="button" data-b="">—</button>' + ROOTS.map(function (r) { return '<button type="button" data-b="' + r + '">/' + r + "</button>"; }).join("") + "</div>" +
      '<div class="act"><button class="btn ghost" data-a="del">Tirar</button><button class="btn ghost" data-a="x">Cancelar</button><button class="btn" data-a="ok">Pôr acorde</button></div></div>';
    document.body.appendChild(bg);
    var inp = bg.querySelector("#pkIn");
    function sync() {
      inp.value = st.r ? st.r + st.q + (st.b ? "/" + st.b : "") : inp.value;
      bg.querySelectorAll("[data-r]").forEach(function (x) { x.classList.toggle("on", x.getAttribute("data-r") === st.r); });
      bg.querySelectorAll("[data-q]").forEach(function (x) { x.classList.toggle("on", x.getAttribute("data-q") === st.q); });
      bg.querySelectorAll("[data-b]").forEach(function (x) { x.classList.toggle("on", x.getAttribute("data-b") === st.b); });
    }
    sync();
    bg.addEventListener("click", function (e) {
      var t = e.target, a = t.getAttribute("data-a");
      if (t === bg || a === "x") { bg.remove(); return; }
      if (t.hasAttribute("data-c")) { inp.value = t.getAttribute("data-c"); st = { r: "", q: "", b: "" }; bg.querySelectorAll(".on").forEach(function (x) { x.classList.remove("on"); }); return; }
      if (t.hasAttribute("data-r")) { st.r = t.getAttribute("data-r"); sync(); return; }
      if (t.hasAttribute("data-q")) { st.q = t.getAttribute("data-q"); if (!st.r) st.r = "C"; sync(); return; }
      if (t.hasAttribute("data-b")) { st.b = t.getAttribute("data-b"); if (!st.r) st.r = "C"; sync(); return; }
      if (a === "del") { setChordAt(li, pos, k, null); bg.remove(); return; }
      if (a === "ok") {
        var v = inp.value.trim().replace(/\s+/g, "");
        if (!v) { setChordAt(li, pos, k, null); bg.remove(); return; }
        if (!CHORD_RE.test(v)) { inp.focus(); inp.classList.add("bad"); return; }
        setChordAt(li, pos, k, trChord(v, -shift, ok ? useFlats(ok.i, ok.minor) : false));   // guarda no tom original
        bg.remove();
      }
    });
    inp.addEventListener("input", function () { inp.classList.remove("bad"); });
  }

  // ---------- Letra em texto ----------
  function showLyrics(n) {
    reset(); view = "letra";
    var html = "", txt = LETRAS[n] || "";
    txt.split(/\n{2,}/).forEach(function (st) {
      html += '<div class="stanza">' + st.split("\n").map(function (ln) {
        return ln.charAt(0) === "§" ? '<div class="lmark">' + esc(ln.slice(1)) + "</div>" : '<div class="ln">' + (esc(ln) || "&nbsp;") + "</div>";
      }).join("") + "</div>";
    });
    $("pages").classList.add("txt");
    $("pages").innerHTML = '<article class="lyrics" style="font-size:' + (19 * tzoom).toFixed(1) + 'px">' + html + "</article>";
    $("pages").scrollTop = 0;
  }

  // ---------- Menu lateral ----------
  function drawer() {
    var d = cur;
    $("dNum").textContent = d && d.n ? d.n : "";
    $("dTitle").textContent = d ? d.t : $("vName").textContent;
    var note = "";
    if (view === "cifra" && curCifra) {
      if (curCifra.g === 3) note = curCifra.ed ? " · acordes colocados por você" : " · a partitura não tem acordes — use “Adicionar acordes”";
      else if (curCifra.g === 2) note = " · cifra montada da partitura — confira, pode ter palavras quebradas";
      else if (curCifra.g === 1) note = " · cifra montada a partir da partitura";
      if (curCifra.ed && curCifra.g !== 3) note += " · com suas alterações";
    }
    $("dCol").textContent = (d ? d.cs : "Caderno") + note;
    $("dDocs").innerHTML = curDocs.map(function (x, i) {
      var ic = /^(C:|M:)/.test(x[0]) ? "♪" : /^L\d/.test(x[0]) ? "¶" : "▤";
      return '<button type="button" role="tab" data-i="' + i + '" aria-selected="' + (i === curIdx) + '"><span class="di">' + ic + "</span>" + esc(x[1]) + "</button>";
    }).join("");
    $("secDocs").hidden = curDocs.length < 2;
    $("secTom").hidden = view !== "cifra" || !curCifra || !keyInfo(origKey(curCifra));
    $("secEdit").hidden = !(view === "cifra" && cifraKey);
    $("editBtn").textContent = editing ? "✓ Concluir edição" : (curCifra && curCifra.g === 3 && !curCifra.ed ? "✎ Adicionar acordes" : "✎ Editar acordes");
    $("editUndo").hidden = !(cifraKey && edits[cifraKey]);
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
    drawerAdd();
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
      from = $("drawer").classList.contains("open") ? "open" : (setPos >= 0 && !editing ? "set" : (sx > window.innerWidth - 24 ? "edge" : null));
    }, { passive: true });
    $("viewer").addEventListener("touchend", function (e) {
      if (!from) return;
      var dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
      if (Math.abs(dx) > 50 && Math.abs(dy) < 60) {
        if (from === "edge" && dx < 0) openDrawer();
        if (from === "open" && dx > 0) closeDrawer();
        if (from === "set" && Math.abs(dx) > 60 && Math.abs(dy) < Math.abs(dx) * 0.6) {
          var pg = $("pages");
          if (pg.scrollWidth <= pg.clientWidth + 4 || view !== "pdf") goSet(dx < 0 ? 1 : -1);
        }
      }
      from = null;
    }, { passive: true });
  })();

  function closeViewer() {
    closeDrawer(); stopScroll();
    var v = $("viewer");
    if (!window.matchMedia || !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      v.classList.add("out");
      setTimeout(function () { v.classList.remove("out"); }, 190);
    }
    closing = true;
    setTimeout(function () { if (closing) finishClose(); }, 170);
  }
  var closing = false;
  function finishClose() {
    closing = false;
    $("viewer").hidden = true; document.documentElement.style.overflow = "";
    reset(); view = ""; curCifra = null;
    $("pages").innerHTML = "";
    keepAwake(false);
    setPos = -1;
    if (!$("tabSet").hidden) renderSet(); else { renderChips(); run(); }
    afterSetChange();
  }
  $("vBack").addEventListener("click", function () { history.back(); });
  window.addEventListener("popstate", function () { if (!$("viewer").hidden) closeViewer(); });
  document.addEventListener("keydown", function (e) {
    if ($("viewer").hidden) return;
    if (e.key === "Escape") { if ($("drawer").classList.contains("open")) closeDrawer(); else history.back(); }
    if (e.target && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
    if (setPos >= 0 && (e.key === "ArrowRight" || e.key === "PageDown" && e.shiftKey)) { e.preventDefault(); goSet(1); }
    if (setPos >= 0 && e.key === "ArrowLeft") { e.preventDefault(); goSet(-1); }
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
  function startScroll() { rolling = true; rollLast = 0; rollAcc = 0; $("scrollFab").hidden = false; $("scrollBtn").textContent = "❚❚ Parar"; $("vdock").classList.add("hide"); $("qRoll").classList.add("on"); requestAnimationFrame(rollFrame); }
  function stopScroll() { rolling = false; $("scrollFab").hidden = true; $("scrollBtn").textContent = "▶ Rolar"; $("qRoll").classList.remove("on"); $("vdock").classList.remove("hide"); }
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
  // Essencial (sempre salvo): partituras dos louvores que não têm cifra nem letra em texto + cadernos.
  // O resto das partituras é salvo quando você abre, ou tudo de uma vez se escolher "Baixar todas".
  var allPdf = load("lv.allpdf", false);
  var essential = {};
  DATA.forEach(function (d) {
    if (!d.d.some(function (x) { return /^(C:|L\d)/.test(x[0]); })) d.d.forEach(function (x) { if (FILES[x[0]]) essential[x[0]] = 1; });
  });
  CADS.forEach(function (c) { if (FILES[c.id]) essential[c.id] = 1; });
  function wanted() { return Object.keys(FILES).filter(function (k) { return allPdf || essential[k]; }); }
  var allFiles = wanted();
  function bytesOf(list) { return list.reduce(function (a, k) { return a + FILES[k]; }, 0); }
  var totalBytes = bytesOf(Object.keys(FILES));
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
    if (st) st.textContent = state.done >= state.total ? (allPdf ? "Tudo salvo, inclusive todas as partituras." : "Pronto. Cifras, letras e partituras essenciais salvas.") : state.done + " de " + state.total + " partituras salvas no aparelho" + (state.error && !state.running ? " — conecte-se à internet para terminar." : "");
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
          if (m && FILES[m[1]]) have[m[1]] = 1; else if (!m || !FILES[m[1]]) cache.delete(r); // tira arquivos que saíram do site
        });
        allFiles = wanted(); state.total = allFiles.length;
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
        return Promise.all([worker(), worker(), worker()]).then(function () { if (fails) state.error = true; });
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
      "<p>Todas as cifras e letras (" + DATA.length + " louvores) já ficam salvas no aparelho e funcionam sem internet. As partituras são salvas quando você abre cada uma.</p>" +
      '<div class="bar"><i></i></div><p class="st"></p>' +
      '<label class="dsw sw-all"><span>Baixar todas as partituras<small>' + Math.round(totalBytes / 1e6) + ' MB · para usar qualquer partitura sem internet</small></span><input type="checkbox" id="allPdf"' + (allPdf ? " checked" : "") + "><i></i></label>" +
      (standalone ? "" : '<div class="howto"><b>No iPhone (Safari):</b> toque em <b>Compartilhar</b> → <b>Adicionar à Tela de Início</b> e abra sempre pelo ícone. Assim o iPhone não apaga os arquivos salvos.</div>') +
      '<div class="opts" role="group" aria-label="Tema">' +
      ["auto", "light", "dark"].map(function (t) { return '<button type="button" data-t="' + t + '" aria-pressed="' + (theme === t) + '">' + { auto: "Automático", light: "Claro", dark: "Escuro" }[t] + "</button>"; }).join("") + "</div>" +
      '<div class="act"><button class="btn ghost" data-a="x">Fechar</button><button class="btn" data-a="go">' + (state.done >= state.total ? "Verificar de novo" : "Salvar agora") + "</button></div></div>";
    document.body.appendChild(bg);
    bg.querySelector("#allPdf").addEventListener("change", function () {
      allPdf = this.checked; save("lv.allpdf", allPdf);
      allFiles = wanted(); state.total = allFiles.length; state.done = 0;
      if (allPdf) syncAll(); else { pill(); syncAll(); }
    });
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

  // ---------- Lista do culto ----------
  var BYKEY = {}, BYSID = {};
  function sid(str) {   // id curto e estável de cada louvor (para o link)
    var a = 5381, b = 52711;
    for (var i = 0; i < str.length; i++) { var c = str.charCodeAt(i); a = (a * 33) ^ c; b = (b * 31 + c) | 0; }
    return ((a >>> 0).toString(36) + (b >>> 0).toString(36)).slice(0, 7);
  }
  DATA.forEach(function (d) { BYKEY[d.sk] = d; d.sid = sid(d.sk); BYSID[d.sid] = d; });
  function today() {
    var d = new Date(), w = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"][d.getDay()];
    return "Culto de " + w.toLowerCase() + ", " + d.getDate() + "/" + (d.getMonth() + 1);
  }
  var setState = load("lv.sets", null);
  if (!setState || !setState.lists || !setState.lists.length) {
    setState = { cur: "s1", lists: [{ id: "s1", name: "Culto", items: [], t: Date.now() }] };
  }
  function curSet() {
    var s = setState.lists.filter(function (x) { return x.id === setState.cur; })[0];
    if (!s) { s = setState.lists[0]; setState.cur = s.id; }
    s.items = s.items.filter(function (k) { return BYKEY[k]; });
    return s;
  }
  function saveSets() { curSet().t = Date.now(); save("lv.sets", setState); }
  function inSet(d) { return curSet().items.indexOf(d.sk) >= 0; }
  function toggleSet(d, silent) {
    var s = curSet(), i = s.items.indexOf(d.sk);
    if (i >= 0) {
      s.items.splice(i, 1); saveSets();
      if (!silent) toast("Removido da lista", "Desfazer", function () { s.items.splice(Math.min(i, s.items.length), 0, d.sk); saveSets(); afterSetChange(); });
    } else {
      s.items.push(d.sk); saveSets();
      if (!silent) toast("Adicionado à lista · " + s.items.length + "º louvor");
      var b = $("setBadge"); b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop");
    }
    afterSetChange();
  }
  function afterSetChange() {
    var n = curSet().items.length, b = $("setBadge");
    b.hidden = !n; b.textContent = n;
    document.querySelectorAll("#list [data-add]").forEach(function (btn) {
      var d = DATA[+btn.getAttribute("data-add")], on = inSet(d);
      btn.classList.toggle("on", on); btn.innerHTML = "<i>" + (on ? CHECK : PLUS) + "</i>";
      btn.setAttribute("aria-label", on ? "Tirar da lista do culto" : "Adicionar à lista do culto");
    });
    if (!$("tabSet").hidden) renderSet();
    if (!$("viewer").hidden) { dockUI(); drawerAdd(); }
  }

  var toastT;
  function toast(msg, act, fn) {
    var t = $("toast");
    t.innerHTML = "<span>" + esc(msg) + "</span>" + (act ? '<button type="button">' + esc(act) + "</button>" : "");
    t.hidden = false; t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
    if (act) t.querySelector("button").onclick = function () { t.hidden = true; fn(); };
    clearTimeout(toastT); toastT = setTimeout(function () { t.hidden = true; }, act ? 4000 : 1800);
  }

  function keyLabel(d) {
    var k = null;
    d.d.some(function (x) {
      if (/^C:/.test(x[0]) && CIFRAS[x[0].slice(2)]) { k = CIFRAS[x[0].slice(2)]; return true; }
      return false;
    });
    if (!k) return "";
    var ok = keyInfo(origKey(k)); if (!ok) return "";
    return keyName(ok.i + (tons[d.key] || 0), ok.minor);
  }
  var HANDLE = '<svg viewBox="0 0 24 24"><circle cx="9" cy="6" r="1.6" fill="currentColor"/><circle cx="15" cy="6" r="1.6" fill="currentColor"/><circle cx="9" cy="12" r="1.6" fill="currentColor"/><circle cx="15" cy="12" r="1.6" fill="currentColor"/><circle cx="9" cy="18" r="1.6" fill="currentColor"/><circle cx="15" cy="18" r="1.6" fill="currentColor"/></svg>';
  var XICON = '<svg viewBox="0 0 24 24"><path d="M7 7l10 10M17 7L7 17" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>';
  function renderSet() {
    var s = curSet();
    $("setName").textContent = s.name;
    var n = s.items.length;
    $("setInfo").textContent = n ? n + (n === 1 ? " louvor" : " louvores") + " · toque para abrir, arraste ⠿ para mudar a ordem" : "";
    $("setPlay").hidden = !n; $("setEmpty").hidden = !!n;
    $("setList").innerHTML = s.items.map(function (k, i) {
      var d = BYKEY[k], kl = keyLabel(d);
      return '<li class="si" data-k="' + esc(k) + '">' +
        '<button class="si-handle" type="button" aria-label="Arrastar para mudar a ordem">' + HANDLE + "</button>" +
        '<div class="si-n">' + (i + 1) + "</div>" +
        '<button class="si-main" type="button" data-open="' + i + '"><div class="si-t">' + esc(d.t) + "</div>" +
        '<div class="si-s">' + (kl ? '<span class="k">' + esc(kl) + "</span>" : "") + "<span>" + esc((d.n ? d.n + " · " : "") + d.c) + "</span></div></button>" +
        '<button class="si-x" type="button" data-rm="' + i + '" aria-label="Tirar da lista">' + XICON + "</button></li>";
    }).join("");
  }
  $("setList").addEventListener("click", function (e) {
    var o = e.target.closest("[data-open]"), r = e.target.closest("[data-rm]");
    if (o) openFromSet(+o.getAttribute("data-open"));
    if (r) toggleSet(BYKEY[curSet().items[+r.getAttribute("data-rm")]]);
  });
  $("setPlay").addEventListener("click", function () { openFromSet(0); });
  $("setGo").addEventListener("click", function () { showTab("songs"); setTimeout(function () { $("q").focus(); }, 50); });

  // arrastar para reordenar (pelo ⠿)
  (function dragSort() {
    var box = $("setList"), el = null, sy = 0, start = 0, h = 0, rows = [], to = 0;
    box.addEventListener("pointerdown", function (e) {
      var hd = e.target.closest(".si-handle"); if (!hd) return;
      e.preventDefault();
      el = hd.closest(".si"); rows = Array.prototype.slice.call(box.children);
      start = to = rows.indexOf(el); sy = e.clientY; h = el.offsetHeight + 8;
      el.classList.add("drag"); hd.setPointerCapture(e.pointerId);
      if (navigator.vibrate) navigator.vibrate(8);
    });
    box.addEventListener("pointermove", function (e) {
      if (!el) return;
      var dy = e.clientY - sy;
      el.style.transform = "translateY(" + dy + "px) scale(1.02)";
      to = Math.max(0, Math.min(rows.length - 1, start + Math.round(dy / h)));
      rows.forEach(function (r, i) {
        if (r === el) return;
        var shift = (i > start && i <= to) ? -h : (i < start && i >= to) ? h : 0;
        r.style.transform = shift ? "translateY(" + shift + "px)" : "";
      });
    });
    function end() {
      if (!el) return;
      rows.forEach(function (r) { r.style.transform = ""; });
      el.classList.remove("drag");
      if (to !== start) {
        var it = curSet().items, k = it.splice(start, 1)[0]; it.splice(to, 0, k); saveSets();
      }
      el = null; renderSet();
    }
    box.addEventListener("pointerup", end); box.addEventListener("pointercancel", end);
  })();

  function copyText(t, msg) {
    function fallback() {
      var ta = document.createElement("textarea"); ta.value = t; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); toast(msg); } catch (e) { toast("Não foi possível copiar"); }
      ta.remove();
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(function () { toast(msg); }, fallback);
    else fallback();
  }
  function setSheet(html, onClick) {
    var bg = document.createElement("div"); bg.className = "sheet-bg";
    bg.innerHTML = '<div class="sheet" role="dialog">' + html + "</div>";
    document.body.appendChild(bg);
    bg.addEventListener("click", function (e) { if (e.target === bg) bg.remove(); else onClick(e, bg); });
    return bg;
  }
  function renameSet(isNew) {
    var s = curSet();
    var bg = setSheet("<h2>" + (isNew ? "Nova lista" : "Nome da lista") + '</h2><input class="field" id="setNameIn" maxlength="60" value="' + esc(isNew ? today() : s.name) + '">' +
      '<div class="act"><button class="btn ghost" data-a="x">Cancelar</button><button class="btn" data-a="ok">' + (isNew ? "Criar" : "Salvar") + "</button></div>", function (e, bg) {
      var a = e.target.getAttribute("data-a");
      if (a === "x") bg.remove();
      if (a === "ok") {
        var v = bg.querySelector("#setNameIn").value.trim() || "Culto";
        if (isNew) { var id = "s" + Date.now(); setState.lists.unshift({ id: id, name: v, items: [], t: Date.now() }); setState.cur = id; }
        else s.name = v;
        saveSets(); bg.remove(); renderSet(); afterSetChange();
      }
    });
    var inp = bg.querySelector("#setNameIn");
    setTimeout(function () { inp.focus(); inp.select(); }, 60);
    inp.addEventListener("keydown", function (e) { if (e.key === "Enter") bg.querySelector('[data-a="ok"]').click(); });
  }
  $("setName").addEventListener("click", function () { renameSet(false); });
  $("setLists").addEventListener("click", function () {
    var html = "<h2>Minhas listas</h2><div class=\"lists\">" + setState.lists.slice().sort(function (a, b) { return b.t - a.t; }).map(function (l) {
      return '<button type="button" data-id="' + l.id + '" class="' + (l.id === setState.cur ? "on" : "") + '"><span><b>' + esc(l.name) + "</b><small>" +
        (l.items.length ? esc(l.items.slice(0, 3).map(function (k) { return BYKEY[k] ? BYKEY[k].t : ""; }).join(", ")) + (l.items.length > 3 ? "…" : "") : "vazia") +
        '</small></span><span class="lc">' + l.items.length + "</span></button>";
    }).join("") + '</div><div class="act"><button class="btn" data-a="new">＋ Nova lista</button></div>';
    setSheet(html, function (e, bg) {
      var b = e.target.closest("[data-id]");
      if (b) { setState.cur = b.getAttribute("data-id"); save("lv.sets", setState); bg.remove(); renderSet(); afterSetChange(); }
      if (e.target.getAttribute("data-a") === "new") { bg.remove(); renameSet(true); }
    });
  });
  // ---------- Link da lista ----------
  function shareLink() {
    var s = curSet();
    var items = s.items.map(function (k) { var d = BYKEY[k], t = tons[d.key] || 0; return d.sid + (t ? "~" + t : ""); });
    return location.href.split("#")[0].split("?")[0] + "#lista=" + encodeURIComponent(s.name) + "&s=" + items.join(".");
  }
  function readLink() {
    var m = /[#&]lista=([^&]*)&s=([^&]*)/.exec(location.hash);
    if (!m) return null;
    var name = decodeURIComponent(m[1]) || "Lista recebida", items = [], tones = {}, miss = 0;
    m[2].split(".").forEach(function (x) {
      var p = x.split("~"), d = BYSID[p[0]];
      if (!d) { if (p[0]) miss++; return; }
      items.push(d.sk); if (p[1]) tones[d.key] = +p[1];
    });
    return { name: name, items: items, tones: tones, miss: miss };
  }
  function receiveLink() {
    var L = readLink(); if (!L) return;
    history.replaceState(null, "", location.href.split("#")[0]);
    if (!L.items.length) { toast("Link de lista inválido"); return; }
    var same = setState.lists.filter(function (x) { return x.name === L.name && x.items.join() === L.items.join(); })[0];
    var html = "<h2>" + esc(L.name) + "</h2><p>Lista compartilhada com " + L.items.length + (L.items.length === 1 ? " louvor" : " louvores") +
      (L.miss ? " (" + L.miss + " não encontrado" + (L.miss > 1 ? "s" : "") + " nesta versão do site)" : "") + ".</p>" +
      '<div class="dsetlist recv">' + L.items.map(function (k, i) {
        var d = BYKEY[k], t = L.tones[d.key];
        return "<button type=\"button\" tabindex=\"-1\"><i>" + (i + 1) + "</i><span>" + esc(d.t) + (t ? " · tom " + (t > 0 ? "+" : "") + t : "") + "</span></button>";
      }).join("") + "</div>" +
      '<div class="act"><button class="btn ghost" data-a="x">Agora não</button><button class="btn" data-a="ok">' + (same ? "Abrir lista" : "Salvar e abrir") + "</button></div>";
    setSheet(html, function (e, bg) {
      var a = e.target.getAttribute("data-a"); if (!a) return;
      bg.remove(); if (a !== "ok") return;
      if (same) setState.cur = same.id;
      else { var id = "s" + Date.now(); setState.lists.unshift({ id: id, name: L.name, items: L.items, t: Date.now() }); setState.cur = id; }
      Object.keys(L.tones).forEach(function (k) { if (tons[k] == null) tons[k] = L.tones[k]; });
      save("lv.tons", tons); saveSets(); afterSetChange(); showTab("set");
      toast(same ? "Lista aberta" : "Lista salva nas suas listas");
    });
  }
  window.addEventListener("hashchange", receiveLink);
  function shareText() {
    var s = curSet();
    return s.name + "\n\n" + s.items.map(function (k, i) {
      var d = BYKEY[k], kl = keyLabel(d);
      return (i + 1) + ". " + (d.n ? d.n + " – " : "") + d.t + (kl ? " (tom " + kl + ")" : "");
    }).join("\n") + "\n\nAbrir no app: " + shareLink();
  }
  $("setMore").addEventListener("click", function () {
    var I = function (p) { return '<svg viewBox="0 0 24 24">' + p + "</svg>"; };
    setSheet("<h2>" + esc(curSet().name) + '</h2><div class="menu-list">' +
      '<button data-a="share">' + I('<path d="M12 15V4M8 8l4-4 4 4M5 12v7h14v-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>') + "Compartilhar link da lista</button>" +
      '<button data-a="copy">' + I('<rect x="8" y="8" width="12" height="12" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" fill="none" stroke="currentColor" stroke-width="2"/>') + "Copiar link</button>" +
      '<button data-a="ren">' + I('<path d="M4 20h4L19 9l-4-4L4 16z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>') + "Renomear</button>" +
      '<button data-a="new">' + I('<path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>') + "Nova lista</button>" +
      '<button data-a="clr" class="danger">' + I('<path d="M5 7h14M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>') + "Esvaziar lista</button>" +
      (setState.lists.length > 1 ? '<button data-a="del" class="danger">' + I('<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>') + "Apagar esta lista</button>" : "") +
      '</div><div class="act"><button class="btn ghost" data-a="x">Fechar</button></div>', function (e, bg) {
      var a = (e.target.closest("[data-a]") || {}).getAttribute ? e.target.closest("[data-a]").getAttribute("data-a") : null;
      if (!a) return;
      bg.remove();
      var s = curSet();
      if (!s.items.length && (a === "share" || a === "copy")) { toast("A lista está vazia"); return; }
      if (a === "share") {
        var txt = shareText();
        if (navigator.share) navigator.share({ title: s.name, text: txt }).catch(function () {});
        else copyText(txt, "Lista e link copiados");
      }
      if (a === "copy") copyText(shareLink(), "Link copiado");
      if (a === "ren") renameSet(false);
      if (a === "new") renameSet(true);
      if (a === "clr" && s.items.length) {
        var old = s.items.slice(); s.items = []; saveSets(); afterSetChange();
        toast("Lista esvaziada", "Desfazer", function () { s.items = old; saveSets(); afterSetChange(); });
      }
      if (a === "del") {
        setState.lists = setState.lists.filter(function (x) { return x !== s; });
        setState.cur = setState.lists[0].id; save("lv.sets", setState); afterSetChange(); renderSet();
      }
    });
  });

  // ---------- Abas ----------
  var curTab = "songs";
  function showTab(t) {
    var prevFilter = filter;
    if (t === "fav") { filter = "fav"; save("lv.filter", filter); }
    else if (t === "songs" && curTab === "fav") { filter = "all"; save("lv.filter", filter); }
    curTab = t;
    $("tabSongs").hidden = t === "set"; $("tabSet").hidden = t !== "set";
    document.querySelectorAll("#tabbar [data-tab]").forEach(function (b) { b.setAttribute("aria-selected", b.getAttribute("data-tab") === t); });
    if (t === "set") renderSet();
    else if (filter !== prevFilter || t === "fav") { renderChips(); run(); }
    window.scrollTo(0, 0);
  }
  $("tabbar").addEventListener("click", function (e) {
    var b = e.target.closest("[data-tab]"); if (!b) return;
    var t = b.getAttribute("data-tab");
    if (t === curTab && t === "songs") { window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    showTab(t);
  });

  // ---------- Visualizador: barra de baixo e navegação da lista ----------
  var setPos = -1;
  function openFromSet(i) {
    var s = curSet(); if (!s.items[i]) return;
    setPos = i; open(BYKEY[s.items[i]]);
    $("pages").scrollTop = 0;
  }
  function dockUI() {
    var s = curSet(), nav = setPos >= 0 && cur && s.items[setPos] === cur.sk;
    if (!nav && cur && setPos >= 0) setPos = s.items.indexOf(cur.sk);
    nav = setPos >= 0 && cur;
    $("viewer").classList.toggle("inset", !!nav);
    $("vNav").hidden = true;
    if (nav) $("vSub").textContent = $("vSub").textContent.replace(/ · \d+ de \d+$/, "") + " · " + (setPos + 1) + " de " + s.items.length;
    drawerSet();
    if (nav) {
      var p = BYKEY[s.items[setPos - 1]], n = BYKEY[s.items[setPos + 1]];
      $("vPrev").disabled = !p; $("vNext").disabled = !n;
      $("vPrevT").textContent = p ? p.t : "—"; $("vNextT").textContent = n ? n.t : "Fim da lista";
      $("vPos").textContent = (setPos + 1) + " de " + s.items.length;
    }
    var ok = view === "cifra" && curCifra && keyInfo(origKey(curCifra));
    $("qTom").hidden = !ok;
    if (ok) $("qKeyV").textContent = keyName(ok.i + cifraShift(), ok.minor);
    $("vAdd").hidden = !cur;
    if (cur) $("vAdd").innerHTML = inSet(cur)
      ? '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.5" fill="currentColor"/><path d="M7.5 12.3l3 3 6-6.3" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'
      : '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M12 8v8M8 12h8" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
    $("qRoll").classList.toggle("on", rolling);
  }
  function drawerSet() {
    var s = curSet(), on = setPos >= 0 && cur;
    $("secSet").hidden = !on; $("secAdd").hidden = !!on || !cur;
    if (!on) return;
    $("dSetPos").textContent = (setPos + 1) + " de " + s.items.length;
    $("dPrev").disabled = setPos <= 0; $("dNext").disabled = setPos >= s.items.length - 1;
    $("dSetList").innerHTML = s.items.map(function (k, i) {
      var d = BYKEY[k];
      return '<button type="button" data-go="' + i + '" class="' + (i === setPos ? "on" : "") + '"><i>' + (i + 1) + "</i><span>" + esc(d.t) + "</span></button>";
    }).join("");
  }
  $("dPrev").addEventListener("click", function () { goSet(-1); closeDrawer(); });
  $("dNext").addEventListener("click", function () { goSet(1); closeDrawer(); });
  $("dSetList").addEventListener("click", function (e) {
    var b = e.target.closest("[data-go]"); if (!b) return;
    var i = +b.getAttribute("data-go"); closeDrawer();
    if (i !== setPos) { var dir = i > setPos ? 1 : -1; openFromSet(i); slide(dir); }
  });
  var tipT;
  function slide(dir) {
    var pg = $("pages"); pg.classList.remove("slide-l", "slide-r"); void pg.offsetWidth; pg.classList.add(dir > 0 ? "slide-l" : "slide-r");
    var t = $("swipeTip");
    if (!t) { t = document.createElement("div"); t.id = "swipeTip"; t.className = "swipe-tip"; $("viewer").appendChild(t); }
    t.textContent = (setPos + 1) + " de " + curSet().items.length + " · " + cur.t;
    t.hidden = false; clearTimeout(tipT); tipT = setTimeout(function () { t.hidden = true; }, 1300);
  }
  function goSet(dir) {
    var n = setPos + dir, s = curSet();
    if (setPos < 0) return;
    if (n < 0 || n >= s.items.length) { toast(n < 0 ? "Este é o primeiro louvor da lista" : "Fim da lista"); return; }
    openFromSet(n); slide(dir);
  }
  function drawerAdd() {
    if (!cur || setPos >= 0) { $("dAdd").parentNode.hidden = true; return; }
    $("dAdd").parentNode.hidden = false;
    var on = inSet(cur);
    $("dAdd").textContent = on ? "✓ Na lista do culto — tirar" : "＋ Adicionar à lista do culto";
    $("dAdd").classList.toggle("on", on);
  }
  $("vAdd").addEventListener("click", function () { if (cur) toggleSet(cur); });
  $("dAdd").addEventListener("click", function () { if (cur) toggleSet(cur); });
  $("vPrev").addEventListener("click", function () { if (setPos > 0) openFromSet(setPos - 1); });
  $("vNext").addEventListener("click", function () { if (setPos < curSet().items.length - 1) openFromSet(setPos + 1); });
  $("qTomUp").addEventListener("click", function () { setTom(cifraShift() + 1); });
  $("qTomDown").addEventListener("click", function () { setTom(cifraShift() - 1); });
  $("qKey").addEventListener("click", openDrawer);
  $("qZIn").addEventListener("click", function () { $("zIn").click(); });
  $("qZOut").addEventListener("click", function () { $("zOut").click(); });
  $("qRoll").addEventListener("click", function () { if (rolling) stopScroll(); else startScroll(); });
  // toque no conteúdo mostra/esconde a barra de baixo; rolar para baixo esconde
  (function dockAuto() {
    var lastY = 0, moved = 0;
    $("pages").addEventListener("scroll", function () {
      var y = $("pages").scrollTop, dy = y - lastY; lastY = y;
      if (rolling) return;
      moved += dy;
      if (moved > 60) { $("vdock").classList.add("hide"); moved = 0; }
      else if (moved < -40 || y < 20) { $("vdock").classList.remove("hide"); moved = 0; }
    }, { passive: true });
    $("pages").addEventListener("click", function (e) {
      if (editing || e.target.closest("button, a, .sg[data-l]")) return;
      $("vdock").classList.toggle("hide");
    });
  })();

  // ---------- Início ----------
  $("ver").textContent = "v" + (window.DATA_VERSION || "").slice(0, 6);
  if (filter === "fav") filter = "all";
  renderChips();
  run();
  afterSetChange();
  WAIT.busca = [onBusca]; WAIT.conteudo = [onConteudo, function () { if (!$("tabSet").hidden) renderSet(); }];
  var idle = window.requestIdleCallback || function (f) { setTimeout(f, 300); };
  idle(function () { need("busca"); });
  receiveLink();
  $("q").addEventListener("focus", function () { need("busca"); }, { once: true });
  setTimeout(function () { need("conteudo"); }, 900);
})();
