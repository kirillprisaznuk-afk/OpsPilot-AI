import {
  authenticated,
  backendFetch,
  bodyText,
  failure,
  GatewayError,
  requireCsrf,
  signConversation,
  verifyConversation,
} from '@/lib/server-session';
import { allowedEndpoint } from '@/lib/proxy-policy';
export const runtime = 'nodejs';
type Context = { params: Promise<{ path: string[] }> };
async function forward(request: Request, context: Context) {
  try {
    const path = (await context.params).path.join('/');
    if (!allowedEndpoint(request.method, path))
      throw new GatewayError(404, 'endpoint_unavailable', 'This operation is not available.');
    const { session, principal } = await authenticated();
    if (!principal.roles.length)
      throw new GatewayError(
        403,
        'workspace_membership_required',
        'A current workspace role is required.',
      );
    let body: string | undefined;
    if (request.method === 'POST') {
      requireCsrf(request, session);
      body = await bodyText(request);
      if (path === 'api/v1/hybrid/query') {
        const question: unknown = JSON.parse(body);
        if (
          !question ||
          typeof question !== 'object' ||
          !('mode' in question) ||
          question.mode !== 'DETERMINISTIC'
        )
          throw new GatewayError(
            422,
            'mode_unavailable',
            'Use Verified Intelligence. Local LLM acceptance remains blocked.',
          );
        if ('conversation_id' in question && question.conversation_id != null) {
          body = JSON.stringify({
            ...question,
            conversation_id: await verifyConversation(question.conversation_id, session.csrf),
          });
        }
      }
    }
    const key = request.headers.get('idempotency-key');
    if (key && !/^[a-f0-9-]{36}$/i.test(key))
      throw new GatewayError(422, 'invalid_key', 'Invalid operation reference.');
    const response = await backendFetch('/' + path + new URL(request.url).search, session.token, {
      method: request.method,
      body,
      headers: key ? { 'Idempotency-Key': key } : {},
    });
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    };
    for (const name of ['server-timing', 'x-request-id']) {
      const value = response.headers.get(name);
      if (value) headers[name] = value;
    }
    if (path === 'api/v1/hybrid/query' && response.ok) {
      const data = (await response.json()) as Record<string, unknown>;
      if (typeof data.conversation_id === 'string')
        data.conversation_id = await signConversation(data.conversation_id, session.csrf);
      return Response.json(data, { status: response.status, headers });
    }
    return new Response(await response.text(), { status: response.status, headers });
  } catch (e) {
    return failure(e);
  }
}
export const GET = forward;
export const POST = forward;
