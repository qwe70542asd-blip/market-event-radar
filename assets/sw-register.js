(() => {
  "use strict";
  const VERSION = "10.4.1";
  const VERSION_KEY = "market-radar-version";
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", async () => {
    try {
      const previous = localStorage.getItem(VERSION_KEY);
      localStorage.setItem(VERSION_KEY, VERSION);
      const registration = await navigator.serviceWorker.register(`./service-worker.js?v=${VERSION}`, {
        updateViaCache: "none"
      });
      await registration.update();

      if (registration.waiting) registration.waiting.postMessage({ type: "SKIP_WAITING" });

      let reloaded = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (reloaded) return;
        reloaded = true;
        if (previous && previous !== VERSION) location.reload();
      });
    } catch (error) {
      console.warn("Service worker registration failed:", error);
    }
  });
})();