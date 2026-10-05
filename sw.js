const CACHE = 'papergrader-v2-build1-v3';
const CORE = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './graders.js',
  './i18n.js',
  './manifest.webmanifest',
];
self.addEventListener('install', (event) =>
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(CORE))
      .then(() => self.skipWaiting()),
  ),
);
self.addEventListener('activate', (event) =>
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  ),
);
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const sameOrigin = new URL(event.request.url).origin === self.location.origin;
  if (sameOrigin) {
    event.respondWith(
      fetch(event.request)
        .then(async (resp) => {
          if (resp.ok)
            await caches
              .open(CACHE)
              .then((c) => c.put(event.request, resp.clone()))
              .catch(() => {});
          return resp;
        })
        .catch(async (error) => (await caches.match(event.request)) || Promise.reject(error)),
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then(
      (hit) =>
        hit ||
        fetch(event.request).then(async (resp) => {
          if (resp.ok || resp.type === 'opaque')
            await caches
              .open(CACHE)
              .then((c) => c.put(event.request, resp.clone()))
              .catch(() => {});
          return resp;
        }),
    ),
  );
});
