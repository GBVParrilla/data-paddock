import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Dev: API calls are proxied to the FastAPI backend. Prod: `vite build` output is served by FastAPI itself.
const API = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: Object.fromEntries(['/seasons', '/events', '/sessions', '/drivers', '/health'].map((p) => [p, { target: API, changeOrigin: true }])),
  },
})
