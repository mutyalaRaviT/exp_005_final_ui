/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5199,
    strictPort: true,
    proxy: {
      '/api': process.env.VITE_PROXY ?? 'http://localhost:8110',
      // HOLA sidecar (scripts/hola_server) — tier 5 layout toggle
      '/hola': process.env.VITE_HOLA_PROXY ?? 'http://localhost:8765',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
  },
})
