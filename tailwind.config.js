/** Tailwind is compiled locally (no CDN in production).
 *  Rebuild after editing templates:  npm run css   */
module.exports = {
  content: ["./templates/**/*.html", "./static/js/*.js", "./routes/*.py"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Vazirmatn', 'system-ui', 'sans-serif'],
        kurdish: ['Vazirmatn', 'Noto Sans Arabic', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};
