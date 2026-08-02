const CACHE_NAME = "market-event-radar-v11-0-0-complete";
const STATIC_ASSETS = [
  "./", "index.html", "404.html", "event.html", "news.html", "portfolio.html", "tw-market.html", "asset.html", "institutional.html", "manifest.webmanifest",
  "assets/styles.css?v=11.0.0", "assets/data-source.js?v=11.0.0", "assets/app.js?v=11.0.0",
  "assets/market-ticker.js?v=11.0.0", "assets/crypto-live.js?v=11.0.0", "assets/event.js?v=11.0.0",
  "assets/auth.js?v=11.0.0", "assets/firebase-config.js",
  "assets/news-core.js?v=11.0.0", "assets/news-ui.js?v=11.0.0",
  "assets/news-page.js?v=11.0.0", "assets/portfolio.js?v=11.0.0", "assets/asset-master.js?v=11.0.0", "assets/asset-detail.js?v=11.0.0", "assets/announcements.js?v=11.0.0",
  "assets/institutional.js?v=11.0.0", "assets/tw-market.js?v=11.0.0", "assets/sw-register.js?v=11.0.0", "assets/favicon.svg",
  "data/seed.js?v=11.0.0", "data/news-seed.js?v=11.0.0", "data/assets-seed.js?v=11.0.0", "data/announcements-seed.js?v=11.0.0", "data/institutional-history-seed.js?v=11.0.0", "data/market-snapshot-seed.js?v=11.0.0", "data/tw-market-seed.js?v=11.0.0", "data/tw-chips-seed.js?v=11.0.0"
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

  if (url.pathname.endsWith("/data/news.json") || url.pathname.endsWith("/data/events.json") || url.pathname.endsWith("/data/assets.json") || url.pathname.endsWith("/data/announcements.json") || url.pathname.endsWith("/data/institutional-history.json") || url.pathname.endsWith("/data/market-snapshot.json") || url.pathname.endsWith("/data/tw-market.json") || url.pathname.endsWith("/data/tw-chips.json")) {
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
