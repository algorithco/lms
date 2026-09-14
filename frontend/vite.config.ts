import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const DJANGO = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 0.0.0.0: reachable via localhost AND 127.0.0.1 (avoids ::1-only
    // binding that made the UI unreachable for some browsers).
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      // Same-origin in dev: React uses relative URLs, Vite forwards to Daphne.
      '/api': { target: DJANGO, changeOrigin: true },
      '/essays': { target: DJANGO, changeOrigin: true },
      '/arena': { target: DJANGO, changeOrigin: true },
      '/subscribe': { target: DJANGO, changeOrigin: true },
      '/tma': { target: DJANGO, changeOrigin: true },
      '/media': { target: DJANGO, changeOrigin: true },
      '/static': { target: DJANGO, changeOrigin: true },
      // NOTE: /login, /logout and /password-reset* are intentionally NOT
      // proxied — the SPA owns those pages and talks to Django only via the
      // /api/auth/* JSON endpoints (proxied above). The retired Django HTML
      // auth views are unreachable from the UI.
      '/ws': { target: 'ws://localhost:8000', ws: true, changeOrigin: true },
    },
  },
})
