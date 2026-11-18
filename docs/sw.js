// Gerado automaticamente — a versão muda a cada atualização dos dados.
const SHELL = "louvores-shell-5a16f79c4b";
const PDF = "louvores-pdf-v1";
const FILES = ["./", "index.html", "style.css", "app.js", "data.js", "manifest.webmanifest", "lib/pdf.min.mjs", "lib/pdf.worker.min.mjs", "icons/icon-180.png", "icons/icon-192.png", "icons/icon-32.png", "icons/icon-512.png", "img/icm-red.svg", "img/icm-white.svg", "img/icm.svg", "fonts/nunito-sans-latin-wght-italic.woff2", "fonts/nunito-sans-latin-wght-normal.woff2", "lib/standard_fonts/FoxitDingbats.pfb", "lib/standard_fonts/FoxitFixed.pfb", "lib/standard_fonts/FoxitFixedBold.pfb", "lib/standard_fonts/FoxitFixedBoldItalic.pfb", "lib/standard_fonts/FoxitFixedItalic.pfb", "lib/standard_fonts/FoxitSerif.pfb", "lib/standard_fonts/FoxitSerifBold.pfb", "lib/standard_fonts/FoxitSerifBoldItalic.pfb", "lib/standard_fonts/FoxitSerifItalic.pfb", "lib/standard_fonts/FoxitSymbol.pfb", "lib/standard_fonts/LICENSE_FOXIT", "lib/standard_fonts/LICENSE_LIBERATION", "lib/standard_fonts/LiberationSans-Bold.ttf", "lib/standard_fonts/LiberationSans-BoldItalic.ttf", "lib/standard_fonts/LiberationSans-Italic.ttf", "lib/standard_fonts/LiberationSans-Regular.ttf"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== PDF).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.includes("/pdf/")) {
    e.respondWith(caches.open(PDF).then(c => c.match(req, { ignoreSearch: true })
      .then(hit => hit || fetch(req).then(r => { if (r.ok) c.put(req, r.clone()); return r; }))));
    return;
  }
  e.respondWith(caches.match(req, { ignoreSearch: true })
    .then(hit => hit || (req.mode === "navigate" ? caches.match("./") : null))
    .then(hit => hit || fetch(req)));
});
