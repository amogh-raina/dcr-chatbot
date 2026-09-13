import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/static/demo/',
  plugins: [react()],
  build: {
    outDir: '../static/demo',
    emptyOutDir: true,
  },
});
