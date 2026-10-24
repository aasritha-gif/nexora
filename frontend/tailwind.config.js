/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        midnight: {
          950: "#060814",
          900: "#0b0f19",
          850: "#101626",
          800: "#151d33",
          700: "#1e2942",
          600: "#2d3c5e",
        },
        indigo: {
          brand: "#6366f1",
          glow: "#4f46e5",
          accent: "#818cf8",
        },
        cyan: {
          glow: "#06b6d4",
          accent: "#22d3ee",
        },
        violet: {
          brand: "#8b5cf6",
          glow: "#7c3aed",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "monospace"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "cosmos-glow": "radial-gradient(circle at 50% 20%, rgba(99, 102, 241, 0.15), transparent 70%)",
        "mesh-gradient": "linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(6,182,212,0.05) 50%, rgba(139,92,246,0.08) 100%)",
      },
    },
  },
  plugins: [],
};
