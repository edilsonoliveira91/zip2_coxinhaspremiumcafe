
// Dummy Service Worker to satisfy PWA requirements
self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', function(event) {
  // Faz o fetch normal (só precisamos do listener pra passar no teste do Chrome)
  event.respondWith(fetch(event.request));
});
