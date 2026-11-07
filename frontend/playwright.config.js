import { defineConfig } from '@playwright/test';

// Own a separate server so tests cannot reuse another branch’s running frontend.
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  use: { baseURL: 'http://127.0.0.1:5174', browserName: 'chromium', channel: 'chromium', headless: true },
  webServer: { command: 'npm run dev -- --port 5174', url: 'http://127.0.0.1:5174/login', reuseExistingServer: false },
});
