(() => {
  "use strict";
  const VERSION = "10.6.2";
  const VERSION_KEY = "market-radar-version";
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", async () => {
    try {
      const previous = localStorage.getItem(VERSION_KEY);
      const registration = await navigator.serviceWorker.register(`./service-worker.js?v=${VERSION}`, {
        updateViaCache: "none"
      });

      await registration.update();
      localStorage.setItem(VERSION_KEY, VERSION);

      let reloaded = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (reloaded) return;
        reloaded = true;
        location.reload();
      });

      if (registration.waiting) {
        registration.waiting.postMessage({ type: "SKIP_WAITING" });
      }

      // When a new worker is still installing, activate it as soon as it is ready.
      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        worker?.addEventListener("statechange", () => {
          if (worker.state === "installed" && navigator.serviceWorker.controller) {
            worker.postMessage({ type: "SKIP_WAITING" });
          }
        });
      });

      // Clear leftovers from builds that reused the same cache version.
      if (previous !== VERSION && "caches" in window) {
        const keep = "market-event-radar-v10-6-0-clean";
        const keys = await caches.keys();
        await Promise.all(keys.filter(key => key.startsWith("market-event-radar-") && key !== keep).map(key => caches.delete(key)));
      }
    } catch (error) {
      console.warn("Service worker registration failed:", error);
    }
  });
})();
