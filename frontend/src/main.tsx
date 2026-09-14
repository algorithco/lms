import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './theme.css'
import App from './App.tsx'
import { LangProvider } from './i18n/LangContext.tsx'

/**
 * React equivalent of legacy static/js/push-notifications.js PushManager.init().
 * Registers the service worker (/sw.js, shipped from frontend/public/ via
 * Vite into dist/) on app start. Registration only — subscribing still needs
 * a user gesture + VAPID key (see Push.subscribe in lib/api.ts), exactly like
 * the legacy manager. Prod-only so dev never serves stale cached bundles,
 * and fully non-blocking (push is best-effort).
 */
function initPushNotifications(): void {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return
  if (!import.meta.env.PROD) return
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* push unavailable — app works without it */
    })
  })
}

initPushNotifications()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LangProvider>
      <App />
    </LangProvider>
  </StrictMode>,
)
