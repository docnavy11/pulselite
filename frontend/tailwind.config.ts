import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        sidebar: {
          bg: "#ffffff",
          border: "#f0ebe3",
          text: "#777777",
          active: "#ff6b35",
          "active-bg": "#fff3ee",
          hover: "#faf8f5",
        },
        warm: {
          50: "#faf8f5",
          100: "#f5f0ea",
          200: "#f0ebe3",
          300: "#ede8e0",
        },
        primary: {
          50: "#fff3ee",
          100: "#ffe4d6",
          200: "#ffcbb8",
          300: "#ffa882",
          400: "#ff8552",
          500: "#ff6b35",
          600: "#e85a26",
          700: "#c44a1e",
          800: "#9e3c18",
          900: "#7a2e12",
        },
      },
    },
  },
  plugins: [],
};
export default config;
