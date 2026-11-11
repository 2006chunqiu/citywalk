import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// GitHub Pages 的仓库页面挂在 /citywalk/ 子路径下，
// 部署时通过 VITE_BASE 注入；本地开发默认 '/'。
const base = process.env.VITE_BASE || '/'

export default defineConfig({
  base,
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 前端所有 /api 请求转发到后端，避免跨域配置
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
