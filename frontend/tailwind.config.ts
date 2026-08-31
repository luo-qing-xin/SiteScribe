import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        site: { 50: "#fff3f0", 100: "#ffe2dc", 300: "#f4a99b", 500: "#d94836", 600: "#c9362a", 700: "#ad2b22", 800: "#84251f", 900: "#5d1d1a" },
        ink: { 50: "#f3f3f0", 100: "#e5e4de", 700: "#33332f", 800: "#242522", 900: "#171916", 950: "#10120f" },
        gold: { 100: "#f7ecd4", 300: "#e6c77f", 500: "#c99a3d", 700: "#91671f" },
        paper: "#f6f3ed",
      },
      boxShadow: {
        card: "0 1px 2px rgba(23,25,22,.06), 0 12px 30px rgba(23,25,22,.06)",
        lift: "0 18px 50px rgba(23,25,22,.12)",
      },
    },
  },
  plugins: [],
} satisfies Config;
