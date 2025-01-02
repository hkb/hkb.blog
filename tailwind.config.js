/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./.site/**/*.html'],
  theme: {
    extend: {
      listStyleType: {
        dash: '"\\2014"',
      }
    },
  },
  plugins: [],
}
