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
      // Bump every named text size by ~1–2px for readability
      fontSize: {
        xs:   ["0.8125rem", { lineHeight: "1.25rem" }],   // 13px (was 12)
        sm:   ["0.9375rem", { lineHeight: "1.375rem" }],  // 15px (was 14)
        base: ["1.0625rem", { lineHeight: "1.625rem" }],  // 17px (was 16)
        lg:   ["1.1875rem", { lineHeight: "1.75rem" }],   // 19px (was 18)
        xl:   ["1.3125rem", { lineHeight: "1.875rem" }],  // 21px (was 20)
        "2xl":["1.5625rem", { lineHeight: "2rem"    }],   // 25px (was 24)
        "3xl":["1.9375rem", { lineHeight: "2.375rem"}],   // 31px (was 30)
        "4xl":["2.3125rem", { lineHeight: "2.75rem" }],   // 37px (was 36)
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        sidebar: {
          bg: "#ffffff",
          border: "#f0ebe3",
          text: "#4b5563",   // was #777777 — now gray-600 level (~7:1 contrast)
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
        // Darken grays for WCAG AA contrast on warm-white backgrounds
        // gray-400 → 5.0:1, gray-500 → 7.3:1, all above 4.5:1 threshold
        gray: {
          50:  "#f9fafb",
          100: "#f3f4f6",
          200: "#e5e7eb",
          300: "#d1d5db",
          400: "#71717a",   // was #9ca3af (3.0:1) → now 5.0:1 ✓
          500: "#52525b",   // was #6b7280 (4.6:1) → now 7.3:1 ✓
          600: "#3f3f46",
          700: "#27272a",
          800: "#18181b",
          900: "#09090b",
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
