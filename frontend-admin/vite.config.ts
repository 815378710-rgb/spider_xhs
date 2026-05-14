import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/admin/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
  server: {
    port: 3456,
    proxy: {
      '/api': {
        target: 'http://192.168.68.161:5005',
        changeOrigin: true,
      },
    },
  },
})
