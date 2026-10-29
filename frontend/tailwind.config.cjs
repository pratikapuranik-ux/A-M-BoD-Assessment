/** A&M brand palette (see src/styles/legacy.css header). Interface: navy / slate / bright blue; accents are for data. */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  // The legacy stylesheet owns base typography and form styling, so Tailwind's reset stays off.
  corePlugins: { preflight: false },
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#002B49', 2: '#1A405B' },
        brand: '#0085CA',
        teal: '#00677F',
        slate: '#5E8AB4',
        amber: '#CF7F00',
        rust: '#A6192E',
        tint: '#EFF3F8',
        line: { DEFAULT: '#ECECEC', 2: '#D9D9D9' },
        muted: '#646464',
        surface: '#F7F9FB',
        grade: { A: '#00677F', B: '#0085CA', C: '#5E8AB4', D: '#CF7F00', F: '#A6192E', NA: '#969696' },
      },
      fontFamily: { sans: ['Arial', 'Helvetica', 'sans-serif'] },
      borderRadius: { card: '10px' },
      boxShadow: { card: '0 1px 2px rgba(0,43,73,.04),0 4px 14px rgba(0,43,73,.05)' },
    },
  },
  plugins: [],
}
