/* Alphaops · service worker: cascarón sin conexión + caché de lectura de las últimas respuestas de la API.
   La app y sus assets van RED PRIMERO (el bundle nuevo llega en el primer load tras un despliegue); la caché solo sirve sin conexión. */
const VERSION = 'v3'
const SHELL = 'aq-shell-' + VERSION, DATA = 'aq-data-' + VERSION
self.addEventListener('install', e => { self.skipWaiting() })
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k)))).then(() => self.clients.claim()))
})
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET') return
  if (url.pathname.startsWith('/aq_portal/api/')) {
    // red primero; si falla, última respuesta conocida (solo lectura)
    e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(DATA).then(cache => cache.put(e.request, c)) } return r })
      .catch(() => caches.match(e.request).then(r => r || new Response(JSON.stringify({ error: 'Sin conexión: no hay información guardada para esta vista', code: 503 }), { status: 503, headers: { 'Content-Type': 'application/json' } }))))
    return
  }
  if (e.request.mode === 'navigate' || url.pathname.startsWith('/aq_admin_portal/static/') || url.pathname.startsWith('/admin-portal')) {
    e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(SHELL).then(cache => cache.put(e.request, c)) } return r })
      .catch(() => caches.match(e.request).then(hit => hit || (e.request.mode === 'navigate' ? caches.match('/admin-portal/') : undefined)).then(r => r || new Response('Sin conexión', { status: 503 }))))
  }
})
