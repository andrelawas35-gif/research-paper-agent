/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Calm-studio semantic tokens ──────────────────────────
        paper: '#F6F3EC',
        surface: '#FFFFFF',
        ink: '#1F2429',
        muted: '#596166',
        action: '#1A5752',
        'action-soft': '#E0F1EE',
        caution: '#9A651D',
        danger: '#A33A3A',
        border: '#D1CDC4',
      },
      spacing: {
        // 4px scale: 4, 8, 12, 16, 24, 32, 48, 64
        '0.5': '4px',
        '1.5': '12px',
        12: '12px',
        13: undefined, // skip
        15: undefined,
        18: undefined,
        22: undefined,
        26: undefined,
        30: undefined,
        34: undefined,
      },
      borderRadius: {
        control: '8px',
        row: '16px',
        panel: '20px',
        shell: '28px',
      },
      fontSize: {
        '2xs': ['12px', { lineHeight: '1.3' }],
        xs: ['14px', { lineHeight: '1.4' }],
        sm: ['16px', { lineHeight: '1.5' }],
        base: ['16px', { lineHeight: '1.6' }],
        lg: ['20px', { lineHeight: '1.4' }],
        xl: ['24px', { lineHeight: '1.3' }],
        '2xl': ['32px', { lineHeight: '1.2' }],
      },
      fontWeight: {
        normal: '400',
        semibold: '600',
        bold: '700',
      },
      fontFamily: {
        ui: ['Atkinson Hyperlegible', 'system-ui', 'sans-serif'],
        reading: ['Source Serif 4', 'Georgia', 'serif'],
      },
      transitionDuration: {
        inline: '120ms',
        state: '180ms',
        context: '240ms',
      },
      transitionTimingFunction: {
        calm: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      ringWidth: {
        3: '3px',
      },
      ringColor: {
        focus: '#1A5752',
      },
    },
  },
  plugins: [],
};
