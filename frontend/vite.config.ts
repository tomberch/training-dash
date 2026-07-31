import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/login': 'http://localhost:8000',
      '/activities': 'http://localhost:8000',
      '/upload': 'http://localhost:8000',
    },
  },
})