import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 120000,
  expect: { timeout: 20000 },
  retries: 0,
  reporter: [
    ['list'],
    [
      'json',
      {
        outputFile:
          (process.env.OPSPILOT_BROWSER_EVIDENCE_DIR ?? '../.local-tools/stage6-browser') +
          '/results.json',
      },
    ],
  ],
  use: {
    baseURL: process.env.OPSPILOT_WEB_URL ?? 'http://127.0.0.1:3106',
    channel: process.env.OPSPILOT_BROWSER_CHANNEL || 'msedge',
    viewport: { width: 1440, height: 980 },
    trace: 'off',
    actionTimeout: 16000,
    navigationTimeout: 30000,
    video: 'off',
    screenshot: 'off',
  },
});
