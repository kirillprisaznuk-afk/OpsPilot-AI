import { test } from 'node:test';
import assert from 'node:assert/strict';
import { allowedEndpoint } from '../src/lib/proxy-policy';
import { amount, date } from '../src/lib/format';

test('browser gateway grants only the named routes and methods, without traversal or provider inference', () => {
  const proposal = 'api/v1/workflows/proposals/12345678-1234-1234-1234-123456789abc';
  assert.ok(allowedEndpoint('GET', proposal));
  assert.ok(allowedEndpoint('POST', proposal + '/approve'));
  assert.ok(allowedEndpoint('GET', 'api/v1/knowledge/citations/kc_' + 'a'.repeat(64)));
  for (const [method, url] of [
    ['DELETE', proposal],
    ['POST', 'api/v1/agent/query'],
    ['POST', 'api/v1/auth/login'],
    ['GET', 'api/v1/workspace/../auth/me'],
    ['GET', 'api/v1/knowledge/documents/%2e%2e'],
    ['GET', 'http://example.invalid/api/v1/demo/summary'],
    ['GET', 'api/v1/knowledge/documents/javascript:alert(1)'],
  ])
    assert.equal(allowedEndpoint(method, url), false, method + ' ' + url);
});
test('report formatting preserves missing versus recorded zero, GBP, and percentage-point units', () => {
  assert.equal(amount(null, 'GBP'), 'Not available');
  assert.equal(amount('', 'GBP'), 'Not available');
  assert.equal(amount('0.00', 'GBP'), '£0.00');
  assert.equal(amount('3061430.69', 'GBP'), '£3,061,430.69');
  assert.equal(amount('-61.67', 'percentage_points'), '-61.67 pp');
  assert.equal(amount('33.33', 'percent'), '33.33%');
  assert.equal(date('2026-09-30'), '30 Sept 2026');
});
