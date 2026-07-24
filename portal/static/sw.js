// Caches ONLY same-origin /static/ assets (css/js/img/manifest) — cache-first,
// so repeat visits on slow/2G connections skip re-downloading them.
//
// Deliberately never caches anything else: not HTML pages, not /loan/* or
// /pay/* dues data, not PDFs, not the /device-location beacon. This portal
// renders everything live from AllCloud (see dashboard.py) and shows real
// money figures — a stale cached dues page, or worse a cached authenticated
// page served to the next person on a shared device after logout, would be
// a real problem. Static assets carry no customer data, so they're the only
// safe thing to cache.

var CACHE_NAME = "smsquare-static-v1";
var STATIC_PREFIX = "/static/";

self.addEventListener("install", function (event) {
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names
          .filter(function (name) { return name !== CACHE_NAME; })
          .map(function (name) { return caches.delete(name); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin ||
      url.pathname.indexOf(STATIC_PREFIX) !== 0) {
    return; // let the browser handle everything else normally (network)
  }

  event.respondWith(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.match(event.request).then(function (cached) {
        var fetchPromise = fetch(event.request).then(function (response) {
          if (response && response.ok) cache.put(event.request, response.clone());
          return response;
        }).catch(function () { return cached; });
        return cached || fetchPromise;
      });
    })
  );
});
