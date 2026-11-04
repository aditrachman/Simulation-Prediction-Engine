import js from "@eslint/js";
import nextPlugin from "@next/eslint-plugin-next";

export default [
  js.configs.recommended,
  {
    plugins: { "@next/next": nextPlugin },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      "no-unused-vars": ["warn", { "argsIgnorePattern": "^_", "varsIgnorePattern": "^_" }],
      "no-undef": "warn",
    },
    languageOptions: {
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        browser: true,
        es2021: true,
        node: true,
        process: "readonly",
      },
    },
  },
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: {
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
  },
  {
    ignores: [
      ".next/**",
      ".next.bak-**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      "node_modules/**",
      "*.config.*",
    ],
  },
];
