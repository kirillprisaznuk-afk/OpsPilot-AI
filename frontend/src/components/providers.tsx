'use client';
import Link from 'next/link';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { usePathname, useRouter } from 'next/navigation';
import type { Session } from '@/lib/types';
import { ApiError, clearOperations, mutation, operationKey, read, responseData } from '@/lib/api';
type Context = Session & {
  logout: () => Promise<void>;
  can: (
    permission: 'propose' | 'submit' | 'review' | 'execute' | 'admin',
    departments?: number[],
  ) => boolean;
};
const Auth = createContext<Context | null>(null);
type Observation = {
  observation_start: string;
  observation_end: string;
  fingerprint: string;
  counts: Record<string, number>;
};
type Reporting = {
  start: string;
  end: string;
  ready: boolean;
  meta?: Observation;
  error: Error | null;
  retry: () => void;
  setPeriod: (start: string, end: string) => void;
  query: string;
};
const ReportingContext = createContext<Reporting | null>(null);
export function useReporting() {
  const value = useContext(ReportingContext);
  if (!value) throw new Error('Reporting context missing');
  return value;
}
function ReportingProvider({ children }: { children: ReactNode }) {
  const meta = useData<Observation>('api/v1/demo/summary');
  const [selection, setSelection] = useState<{ start: string; end: string } | null>(null);
  const start = selection?.start ?? meta.data?.observation_start ?? '',
    end = selection?.end ?? meta.data?.observation_end ?? '';
  return (
    <ReportingContext.Provider
      value={{
        start,
        end,
        ready: !!meta.data,
        meta: meta.data,
        error: meta.error,
        retry: () => {
          void meta.refetch();
        },
        setPeriod: (s, e) => setSelection({ start: s, end: e }),
        query: new URLSearchParams({ start_date: start, end_date: end, as_of: end }).toString(),
      }}
    >
      {children}
    </ReportingContext.Provider>
  );
}
export function useAuth() {
  const auth = useContext(Auth);
  if (!auth) throw new Error('Authenticated context missing');
  return auth;
}
export function useData<T>(path: string, enabled = true) {
  const { principal } = useAuth();
  return useQuery({
    queryKey: [principal.id, path],
    queryFn: ({ signal }) => read<T>(path, signal),
    enabled,
    staleTime: path.includes('/analytics/') ? 30000 : 0,
  });
}
export function useAction() {
  const auth = useAuth(),
    cache = useQueryClient();
  return async <T,>(path: string, body: unknown) => {
    const key = await operationKey(auth.principal.id, path, body);
    const result = await mutation<T>(path, body, auth.csrf, key);
    if (!['api/v1/knowledge/search', 'api/v1/hybrid/query'].includes(path))
      await cache.invalidateQueries({ predicate: (q) => q.queryKey[0] === auth.principal.id });
    return result;
  };
}
export function useActorNames(ids: (string | null | undefined)[]) {
  const requested = [...new Set(ids.filter((id): id is string => !!id))].sort().slice(0, 100);
  const query = new URLSearchParams(requested.map((id) => ['ids', id]));
  const labels = useData<{ id: string; username: string }[]>(
    'api/v1/workspace/actor-labels?' + query,
    requested.length > 0,
  );
  return new Map(labels.data?.map((r) => [r.id, r.username]));
}
const permissions = {
  propose: ['OPERATIONS_ANALYST', 'WORKFLOW_OPERATOR', 'WORKFLOW_ADMIN'],
  submit: ['WORKFLOW_OPERATOR', 'WORKFLOW_ADMIN'],
  review: ['WORKFLOW_APPROVER', 'WORKFLOW_ADMIN'],
  execute: ['WORKFLOW_OPERATOR', 'WORKFLOW_ADMIN'],
  admin: ['WORKFLOW_ADMIN'],
};
function Authentication({ children }: { children: ReactNode }) {
  const pathname = usePathname(),
    router = useRouter(),
    cache = useQueryClient();
  const session = useQuery({
    queryKey: ['session'],
    queryFn: async () =>
      responseData<Session>(await fetch('/api/session', { cache: 'no-store' }), 'session'),
    enabled: pathname !== '/login',
    retry: false,
    refetchOnWindowFocus: true,
    refetchInterval: 60000,
  });
  useEffect(() => {
    const expired = () => {
      cache.clear();
      clearOperations();
      router.replace('/login');
    };
    window.addEventListener('opspilot:expired', expired);
    return () => window.removeEventListener('opspilot:expired', expired);
  }, [cache, router]);
  useEffect(() => {
    if (session.error instanceof ApiError && session.error.status === 401 && pathname !== '/login')
      router.replace('/login');
  }, [session.error, pathname, router]);
  if (pathname === '/login') return children;
  if (session.isPending)
    return (
      <div className="boot">
        <span className="mark">O</span>
        <p>Opening your workspace…</p>
      </div>
    );
  if (!session.data)
    return (
      <div className="boot">
        <h1>Workspace unavailable</h1>
        <p>{session.error?.message ?? 'Please sign in to continue.'}</p>
        <button onClick={() => session.refetch()}>Retry connection</button>
        <Link href="/login">Return to sign in</Link>
      </div>
    );
  const value: Context = {
    ...session.data,
    can: (permission, departments) => {
      const roles = session.data.principal.roles as {
        role_code: string;
        department_id: number | null;
      }[];
      return (departments ?? [undefined]).every((dept) =>
        roles.some(
          (r) =>
            permissions[permission].includes(r.role_code) &&
            (dept === undefined || r.department_id === null || r.department_id === dept),
        ),
      );
    },
    logout: async () => {
      await responseData(
        await fetch('/api/session', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.data.csrf },
          body: '{}',
        }),
        'session',
      );
      cache.clear();
      clearOperations();
      router.replace('/login');
    },
  };
  if (!value.principal.roles.length)
    return (
      <div className="boot">
        <h1>Workspace access required</h1>
        <p>Your account has no active workspace role.</p>
        <button className="button secondary" onClick={() => void value.logout()}>
          Sign out
        </button>
      </div>
    );
  return (
    <Auth.Provider value={value}>
      <ReportingProvider>{children}</ReportingProvider>
    </Auth.Provider>
  );
}
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: (count, error) =>
              error instanceof ApiError ? [0, 503].includes(error.status) && count < 1 : false,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <Authentication>{children}</Authentication>
    </QueryClientProvider>
  );
}
