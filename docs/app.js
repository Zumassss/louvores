(function () {
  "use strict";
  var DATA = window.LOUVORES || [];
  var $ = function (id) { return document.getElementById(id); };

  // ---------- Normalização ----------
  function norm(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, " ").trim();
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  var COL = {
    "Louvores Coletânea": "Coletânea",
    "Louvores Avulsos": "Avulsos",
    "Louvores Coletânea CIAs": "Coletânea CIAs",
    "Louvores Avulsos CIAs": "Avulsos CIAs",
    "Seminário de Louvor Ago/25": "Seminário Ago/25",
    "Equipe de Louvor - Maanaim de Domingos Martins/ES": "Equipe Maanaim"
  };

  // ---------- Índice ----------
  DATA.forEach(function (d, i) {
    d.i = i;
    d.nt = norm(d.t);
    d.ct = d.nt.replace(/ /g, "");
    d.tw = d.nt.split(" ").filter(Boolean);
    d.cx = (d.x || "").replace(/ /g, "");
    var seen = {}, lw = [];
    (d.x || "").split(" ").forEach(function (w) { if (w.length > 2 && !seen[w]) { seen[w] = 1; lw.push(w); } });
    d.lw = lw;
    var m = /^(cia\s*)?([a-z]?)0*(\d+)$/i.exec((d.n || "").replace(/\s+/g, " ").trim());
    d.numDigits = m ? m[3] : "";
    d.numPre = m ? ((m[1] ? "cia" : "") + m[2].toLowerCase()) : "";
    d.cs = COL[d.c] || d.c;
  });

  // Distância de edição limitada (para erros de digitação)
  function lev(a, b, max) {
    var la = a.length, lb = b.length;
    if (Math.abs(la - lb) > max) return max + 1;
    var prev = new Array(lb + 1), cur = new Array(lb + 1), j;
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

  // quanto o termo "casa" com alguma palavra da lista (1 = exato/prefixo, 0.8 = com erro, 0 = nada)
  function wordHit(tok, words, last) {
    var tol = tolerance(tok.length), best = 0;
    for (var k = 0; k < words.length; k++) {
      var w = words[k];
      if (w === tok) return 1;
      if ((last || tok.length >= 3) && w.indexOf(tok) === 0) { best = Math.max(best, 0.95); continue; }
      if (tol && best < 0.8) {
        var cut = w.length > tok.length + tol && last ? w.slice(0, tok.length) : w;
        if (lev(tok, cut, tol) <= tol) best = 0.8;
      }
    }
    return best;
  }

  function score(d, q, toks, cq) {
    var s = 0, why = "t";
    // Número
    var nm = /^(cia\s*|c\s*)?([a-z]?)\s*0*(\d+)$/.exec(q);
    if (nm && d.numDigits) {
      var pre = (nm[1] ? "cia" : "") + (nm[2] || "");
      if (d.numDigits === nm[3] && (!pre || pre === d.numPre || (pre === "c" && d.numPre === "cia"))) s = Math.max(s, pre || !d.numPre ? 1000 : 950);
      else if (d.numDigits.indexOf(nm[3]) === 0 && (!pre || pre === d.numPre)) s = Math.max(s, 300);
    }
    if (!toks.length) return { s: s, why: why };
    // Título
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
    // Letra
    if (s < 600 && d.cx) {
      var ls = 0;
      if (cq.length >= 5 && d.cx.indexOf(cq) >= 0) ls = 600;
      else if (toks.length) {
        var t2 = 0, n = 0;
        for (var j = 0; j < toks.length; j++) {
          if (toks[j].length < 3) continue;
          n++;
          t2 += d.x.indexOf(toks[j]) >= 0 ? 1 : wordHit(toks[j], d.lw, j === toks.length - 1);
        }
        if (n) {
          var fl = t2 / n;
          if (fl >= 0.999) ls = 520 + Math.min(n, 6) * 10;
          else if (fl >= 0.7 && n >= 2) ls = 300 + 200 * fl;
        }
      }
      if (ls > s) { s = ls; why = "l"; }
    }
    return { s: s, why: why };
  }

  // Trecho da letra com destaque
  function snippet(d, toks) {
    var x = d.x, pos = -1, k;
    var real = toks.filter(function (t) { return t.length >= 3; });
    for (k = 0; k < real.length && pos < 0; k++) pos = x.indexOf(real[k]);
    if (pos < 0) {
      for (k = 0; k < real.length && pos < 0; k++) {
        for (var w = 0; w < d.lw.length; w++) {
          if (lev(real[k], d.lw[w].slice(0, real[k].length + 1), tolerance(real[k].length)) <= tolerance(real[k].length)) { pos = x.indexOf(d.lw[w]); break; }
        }
      }
    }
    if (pos < 0) return "";
    var a = Math.max(0, x.lastIndexOf(" ", Math.max(0, pos - 28)));
    var b = x.indexOf(" ", Math.min(x.length, pos + 70)); if (b < 0) b = x.length;
    var s = esc(x.slice(a, b).trim());
    real.forEach(function (t) { s = s.replace(new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "[a-z]*)", "g"), "<mark>$1</mark>"); });
    return (a > 0 ? "… " : "") + s + (b < x.length ? " …" : "");
  }

  // ---------- Estado ----------
  function load(k, def) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch (e) { return def; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  var favs = load("lv.favs", []);
  var recents = load("lv.recents", []);
  var filter = load("lv.filter", "all");

  var FILTERS = [
    { id: "all", label: "Todos", test: function () { return true; } },
    { id: "fav", label: "★ Favoritos", test: function (d) { return favs.indexOf(d.f) >= 0; } },
    { id: "cifra", label: "Só cifras", test: function (d) { return d.k === "cifra"; } },
    { id: "col", label: "Coletânea", test: function (d) { return d.c === "Louvores Coletânea"; } },
    { id: "av", label: "Avulsos", test: function (d) { return d.c === "Louvores Avulsos"; } },
    { id: "cia", label: "CIAs", test: function (d) { return /CIAs/.test(d.c); } },
    { id: "eq", label: "Seminários / Equipe", test: function (d) { return /Seminário|Equipe/.test(d.c); } }
  ];
  if (!FILTERS.some(function (f) { return f.id === filter; })) filter = "all";

  function renderChips() {
    $("chips").innerHTML = FILTERS.map(function (f) {
      var n = DATA.filter(f.test).length;
      return '<button class="chip" role="tab" data-f="' + f.id + '" aria-selected="' + (f.id === filter) + '">' + esc(f.label) + '<span class="n">' + n + "</span></button>";
    }).join("");
  }
  $("chips").addEventListener("click", function (e) {
    var b = e.target.closest(".chip"); if (!b) return;
    filter = b.getAttribute("data-f"); save("lv.filter", filter);
    renderChips(); run();
  });

  // ---------- Lista ----------
  var STAR = '<svg class="star" viewBox="0 0 24 24"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" fill="currentColor"/></svg>';
  function badge(d) {
    if (!d.n) return '<div class="badge none"><svg viewBox="0 0 24 24"><path d="M9 18V6l10-2v12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="7" cy="18" r="2.2" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="17" cy="16" r="2.2" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></div>';
    var m = /^(CIA)\s*(\d+)$/i.exec(d.n);
    if (m) return '<div class="badge"><span><small>CIA</small>' + esc(m[2]) + "</span></div>";
    return '<div class="badge">' + esc(d.n) + "</div>";
  }
  function itemHTML(d, snip) {
    var col = d.cs + (d.g ? " · " + d.g : "");
    return '<li class="item" data-i="' + d.i + '">' + badge(d) +
      '<div class="info"><div class="title">' + esc(d.t) + '</div>' +
      '<div class="line2"><span class="tag ' + (d.k === "cifra" ? "cifra" : "partitura") + '">' + (d.k === "cifra" ? "Cifra" : "Partitura") + '</span><span class="col">' + esc(col) + "</span></div>" +
      (snip ? '<div class="snip">' + snip + "</div>" : "") + "</div>" +
      (favs.indexOf(d.f) >= 0 ? STAR : "") + "</li>";
  }

  var LIMIT = 80, lastList = [], shown = 0;
  function paint(list, q, toks) {
    lastList = list; shown = 0;
    $("list").innerHTML = "";
    $("empty").hidden = list.length > 0;
    more(q, toks);
  }
  function more(q, toks) {
    var slice = lastList.slice(shown, shown + LIMIT), html = "";
    slice.forEach(function (r) { html += itemHTML(r.d, r.why === "l" ? snippet(r.d, toks) : ""); });
    $("list").insertAdjacentHTML("beforeend", html);
    shown += slice.length;
  }
  var curToks = [], curQ = "";
  window.addEventListener("scroll", function () {
    if (shown < lastList.length && window.innerHeight + window.scrollY > document.body.offsetHeight - 900) more(curQ, curToks);
  }, { passive: true });

  function run() {
    var raw = $("q").value;
    var q = norm(raw), toks = q ? q.split(" ") : [], cq = toks.join("");
    curQ = q; curToks = toks;
    $("clear").hidden = !raw;
    var f = FILTERS.filter(function (x) { return x.id === filter; })[0];
    var pool = DATA.filter(f.test);
    var out;
    if (!q) {
      out = pool.map(function (d) { return { d: d, s: 0 }; });
      var rec = recents.map(function (id) { return pool.filter(function (d) { return d.f === id; })[0]; }).filter(Boolean).slice(0, 6);
      $("meta").innerHTML = pool.length + " louvores" + (filter === "all" ? "" : " · " + esc(f.label));
      paint(out, q, toks);
      if (rec.length && filter === "all") {
        $("list").insertAdjacentHTML("afterbegin", '<li class="sec">Abertos recentemente</li>' + rec.map(function (d) { return itemHTML(d); }).join("") + '<li class="sec">Todos os louvores</li>');
      }
      return;
    }
    out = [];
    for (var i = 0; i < pool.length; i++) {
      var r = score(pool[i], q, toks, cq);
      if (r.s > 0) out.push({ d: pool[i], s: r.s, why: r.why });
    }
    out.sort(function (a, b) { return b.s - a.s || (a.d.k === "cifra" ? -1 : 0) - (b.d.k === "cifra" ? -1 : 0) || a.d.nt.localeCompare(b.d.nt); });
    $("meta").textContent = out.length + (out.length === 1 ? " resultado" : " resultados");
    paint(out, q, toks);
  }

  var tmr;
  $("q").addEventListener("input", function () { clearTimeout(tmr); tmr = setTimeout(run, 60); });
  $("q").addEventListener("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); $("q").blur(); if (lastList[0] && /^\s*\S+\s*$/.test($("q").value) && lastList[0].s >= 950) open(lastList[0].d); }
  });
  $("clear").addEventListener("click", function () { $("q").value = ""; run(); $("q").focus(); });
  $("list").addEventListener("click", function (e) {
    var li = e.target.closest(".item"); if (!li) return;
    open(DATA[+li.getAttribute("data-i")]);
  });

  // ---------- Visualizador (pdf.js) ----------
  var pdfjsP = null;
  function pdfjs() {
    if (!pdfjsP) pdfjsP = import("./lib/pdf.min.mjs").then(function (m) {
      m.GlobalWorkerOptions.workerSrc = new URL("lib/pdf.worker.min.mjs", location.href).href;
      return m;
    });
    return pdfjsP;
  }
  var cur = null, doc = null, zoom = 1, observer = null, renderToken = 0;

  function open(d, fileId) {
    cur = d;
    if (!fileId) {
      recents = [d.f].concat(recents.filter(function (x) { return x !== d.f; })).slice(0, 12);
      save("lv.recents", recents);
    }
    $("vNum").textContent = d.n || "";
    $("vName").textContent = d.t;
    $("vStar").classList.toggle("on", favs.indexOf(d.f) >= 0);
    var docs = [{ id: d.f, label: d.k === "cifra" ? "Cifra" : "Partitura" }];
    if (d.l) docs.push({ id: d.l, label: "Letra" });
    fileId = fileId || d.f;
    $("vDocs").innerHTML = docs.length > 1 ? docs.map(function (x) {
      return '<button type="button" data-id="' + x.id + '" aria-pressed="' + (x.id === fileId) + '">' + x.label + "</button>";
    }).join("") : '<span style="font-size:13px;color:var(--muted)">' + docs[0].label + "</span>";
    if ($("viewer").hidden) {
      $("viewer").hidden = false;
      document.body.style.overflow = "hidden";
      history.pushState({ v: 1 }, "");
    }
    loadPdf(fileId);
  }
  $("vDocs").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-id]"); if (b) open(cur, b.getAttribute("data-id"));
  });

  function closeViewer() {
    $("viewer").hidden = true; document.body.style.overflow = "";
    renderToken++; if (doc) { doc.destroy(); doc = null; }
    $("pages").innerHTML = "";
    run();
  }
  $("vBack").addEventListener("click", function () { history.back(); });
  window.addEventListener("popstate", function () { if (!$("viewer").hidden) closeViewer(); });
  $("vStar").addEventListener("click", function () {
    var i = favs.indexOf(cur.f);
    if (i >= 0) favs.splice(i, 1); else favs.unshift(cur.f);
    save("lv.favs", favs); $("vStar").classList.toggle("on", i < 0); renderChips();
  });

  function setZoom(z) {
    zoom = Math.max(0.6, Math.min(3, Math.round(z * 10) / 10));
    $("zVal").textContent = Math.round(zoom * 100) + "%";
    save("lv.zoom", zoom);
    if (doc) layout();
  }
  zoom = load("lv.zoom", 1); $("zVal").textContent = Math.round(zoom * 100) + "%";
  $("zIn").addEventListener("click", function () { setZoom(zoom + 0.25); });
  $("zOut").addEventListener("click", function () { setZoom(zoom - 0.25); });

  function loadPdf(id) {
    var token = ++renderToken;
    if (doc) { doc.destroy(); doc = null; }
    $("pages").innerHTML = '<div class="vmsg"><div class="spinner"></div>Abrindo…</div>';
    Promise.all([pdfjs(), fetch("pdf/" + id + ".pdf").then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.arrayBuffer(); })])
      .then(function (res) {
        if (token !== renderToken) return;
        return res[0].getDocument({ data: new Uint8Array(res[1]), standardFontDataUrl: new URL("lib/standard_fonts/", location.href).href, isEvalSupported: false }).promise;
      })
      .then(function (pdf) {
        if (!pdf || token !== renderToken) return;
        doc = pdf; layout();
      })
      .catch(function (err) {
        if (token !== renderToken) return;
        $("pages").innerHTML = '<div class="vmsg">Não foi possível abrir este arquivo' + (navigator.onLine ? "." : " sem internet.<br>Ele ainda não foi baixado para uso offline.") + '<br><br><a href="pdf/' + id + '.pdf" target="_blank" rel="noopener" style="color:var(--red)">Tentar abrir direto</a></div>';
        console.error(err);
      });
  }

  function layout() {
    var token = renderToken, pdf = doc, box = $("pages");
    if (observer) observer.disconnect();
    box.innerHTML = "";
    var avail = Math.min(box.clientWidth - 16, 1100);
    var width = Math.round(avail * zoom);
    box.style.overflowX = zoom > 1 ? "auto" : "hidden";
    var dpr = Math.min(window.devicePixelRatio || 1, 3);
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting && !en.target.dataset.done) { en.target.dataset.done = 1; draw(en.target); }
      });
    }, { root: box, rootMargin: "1200px 0px" });
    function draw(el) {
      pdf.getPage(+el.dataset.p).then(function (page) {
        if (token !== renderToken) return;
        var vp1 = page.getViewport({ scale: 1 });
        var scale = (width / vp1.width) * dpr;
        // limita a área do canvas (Safari tem limite de memória)
        var maxPx = 16e6; if (vp1.width * vp1.height * scale * scale > maxPx) scale = Math.sqrt(maxPx / (vp1.width * vp1.height));
        var vp = page.getViewport({ scale: scale });
        var c = document.createElement("canvas");
        c.width = Math.floor(vp.width); c.height = Math.floor(vp.height);
        el.appendChild(c);
        page.render({ canvasContext: c.getContext("2d", { alpha: false }), viewport: vp });
      });
    }
    var first = Promise.resolve();
    pdf.getPage(1).then(function (p1) {
      if (token !== renderToken) return;
      var vp = p1.getViewport({ scale: 1 }), ratio = vp.height / vp.width;
      for (var i = 1; i <= pdf.numPages; i++) {
        var el = document.createElement("div");
        el.className = "page"; el.dataset.p = i;
        el.style.width = width + "px"; el.style.height = Math.round(width * ratio) + "px";
        box.appendChild(el); observer.observe(el);
      }
    });
    return first;
  }
  var rz; window.addEventListener("resize", function () { clearTimeout(rz); rz = setTimeout(function () { if (doc && !$("viewer").hidden) layout(); }, 250); });

  // ---------- Offline ----------
  var PDF_CACHE = "louvores-pdf-v1";
  var allFiles = []; DATA.forEach(function (d) { allFiles.push(d.f); if (d.l) allFiles.push(d.l); });
  var totalBytes = DATA.reduce(function (a, d) { return a + (d.s || 0); }, 0);
  var state = { done: 0, total: allFiles.length, running: false, error: false };

  function pill() {
    var b = $("offlineBtn"), t = $("offlineTxt");
    b.classList.remove("ok", "err");
    if (!("caches" in window) || !("serviceWorker" in navigator)) { t.textContent = "Offline indisponível"; b.classList.add("err"); return; }
    if (state.done >= state.total) { t.textContent = "Pronto offline"; b.classList.add("ok"); }
    else if (state.running) t.textContent = "Baixando " + Math.floor(100 * state.done / state.total) + "%";
    else if (state.error) { t.textContent = "Baixar p/ offline"; b.classList.add("err"); }
    else t.textContent = state.done + "/" + state.total + " offline";
    var bar = document.querySelector(".sheet .bar > i"); if (bar) bar.style.width = (100 * state.done / state.total) + "%";
    var st = document.querySelector(".sheet .st"); if (st) st.textContent = state.done + " de " + state.total + " arquivos salvos no aparelho";
  }

  function syncAll() {
    if (state.running || !("caches" in window)) return;
    state.running = true; state.error = false; pill();
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {});
    caches.open(PDF_CACHE).then(function (cache) {
      return cache.keys().then(function (keys) {
        var have = {};
        keys.forEach(function (r) { var m = /pdf\/([^/?]+)\.pdf/.exec(r.url); if (m) have[m[1]] = 1; });
        var todo = allFiles.filter(function (id) { return !have[id]; });
        state.done = state.total - todo.length; pill();
        var idx = 0, fails = 0;
        function worker() {
          if (idx >= todo.length) return Promise.resolve();
          var id = todo[idx++], url = "pdf/" + id + ".pdf";
          return fetch(url, { cache: "no-cache" }).then(function (r) {
            if (!r.ok) throw new Error(r.status);
            return cache.put(url, r);
          }).then(function () { state.done++; pill(); }, function () { fails++; })
            .then(worker);
        }
        return Promise.all([worker(), worker(), worker(), worker()]).then(function () {
          if (fails) state.error = true;
        });
      });
    }).catch(function () { state.error = true; })
      .then(function () { state.running = false; pill(); });
  }

  function sheet() {
    var standalone = window.navigator.standalone || matchMedia("(display-mode: standalone)").matches;
    var bg = document.createElement("div"); bg.className = "sheet-bg";
    bg.innerHTML = '<div class="sheet" role="dialog" aria-label="Uso offline"><h2>Usar sem internet</h2>' +
      '<p>Todos os ' + state.total + ' arquivos (' + Math.round(totalBytes / 1e6) + ' MB) ficam salvos no aparelho. Depois disso o site abre e funciona sem internet.</p>' +
      '<div class="bar"><i></i></div><p class="st"></p>' +
      (standalone ? "" : '<div class="howto"><b>No iPhone:</b> toque em <b>Compartilhar</b> <span aria-hidden="true">⎋</span> → <b>Adicionar à Tela de Início</b>. Abra pelo ícone; assim o iPhone não apaga os arquivos salvos.</div>') +
      '<div class="act"><button class="btn ghost" data-a="x">Fechar</button><button class="btn" data-a="go">' + (state.done >= state.total ? "Verificar de novo" : "Baixar agora") + "</button></div></div>";
    document.body.appendChild(bg);
    bg.addEventListener("click", function (e) {
      var a = e.target.getAttribute("data-a");
      if (e.target === bg || a === "x") bg.remove();
      if (a === "go") syncAll();
    });
    pill();
  }
  $("offlineBtn").addEventListener("click", sheet);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").then(function () { return navigator.serviceWorker.ready; })
      .then(function () { syncAll(); })
      .catch(function () { state.error = true; pill(); });
  } else pill();

  // ---------- Início ----------
  renderChips();
  run();
})();
