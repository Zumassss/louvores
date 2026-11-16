const SHELL = "louvores-shell-1945655478-1";
const PDF = "louvores-pdf-v1";
const FILES = ["./", "index.html", "style.css", "app.js", "data.js", "manifest.webmanifest",
  "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png",
  "lib/pdf.min.mjs", "lib/pdf.worker.min.mjs"];

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
    .then(hit => hit || (req.mode === "navigate" ? caches.match("index.html") : null))
    .then(hit => hit || fetch(req).then(r => {
      if (r.ok && url.pathname.includes("/standard_fonts/")) { const cl = r.clone(); caches.open(SHELL).then(c => c.put(req, cl)); }
      return r;
    })));
});
