import jsxA11y from 'eslint-plugin-jsx-a11y';

export default [{
  ...jsxA11y.flatConfigs.recommended,
  files: ['src/**/*.{js,jsx}'],
  settings: { 'jsx-a11y': { components: { Link: 'a', NavLink: 'a' } } },
  rules: {
    ...jsxA11y.flatConfigs.recommended.rules,
    // Router links render real anchors with href derived from to.
    'jsx-a11y/anchor-is-valid': ['error', { components: ['Link', 'NavLink'], specialLink: ['to'] }],
    // Named scrollable regions need keyboard focus for independent scrolling.
    'jsx-a11y/no-noninteractive-tabindex': ['error', { roles: ['tabpanel', 'region'] }],
  },
}];
