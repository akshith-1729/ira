export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "rgb(var(--ink) / <alpha-value>)",
        panel: "rgb(var(--panel) / <alpha-value>)",
        lift: "rgb(var(--lift) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        cream: "rgb(var(--cream) / <alpha-value>)",
        mute: "rgb(var(--mute) / <alpha-value>)",
        teal: "rgb(var(--accent) / <alpha-value>)",
        amber: "rgb(var(--amber) / <alpha-value>)",
        rose: "rgb(var(--rose) / <alpha-value>)",
        violet: "rgb(var(--violet) / <alpha-value>)",
        sky: "rgb(var(--sky) / <alpha-value>)",
        lime: "rgb(var(--lime) / <alpha-value>)",
      },
      fontFamily: {
        serif: ["Fraunces", "Iowan Old Style", "Georgia", "serif"],
        sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 18px 40px -28px rgba(0,0,0,0.45)",
      },
    },
  },
  plugins: [],
};
