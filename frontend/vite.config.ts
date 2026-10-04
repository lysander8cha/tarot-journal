import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  // Dev only: forward API calls to Flask so the browser sees one origin.
  server: { proxy: { '/api': 'http://localhost:5678' } },
})
