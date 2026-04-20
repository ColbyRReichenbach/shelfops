import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const apiTarget = process.env.VITE_DEV_PROXY_TARGET ?? 'http://localhost:8000'
const wsTarget = apiTarget.replace(/^http/i, 'ws')

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 3000,
        proxy: {
            '/api': {
                target: apiTarget,
                changeOrigin: true,
            },
            '/ws': {
                target: wsTarget,
                ws: true,
            },
        },
    },
    build: {
        chunkSizeWarningLimit: 600,
        rollupOptions: {
            output: {
                manualChunks: {
                    'vendor-react': ['react', 'react-dom', 'react-router-dom'],
                    'vendor-charts': ['recharts'],
                    'vendor-ui': [
                        '@radix-ui/react-dialog',
                        '@radix-ui/react-dropdown-menu',
                        '@radix-ui/react-select',
                        '@radix-ui/react-slot',
                        '@radix-ui/react-tabs',
                        '@radix-ui/react-toast',
                        'lucide-react',
                        'class-variance-authority',
                        'clsx',
                        'tailwind-merge',
                    ],
                    'vendor-query': ['@tanstack/react-query'],
                    'vendor-auth': ['@auth0/auth0-react'],
                },
            },
        },
    },
})
