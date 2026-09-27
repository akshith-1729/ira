export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0c0d10",
        panel: "#14161c",
        line: "#2c3038",
        cream: "#eceae4",
        mute: "#9a958b",
        teal: "#3dbea5",
        amber: "#e0a15a",
      },
      fontFamily: {
        serif: ["Georgia", "Iowan Old Style", "Palatino Linotype", "Palatino", "serif"],
        sans: ["Segoe UI", "Helvetica Neue", "sans-serif"],
      },
    },
  },
  plugins: [],
};
