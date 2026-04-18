/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        teal: { DEFAULT: '#00c9a7', dark: '#009e85', light: '#33d4b8' },
        surface: { DEFAULT: '#111111', muted: '#0e0e0e', border: '#1a1a1a' },
      },
      animation: {
        'fade-up': 'fadeUp 0.4s ease forwards',
        'spin-slow': 'spin 3s linear infinite',
        'pulse-teal': 'pulseTeal 2s ease-in-out infinite',
      },
      keyframes: {
        fadeUp: { '0%': { opacity: '0', transform: 'translateY(12px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        pulseTeal: { '0%,100%': { boxShadow: '0 0 0 0 rgba(0,201,167,0.3)' }, '50%': { boxShadow: '0 0 0 8px rgba(0,201,167,0)' } },
      },
    },
  },
  plugins: [],
}
