import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        site: { 50: "#eef8f3", 100: "#d8eee3", 600: "#087354", 700: "#075f47", 800: "#064d3b", 900: "#063e31" },
      },
      boxShadow: { card: "0 1px 3px rgba(10,42,33,.08), 0 6px 18px rgba(10,42,33,.05)" },
    },
  },
  plugins: [],
} satisfies Config;

