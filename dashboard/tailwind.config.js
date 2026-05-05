/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      keyframes: {
        'torus-spin': {
          from: { transform: 'rotateX(65deg) rotateZ(0deg)' },
          to:   { transform: 'rotateX(65deg) rotateZ(360deg)' },
        },
        'cradle-left': {
          '0%, 100%': { transform: 'translateX(-5px) translateY(-5px)' },
          '25%, 75%':  { transform: 'translateX(0) translateY(0)' },
        },
        'cradle-right': {
          '0%, 25%, 75%, 100%': { transform: 'translateX(0) translateY(0)' },
          '50%': { transform: 'translateX(5px) translateY(-5px)' },
        },
      },
      animation: {
        'torus-spin':   'torus-spin 2.5s linear infinite',
        'cradle-left':  'cradle-left 1.2s ease-in-out infinite',
        'cradle-right': 'cradle-right 1.2s ease-in-out infinite',
      },
      colors: {
        base: 'var(--color-base)',
        surface: 'var(--color-surface)',
        elevated: 'var(--color-elevated)',
        sidebar: 'var(--color-sidebar)',
        border: 'var(--color-border)',
        primary: 'var(--color-primary)',
        muted: 'var(--color-muted)',
        accent: 'var(--color-accent)',
        'accent-hover': 'var(--color-accent-hover)',
      },
    },
  },
  plugins: [],
};
