/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: "#0B0F17",
        surface: {
          DEFAULT: "#111827",
          hover: "#172033",
          card: "#0F172A",
          inset: "#090D14",
          border: "#1F2937",
          borderLight: "#2D3748"
        },
        brand: {
          primary: "#3B82F6",
          hover: "#2563EB",
          light: "#60A5FA"
        },
        severity: {
          critical: "#EF4444",
          criticalBg: "rgba(239, 68, 68, 0.15)",
          criticalBorder: "rgba(239, 68, 68, 0.35)",
          high: "#F59E0B",
          highBg: "rgba(245, 158, 11, 0.15)",
          positive: "#22C55E",
          positiveBg: "rgba(34, 197, 94, 0.15)",
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['Figma Mono', 'JetBrains Mono', 'Menlo', 'monospace']
      }
    },
  },
  plugins: [],
}
