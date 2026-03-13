import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0a0a0a",
          secondary: "#111118",
          card: "#1a1a2e",
          hover: "#24243e",
        },
        accent: {
          blue: "#4f6ef7",
          purple: "#7c3aed",
          cyan: "#06b6d4",
        },
        confidence: {
          high: "#22c55e",
          medium: "#eab308",
          low: "#ef4444",
        },
        status: {
          active: "#3b82f6",
          resolved: "#22c55e",
          expired: "#6b7280",
        },
        border: {
          DEFAULT: "#2a2a3e",
          light: "#3a3a4e",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
