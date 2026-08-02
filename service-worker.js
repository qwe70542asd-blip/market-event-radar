const CACHE_NAME = "market-event-radar-v10-8-2-integrated";
const STATIC_ASSETS = [
  "./", "index.html", "404.html", "event.html", "news.html", "portfolio.html", "asset.html", "institutional.html", "manifest.webmanifest",
  "assets/styles.css?v=10.8.2", "assets/data-source.js?v=10.8.2", "assets/app.js?v=10.8.2",
  "assets/market-ticker.js?v=10.8.2", "assets/crypto-live.js?v=10.8.2", "assets/event.js?v=10.8.2",
  "assets/auth.js?v=10.8.2", "assets/firebase-config.js",
  "assets/news-core.js?v=10.8.2", "assets/news-ui.js?v=10.8.2",
  "assets/news-page.js?v=10.8.2", "assets/portfolio.js?v=10.8.2", "assets/asset-master.js?v=10.8.2", "assets/asset-detail.js?v=10.8.2", "assets/announcements.js?v=10.8.2",
  "assets/institutional.js?v=10.8.2", "assets/sw-register.js?v=10.8.2", "assets/favicon.svg",
  "data/seed.js?v=10.8.2", "data/news-seed.js?v=10.8.2", "data/assets-seed.js?v=10.8.2", "data/announcements-seed.js?v=10.8.2", "data/institutional-history-seed.js?v=10.8.2", "data/market-snapshot-seed.js?v=10.8.2"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(request, fallbackPath) {
  try {
    const freshRequest = new Request(request, { cache: "no-store" });
    const response = await fetch(freshRequest);
    if (response && response.ok) {
      const cache = await caches.open(CACHE_NAME);
      const url = new URL(request.url);
      const stableKey = new Request(url.origin + url.pathname);
      cache.put(stableKey, response.clone()).catch(() => {});
      return response;
    }
    if (fallbackPath) return (await caches.match(fallbackPath)) || response;
    return response;
  } catch (error) {
    const url = new URL(request.url);
    const stableKey = new Request(url.origin + url.pathname);
    return (await caches.match(stableKey)) || (fallbackPath ? await caches.match(fallbackPath) : Response.error());
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  const network = fetch(new Request(request, { cache: "no-cache" }))
    .then(response => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => null);
  return cached || await network || Response.error();
}

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  if (url.pathname.endsWith("/data/news.json") || url.pathname.endsWith("/data/events.json") || url.pathname.endsWith("/data/assets.json") || url.pathname.endsWith("/data/announcements.json") || url.pathname.endsWith("/data/institutional-history.json") || url.pathname.endsWith("/data/market-snapshot.json")) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(networkFirst(event.request, "index.html"));
    return;
  }

  if (url.origin === self.location.origin && /\.(?:js|css|html)$/.test(url.pathname)) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  if (url.origin === self.location.origin) {
    event.respondWith(staleWhileRevalidate(event.request));
  }
});

self.addEventListener("message", event => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});
