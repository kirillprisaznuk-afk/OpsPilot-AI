import { defineConfig } from '@playwright/test';
import config from './playwright.config';
export default defineConfig({
  ...config,
  testMatch: ['**/restart.accept.ts', '**/recovery.accept.ts'],
  timeout: 180000,
  reporter: [
    ['list'],
    [
      'json',
      {
        outputFile:
          (process.env.OPSPILOT_BROWSER_EVIDENCE_DIR ?? '../.local-tools/stage6-browser') +
          '/restart-results.json',
      },
    ],
  ],
});
