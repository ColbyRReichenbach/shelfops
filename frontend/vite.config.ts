import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

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
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/models': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/ml-alerts': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/experiments': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/outcomes': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/anomalies': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/ws': {
                target: 'ws://localhost:8000',
                ws: true,
            },
        },
    },
})
