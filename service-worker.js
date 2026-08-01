const CACHE_NAME = "market-event-radar-v8";
const ASSETS = [
  "./",
  "index.html",
  "event.html",
  "manifest.webmanifest",
  "service-worker.js",
  "assets/styles.css?v=8",
  "assets/app.js?v=8",
  "assets/auth.js?v=8",
  "assets/firebase-config.js",
  "assets/event.js?v=8",
  "assets/favicon.svg",
  "data/seed.js",
  "data/news-seed.js",
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
