import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Bundle totalmente independiente de los assets de Odoo.
// Se compila en ../static/spa y Odoo lo sirve en /admin-portal
export default defineConfig({
  plugins: [react()],
  base: '/aq_admin_portal/static/spa/',
  build: {
    outDir: '../static/spa',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/aq_portal': { target: process.env.ODOO_URL || 'http://localhost:8069', changeOrigin: true },
    },
  },
})
