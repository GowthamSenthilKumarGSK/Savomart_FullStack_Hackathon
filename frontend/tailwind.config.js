/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        savo: {
          purple: '#782B90',
          yellow: '#FFF200',
          'purple-dark': '#5C1F6E',
          'purple-light': '#9B4DB3',
        },
      },
    },
  },
  plugins: [],
}
