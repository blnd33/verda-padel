// Bump CACHE whenever this file's strategy changes: activate deletes every other
// cache, which is how a stale copy already sitting in visitors' browsers is purged.
const CACHE = 'verda-v2';

// Pages and icons only. Stylesheets and scripts are requested with a ?v= stamp
// (see version_static_urls), so an unversioned precache entry would never match.
const PRECACHE = [
  '/',
  '/booking/',
  '/store/',
  '/about',
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

// Keep one copy per asset: when a new ?v= arrives, drop the older ones.
async function storeLatest(request, response) {
  const cache = await caches.open(CACHE);
  const path = new URL(request.url).pathname;
  const stale = (await cache.keys()).filter(k => new URL(k.url).pathname === path && k.url !== request.url);
  await Promise.all(stale.map(k => cache.delete(k)));
  await cache.put(request, response);
}

self.addEventListener('fetch', e => {
  const { request } = e;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== location.origin) return;

  // Admin and auth: always network-only
  if (url.pathname.startsWith('/admin') || url.pathname.startsWith('/auth') || url.pathname.startsWith('/pos')) return;

  // Static assets: cache-first. Safe because changed files arrive under a new ?v= URL.
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(caches.match(request).then(cached => cached || fetch(request).then(res => {
      if (res.ok) storeLatest(request, res.clone());
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
