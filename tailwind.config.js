/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        democrat: "#1d4ed8",
        republican: "#b91c1c",
        independent: "#6b7280",
      },
    },
  },
  plugins: [],
};
