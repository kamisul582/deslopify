/* global process */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Open Graph needs absolute URLs. Use VITE_SITE_URL if set, else the Vercel
// production domain, else fall back to root-relative paths (fine locally).
function siteUrl() {
  if (process.env.VITE_SITE_URL) return process.env.VITE_SITE_URL.replace(/\/$/, '')
  if (process.env.VERCEL_PROJECT_PRODUCTION_URL) return `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
  return ''
}

const injectSiteUrl = () => ({
  name: 'inject-site-url',
  transformIndexHtml: (html) => html.replaceAll('__SITE_URL__', siteUrl()),
})

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), injectSiteUrl()],
  server: {
    proxy: {
      "/analyze": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
})
