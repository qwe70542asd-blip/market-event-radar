const CACHE_NAME = "market-event-radar-v9-1";
const ASSETS = [
  "./", "index.html", "event.html", "news.html", "manifest.webmanifest",
  "assets/styles.css?v=9.1", "assets/app.js?v=9.1", "assets/event.js?v=9",
  "assets/auth.js?v=9", "assets/firebase-config.js", "assets/news-ui.js?v=9",
  "assets/news-page.js?v=9", "assets/sw-register.js?v=9.1",
  "assets/favicon.svg", "data/seed.js", "data/news-seed.js"
];
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(fetch(event.request).then((response) => {
    const copy = response.clone();
    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => {});
    return response;
  }).catch(() => caches.match(event.request).then((cached) => cached || caches.match("index.html"))));
});
