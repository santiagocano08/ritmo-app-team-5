import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: "#F4F6F9",
        surface: "#FFFFFF",
        text: {
          primary: "#12161C",
          secondary: "#4A5361",
        },
        border: {
          DEFAULT: "#DDE1E7",
          placeholder: "#A3ACB9",
        },
        link: {
          DEFAULT: "#1D4ED8",
          hover: "#1E3A8A",
        },
        sidebar: {
          DEFAULT: "#14213D",
          inactive: "#E2E8F0",
          divider: "#2B3A5C",
          role: "#CBD5E1",
        },
        logo: "#FBBF24",
        status: {
          "live-bg": "#DCFCE7",
          "live-fg": "#166534",
          "estimated-bg": "#FEF3C7",
          "estimated-fg": "#78350F",
          "nodata-bg": "#FEE2E2",
          "nodata-fg": "#991B1B",
        },
      },
      borderRadius: {
        token: "8px",
        card: "12px",
        pill: "999px",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        brand: ["'Space Grotesk'", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
