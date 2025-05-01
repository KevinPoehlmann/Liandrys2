import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/patch': 'http://liandrys-fastapi:5000',
      '/champion': 'http://liandrys-fastapi:5000',
      '/item': 'http://liandrys-fastapi:5000',
      '/rune': 'http://liandrys-fastapi:5000',
      '/summonerspell': 'http://liandrys-fastapi:5000',
      '/simulation': 'http://liandrys-fastapi:5000',
      '/images': 'http://liandrys-fastapi-admin:5001',
    },
    watch: {
      usePolling: true
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
})
