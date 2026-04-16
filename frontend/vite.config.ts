import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// fm-web frontend — Vite dev server at :5173, FastAPI at :8000.
// Dev proxies /api → :8000 so the SPA and API share an origin and
// cookies work without CORS preflight.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
})
