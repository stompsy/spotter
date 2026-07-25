/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/templates/**/*.html",
    "./src/apps/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        "brand-ink": "#09101d",
        "brand-panel": "#0f1c2f",
        "brand-panel-soft": "#16253f",
        "brand-neon": "#58f2bf",
        "brand-neon-soft": "#80ffd2",
        "brand-sunset": "#ff8d4a",
      },
      boxShadow: {
        pulse: "0 14px 40px -24px rgba(88, 242, 191, 0.6)",
      },
      animation: {
        floatup: "floatup 700ms ease-out both",
      },
      keyframes: {
        floatup: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
