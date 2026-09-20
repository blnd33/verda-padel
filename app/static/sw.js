const CACHE = 'verda-v1';
const PRECACHE = [
  '/',
  '/booking/',
  '/store/',
  '/about',
  '/static/css/verda.css',
  '/static/css/site.css',
  '/static/js/verda.js',
  '/static/images/verda-logo.png',
  '/static/images/icon-192.png',
  '/static/manifest.json'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const { request } = e;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== location.origin) return;

  // Admin and auth: always network-only
  if (url.pathname.startsWith('/admin') || url.pathname.startsWith('/auth') || url.pathname.startsWith('/pos')) return;

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(caches.match(request).then(cached => cached || fetch(request).then(res => {
      const clone = res.clone();
      caches.open(CACHE).then(c => c.put(request, clone));
      return res;
    })));
    return;
  }

  // HTML pages: network-first, fall back to cache
  e.respondWith(fetch(request).then(res => {
    const clone = res.clone();
    caches.open(CACHE).then(c => c.put(request, clone));
    return res;
  }).catch(() => caches.match(request)));
});
