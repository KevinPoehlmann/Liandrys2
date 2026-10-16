/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#F3F4F6",
          dark: "#1F2937",
        },
        secondary: {
          DEFAULT: "#E5E7EB",
          dark: "#374151",
        }, 
        accent: {
          DEFAULT: "#32CD32",
          dark: "#228B22",
        },
        background: {
          DEFAULT: "#FFFFFF",
          dark: "#111827",
        },
        text: {
          DEFAULT: "#000000",
          dark: "#F3F4F6",
        },
        blueSide: {
          DEFAULT: "#EFF6FF",
          dark: "#1E3A8A",
        },
        redSide: {
          DEFAULT: "#FEF2F2",
          dark: "#7F1D1D",
        },
      },
    },
  },
  plugins: [],
  darkMode: 'class',
}

