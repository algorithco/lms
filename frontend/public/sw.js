// Service Worker for Web Push Notifications
// Ona Tili & Adabiyot — served from /sw.js (frontend/public/sw.js via Vite).
// NOTE: no fetch handler on purpose — the app shell is never cached, so
// clients can never pin a stale bundle (matches legacy static/js/sw.js).

// Install event
self.addEventListener('install', (_event) => {
    self.skipWaiting();
});

// Activate event
self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

// Push event — handle incoming push notifications
self.addEventListener('push', (event) => {
    let data = {
        title: 'Ona Tili & Adabiyot',
        body: 'Yangi xabar bor!',
        icon: '/grandec.png',
        badge: '/grandec.png',
        data: { url: '/dashboard/' },
    };

    if (event.data) {
        try {
            data = { ...data, ...event.data.json() };
        } catch {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: data.icon,
        badge: data.badge,
        vibrate: [100, 50, 100],
        data: data.data,
        actions: data.actions || [],
        tag: data.tag || 'lms-notification',
        renotify: true,
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Notification click event
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const url = event.notification.data?.url || '/dashboard/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            // Focus existing window if open
            for (const client of clientList) {
                if (client.url.includes(url) && 'focus' in client) {
                    return client.focus();
                }
            }
            // Open new window
            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});
