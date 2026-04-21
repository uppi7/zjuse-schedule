import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // 开发时把 /api 请求转发到后端（容器内走 Docker 内网名称）
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://localhost:8002',
        changeOrigin: true,
      },
    },
  },
})
