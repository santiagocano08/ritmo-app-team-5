/* eslint-env node */
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: 2022, sourceType: "module" },
  settings: { react: { version: "19.0" } },
  plugins: ["@typescript-eslint", "react-hooks", "react-refresh"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  ignorePatterns: [
    "dist",
    "coverage",
    "src/api/generated/**",
    ".eslintrc.cjs",
    "scripts/**",
  ],
  rules: {
    "@typescript-eslint/no-explicit-any": "error",
    "no-restricted-syntax": [
      "error",
      {
        selector:
          "CallExpression[callee.name='useEffect'] CallExpression[callee.name='fetch']",
        message:
          "No data fetching inside useEffect — use TanStack Query (coding standards, R3).",
      },
    ],
  },
  overrides: [
    {
      files: ["tests/**/*.{ts,tsx}"],
      env: { node: true },
    },
  ],
};
