/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c', // Primary deep red
          800: '#991b1b', // Primary hover
          900: '#7f1d1d', // Primary active
          950: '#450a0a',
        },
        dark: {
          DEFAULT: '#0a0a0a',
          surface: '#121212',
          card: '#18181b',
          border: '#27272a',
          foreground: '#f4f4f5',
          muted: '#a1a1aa',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'brand-glow': '0 4px 20px -2px rgba(185, 28, 28, 0.25)',
      },
    },
  },
  plugins: [],
}
