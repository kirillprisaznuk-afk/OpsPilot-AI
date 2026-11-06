'use client';
import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Activity, ArrowUpRight, Database, LogOut, ShieldCheck } from 'lucide-react';
import { useAction, useActorNames, useAuth, useData } from './providers';
import {
  Panel,
  PageHeading,
  Status,
  Loading,
  ErrorState,
  Empty,
  Pagination,
  Modal,
  Field,
  Limitations,
} from './ui';
import { date, label, shortId } from '@/lib/format';
import type { Audit, Page, JsonRecord, Subject } from '@/lib/types';
export function Governance({ section }: { section: string }) {
  return section === 'audit' ? (
    <AuditExplorer />
  ) : section === 'settings' ? (
    <Settings />
  ) : (
    <SystemStatus />
  );
}
function AuditExplorer() {
  const params = useSearchParams(),
    [proposal, setProposal] = useState(params.get('proposal_id') ?? ''),
    [search, setSearch] = useState(''),
    [action, setAction] = useState(''),
    [offset, setOffset] = useState(0),
    [selected, setSelected] = useState<Audit | null>(null);
  const valid = !proposal || /^[a-f0-9-]{36}$/.test(proposal);
  const data = useData<Page<Audit>>(
    'api/v1/workflows/audit?newest=true&limit=15&offset=' +
      offset +
      (proposal ? '&proposal_id=' + encodeURIComponent(proposal) : '') +
      (search ? '&search=' + encodeURIComponent(search) : '') +
      (action ? '&action=' + encodeURIComponent(action) : ''),
    valid,
  );
  const names = useActorNames(data.data?.items.map((x) => x.actor_id) ?? []);
  return (
    <>
      <PageHeading
        eyebrow="GOVERNANCE / AUDIT"
        title="Every action leaves a trace."
        description="Authenticated decisions, actual changes and durable execution events."
      />
      <div className="toolbar">
        <input
          aria-label="Search audit events"
          placeholder="Search actor, action or target…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
        <select
          aria-label="Filter audit action"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All event types</option>
          {[
            'proposal.created',
            'proposal.approved',
            'proposal.rejected',
            'execution.completed',
            'execution.failed',
            'task.created',
            'task.status_changed',
          ].map((a) => (
            <option value={a} key={a}>
              {label(a)}
            </option>
          ))}
        </select>
        <input
          aria-label="Filter by proposal reference"
          style={{ width: 320 }}
          placeholder="Filter by exact proposal reference…"
          value={proposal}
          onChange={(e) => {
            setProposal(e.target.value);
            setOffset(0);
          }}
        />
        {proposal && (
          <button
            className="button secondary"
            onClick={() => {
              setProposal('');
              setOffset(0);
            }}
          >
            Clear filter
          </button>
        )}
        <span className="muted" style={{ fontSize: 11 }}>
          Append-only database history · UTC timestamps
        </span>
      </div>
      {!valid ? (
        <div className="notice">Enter a complete proposal reference from its detail page.</div>
      ) : data.isPending ? (
        <Loading />
      ) : data.error ? (
        <ErrorState error={data.error} />
      ) : (
        <Panel
          title="Activity ledger"
          description="Only events visible within your current scope are returned"
        >
          {data.data?.items.length ? (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Event / sequence</th>
                      <th>Actor</th>
                      <th>Target</th>
                      <th>Timestamp (UTC)</th>
                      <th>Result</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.data.items.map((e) => (
                      <tr key={e.id}>
                        <td>
                          <button
                            className="text-link"
                            style={{ border: 0, background: 'none', padding: 0, textAlign: 'left' }}
                            onClick={() => setSelected(e)}
                          >
                            {label(e.action)}
                          </button>
                          <small>
                            Sequence {e.sequence} · {shortId(e.id)}
                          </small>
                        </td>
                        <td>
                          {e.actor_id
                            ? (names.get(e.actor_id) ?? 'Principal ' + shortId(e.actor_id))
                            : 'Authentication / maintenance'}
                        </td>
                        <td>
                          {label(e.object_type)} {shortId(e.object_id)}
                        </td>
                        <td>{date(e.created_at, true)}</td>
                        <td>
                          <Status value={e.result} />
                        </td>
                        <td>
                          <button
                            className="icon-button"
                            aria-label={'Inspect audit event ' + e.sequence}
                            onClick={() => setSelected(e)}
                          >
                            <ArrowUpRight size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination total={data.data.total} limit={15} offset={offset} onChange={setOffset} />
            </>
          ) : (
            <Empty title="No audit events in this scope" />
          )}
        </Panel>
      )}
      <Modal
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
        title={selected ? label(selected.action) : 'Audit event'}
        description="Immutable database event. Parameters are evidence, not an authorization instruction."
        wide
      >
        {selected && (
          <>
            <dl className="detail-list">
              <dt>Timestamp</dt>
              <dd>{date(selected.created_at, true)}</dd>
              <dt>Actor</dt>
              <dd>{selected.actor_id ?? 'Authentication / maintenance'}</dd>
              <dt>Result</dt>
              <dd>
                <Status value={selected.result} />
              </dd>
              <dt>Reason</dt>
              <dd>{selected.reason ?? 'No additional reason recorded'}</dd>
              <dt>Request ID</dt>
              <dd className="digest">{selected.request_id}</dd>
              {selected.proposal_id && (
                <>
                  <dt>Proposal</dt>
                  <dd>
                    <Link className="text-link" href={'/proposals/' + selected.proposal_id}>
                      {shortId(selected.proposal_id)}
                      <ArrowUpRight size={12} />
                    </Link>
                  </dd>
                </>
              )}
            </dl>
            <div className="change-grid">
              <div>
                <small>BEFORE</small>
                <StateFields values={selected.before_state} />
              </div>
              <div>
                <small>AFTER / RESULT</small>
                <StateFields values={selected.after_state} />
              </div>
            </div>
          </>
        )}
      </Modal>
    </>
  );
}
function StateFields({ values }: { values: JsonRecord }) {
  return Object.keys(values).length ? (
    <dl>
      {Object.entries(values).map(([key, value]) => (
        <div key={key} style={{ display: 'contents' }}>
          <dt>{label(key)}</dt>
          <dd>
            {value === null
              ? 'None'
              : typeof value === 'object'
                ? JSON.stringify(value)
                : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  ) : (
    <p className="muted" style={{ fontSize: 11 }}>
      No state fields recorded for this event.
    </p>
  );
}
type PrincipalInfo = {
  id: string;
  username: string;
  active: boolean;
  is_human: boolean;
  created_at: string;
  roles: { role_code: string; department_id: number | null }[];
};
function Settings() {
  const auth = useAuth(),
    act = useAction(),
    [error, setError] = useState<Error | null>(null),
    [change, setChange] = useState<PrincipalInfo | null>(null),
    [role, setRole] = useState('VIEWER'),
    [dept, setDept] = useState(''),
    [active, setActive] = useState(true),
    [reason, setReason] = useState(''),
    [busy, setBusy] = useState(false);
  const users = useData<PrincipalInfo[]>('api/v1/workspace/principals', auth.can('admin')),
    departments = useData<Page<Subject>>('api/v1/workspace/subjects?kind=department&limit=100');
  return (
    <>
      <PageHeading
        eyebrow="ACCOUNT & ACCESS"
        title="Your workspace identity."
        description="Current authenticated membership. Permissions are enforced by the backend."
      />
      {error && <ErrorState error={error} />}
      <div className="split-detail">
        <div className="stack">
          <Panel title="Account & session">
            <div className="panel-body">
              <div className="account-profile">
                <span className="avatar">{auth.principal.username.slice(0, 2).toUpperCase()}</span>
                <div>
                  <h2>{auth.principal.username}</h2>
                  <p>Active human-class principal · Local demo identity</p>
                </div>
              </div>
              <dl className="detail-list">
                <dt>Principal</dt>
                <dd className="digest">{auth.principal.id}</dd>
                <dt>Session expires</dt>
                <dd>{date(auth.expires_at, true)}</dd>
                <dt>Auth version</dt>
                <dd>{auth.principal.authz_version}</dd>
                <dt>Membership</dt>
                <dd>
                  {(
                    auth.principal.roles as { role_code: string; department_id: number | null }[]
                  ).map((r, i) => (
                    <p key={i}>
                      {label(r.role_code)} ·{' '}
                      {r.department_id === null
                        ? 'Global'
                        : (departments.data?.items.find((d) => d.id === r.department_id)?.label ??
                          'Department #' + r.department_id)}
                    </p>
                  ))}
                </dd>
              </dl>
              <button
                className="button secondary"
                style={{ marginTop: 24 }}
                onClick={async () => {
                  try {
                    await auth.logout();
                  } catch (e) {
                    setError(e instanceof Error ? e : new Error('Logout failed'));
                  }
                }}
              >
                <LogOut size={14} />
                Sign out of this session
              </button>
            </div>
          </Panel>
          {auth.can('admin') && (
            <Panel
              title="Local access directory"
              description="Global administration · Changes revoke affected sessions and invalidate prior approvals"
            >
              {users.data ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Principal</th>
                        <th>Membership</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {users.data.map((u) => (
                        <tr key={u.id}>
                          <td>
                            {u.username}
                            <small>
                              {u.active ? 'Active' : 'Disabled'} · {shortId(u.id)}
                            </small>
                          </td>
                          <td>
                            {u.roles.map((r, i) => (
                              <small key={i}>
                                {label(r.role_code)} ·{' '}
                                {r.department_id === null
                                  ? 'Global'
                                  : 'Department #' + r.department_id}
                              </small>
                            ))}
                          </td>
                          <td>
                            <button
                              className="button secondary small"
                              onClick={() => {
                                setChange(u);
                                setRole('VIEWER');
                                setDept('');
                                setReason('');
                              }}
                            >
                              Manage role
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : users.error ? (
                <ErrorState error={users.error} />
              ) : (
                <Loading />
              )}
            </Panel>
          )}
        </div>
        <div className="stack">
          <Panel title="Security by design">
            <div className="panel-body">
              <div className="notice">
                <ShieldCheck size={17} />
                <p>
                  Backend bearer tokens stay on the frontend server. The browser holds only an
                  httpOnly session reference.
                </p>
              </div>
              <p className="muted" style={{ fontSize: 11 }}>
                Logout revokes the backend session. Expiry, role changes or revocation are checked
                against the backend before protected proxy requests.
              </p>
            </div>
          </Panel>
          <Limitations
            items={[
              'Local demo authentication is not enterprise IAM, MFA or proof of human liveness.',
              'No public signup or password recovery is available. Ask the local administrator for trusted account maintenance.',
              'A role label does not override server scope checks or distinct-reviewer rules.',
            ]}
          />
        </div>
      </div>
      <Modal
        open={!!change}
        onOpenChange={(open) => {
          if (!busy && !open) setChange(null);
        }}
        title="Change local role assignment"
        description="This is a real administrative action. Affected sessions and approvals become invalid."
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!change || busy) return;
            setBusy(true);
            try {
              await act('api/v1/auth/principals/' + change.id + '/roles', {
                role,
                department_id: dept ? Number(dept) : null,
                active,
                reason,
              });
              setChange(null);
              await users.refetch();
            } catch (e) {
              setError(e instanceof Error ? e : new Error('Role change failed'));
              setChange(null);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="form-stack">
            <p className="muted">Principal: {change?.username}</p>
            <Field label="Role">
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {[
                  'VIEWER',
                  'OPERATIONS_ANALYST',
                  'WORKFLOW_OPERATOR',
                  'WORKFLOW_APPROVER',
                  'WORKFLOW_ADMIN',
                ].map((x) => (
                  <option value={x} key={x}>
                    {label(x)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Scope">
              <select value={dept} onChange={(e) => setDept(e.target.value)}>
                <option value="">Global</option>
                {departments.data?.items.map((d) => (
                  <option value={d.id} key={d.id}>
                    {d.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Assignment state">
              <select
                value={active ? 'active' : 'revoked'}
                onChange={(e) => setActive(e.target.value === 'active')}
              >
                <option value="active">Grant / keep active</option>
                <option value="revoked">Revoke assignment</option>
              </select>
            </Field>
            <Field label="Administrative reason">
              <textarea
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={1000}
              />
            </Field>
          </div>
          <div className="form-actions">
            <button className="button secondary" type="button" onClick={() => setChange(null)}>
              Cancel
            </button>
            <button className="button primary" disabled={busy}>
              {busy ? 'Applying…' : 'Confirm role change'}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
function SystemStatus() {
  const version = useData<{ api_version: string }>('api/v1/workspace/status');
  const health = useData<{ status: string }>('health'),
    ready = useData<{ status: string }>('ready'),
    knowledge = useData<{
      state: string;
      documents: number;
      versions: number;
      chunks: number;
      model_cached: boolean;
    }>('api/v1/knowledge/status'),
    hybrid = useData<JsonRecord>('api/v1/hybrid/status'),
    summary = useData<JsonRecord>('api/v1/workflows/summary'),
    agent = useData<JsonRecord>('api/v1/agent/status');
  const rows = [
    {
      title: 'FastAPI service',
      description: health.data
        ? 'Backend is reachable.'
        : (health.error?.message ?? 'Checking reachability…'),
      status: health.data?.status === 'ok' ? 'ready' : health.error ? 'unavailable' : 'checking',
    },
    {
      title: 'PostgreSQL readiness',
      description: ready.data
        ? 'Migration 0004 and seeded source data are ready.'
        : (ready.error?.message ?? 'Checking database…'),
      status: ready.data?.status === 'ready' ? 'ready' : ready.error ? 'unavailable' : 'checking',
    },
    {
      title: 'Corporate knowledge index',
      description: knowledge.data
        ? `${knowledge.data.documents} documents · ${knowledge.data.versions} versions · ${knowledge.data.chunks} chunks · Local embeddings`
        : (knowledge.error?.message ?? 'Checking index…'),
      status: knowledge.data?.state ?? (knowledge.error ? 'unavailable' : 'checking'),
    },
    {
      title: 'Verified Intelligence',
      description: hybrid.data
        ? 'Deterministic grounded analysis is available without model inference.'
        : (hybrid.error?.message ?? 'Checking capability engine…'),
      status: hybrid.data?.deterministic_available_without_llm
        ? 'ready'
        : hybrid.error
          ? 'unavailable'
          : 'checking',
    },
    {
      title: 'Governed workflow service',
      description: summary.data
        ? 'Current scoped workflow state is readable with your authenticated identity.'
        : (summary.error?.message ?? 'Checking authenticated workflow access…'),
      status: summary.data ? 'ready' : summary.error ? 'unavailable' : 'checking',
    },
    {
      title: 'Optional local LLM',
      description: agent.data
        ? 'Provider state: ' +
          String(agent.data.state ?? 'unknown') +
          '. Stage 4C live-model acceptance remains blocked; no inference was requested.'
        : (agent.error?.message ?? 'Checking provider metadata only…'),
      status: 'blocked',
    },
  ];
  return (
    <>
      <PageHeading
        eyebrow="LOCAL WORKSPACE / SYSTEM STATUS"
        title="Know what is available."
        description="Observed service health. Separate from production or model-quality acceptance."
      />
      <Panel
        title="Service availability"
        description="Read-only status requests · No model loading or inference"
      >
        {rows.map((r, i) => (
          <div className="health-row" key={r.title}>
            {i === 1 ? (
              <Database size={20} style={{ color: '#99a3b5' }} />
            ) : (
              <Activity size={20} style={{ color: '#99a3b5' }} />
            )}
            <div>
              <h3>{r.title}</h3>
              <p>{r.description}</p>
            </div>
            <Status value={r.status} />
          </div>
        ))}
      </Panel>
      <div className="two-col" style={{ marginTop: 20 }}>
        <Panel title="Operating boundaries">
          <div className="panel-body">
            <dl className="detail-list">
              <dt>Frontend</dt>
              <dd>OpsPilot Stage 6 · Next.js application</dd>
              <dt>Backend contract</dt>
              <dd>{version.data?.api_version ?? 'Unavailable'} · Migration 0004</dd>
              <dt>Primary mode</dt>
              <dd>Verified Intelligence · Deterministic</dd>
              <dt>Inference</dt>
              <dd>No paid API, no cloud fallback</dd>
              <dt>Workflow actions</dt>
              <dd>Eight internal allowlisted operations</dd>
            </dl>
          </div>
        </Panel>
        <Limitations
          items={[
            'Healthy services do not establish production deployment readiness.',
            'Local LLM quality acceptance remains blocked independently of deterministic intelligence. The interface does not load or invoke Qwen.',
            'Historical read APIs retain their original local-demo exposure. The frontend proxy requires a verified per-user session for every allowed route.',
          ]}
        />
      </div>
    </>
  );
}
