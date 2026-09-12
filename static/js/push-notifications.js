/**
 * Push Notification Manager for LMS Platform
 *
 * Usage:
 *   PushManager.init()         — Initialize and request permission
 *   PushManager.subscribe()    — Subscribe to push notifications
 *   PushManager.unsubscribe()  — Unsubscribe from push notifications
 *   PushManager.isSupported()  — Check if push is supported
 */

const PushManager = {
    swRegistration: null,
    isSubscribed: false,

    csrfToken() {
        const cookie = document.cookie.split('; ').find(part => part.startsWith('csrftoken='));
        return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
    },

    /**
     * Check if Web Push is supported
     */
    isSupported() {
        return (
            'serviceWorker' in navigator &&
            'PushManager' in window &&
            'Notification' in window
        );
    },

    /**
     * Initialize service worker
     */
    async init() {
        if (!this.isSupported()) {
            console.log('Push notifications not supported');
            return false;
        }

        try {
            this.swRegistration = await navigator.serviceWorker.register('/static/js/sw.js');
            console.log('Service Worker registered:', this.swRegistration.scope);

            // Check if already subscribed
            const subscription = await this.swRegistration.pushManager.getSubscription();
            this.isSubscribed = subscription !== null;

            return true;
        } catch (error) {
            console.error('Service Worker registration failed:', error);
            return false;
        }
    },

    /**
     * Request notification permission
     */
    async requestPermission() {
        if (!this.isSupported()) return false;

        const permission = await Notification.requestPermission();
        return permission === 'granted';
    },

    /**
     * Subscribe to push notifications
     */
    async subscribe() {
        if (!this.swRegistration) {
            await this.init();
        }

        // Request permission first
        const granted = await this.requestPermission();
        if (!granted) {
            console.log('Notification permission denied');
            return false;
        }

        try {
            // Get VAPID key
            const response = await fetch('/api/notifications/push/vapid-key/');
            const data = await response.json();
            const publicKey = data.public_key;

            if (!publicKey) {
                console.log('VAPID key not configured');
                return false;
            }

            // Convert VAPID key
            const applicationServerKey = this.urlBase64ToUint8Array(publicKey);

            // Subscribe
            const subscription = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey,
            });

            // Send subscription to server
            const subJson = subscription.toJSON();
            await fetch('/api/notifications/push/subscribe/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken() },
                body: JSON.stringify({
                    endpoint: subJson.endpoint,
                    p256dh: subJson.keys.p256dh,
                    auth: subJson.keys.auth,
                }),
            });

            this.isSubscribed = true;
            console.log('Push subscription successful');
            return true;

        } catch (error) {
            console.error('Push subscription failed:', error);
            return false;
        }
    },

    /**
     * Unsubscribe from push notifications
     */
    async unsubscribe() {
        if (!this.swRegistration) return false;

        try {
            const subscription = await this.swRegistration.pushManager.getSubscription();
            if (!subscription) return true;

            // Unsubscribe from browser
            await subscription.unsubscribe();

            // Notify server
            await fetch('/api/notifications/push/unsubscribe/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken() },
                body: JSON.stringify({
                    endpoint: subscription.endpoint,
                }),
            });

            this.isSubscribed = false;
            console.log('Push unsubscription successful');
            return true;

        } catch (error) {
            console.error('Push unsubscription failed:', error);
            return false;
        }
    },

    /**
     * Convert VAPID key to Uint8Array
     */
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    },
};

// Auto-initialize on page load
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        if (PushManager.isSupported()) {
            PushManager.init();
        }
    });
}
