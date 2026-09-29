/** @type {import('tailwindcss').Config} */
// Design tokens for the Outbox-inspired dark theme. Everything is centralized
// here so the palette can be re-skinned by editing these values only.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Layered dark surfaces (base -> raised panels).
        ink: {
          DEFAULT: "#0a0e14", // page background
          900: "#0a0e14",
          800: "#0e131c", // section
          700: "#131a25", // card
          600: "#1a2331", // raised / hover
          500: "#243040", // subtle fill
        },
        line: {
          DEFAULT: "#1e2836", // default border
          strong: "#2b3849",
        },
        // Brand accent — confident, premium "precision" violet-blue.
        brand: {
          50: "#ecebff",
          100: "#d6d4ff",
          400: "#8b84ff",
          500: "#6c63ff",
          600: "#584fe6",
          700: "#463dc4",
        },
        // Text tones on dark.
        content: {
          DEFAULT: "#e6edf6",
          muted: "#94a3b8",
          faint: "#64748b",
        },
      },
      boxShadow: {
        panel: "0 1px 2px rgba(0,0,0,0.4), 0 8px 24px -12px rgba(0,0,0,0.5)",
        glow: "0 0 0 1px rgba(108,99,255,0.4), 0 8px 30px -8px rgba(108,99,255,0.35)",
      },
    },
  },
  plugins: [],
};
