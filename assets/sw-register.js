(() => {
  "use strict";
  const CLEAN_KEY = "market-radar-cleanup-10.5.2";
  async function cleanup() {
    try {
      if ("serviceWorker" in navigator) {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map(registration => registration.unregister()));
      }
      if ("caches" in window) {
        const keys = await caches.keys();
        await Promise.all(keys.filter(key => /market-event-radar|market-radar/i.test(key)).map(key => caches.delete(key)));
      }
      if (!sessionStorage.getItem(CLEAN_KEY)) {
        sessionStorage.setItem(CLEAN_KEY,"1");
        const url = new URL(location.href);
        if (!url.searchParams.has("clean")) {
          url.searchParams.set("clean", "1052");
          location.replace(url.href);
        }
      }
    } catch (error) {
      console.warn("Cache cleanup skipped", error);
    }
  }
  window.addEventListener("load", cleanup, {once:true});
})();
