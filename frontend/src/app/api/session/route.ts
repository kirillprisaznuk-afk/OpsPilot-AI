import { randomBytes } from 'node:crypto';
import { cookies } from 'next/headers';
import {
  authenticated,
  backendFetch,
  bodyText,
  cookieName,
  createSession,
  failure,
  GatewayError,
  removeSession,
  requireCsrf,
  requireOrigin,
  sessionCookie,
} from '@/lib/server-session';
export const runtime = 'nodejs';
export async function GET() {
  try {
    const { session, principal } = await authenticated();
    return Response.json(
      { principal, csrf: session.csrf, expires_at: session.expires },
      { headers: { 'Cache-Control': 'no-store' } },
    );
  } catch (e) {
    return failure(e);
  }
}
export async function POST(request: Request) {
  try {
    requireOrigin(request);
    const response = await backendFetch('/api/v1/auth/login', undefined, {
      method: 'POST',
      body: await bodyText(request),
    });
    if (!response.ok)
      return new Response(await response.text(), {
        status: response.status,
        headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
      });
    const data: unknown = await response.json();
    if (
      !data ||
      typeof data !== 'object' ||
      !('access_token' in data) ||
      typeof data.access_token !== 'string' ||
      !('expires_at' in data) ||
      typeof data.expires_at !== 'string'
    )
      throw new GatewayError(
        503,
        'invalid_auth_response',
        'Authentication service returned an invalid response.',
      );
    const csrf = randomBytes(32).toString('base64url');
    const sid = await createSession({ token: data.access_token, expires: data.expires_at, csrf });
    (await cookies()).set(cookieName, sid, {
      ...sessionCookie,
      expires: new Date(data.expires_at),
    });
    return Response.json({ signed_in: true }, { headers: { 'Cache-Control': 'no-store' } });
  } catch (e) {
    return failure(e);
  }
}
export async function DELETE(request: Request) {
  try {
    const { session } = await authenticated();
    requireCsrf(request, session);
    const response = await backendFetch('/api/v1/auth/logout', session.token, { method: 'POST' });
    if (!response.ok)
      throw new GatewayError(
        503,
        'logout_unavailable',
        'Logout was not confirmed. Retry before leaving this device.',
      );
    await removeSession();
    (await cookies()).delete(cookieName);
    return Response.json({ signed_out: true }, { headers: { 'Cache-Control': 'no-store' } });
  } catch (e) {
    return failure(e);
  }
}
