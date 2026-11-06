'use client';
import { z } from 'zod';
const errorSchema = z.object({
  error: z
    .object({ code: z.string(), message: z.string(), details: z.unknown().optional() })
    .optional(),
  detail: z.unknown().optional(),
});
const metric = z
  .object({
    metric: z.string(),
    value: z.union([z.number(), z.string(), z.null()]),
    unit: z.string(),
    status: z.string(),
  })
  .passthrough();
const report = z
  .object({
    domain: z.string(),
    window: z.object({
      as_of: z.string(),
      observation_start: z.string(),
      observation_end: z.string(),
    }),
    metrics: z.record(z.string(), metric),
    breakdowns: z.array(z.unknown()),
    trends: z.array(z.unknown()),
  })
  .passthrough();
const hybrid = z
  .object({
    question: z.string(),
    status: z.string(),
    as_of: z.string(),
    answer: z.string(),
    resolved_entities: z.array(z.unknown()),
    key_findings: z.array(z.unknown()),
    citations: z.array(z.unknown()),
    limitations: z.array(z.string()),
    evidence_graph: z.object({
      facts: z.array(
        z.object({
          kind: z.string(),
          fact_id: z.string(),
          verified: z.boolean(),
          value: z.record(z.string(), z.unknown()),
        }),
      ),
      missing: z.array(z.string()),
    }),
    usage: z.object({ llm_calls: z.literal(0), tool_calls: z.number() }),
    response_origin: z.literal('verified_structured_facts'),
  })
  .passthrough();
const proposal = z
  .object({
    id: z.uuid(),
    version: z.number(),
    digest: z.string().length(64),
    status: z.string(),
    material: z.object({}).passthrough(),
  })
  .passthrough();
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}
export async function responseData<T>(response: Response, endpoint: string): Promise<T> {
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const parsed = errorSchema.safeParse(data);
    const e = parsed.success ? parsed.data.error : undefined;
    const expiredConversation =
      endpoint === 'api/v1/hybrid/query' &&
      response.status === 404 &&
      z.object({ code: z.literal('conversation_not_found') }).safeParse(parsed.data?.detail)
        .success;
    if (response.status === 401 && typeof window !== 'undefined')
      window.dispatchEvent(new Event('opspilot:expired'));
    throw new ApiError(
      response.status,
      e?.code ?? (expiredConversation ? 'conversation_not_found' : 'request_failed'),
      e?.message ??
        (expiredConversation
          ? 'This conversation is no longer available. Start a new conversation to continue.'
          : response.status === 403
            ? 'You do not have permission for this operation.'
            : response.status === 422
              ? 'Please check the selected values.'
              : 'The request could not be completed.'),
      e?.details ?? (parsed.success ? parsed.data.detail : undefined),
    );
  }
  let schema: z.ZodType | undefined;
  if (
    /^api\/v1\/analytics\/(overview|procurement|suppliers(?:\/\d+)?|inventory|warehouses|fulfilment|finance|workforce|incidents)(\?|$)/.test(
      endpoint,
    )
  )
    schema = report;
  if (/^api\/v1\/workflows\/proposals\/[a-f0-9-]{36}$/.test(endpoint)) schema = proposal;
  if (endpoint === 'api/v1/hybrid/query') schema = hybrid;
  if (schema && !schema.safeParse(data).success)
    throw new ApiError(
      502,
      'invalid_response',
      'A service returned an unexpected response. Refresh or check system status.',
    );
  return data as T;
}
export async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch('/api/backend/' + path, { signal, cache: 'no-store' });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new ApiError(
      0,
      'connection_lost',
      'Connection lost. Check the local services and retry.',
    );
  }
  return responseData<T>(response, path);
}
export async function mutation<T>(
  path: string,
  body: unknown,
  csrf: string,
  key: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch('/api/backend/' + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, 'Idempotency-Key': key },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      0,
      'outcome_unknown',
      'Outcome not confirmed. Refresh the authoritative record or retry this same request; its operation reference is preserved.',
    );
  }
  return responseData<T>(response, path);
}
export async function operationKey(actor: string, path: string, body: unknown) {
  const bytes = new TextEncoder().encode(actor + '\n' + path + '\n' + JSON.stringify(body));
  const hashed = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
    .map((x) => x.toString(16).padStart(2, '0'))
    .join('');
  const ref = 'opspilot:operation:' + hashed;
  let key = sessionStorage.getItem(ref);
  if (!key) {
    key = crypto.randomUUID();
    sessionStorage.setItem(ref, key);
  }
  return key;
}
export function clearOperations() {
  for (const key of Object.keys(sessionStorage))
    if (key.startsWith('opspilot:')) sessionStorage.removeItem(key);
}
