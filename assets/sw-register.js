(() => {
  "use strict";
  const VERSION = "9.2";
  const key = "market-radar-version";
  const previous = localStorage.getItem(key);
  localStorage.setItem(key, VERSION);
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", async () => {
    try {
      const reg = await navigator.serviceWorker.register(`./service-worker.js?v=${VERSION}`, { updateViaCache: "none" });
      await reg.update();
      if (previous && previous !== VERSION) {
        const old = await caches.keys();
        await Promise.all(old.filter(name => !name.includes(`v${VERSION}`)).map(name => caches.delete(name)));
      }
    } catch (error) {
      console.warn("Service worker registration failed", error);
    }
  });
})();