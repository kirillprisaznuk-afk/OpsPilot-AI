import { expect, test, type Page } from '@playwright/test';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import AxeBuilder from '@axe-core/playwright';
import type {
  Proposal,
  Report,
  Task,
  Escalation,
  Receipt,
  Page as BackendPage,
} from '../src/lib/types';

const base = process.env.OPSPILOT_WEB_URL ?? 'http://127.0.0.1:3106';
const api = process.env.OPSPILOT_API_URL ?? 'http://127.0.0.1:8001';
const project = path.resolve(process.cwd(), '..');
const folder = path.resolve(
  process.env.OPSPILOT_BROWSER_EVIDENCE_DIR ?? '../.local-tools/stage6-browser',
);
mkdirSync(folder, { recursive: true });
const accounts = JSON.parse(
  readFileSync(path.join(project, '.local-tools/stage5-demo/accounts.json'), 'utf8'),
) as { accounts: { username: string; password: string }[] };
async function signIn(page: Page, role: string) {
  const account = accounts.accounts.find((x) => x.username === 'stage5.' + role);
  if (!account) throw new Error('Requested local demo identity is missing');
  await page.goto('/login');
  // Intentionally disable traces/screenshots/video; credentials never appear in reported artifacts.
  await page.getByRole('textbox', { name: 'Username', exact: true }).fill(account.username);
  await page.getByLabel('Password', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(
    page.getByRole('heading', { name: 'Operations overview', exact: true }),
  ).toBeVisible();
}
async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Open workspace' })).toBeVisible();
}
async function read<T>(page: Page, endpoint: string) {
  const r = await page.request.get('/api/backend/' + endpoint);
  expect(r.status(), endpoint).toBe(200);
  return (await r.json()) as T;
}
async function post(
  page: Page,
  endpoint: string,
  body: unknown,
  extra: Record<string, string> = {},
) {
  const s = await page.request.get('/api/session');
  expect(s.status()).toBe(200);
  const session = (await s.json()) as { csrf: string };
  return page.request.post('/api/backend/' + endpoint, {
    data: body,
    headers: {
      Origin: base,
      'X-CSRF-Token': session.csrf,
      'Idempotency-Key': randomUUID(),
      ...extra,
    },
  });
}
async function decide(page: Page, entry: string, confirm: string) {
  await page.getByRole('button', { name: entry, exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: confirm, exact: true })).toBeDisabled();
  expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  await dialog.getByRole('checkbox').press('Space');
  await expect(dialog.getByRole('checkbox')).toBeChecked();
  await dialog.getByRole('button', { name: confirm, exact: true }).press('Enter');
  await expect(dialog).toBeHidden();
}
const fmt = (value: number | string | null | undefined) =>
  new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 }).format(Number(value));
test('real dashboard, historical filters, supplier terms, knowledge citation and deterministic investigation', async ({
  page,
}) => {
  const start = performance.now();
  await signIn(page, 'analyst');
  const report = await read<Report>(page, 'api/v1/analytics/overview');
  await expect(page.locator('.kpi').first()).toContainText(
    fmt(report.metrics['procurement.on_time_rate'].value) + '%',
  );
  await expect(page.locator('.recharts-area').first()).toBeVisible();
  const dashboardMs = performance.now() - start;
  const initialDocumentMs = await page.evaluate(
    () => performance.getEntriesByType('navigation')[0]?.duration,
  );
  await page.getByLabel('Reporting period').selectOption('2026-04-01|2026-06-30');
  await expect(page.getByText(/01 Apr 2026.*30 Jun 2026/)).toBeVisible();
  const quarter = await read<Report>(
    page,
    'api/v1/analytics/overview?start_date=2026-04-01&end_date=2026-06-30&as_of=2026-06-30',
  );
  await expect(page.locator('.kpi').first()).toContainText(
    fmt(quarter.metrics['procurement.on_time_rate'].value) + '%',
  );
  await page.getByLabel('Reporting period').selectOption('2025-10-01|2026-09-30');
  const supplierStart = performance.now();
  await page
    .locator('.sidebar')
    .getByRole('link', { name: 'Supplier intelligence', exact: true })
    .click();
  await expect(page.getByRole('heading', { name: 'Performance ranking' })).toBeVisible();
  const supplierNavigationMs = performance.now() - supplierStart;
  const tableStart = performance.now();
  await page.getByLabel('Search suppliers').fill('Amberwick Office');
  await expect(page.getByRole('link', { name: /Amberwick Office Works/ }).first()).toBeVisible();
  const tableSearchMs = performance.now() - tableStart;
  await page
    .getByRole('link', { name: /Amberwick Office Works/ })
    .first()
    .click();
  await expect(
    page.getByRole('heading', { name: 'Amberwick Office Works', exact: true }),
  ).toBeVisible();
  const supplier = await read<Report>(page, 'api/v1/analytics/suppliers/1');
  await expect(page.locator('.kpi').first()).toContainText(
    fmt(supplier.metrics.on_time_rate.value) + '%',
  );
  await expect(page.getByText('NS-CON-001', { exact: true })).toBeVisible();
  await page.screenshot({ path: path.join(folder, 'supplier-1440.png') });
  await page.getByRole('link', { name: /Agreement.*Amberwick Office Works/ }).click();
  await expect(page).toHaveURL(/\/knowledge\/\d+$/);
  await expect(page.getByText('Source verified', { exact: true })).toBeVisible();
  await page.locator('.sidebar').getByRole('link', { name: 'Knowledge base', exact: true }).click();
  await page.getByLabel('Search corporate knowledge').fill('Procurement procedure');
  await page.getByLabel('Search method').selectOption('keyword');
  const searchStart = performance.now();
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  const citation = page
    .getByRole('link', { name: 'Inspect verified citation', exact: true })
    .first();
  await expect(citation).toBeVisible();
  const searchMs = performance.now() - searchStart;
  await page.screenshot({ path: path.join(folder, 'knowledge-search-1440.png') });
  await citation.click();
  await expect(page.getByText('Source verified', { exact: true })).toBeVisible();
  expect(page.url()).toMatch(/citations\/kc_[a-f0-9]{64}$/);
  await page.screenshot({ path: path.join(folder, 'citation-1440.png') });
  await page.getByRole('link', { name: 'Open complete registered source' }).click();
  await expect(page).toHaveURL(/knowledge\/\d+\?version=\d+/);
  await expect(page.getByText('Source verified', { exact: true })).toBeVisible();
  await page.locator('.sidebar').getByRole('link', { name: 'Investigations', exact: true }).click();
  await page
    .getByLabel('Business question', { exact: true })
    .fill(
      'Compare Supplier 1 delivery performance against its contractual SLA and escalation policy.',
    );
  const inquiryStart = performance.now();
  await page.getByRole('button', { name: 'Run investigation', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Registered source evidence' })).toBeVisible();
  const inquiryMs = performance.now() - inquiryStart;
  await expect(page.getByText(/4 read-only tool calls · 0 LLM calls/)).toBeVisible();
  await expect(page.locator('.findings')).toContainText('33.33%');
  await page.screenshot({ path: path.join(folder, 'investigation-1440.png') });
  await page
    .locator('.sidebar')
    .getByRole('link', { name: /OpsPilot Copilot/ })
    .click();
  await expect(page).toHaveURL(/\/copilot$/);
  await expect(
    page.getByRole('heading', { name: 'Your operations, in conversation.', exact: true }),
  ).toBeVisible();
  await page
    .getByLabel('Business question', { exact: true })
    .fill('Which suppliers have the weakest on-time delivery performance?');
  await page.getByRole('button', { name: 'Ask OpsPilot', exact: true }).click();
  await expect(page.getByText(/0 LLM calls · Verified structured facts/)).toBeVisible();
  await page
    .getByLabel('Business question', { exact: true })
    .fill('Compare the first two suppliers from that ranking against their applicable contracts.');
  await page.getByRole('button', { name: 'Ask OpsPilot', exact: true }).click();
  await expect(page.getByText(/1 previous question in this conversation/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Registered source evidence' })).toBeVisible();
  await page.screenshot({ path: path.join(folder, 'copilot-1440.png') });
  await page.getByRole('button', { name: 'New conversation', exact: true }).click();
  await expect(page.getByText(/previous question in this conversation/)).toHaveCount(0);
  const cdp = await page.context().newCDPSession(page);
  const heap = await cdp.send('Runtime.getHeapUsage');
  await cdp.detach();
  writeFileSync(
    path.join(folder, 'timing.json'),
    JSON.stringify(
      {
        initialDocumentMs,
        dashboardMs,
        supplierNavigationMs,
        tableSearchMs,
        searchMs,
        inquiryMs,
        browserHeapUsedBytes: heap.usedSize,
        browserHeapAllocatedBytes: heap.totalSize,
      },
      null,
      2,
    ),
  );
});
test('real operator → distinct reviewer → execute, receipt, audit, safe replay and role denial', async ({
  page,
}) => {
  await signIn(page, 'operator');
  await page.goto('/suppliers/1');
  await page.getByRole('link', { name: 'Investigate supplier', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Follow the evidence.', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Run investigation', exact: true }).click();
  await page.getByRole('link', { name: 'Prepare internal review task', exact: true }).click();
  const title = process.env.OPSPILOT_SHOWCASE ?? 'Browser supplier review ' + Date.now();
  const text = 'Internal review. <img src=x onerror="window.__opspilotXss=1">';
  await page.getByLabel('Title', { exact: true }).fill(title);
  await page.getByLabel('Task description', { exact: true }).fill(text);
  await page
    .getByLabel('Why is this action needed?', { exact: true })
    .fill('Explicit synthetic browser acceptance for the verified supplier performance gap.');
  await page.getByRole('button', { name: 'Verify supporting evidence', exact: true }).click();
  await expect(page.getByText(/Verified investigation captured/)).toBeVisible();
  await page.getByRole('button', { name: 'Review proposal', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Save immutable draft', exact: true }).click();
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  const proposalId = page.url().split('/').pop()!;
  const path = 'api/v1/workflows/proposals/' + proposalId;
  const draft = await read<Proposal>(page, path);
  expect(draft.status).toBe('DRAFT');
  await decide(page, 'Submit for human review', 'Confirm submit');
  expect((await read<Proposal>(page, path)).status).toBe('PENDING_REVIEW');
  await expect(page.getByRole('button', { name: 'Review & approve' })).toHaveCount(0);
  const body = { proposal_version: draft.version, digest: draft.digest, reason: null };
  expect((await post(page, path + '/approve', body)).status()).toBe(403);
  await signOut(page);
  await signIn(page, 'reviewer');
  await page
    .locator('.sidebar')
    .getByRole('link', { name: /Approval inbox/ })
    .click();
  await expect(page.getByRole('link', { name: new RegExp(title) })).toBeVisible();
  await page.screenshot({ path: pathJoin(folder, 'approval-inbox-1440.png') });
  await page.getByRole('link', { name: new RegExp(title) }).click();
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  await expect(page.getByText(/Verified source snapshot/)).toBeVisible();
  await page.screenshot({ path: pathJoin(folder, 'approval-1440.png') });
  await decide(page, 'Review & approve', 'Confirm approve');
  const approved = await read<Proposal>(page, path);
  expect(approved.status).toBe('APPROVED');
  expect((approved.approvals[0] as { actor_id: string }).actor_id).not.toBe(approved.proposer_id);
  await expect(page.getByRole('button', { name: 'Execute approved action' })).toHaveCount(0);
  await signOut(page);
  await signIn(page, 'operator');
  await page.goto('/proposals/' + proposalId);
  const keys: string[] = [];
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().endsWith('/' + proposalId + '/execute'))
      keys.push(r.headers()['idempotency-key']);
  });
  let committedBeforeResponseLoss = false;
  await page.route(
    '**/' + proposalId + '/execute',
    async (route) => {
      const response = await route.fetch();
      committedBeforeResponseLoss = response.ok();
      await route.abort('connectionreset');
    },
    { times: 1 },
  );
  await decide(page, 'Execute approved action', 'Confirm execution');
  expect(committedBeforeResponseLoss).toBe(true);
  await expect(page.getByText(/Outcome not confirmed/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Committed execution receipt' })).toBeVisible();
  const completed = await read<Proposal>(page, path);
  expect(completed.status).toBe('COMPLETED');
  const receipt = completed.executions[0] as {
    id: string;
    result: { objects: { task_id: string } };
  };
  await page.locator('#receipt').screenshot({ path: pathJoin(folder, 'receipt-1440.png') });
  await page.locator('#receipt').scrollIntoViewIfNeeded();
  await page.screenshot({ path: pathJoin(folder, 'receipt-view-1440.png') });
  await decide(page, 'Verify committed receipt', 'Confirm execution');
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[0]).toBe(keys[1]);
  const replay = await read<Proposal>(page, path);
  expect(replay.executions).toHaveLength(1);
  expect(replay.executions[0]).toMatchObject({ id: receipt.id });
  await page.getByRole('link', { name: 'Open affected task', exact: true }).click();
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  await expect(page.getByText(text, { exact: true })).toBeVisible();
  expect(await page.evaluate(() => Reflect.get(window, '__opspilotXss'))).toBeUndefined();
  await page.reload();
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  const persisted = await read<Task>(
    page,
    'api/v1/workflows/tasks/' + receipt.result.objects.task_id,
  );
  expect(persisted.title).toBe(title);
  const list = await read<BackendPage<Task>>(
    page,
    'api/v1/workflows/tasks?search=' + encodeURIComponent(title),
  );
  expect(list.total).toBe(1);
  await page.getByRole('link', { name: 'Inspect full audit', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Activity ledger', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Execution.*completed/i })).toBeVisible();
  await page.screenshot({ path: pathJoin(folder, 'workflow-audit-1440.png') });
  await page.locator('.sidebar').getByRole('link', { name: 'Workflow tasks', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Operational work queue' })).toBeVisible();
  await page.getByPlaceholder('Search tasks…').fill(title);
  await expect(
    page.locator('a[href="/tasks/' + persisted.id + '"]').filter({ hasText: title }),
  ).toBeVisible();
  await page.screenshot({ path: pathJoin(folder, 'workflow-tasks-1440.png') });
  await signOut(page);
  await signIn(page, 'viewer');
  await page.goto('/proposals/' + proposalId);
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Execute approved action' })).toHaveCount(0);
  expect((await post(page, path + '/execute', body)).status()).toBe(403);
  await signOut(page);
  await signIn(page, 'outsider');
  await page.goto('/proposals/' + proposalId);
  await expect(page.getByRole('main').getByRole('alert')).toContainText(/scope|permission/i);
  expect((await page.request.get('/api/backend/' + path)).status()).toBe(403);
  writeFileSync(
    pathJoin(folder, 'workflow.json'),
    JSON.stringify(
      {
        proposal_id: proposalId,
        receipt_id: receipt.id,
        task_id: persisted.id,
        title,
        distinct_reviewer: true,
        one_effect: true,
        same_operation_key: true,
        first_execution_response_lost: true,
        xss_inert: true,
      },
      null,
      2,
    ),
  );
});
const pathJoin = path.join;

async function saveDraft(page: Page) {
  await page.getByRole('button', { name: 'Review proposal', exact: true }).click();
  await page.getByRole('button', { name: 'Save immutable draft', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Submit for human review', exact: true }),
  ).toBeVisible();
  return page.url().split('/').pop()!;
}
const reviewed = (p: Proposal) => ({ proposal_version: p.version, digest: p.digest, reason: null });
const pathOf = (id: string) => 'api/v1/workflows/proposals/' + id;
function newTask(title: string, expiry?: string) {
  return {
    department_id: 1,
    reason: 'Explicit synthetic Stage 6 acceptance fixture.',
    ...(expiry ? { expires_at: expiry } : {}),
    action: {
      type: 'CREATE_WORKFLOW_TASK',
      title,
      description: 'Synthetic internal browser acceptance review.',
      priority: 'normal',
      due_at: new Date(Date.now() + 86400000 * 2).toISOString(),
      subject: { kind: 'supplier', entity_id: 1 },
    },
  };
}
async function fixtureDraft(page: Page, body: unknown) {
  const r = await post(page, 'api/v1/workflows/proposals', body);
  expect(r.status()).toBe(200);
  return (await r.json()) as Proposal;
}
async function uiComplete(operator: Page, reviewer: Page, id: string) {
  await decide(operator, 'Submit for human review', 'Confirm submit');
  await reviewer.goto('/proposals/' + id);
  await decide(reviewer, 'Review & approve', 'Confirm approve');
  await operator.reload();
  await decide(operator, 'Execute approved action', 'Confirm execution');
  const p = await read<Proposal>(operator, pathOf(id));
  expect(p.status).toBe('COMPLETED');
  return p.executions[0] as Receipt;
}

test('real task change, evidence-bound escalation and stale/rejected/expired guards', async ({
  page,
  browser,
}) => {
  test.setTimeout(180000);
  await signIn(page, 'operator');
  const reviewer = await browser.newPage({ baseURL: base });
  try {
    await signIn(reviewer, 'reviewer');
    const created = await fixtureDraft(page, newTask('Stage 6 change fixture ' + Date.now()));
    const createdPath = pathOf(created.id);
    expect((await post(page, createdPath + '/submit', reviewed(created))).status()).toBe(200);
    expect((await post(reviewer, createdPath + '/approve', reviewed(created))).status()).toBe(200);
    const applied = await post(page, createdPath + '/execute', reviewed(created));
    expect(applied.status()).toBe(200);
    const result = (await applied.json()) as { result: { objects: { task_id: string } } };
    const taskId = result.result.objects.task_id;
    const stale = await fixtureDraft(page, {
      department_id: 1,
      reason: 'Competing expected-version fixture.',
      action: {
        type: 'UPDATE_WORKFLOW_TASK_PRIORITY',
        task_id: taskId,
        expected_version: 1,
        priority: 'high',
      },
    });
    expect((await post(page, pathOf(stale.id) + '/submit', reviewed(stale))).status()).toBe(200);
    expect((await post(reviewer, pathOf(stale.id) + '/approve', reviewed(stale))).status()).toBe(
      200,
    );
    await page.goto('/tasks/' + taskId);
    await page.getByRole('link', { name: 'Change task priority', exact: true }).click();
    await page
      .getByRole('combobox', { name: 'Proposed priority', exact: true })
      .selectOption('urgent');
    await page
      .getByLabel('Why is this action needed?', { exact: true })
      .fill('Prioritize internal review of the verified supplier observation.');
    const update = await saveDraft(page);
    await uiComplete(page, reviewer, update);
    const updated = await read<Task>(page, 'api/v1/workflows/tasks/' + taskId);
    expect(updated.version).toBe(2);
    expect(updated.priority).toBe('urgent');
    await page.goto('/proposals/' + stale.id);
    await expect(
      page.getByText('Changed · Fresh revision required', { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Execute approved action' })).toHaveCount(0);
    const staleReply = await post(page, pathOf(stale.id) + '/execute', reviewed(stale));
    expect(staleReply.status()).toBe(409);
    expect((await staleReply.json()).error.code).toBe('stale_target');
    expect((await read<Task>(page, 'api/v1/workflows/tasks/' + taskId)).priority).toBe('urgent');
    await page.getByRole('link', { name: 'Prepare fresh revision', exact: true }).click();
    await expect(page.getByText(/Its approvals do not carry over/)).toBeVisible();
    await page.getByRole('button', { name: 'Review proposal', exact: true }).click();
    await page.getByRole('button', { name: 'Save fresh revision', exact: true }).click();
    await expect(
      page.getByRole('button', { name: 'Submit for human review', exact: true }),
    ).toBeVisible();
    const revision = await read<Proposal>(page, pathOf(page.url().split('/').pop()!));
    expect(revision.version).toBe(2);
    expect(revision.approvals).toEqual([]);
    const escalationTitle = 'Stage 6 verified escalation ' + Date.now();
    await page.goto(
      '/proposals/new?action=CREATE_INTERNAL_ESCALATION&subject_kind=supplier&subject_id=1&related_task_id=' +
        taskId,
    );
    await page.getByLabel('Title', { exact: true }).fill(escalationTitle);
    await page
      .getByLabel('Escalation reason', { exact: true })
      .fill('Review a verified below-target supplier observation internally.');
    await page
      .getByLabel('Why is this action needed?', { exact: true })
      .fill('Escalate the internal review to the owning department.');
    await page.getByRole('button', { name: 'Verify supporting evidence', exact: true }).click();
    await expect(page.getByText(/Verified investigation captured/)).toBeVisible();
    const createEscalation = await saveDraft(page),
      opened = await uiComplete(page, reviewer, createEscalation);
    const escalationId = String((opened.result.objects as Record<string, unknown>).escalation_id);
    const initial = await read<Escalation>(page, 'api/v1/workflows/escalations/' + escalationId);
    expect(initial.status).toBe('open');
    expect(initial.task_id).toBe(taskId);
    await page.getByRole('link', { name: 'Open affected escalation', exact: true }).click();
    await page.getByRole('link', { name: 'Close internal escalation', exact: true }).click();
    await page
      .getByLabel('Internal resolution', { exact: true })
      .fill('The internal review was completed; no external action was taken.');
    await page
      .getByLabel('Why is this action needed?', { exact: true })
      .fill('Record the reviewed internal outcome.');
    const close = await saveDraft(page);
    await uiComplete(page, reviewer, close);
    expect(
      (await read<Escalation>(page, 'api/v1/workflows/escalations/' + escalationId)).status,
    ).toBe('closed');
    const reject = await fixtureDraft(page, newTask('Stage 6 explicitly rejected ' + Date.now()));
    expect((await post(page, pathOf(reject.id) + '/submit', reviewed(reject))).status()).toBe(200);
    await reviewer.goto('/proposals/' + reject.id);
    await decide(reviewer, 'Reject proposal', 'Confirm reject');
    expect((await read<Proposal>(page, pathOf(reject.id))).status).toBe('REJECTED');
    expect((await post(page, pathOf(reject.id) + '/execute', reviewed(reject))).status()).toBe(409);
    const expired = await fixtureDraft(
      page,
      newTask('Stage 6 expiry ' + Date.now(), new Date(Date.now() + 6000).toISOString()),
    );
    expect((await post(page, pathOf(expired.id) + '/submit', reviewed(expired))).status()).toBe(
      200,
    );
    expect(
      (await post(reviewer, pathOf(expired.id) + '/approve', reviewed(expired))).status(),
    ).toBe(200);
    await expect
      .poll(async () => (await read<Proposal>(page, pathOf(expired.id))).effective_status, {
        timeout: 12000,
      })
      .toBe('EXPIRED');
    await page.goto('/proposals/' + expired.id);
    await expect(page.getByText('Expired', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Execute approved action' })).toHaveCount(0);
    expect((await post(page, pathOf(expired.id) + '/execute', reviewed(expired))).status()).toBe(
      409,
    );
    writeFileSync(
      pathJoin(folder, 'extended-workflow.json'),
      JSON.stringify(
        {
          task_id: taskId,
          update_proposal_id: update,
          escalation_id: escalationId,
          stale_proposal_id: stale.id,
          revision_proposal_id: revision.id,
          rejected_proposal_id: reject.id,
          expired_proposal_id: expired.id,
        },
        null,
        2,
      ),
    );
  } finally {
    await reviewer.close();
  }
});

test('historical inventory, financial exposure, customer promises and separate workforce counts', async ({
  page,
}) => {
  await signIn(page, 'viewer');
  await page.goto('/analytics/inventory');
  await page.getByRole('combobox', { name: 'Warehouse', exact: true }).selectOption('3');
  await page.getByLabel('Search registered products', { exact: true }).fill('44');
  await page.getByRole('combobox', { name: 'Product', exact: true }).selectOption('44');
  const inventory = await read<Report>(
    page,
    'api/v1/analytics/inventory?product_id=44&warehouse_id=3',
  );
  await expect(page.locator('.kpi').first()).toContainText(
    fmt(inventory.metrics.stock_on_hand.value) + ' units',
  );
  await page.screenshot({ path: pathJoin(folder, 'inventory-1440.png') });
  await page.goto('/analytics/finance');
  const finance = await read<Report>(page, 'api/v1/analytics/finance');
  const expected = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(
    Number(finance.metrics.invoice_value.value),
  );
  await expect(page.locator('.kpi').first()).toContainText(expected);
  await expect(page.getByText(/Unrecorded loss and profit remain unknown/)).toBeVisible();
  await page.goto('/analytics/fulfilment');
  await expect(page.getByText(/Customer dispatch promises and observed fulfilment/)).toBeVisible();
  const sales = await read<Report>(page, 'api/v1/analytics/fulfilment');
  await expect(page.locator('.kpi').first()).toContainText(fmt(sales.metrics.sales_orders.value));
  await expect(page.getByRole('heading', { name: 'Sales orders', exact: true })).toBeVisible();
  await page.goto('/analytics/workforce');
  const workforce = await read<Report>(page, 'api/v1/analytics/workforce');
  await expect(page.locator('.kpi').first()).toContainText(fmt(workforce.metrics.open_tasks.value));
  await expect(page.getByText(/Original seeded operational work/)).toBeVisible();
  await page.goto('/status');
  await expect(page.getByText(/44 documents · 44 versions · 44 chunks/)).toBeVisible();
});

test('authenticated gateway rejects anonymous, forged origins, missing CSRF and local model mode', async ({
  page,
}) => {
  expect((await page.request.get('/api/backend/api/v1/analytics/overview')).status()).toBe(401);
  await page.goto('/tasks');
  await expect(page.getByRole('button', { name: 'Open workspace' })).toBeVisible();
  expect(
    (
      await page.request.post('/api/session', {
        data: { username: 'not-a-user', password: 'not-a-real-password' },
        headers: { Origin: 'https://example.invalid' },
      })
    ).status(),
  ).toBe(403);
  await signIn(page, 'viewer');
  const session = await page.request.get('/api/session');
  expect(session.status()).toBe(200);
  expect(await session.json()).not.toHaveProperty('access_token');
  expect((await page.context().cookies()).find((x) => x.name === 'opspilot_session')).toMatchObject(
    { httpOnly: true, sameSite: 'Strict' },
  );
  expect(await page.evaluate(() => document.cookie)).not.toContain('opspilot_session');
  const revokedCookie = (await page.context().cookies()).find((c) => c.name === 'opspilot_session');
  const noCsrf = await page.request.post('/api/backend/api/v1/workflows/proposals', {
    data: {},
    headers: { Origin: base },
  });
  expect(noCsrf.status()).toBe(403);
  const badMode = await post(page, 'api/v1/hybrid/query', {
    question: 'supplier 1',
    mode: 'HYBRID_LOCAL',
  });
  expect(badMode.status()).toBe(422);
  expect((await post(page, 'api/v1/agent/query', { question: 'test' })).status()).toBe(404);
  const badConversation = await post(page, 'api/v1/hybrid/query', {
    question: 'Compare Supplier 1 against its agreement.',
    mode: 'DETERMINISTIC',
    conversation_id: '0'.repeat(32),
  });
  expect(badConversation.status()).toBe(403);
  await signOut(page);
  expect((await page.request.get('/api/backend/api/v1/workflows/tasks')).status()).toBe(401);
  if (!revokedCookie) throw new Error('Missing opaque session cookie');
  await page.context().addCookies([revokedCookie]);
  expect((await page.request.get('/api/session')).status()).toBe(401);
});
test('responsive dashboard and keyboard/accessibility measurements', async ({ page }) => {
  await signIn(page, 'viewer');
  await expect(page.getByText('69.92%', { exact: true })).toBeVisible();
  const sizes = [];
  const desktopAxe = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const findings = (result: typeof desktopAxe) =>
    result.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      nodes: v.nodes.map((n) => ({ target: n.target, summary: n.failureSummary })),
    }));
  writeFileSync(
    path.join(folder, 'accessibility-desktop.json'),
    JSON.stringify(findings(desktopAxe), null, 2),
  );
  expect(findings(desktopAxe), 'desktop dashboard accessibility').toEqual([]);
  for (const width of [1440, 1280, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 980 });
    await expect(
      page.getByRole('heading', { name: 'Operations overview', exact: true }),
    ).toBeVisible();
    const scroll = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scroll, `page overflow at ${width}`).toBeLessThanOrEqual(width);
    sizes.push({ width, scrollWidth: scroll });
    await page.mouse.move(1, 1);
    await page.screenshot({ path: pathJoin(folder, 'dashboard-' + width + '.png') });
  }
  await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  await expect(
    page.locator('.sidebar').getByRole('link', { name: 'Workflow tasks', exact: true }),
  ).toBeVisible();
  await page.locator('.sidebar').getByRole('link', { name: 'Workflow tasks', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Workflow tasks', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Operational work queue' })).toBeVisible();
  await expect(page.locator('table tbody tr').first()).toBeVisible();
  await page.screenshot({ path: pathJoin(folder, 'tasks-390.png') });
  const axe = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  writeFileSync(
    pathJoin(folder, 'accessibility.json'),
    JSON.stringify(
      {
        sizes,
        desktop_dashboard_violations: desktopAxe.violations.length,
        tested: ['loaded desktop dashboard', 'loaded mobile task list'],
        violations: findings(axe),
      },
      null,
      2,
    ),
  );
  expect(axe.violations.map((v) => v.id)).toEqual([]);
});

test('a verified Copilot conversation cannot be reused outside its exact browser session', async ({
  page,
  browser,
  request,
}) => {
  await signIn(page, 'analyst');
  const question = {
    mode: 'DETERMINISTIC',
    as_of: '2026-09-30',
    question: 'Which suppliers have the weakest on-time delivery performance?',
  };
  const rank = await post(page, 'api/v1/hybrid/query', question);
  expect(rank.status()).toBe(200);
  const { conversation_id: handle } = (await rank.json()) as { conversation_id: string };
  const followup = {
    ...question,
    question:
      'Compare the first two suppliers from that ranking against their applicable contracts.',
  };
  const other = await browser.newPage({ baseURL: base });
  try {
    await signIn(other, 'analyst');
    expect(
      (await post(other, 'api/v1/hybrid/query', { ...followup, conversation_id: handle })).status(),
    ).toBe(403);
    const direct = await request.post(api + '/api/v1/hybrid/query', {
      data: { ...followup, conversation_id: handle.split('.')[0] },
    });
    expect(direct.status()).toBe(404);
    expect(await direct.json()).toMatchObject({ detail: { code: 'conversation_not_found' } });
    const authorized = await post(page, 'api/v1/hybrid/query', {
      ...followup,
      conversation_id: handle,
    });
    expect(authorized.status()).toBe(200);
    expect(await authorized.json()).toMatchObject({ status: 'completed', usage: { llm_calls: 0 } });
    expect(
      (
        await page.request.post('/api/session', {
          headers: { Origin: base, 'Content-Type': 'application/json-other' },
          data: {},
        })
      ).status(),
    ).toBe(415);
  } finally {
    await other.close();
  }
});

test('finance drill-down, historical scope and remaining navigation load real views', async ({
  page,
}) => {
  await page.goto('/login');
  await expect(page.getByRole('button', { name: 'Open workspace' })).toBeVisible();
  await page.screenshot({ path: path.join(folder, 'login-1440.png') });
  await signIn(page, 'admin');
  const navigation = page.locator('.sidebar');
  await navigation.getByRole('link', { name: 'Business intelligence', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Procurement intelligence' })).toBeVisible();
  await page
    .getByRole('combobox', { name: 'Reporting period' })
    .selectOption('2026-08-01|2026-08-31');
  await expect(page.getByText('31 Aug 2026', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Auditable measurements' })).toBeVisible();
  await page.screenshot({ path: path.join(folder, 'procurement-1440.png') });
  await page.getByRole('link', { name: 'Inventory & warehouses', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inventory & warehouses' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Reporting period' })).toHaveValue(
    '2026-08-01|2026-08-31',
  );
  await page.getByRole('link', { name: 'fulfilment', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Customer fulfilment' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Sales orders' })).toBeVisible();
  await page.screenshot({ path: path.join(folder, 'fulfilment-1440.png') });
  await page.getByRole('link', { name: 'Financial', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Financial intelligence' })).toBeVisible();
  await expect(page.getByText('View exact comparison values', { exact: true })).toBeVisible();
  await page.screenshot({ path: path.join(folder, 'finance-overview-1440.png') });
  await page.getByText('View exact comparison values', { exact: true }).click();
  const comparison = page
    .locator('details.chart-data')
    .filter({ hasText: 'View exact comparison values' });
  const supplier = comparison.getByRole('link').first();
  await expect(supplier).toHaveAttribute('href', /^\/suppliers\/[1-9][0-9]*$/);
  await expect(comparison.locator('tbody tr').first()).toContainText('£');
  await comparison.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(folder, 'finance-1440.png') });
  await supplier.click();
  await expect(page).toHaveURL(/\/suppliers\/[1-9][0-9]*$/);
  await expect(page.getByRole('heading', { name: 'Agreement & target' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Reporting period' })).toHaveValue(
    '2026-08-01|2026-08-31',
  );

  const views = [
    ['Knowledge base', 'Registered library', 'knowledge'],
    ['Internal escalations', 'Internal review queue', 'escalations'],
    ['Approval inbox', 'Awaiting deliberate review', 'approvals'],
    ['Action proposals', 'Action proposals', 'proposals'],
    ['Audit trail', 'Activity ledger', 'audit'],
    ['System status', 'Service availability', 'status'],
    ['Account & access', 'Account & session', 'settings'],
  ];
  for (const [link, loaded, name] of views) {
    await navigation.getByRole('link', { name: link, exact: true }).click();
    await expect(page.getByRole('heading', { name: loaded, exact: true })).toBeVisible();
    if (name === 'settings')
      await expect(page.getByRole('button', { name: 'Manage role' }).first()).toBeVisible();
    await page.screenshot({ path: path.join(folder, name + '-1440.png') });
  }
  const audit = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const violations = audit.violations.map((violation) => ({
    id: violation.id,
    nodes: violation.nodes.map((node) => ({ target: node.target, summary: node.failureSummary })),
  }));
  writeFileSync(
    path.join(folder, 'accessibility-settings.json'),
    JSON.stringify(violations, null, 2),
  );
  expect(violations).toEqual([]);
});
