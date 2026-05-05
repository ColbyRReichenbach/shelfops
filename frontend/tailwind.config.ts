import tailwindcssAnimate from 'tailwindcss-animate'

/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                shelf: {
                    primary: '#0071e3',
                    secondary: '#0071e3',
                    accent: '#5856d6',
                    foreground: '#1d1d1f',
                    background: '#f5f5f7',
                },
                apple: {
                    blue: '#0071e3',
                    green: '#34c759',
                    red: '#ff3b30',
                    orange: '#ff9500',
                    yellow: '#ffcc00',
                    purple: '#5856d6',
                    pink: '#af52de',
                    gray: '#86868b',
                    'gray-light': '#f5f5f7',
                    'gray-border': '#d2d2d7',
                    text: '#1d1d1f',
                    'text-secondary': '#86868b',
                },
                brand: {
                    50: '#eef2ff',
                    100: '#e0e7ff',
                    200: '#c7d2fe',
                    300: '#a5b4fc',
                    400: '#818cf8',
                    500: '#6366f1',
                    600: '#4f46e5',
                    700: '#4338ca',
                    800: '#3730a3',
                    900: '#312e81',
                    950: '#1e1b4b',
                },
                surface: {
                    50: '#f8fafc',
                    100: '#f1f5f9',
                    200: '#e2e8f0',
                    700: '#1e293b',
                    800: '#0f172a',
                    900: '#020617',
                },
                success: '#34c759',
                warning: '#ff9500',
                danger: '#ff3b30',
                critical: '#ff3b30',
            },
            fontFamily: {
                sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'fade-in': 'fadeIn 0.4s ease-out',
                'slide-up': 'slideUp 0.4s ease-out',
            },
            keyframes: {
                fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
                slideUp: {
                    '0%': { opacity: '0', transform: 'translateY(10px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
            },
        },
    },
    plugins: [tailwindcssAnimate],
}
