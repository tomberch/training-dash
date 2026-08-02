import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/login': 'http://localhost:8000',
      '/logout': 'http://localhost:8000',
      '/me': 'http://localhost:8000',
      '/activities': 'http://localhost:8000',
      '/records': 'http://localhost:8000',
      '/upload': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/pmc': 'http://localhost:8000',
      '/power-curve': 'http://localhost:8000',
      '/fitness': 'http://localhost:8000',
      '/tiles': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
  },
})