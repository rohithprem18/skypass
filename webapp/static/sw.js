/* SkyPass service worker.
 *
 * Caches the shell only. Plans are deliberately never cached: a stale
 * timetable is worse than no timetable -- the sky will have moved on, and an
 * observer acting on yesterday's plan looks at the wrong patch of sky.
 */
const SHELL = 'skypass-shell-v1';
const ASSETS = ['/', '/styles.css', '/app.js', '/icon.svg',
                '/manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(ASSETS))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== SHELL)
      .map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) return;      // always live
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request))
  );
});
