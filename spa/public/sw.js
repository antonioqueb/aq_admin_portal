/* Alphaops · service worker: cascarón sin conexión + caché de lectura de las últimas respuestas de la API. */
const SHELL = 'aq-shell-v1', DATA = 'aq-data-v1'
self.addEventListener('install', e => { self.skipWaiting() })
self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()) })
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET') return
  if (url.pathname.startsWith('/aq_portal/api/')) {
    // red primero; si falla, última respuesta conocida (solo lectura)
    e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(DATA).then(cache => cache.put(e.request, c)); return r })
      .catch(() => caches.match(e.request).then(r => r || new Response(JSON.stringify({ error: 'Sin conexión: mostrando última información conocida no disponible', code: 503 }), { status: 503, headers: { 'Content-Type': 'application/json' } }))))
    return
  }
  if (url.pathname.startsWith('/aq_admin_portal/static/') || url.pathname.startsWith('/admin-portal')) {
    e.respondWith(caches.match(e.request).then(hit => { const net = fetch(e.request).then(r => { const c = r.clone(); caches.open(SHELL).then(cache => cache.put(e.request, c)); return r }).catch(() => hit); return hit || net }))
  }
})
