import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Build into a dist/ the Python server serves directly, so production needs no
// Node process -- the research repo still runs with Python alone.
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false },
  server: {
    port: 5173,
    // During development Vite serves the UI and forwards the API to the
    // Python planner, so there is one source of truth for the astronomy.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
