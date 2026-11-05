import jsxA11y from 'eslint-plugin-jsx-a11y';

// Accessibility lint for the React app (`npm run lint`, also run in CI).
// Only the jsx-a11y rules are on for now. Adding ESLint's core rules
// (@eslint/js) or React rules is a separate decision.
// eslint-plugin-jsx-a11y 6.x supports ESLint up to 9, so do not upgrade
// eslint to 10 until the plugin does.
export default [
  { ignores: ['dist/', 'node_modules/'] },
  {
    files: ['src/**/*.{js,jsx}'],
    ...jsxA11y.flatConfigs.recommended,
    languageOptions: {
      ...jsxA11y.flatConfigs.recommended.languageOptions,
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
];
