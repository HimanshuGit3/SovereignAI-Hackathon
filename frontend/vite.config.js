import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Relative base so the built bundle works from any mount point
  // when FastAPI serves it as static files.
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsDir: 'assets',
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Dev server proxies /api to the backend so the frontend can be
    // developed against a live workbench without CORS juggling.
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
