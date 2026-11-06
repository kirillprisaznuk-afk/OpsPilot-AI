import 'server-only';
import {
  createCipheriv,
  createDecipheriv,
  createHash,
  createHmac,
  randomBytes,
  timingSafeEqual,
} from 'node:crypto';
import { mkdir, readFile, writeFile, unlink } from 'node:fs/promises';
import path from 'node:path';
import { cookies } from 'next/headers';
import { z } from 'zod';

const directory = process.env.FRONTEND_SESSION_DIR ?? path.join(process.cwd(), '.runtime');
export const cookieName = 'opspilot_session';
export const backend = process.env.BACKEND_URL ?? 'http://127.0.0.1:8001';
const appOrigin = process.env.APP_ORIGIN ?? 'http://127.0.0.1:3106';
const sessionSchema = z.object({
  token: z.string().min(40).max(100),
  csrf: z.string(),
  expires: z.string().datetime({ offset: true }),
});
const principalSchema = z.object({
  id: z.uuid(),
  username: z.string(),
  active: z.literal(true),
  is_human: z.literal(true),
  authz_version: z.number().int(),
  employee_id: z.number().int().nullable(),
  created_at: z.string(),
  roles: z.array(z.object({ role_code: z.string(), department_id: z.number().int().nullable() })),
});
type Session = z.infer<typeof sessionSchema>;

export class GatewayError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function key() {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const file = path.join(directory, 'key');
  try {
    await writeFile(file, randomBytes(32), { flag: 'wx', mode: 0o600 });
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== 'EEXIST') throw e;
  }
  const value = await readFile(file);
  if (value.length !== 32) throw new Error('Invalid session encryption key');
  return value;
}
export async function signConversation(rawId: string, csrf: string) {
  if (!/^[a-f0-9]{32}$/.test(rawId))
    throw new GatewayError(
      502,
      'invalid_conversation',
      'Invalid conversation response. Start a new investigation.',
    );
  return (
    rawId +
    '.' +
    createHmac('sha256', await key())
      .update('conversation-v1\n' + csrf + '\n' + rawId)
      .digest('hex')
  );
}
export async function verifyConversation(handle: unknown, csrf: string) {
  if (typeof handle !== 'string' || !/^[a-f0-9]{32}\.[a-f0-9]{64}$/.test(handle))
    throw new GatewayError(
      403,
      'conversation_scope',
      'Start a new conversation in this signed-in session.',
    );
  const rawId = handle.slice(0, 32),
    expected = await signConversation(rawId, csrf);
  if (!timingSafeEqual(Buffer.from(handle), Buffer.from(expected)))
    throw new GatewayError(
      403,
      'conversation_scope',
      'This conversation does not belong to the current session.',
    );
  return rawId;
}
function filename(sid: string) {
  if (!/^[A-Za-z0-9_-]{43}$/.test(sid))
    throw new GatewayError(401, 'session_required', 'Please sign in again.');
  return path.join(directory, createHash('sha256').update(sid).digest('hex') + '.session');
}
export async function createSession(value: Session) {
  const sid = randomBytes(32).toString('base64url'),
    iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', await key(), iv);
  const data = Buffer.concat([
    cipher.update(JSON.stringify(sessionSchema.parse(value))),
    cipher.final(),
  ]);
  await writeFile(filename(sid), Buffer.concat([iv, cipher.getAuthTag(), data]), {
    flag: 'wx',
    mode: 0o600,
  });
  return sid;
}
export async function loadSession(): Promise<Session> {
  const sid = (await cookies()).get(cookieName)?.value;
  if (!sid) throw new GatewayError(401, 'session_required', 'Please sign in to continue.');
  try {
    const bytes = await readFile(filename(sid));
    const decipher = createDecipheriv('aes-256-gcm', await key(), bytes.subarray(0, 12));
    decipher.setAuthTag(bytes.subarray(12, 28));
    const value = sessionSchema.parse(
      JSON.parse(
        Buffer.concat([decipher.update(bytes.subarray(28)), decipher.final()]).toString('utf8'),
      ),
    );
    if (Date.parse(value.expires) <= Date.now()) throw new Error('Expired');
    return value;
  } catch {
    throw new GatewayError(
      401,
      'session_expired',
      'Your session has expired. Please sign in again.',
    );
  }
}
export async function removeSession() {
  const sid = (await cookies()).get(cookieName)?.value;
  if (sid) await unlink(filename(sid)).catch(() => undefined);
}
export function requireOrigin(request: Request) {
  if (
    request.headers.get('origin') !== appOrigin ||
    request.headers.get('sec-fetch-site') === 'cross-site'
  ) {
    throw new GatewayError(403, 'origin_denied', 'This request did not originate in OpsPilot.');
  }
  const contentType = request.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase();
  if (contentType !== 'application/json')
    throw new GatewayError(415, 'json_required', 'Use a JSON request.');
}
export function requireCsrf(request: Request, session: Session) {
  requireOrigin(request);
  const token = Buffer.from(request.headers.get('x-csrf-token') ?? '');
  const expected = Buffer.from(session.csrf);
  if (token.length !== expected.length || !timingSafeEqual(token, expected))
    throw new GatewayError(403, 'csrf_denied', 'Refresh the page before retrying this action.');
}
export async function bodyText(request: Request) {
  const reader = request.body?.getReader();
  if (!reader) throw new GatewayError(422, 'body_required', 'A request body is required.');
  const parts: Uint8Array[] = [];
  let size = 0;
  let expired = false;
  const deadline = setTimeout(() => {
    expired = true;
    void reader.cancel().catch(() => undefined);
  }, 10000);
  try {
    while (true) {
      const result = await reader.read();
      if (expired) throw new GatewayError(408, 'body_timeout', 'Request timed out.');
      if (result.done) break;
      size += result.value.length;
      if (size > 65536) {
        await reader.cancel();
        throw new GatewayError(413, 'body_limit', 'Request is too large.');
      }
      parts.push(result.value);
    }
  } finally {
    clearTimeout(deadline);
  }
  const result = Buffer.concat(parts).toString('utf8');
  try {
    JSON.parse(result);
  } catch {
    throw new GatewayError(422, 'invalid_json', 'Invalid JSON request.');
  }
  return result;
}
export async function backendFetch(endpoint: string, token?: string, init: RequestInit = {}) {
  try {
    return await fetch(backend + endpoint, {
      ...init,
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(90000),
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new GatewayError(
      503,
      'backend_unavailable',
      'OpsPilot services are unavailable. Start the local services and retry.',
    );
  }
}
export async function authenticated() {
  const session = await loadSession();
  const response = await backendFetch('/api/v1/auth/me', session.token);
  if (response.status === 401) {
    await removeSession();
    throw new GatewayError(
      401,
      'session_revoked',
      'Your session is no longer valid. Please sign in again.',
    );
  }
  if (!response.ok)
    throw new GatewayError(503, 'auth_unavailable', 'Unable to verify your session.');
  return { session, principal: principalSchema.parse(await response.json()) };
}
export function failure(error: unknown) {
  const e =
    error instanceof GatewayError
      ? error
      : new GatewayError(
          503,
          'gateway_unavailable',
          'The local application is unavailable. Please retry.',
        );
  return Response.json(
    { error: { code: e.code, message: e.message } },
    { status: e.status, headers: { 'Cache-Control': 'no-store' } },
  );
}
export const sessionCookie = {
  httpOnly: true,
  sameSite: 'strict' as const,
  secure: appOrigin.startsWith('https:'),
  path: '/',
};
