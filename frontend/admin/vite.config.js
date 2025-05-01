import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from "path";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5174,
    proxy: {
      '/patch': 'http://liandrys-fastapi-admin:5001',
      '/admin': 'http://liandrys-fastapi-admin:5001',
      '/logs': 'http://liandrys-fastapi-admin:5001',
      '/champion': 'http://liandrys-fastapi-admin:5001',
      '/item': 'http://liandrys-fastapi-admin:5001',
      '/rune': 'http://liandrys-fastapi-admin:5001',
      '/summonerspell': 'http://liandrys-fastapi-admin:5001',
      '/images': 'http://liandrys-fastapi-admin:5001',
      '/enum': 'http://liandrys-fastapi-admin:5001',
    },
    watch: {
      usePolling: true
    },
    fs: {
      cachedChecks: false
    }
  },
  resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
  },
})
