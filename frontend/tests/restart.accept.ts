import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import type { Task } from '../src/lib/types';
const project = path.resolve(process.cwd(), '..'),
  output = path.resolve(
    process.env.OPSPILOT_BROWSER_EVIDENCE_DIR ?? '../.local-tools/stage6-browser',
  );
const docker = (...args: string[]) =>
  execFileSync('docker', args, {
    cwd: project,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();

test('scoped Compose restart preserves the browser session and committed workflow record', async ({
  page,
}) => {
  const active = docker(
    'compose',
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
  expect(active, 'finish disposable PostgreSQL tests before this explicit restart').toBe('0');
  const accounts = JSON.parse(
    readFileSync(path.join(project, '.local-tools/stage5-demo/accounts.json'), 'utf8'),
  ) as { accounts: { username: string; password: string }[] };
  const user = accounts.accounts.find((x) => x.username === 'stage5.operator');
  if (!user) throw new Error('Operator demo account missing');
  const fixture = JSON.parse(readFileSync(path.join(output, 'workflow.json'), 'utf8')) as {
    task_id: string;
  };
  await page.goto('/login');
  await page.getByRole('textbox', { name: 'Username' }).fill(user.username);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(
    page.getByRole('heading', { name: 'Operations overview', exact: true }),
  ).toBeVisible();
  const route = '/api/backend/api/v1/workflows/tasks/' + fixture.task_id;
  const original = await page.request.get(route);
  expect(original.status()).toBe(200);
  const before = (await original.json()) as Task;
  const identity = await page.request.get('/api/session');
  expect(identity.status()).toBe(200);
  const session = (await identity.json()) as { principal: { id: string }; expires_at: string };
  const started = performance.now();
  docker('compose', 'restart', 'db', 'api', 'frontend');
  await expect
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
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Operations overview', exact: true }),
  ).toBeVisible();
  const persisted = await page.request.get(route);
  expect(persisted.status()).toBe(200);
  expect(await persisted.json()).toEqual(before);
  const status = await page.request.get('/api/session');
  const after = (await status.json()) as { principal: { id: string }; expires_at: string };
  expect(after.principal.id).toBe(session.principal.id);
  expect(after.expires_at).toBe(session.expires_at);
  writeFileSync(
    path.join(output, 'restart.json'),
    JSON.stringify(
      {
        passed: true,
        services: ['db', 'api', 'frontend'],
        same_principal: true,
        same_original_session_expiry: true,
        task_id: before.id,
        task_version: before.version,
        elapsed_ms: performance.now() - started,
      },
      null,
      2,
    ),
  );
});
