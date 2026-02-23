import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8008',
          changeOrigin: true,
        },
      },
    },
    define: {
      'import.meta.env.VITE_ENV': JSON.stringify(env.VITE_ENV || 'development'),
    },
  };
});
