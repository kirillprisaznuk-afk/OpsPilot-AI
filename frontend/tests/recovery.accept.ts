import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const api = process.env.OPSPILOT_API_URL ?? 'http://127.0.0.1:8001';

const project = path.resolve(process.cwd(), '..');
const evidence = path.resolve(
  process.env.OPSPILOT_BROWSER_EVIDENCE_DIR ?? '../.local-tools/stage6-browser',
);
const docker = (...args: string[]) =>
  execFileSync('docker', ['compose', ...args], {
    cwd: project,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 35000,
  }).trim();

test('temporary project API and PostgreSQL outages produce recoverable, truthful browser states', async ({
  page,
}) => {
  const active = docker(
    'exec',
    '-T',
    'db',
    'psql',
    '-U',
    'opspilot',
    '-d',
    'opspilot',
    '-tAc',
    "SELECT count(*) FROM pg_stat_activity WHERE datname LIKE 'opspilot_test_%'",
  );
  expect(active, 'finish all disposable PostgreSQL tests before outage acceptance').toBe('0');
  const { accounts } = JSON.parse(
    readFileSync(path.join(project, '.local-tools/stage5-demo/accounts.json'), 'utf8'),
  ) as {
    accounts: { username: string; password: string }[];
  };
  const user = accounts.find((entry) => entry.username === 'stage5.analyst');
  if (!user) throw new Error('Local analyst demo identity missing');
  await page.goto('/login');
  await page.getByRole('textbox', { name: 'Username', exact: true }).fill(user.username);
  await page.getByLabel('Password', { exact: true }).fill(user.password);
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(
    page.getByRole('heading', { name: 'Operations overview', exact: true }),
  ).toBeVisible();
  const session = await page.request.get('/api/session');
  expect(session.status()).toBe(200);
  const originalExpiry = (await session.json()).expires_at as string;
  await page.goto('/copilot');
  const prompt = page.getByRole('textbox', { name: 'Business question' });
  const ask = page.getByRole('button', { name: 'Ask OpsPilot', exact: true });
  const rank = 'Which suppliers have the weakest on-time delivery performance?';
  const followup =
    'Compare the first two suppliers from that ranking against their applicable contracts.';
  await prompt.fill(rank);
  await ask.click();
  await expect(page.getByRole('heading', { name: rank, exact: true })).toBeVisible();

  const waitForSession = () =>
    expect
      .poll(
        async () => {
          try {
            return (await page.request.get('/api/session', { timeout: 3500 })).status();
          } catch {
            return 0;
          }
        },
        { timeout: 60000 },
      )
      .toBe(200);

  const apiStart = performance.now();
  try {
    docker('stop', '-t', '3', 'api');
    await prompt.fill(followup);
    await ask.click();
    await expect(page.getByRole('main').getByRole('alert')).toContainText(
      'OpsPilot services are unavailable',
    );
    await expect(prompt).toHaveValue(followup);
    await expect(page.getByRole('heading', { name: rank, exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: followup, exact: true })).toHaveCount(0);
    await page.screenshot({ path: path.join(evidence, 'api-recovery-1440.png') });
  } finally {
    docker('start', 'api');
  }
  await waitForSession();
  const apiRecovery = performance.now() - apiStart;
  await ask.click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Start a new conversation');
  await page.getByRole('button', { name: 'New conversation', exact: true }).click();
  await prompt.fill(rank);
  await ask.click();
  await expect(page.getByRole('heading', { name: rank, exact: true })).toBeVisible();

  const dbStart = performance.now();
  try {
    docker('stop', '-t', '3', 'db');
    expect((await page.request.get(api + '/ready', { timeout: 12000 })).status()).toBe(503);
    expect(
      (await page.request.get(api + '/api/v1/knowledge/status', { timeout: 12000 })).status(),
    ).toBe(503);
    const blocked = await page.request.get('/api/backend/api/v1/workflows/tasks', {
      timeout: 18000,
    });
    expect(blocked.status()).toBe(503);
    expect(await blocked.json()).toMatchObject({ error: { code: 'auth_unavailable' } });
  } finally {
    docker('start', 'db');
  }
  await waitForSession();
  const dbRecovery = performance.now() - dbStart;
  const recovered = await page.request.get('/api/session');
  expect((await recovered.json()).expires_at).toBe(originalExpiry);
  expect((await page.request.get('/api/backend/api/v1/workflows/tasks')).status()).toBe(200);
  expect((await page.request.get('/api/backend/api/v1/knowledge/status')).status()).toBe(200);
  writeFileSync(
    path.join(evidence, 'recovery.json'),
    JSON.stringify(
      {
        api_stop_to_authenticated_ms: Math.round(apiRecovery),
        db_stop_to_authenticated_ms: Math.round(dbRecovery),
        workflow_and_knowledge_recovered: true,
        preserved_original_session_expiry: true,
        previous_answer_and_unsent_prompt_visible_during_api_failure: true,
        expired_conversation_requires_explicit_reset: true,
      },
      null,
      2,
    ),
  );
});
