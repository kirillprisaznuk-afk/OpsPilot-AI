'use client';
import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  FileCheck2,
  Plus,
  ShieldCheck,
} from 'lucide-react';
import { useAction, useActorNames, useAuth, useData } from './providers';
import {
  PageHeading,
  Panel,
  Status,
  Modal,
  Field,
  Loading,
  ErrorState,
  Empty,
  Pagination,
  Limitations,
} from './ui';
import { ProposalForm, actionNames } from './proposal-form';
import { date, label, shortId } from '@/lib/format';
import type { Proposal, Page, Receipt, Evidence, JsonRecord, Task, Escalation } from '@/lib/types';
export function Proposals({
  id,
  inbox = false,
  revision = false,
}: {
  id?: string;
  inbox?: boolean;
  revision?: boolean;
}) {
  return id === 'new' ? (
    <ProposalForm />
  ) : id && revision ? (
    <Revision id={id} />
  ) : id ? (
    <Review id={id} />
  ) : (
    <ProposalList key={String(inbox)} inbox={inbox} />
  );
}
function Revision({ id }: { id: string }) {
  const existing = useData<Proposal>('api/v1/workflows/proposals/' + id),
    auth = useAuth();
  if (existing.isPending) return <Loading />;
  if (existing.error || !existing.data) return <ErrorState error={existing.error} />;
  const p = existing.data;
  if (
    ['COMPLETED', 'EXECUTING'].includes(p.status) ||
    (!auth.can('admin', [p.department_id]) && p.proposer_id !== auth.principal.id)
  )
    return <ErrorState error={new Error('This proposal cannot be revised by your account.')} />;
  return <ProposalForm key={p.id} revision={p} />;
}
function ProposalList({ inbox }: { inbox: boolean }) {
  const auth = useAuth(),
    [status, setStatus] = useState(inbox ? 'PENDING_REVIEW' : ''),
    [offset, setOffset] = useState(0);
  const data = useData<Page<Proposal>>(
    'api/v1/workflows/proposals?limit=12&offset=' + offset + (status ? '&status=' + status : ''),
  );
  const actorNames = useActorNames(data.data?.items.map((x) => x.proposer_id) ?? []);
  return (
    <>
      <PageHeading
        eyebrow={inbox ? 'GOVERNED DECISIONS' : 'WORKFLOWS / PROPOSALS'}
        title={inbox ? 'The approval inbox.' : 'From intent to accountable action.'}
        description={
          inbox
            ? 'Inspect the exact change, its evidence and consequences. Every decision is explicit.'
            : 'Immutable proposals. Deliberate human decisions. Verifiable execution.'
        }
        actions={
          auth.can('propose') && (
            <Link className="button primary" href="/proposals/new">
              <Plus size={15} />
              Prepare proposal
            </Link>
          )
        }
      />
      {inbox && !auth.can('review') && (
        <div className="notice">
          Your role can inspect permitted proposals. It cannot approve or reject them.
        </div>
      )}
      <div className="toolbar">
        <select
          aria-label="Proposal state"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All states</option>
          {[
            'DRAFT',
            'PENDING_REVIEW',
            'APPROVED',
            'COMPLETED',
            'REJECTED',
            'CANCELLED',
            'EXPIRED',
            'FAILED',
          ].map((s) => (
            <option value={s} key={s}>
              {label(s)}
            </option>
          ))}
        </select>
        <span className="muted" style={{ fontSize: 11 }}>
          Current workflow activity · Scoped to your permissions
        </span>
      </div>
      {data.isPending ? (
        <Loading />
      ) : data.error ? (
        <ErrorState error={data.error} retry={() => data.refetch()} />
      ) : (
        <Panel
          title={inbox ? 'Awaiting deliberate review' : 'Action proposals'}
          description="Review current state before making any decision"
        >
          {data.data?.items.length ? (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Proposed action</th>
                      <th>Business subject</th>
                      <th>Submitted by</th>
                      <th>State</th>
                      <th>Valid until (UTC)</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.data.items.map((p) => {
                      const action = p.material.action as JsonRecord,
                        subject = p.material.subject as JsonRecord;
                      return (
                        <tr key={p.id}>
                          <td>
                            <Link href={'/proposals/' + p.id}>
                              {String(
                                action.title ??
                                  actionNames[p.action_type as keyof typeof actionNames] ??
                                  label(p.action_type),
                              )}
                              <small>
                                {shortId(p.id)} · v{p.version} · {label(p.source_type)}
                              </small>
                            </Link>
                          </td>
                          <td>
                            {label(String(subject.kind))} #{String(subject.entity_id)}
                          </td>
                          <td>
                            {p.proposer_id === auth.principal.id
                              ? auth.principal.username
                              : (actorNames.get(p.proposer_id) ??
                                'Principal ' + shortId(p.proposer_id))}
                            {p.proposer_id === auth.principal.id && <small>Your proposal</small>}
                          </td>
                          <td>
                            <Status value={p.effective_status} />
                            {p.stale && <small>Context changed · review required</small>}
                          </td>
                          <td>{date(p.expires_at, true)}</td>
                          <td>
                            <Link className="text-link" href={'/proposals/' + p.id}>
                              Review
                              <ArrowUpRight size={12} />
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination total={data.data.total} offset={offset} limit={12} onChange={setOffset} />
            </>
          ) : (
            <Empty title={inbox ? 'Your review queue is clear' : 'No proposals in this scope'}>
              New proposals appear here after an explicit user action. No automatic approval is
              performed.
            </Empty>
          )}
        </Panel>
      )}
    </>
  );
}
function Review({ id }: { id: string }) {
  const auth = useAuth(),
    act = useAction(),
    data = useData<Proposal>('api/v1/workflows/proposals/' + id),
    [decision, setDecision] = useState<string | null>(null),
    [reviewed, setReviewed] = useState<Proposal | null>(null),
    [confirmed, setConfirmed] = useState(false),
    [reason, setReason] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [receipt, setReceipt] = useState<Receipt | null>(null);
  const evidence = useData<Evidence>(
    'api/v1/workflows/evidence/' + (data.data?.evidence_id ?? ''),
    !!data.data?.evidence_id,
  );
  const storedAction = data.data?.material.action as JsonRecord | undefined;
  const targetId = storedAction?.expected_version
    ? String(storedAction.task_id ?? storedAction.escalation_id ?? '')
    : '';
  const target = useData<Task | Escalation>(
    'api/v1/workflows/' + (storedAction?.escalation_id ? 'escalations/' : 'tasks/') + targetId,
    !!targetId,
  );
  const actorNames = useActorNames([
    data.data?.proposer_id,
    ...(data.data?.approvals.map((a) => String((a as JsonRecord).actor_id)) ?? []),
  ]);
  async function prepare(action: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setConfirmed(false);
    try {
      const current = await data.refetch();
      if (current.error || !current.data)
        throw current.error ?? new Error('Unable to refresh proposal');
      const allowed: Record<string, string[]> = {
        submit: ['DRAFT'],
        approve: ['PENDING_REVIEW'],
        reject: ['PENDING_REVIEW'],
        execute: ['APPROVED', 'COMPLETED'],
        cancel: ['DRAFT', 'PENDING_REVIEW', 'APPROVED'],
        revoke: ['APPROVED'],
      };
      if (
        !allowed[action]?.includes(current.data.effective_status) ||
        (['submit', 'approve', 'reject', 'execute'].includes(action) &&
          current.data.stale &&
          current.data.status !== 'COMPLETED')
      )
        throw new Error(
          'The proposal changed or expired. Inspect its current state and prepare a fresh revision if required.',
        );
      setReviewed(current.data);
      setDecision(action);
    } catch (e) {
      setError(e instanceof Error ? e : new Error('Review failed'));
    } finally {
      setBusy(false);
    }
  }
  if (data.isPending) return <Loading />;
  if (data.error || !data.data)
    return <ErrorState error={data.error} retry={() => data.refetch()} />;
  const p = data.data,
    action = p.material.action as JsonRecord,
    subject = p.material.subject as JsonRecord,
    policy = p.material.policy as JsonRecord,
    scopes = Array.isArray(policy.scopes) ? policy.scopes.map(Number) : [p.department_id];
  const owner = p.proposer_id === auth.principal.id || auth.can('admin', scopes),
    fresh =
      !p.stale &&
      p.effective_status !== 'EXPIRED' &&
      (!p.evidence_id || !!evidence.data) &&
      (!targetId || !!target.data);
  const pastReceipt =
    receipt ?? (p.executions.length ? (p.executions[p.executions.length - 1] as Receipt) : null);
  return (
    <>
      <Link className="text-link" href="/proposals" style={{ marginBottom: 20 }}>
        <ArrowLeft size={13} />
        Action proposals
      </Link>
      <PageHeading
        eyebrow={'IMMUTABLE PROPOSAL / ' + shortId(p.id)}
        title={String(
          action.title ??
            actionNames[p.action_type as keyof typeof actionNames] ??
            'Review proposed action',
        )}
        description={'Version ' + p.version + ' · Created ' + date(p.created_at, true)}
        actions={<Status value={p.effective_status} />}
      />
      {error && <ErrorState error={error} />}
      <div className="split-detail">
        <div className="stack">
          <Panel>
            <div className="review-banner">
              <ShieldCheck size={25} />
              <div>
                <h2>One exact change. One deliberate decision.</h2>
                <p>Approval and execution are separate. The backend remains the authority.</p>
              </div>
              <Status value={p.stale ? 'stale' : p.source_type} />
            </div>
            <div className="review-summary">
              <h3>Proposed change</h3>
              <div className="change-grid">
                <div>
                  <small>CURRENT CONTEXT</small>
                  <dl>
                    <dt>Subject</dt>
                    <dd>
                      {label(String(subject.kind))} #{String(subject.entity_id)}
                    </dd>
                    <dt>Department</dt>
                    <dd>#{p.department_id}</dd>
                    <dt>Source state</dt>
                    <dd>
                      {(p.material.preconditions as JsonRecord)?.target_version
                        ? 'Target v' +
                          String((p.material.preconditions as JsonRecord).target_version)
                        : 'New workflow record'}
                    </dd>
                    <dt>Proposer</dt>
                    <dd>
                      {p.proposer_id === auth.principal.id
                        ? auth.principal.username
                        : (actorNames.get(p.proposer_id) ?? shortId(p.proposer_id))}
                    </dd>
                    {target.data &&
                      Object.entries(target.data)
                        .filter(
                          ([field]) =>
                            [
                              'status',
                              'priority',
                              'due_at',
                              'department_id',
                              'employee_id',
                              'resolution',
                            ].includes(field) && field in action,
                        )
                        .map(([field, value]) => (
                          <div key={field} style={{ display: 'contents' }}>
                            <dt>{label(field)}</dt>
                            <dd>{value == null ? 'Unassigned' : String(value)}</dd>
                          </div>
                        ))}
                  </dl>
                </div>
                <div>
                  <small>EXACT PROPOSED PARAMETERS</small>
                  <dl>
                    {Object.entries(action)
                      .filter(([k]) => k !== 'type' && k !== 'subject')
                      .map(([k, v]) => (
                        <div key={k} style={{ display: 'contents' }}>
                          <dt>{label(k)}</dt>
                          <dd>
                            {v === null
                              ? 'Unassigned'
                              : typeof v === 'object'
                                ? JSON.stringify(v)
                                : String(v)}
                          </dd>
                        </div>
                      ))}
                  </dl>
                </div>
              </div>
              <h3 style={{ marginTop: 23 }}>Reason & operational context</h3>
              <p className="muted" style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
                {String(p.material.reason)}
              </p>
              {!!p.material.business_context && (
                <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
                  {String(p.material.business_context)}
                </p>
              )}
              <details style={{ marginTop: 20 }}>
                <summary className="text-link" style={{ cursor: 'pointer' }}>
                  Inspect immutable payload and digest
                </summary>
                <pre className="code-payload">{JSON.stringify(p.material, null, 2)}</pre>
                <p className="source-citation">SHA-256 {p.digest}</p>
              </details>
            </div>
          </Panel>
          <Panel
            title="Supporting verified evidence"
            description={
              p.evidence_id
                ? 'Immutable server-created investigation snapshot'
                : 'Human-authored operational context'
            }
          >
            {evidence.data ? (
              <div className="panel-body">
                <div className="notice success">
                  <Check size={15} />
                  Verified source snapshot · Historical cutoff {String(
                    evidence.data.payload.as_of,
                  )}{' '}
                  · Zero LLM calls
                </div>
                <p className="muted" style={{ fontSize: 11 }}>
                  {String(evidence.data.payload.question)}
                </p>
                <details style={{ marginTop: 14 }}>
                  <summary className="text-link" style={{ cursor: 'pointer' }}>
                    Inspect complete analytical response
                  </summary>
                  <div className="response-prose">{String(evidence.data.payload.answer)}</div>
                </details>
                {Array.isArray(evidence.data.payload.citations) &&
                  evidence.data.payload.citations.map((raw, i) => {
                    const c = raw as JsonRecord;
                    return (
                      <Link
                        key={i}
                        className="source-card"
                        style={{ paddingLeft: 0, paddingRight: 0 }}
                        href={'/citations/' + encodeURIComponent(String(c.citation_id))}
                      >
                        <span className="source-title">
                          {String(c.title)}
                          <ArrowUpRight size={12} />
                        </span>
                        <p>
                          Version {String(c.version)} · Effective {date(String(c.effective_on))}
                        </p>
                      </Link>
                    );
                  })}
              </div>
            ) : evidence.error ? (
              <ErrorState error={evidence.error} />
            ) : p.evidence_id ? (
              <div className="panel-body muted" role="status">
                Loading the verified evidence snapshot…
              </div>
            ) : (
              <div className="panel-body">
                <p className="muted" style={{ fontSize: 12 }}>
                  No server evidence snapshot is attached. This action is a human-authored internal
                  proposal; its parameters and reason require independent review.
                </p>
              </div>
            )}
          </Panel>
          {pastReceipt && <ReceiptView receipt={pastReceipt} />}
          <Panel title="Decision history" description="Persisted authenticated decisions">
            <div className="timeline">
              {p.approvals.length ? (
                p.approvals.map((raw, i) => {
                  const a = raw as JsonRecord;
                  return (
                    <div key={i} className="timeline-item">
                      <span className="timeline-dot" />
                      <div>
                        <strong>
                          {label(String(a.decision))} ·{' '}
                          {actorNames.get(String(a.actor_id)) ??
                            'Principal ' + shortId(String(a.actor_id))}
                        </strong>
                        <p>
                          {date(String(a.created_at), true)} · Reviewed v
                          {String(a.proposal_version)}
                        </p>
                        <p>{String(a.reason ?? 'No additional comment')}</p>
                      </div>
                    </div>
                  );
                })
              ) : (
                <Empty title="No review decision yet" />
              )}
            </div>
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Governance check">
            <div className="panel-body">
              <dl className="detail-list">
                <dt>Approval rule</dt>
                <dd>One distinct human reviewer</dd>
                <dt>Risk</dt>
                <dd>{label(String(policy.risk ?? 'Internal operational'))}</dd>
                <dt>Policy version</dt>
                <dd>
                  {String(policy.version)} · {p.approval_policy_current ? 'Current' : 'Changed'}
                </dd>
                <dt>Valid until</dt>
                <dd>{date(p.expires_at, true)}</dd>
                <dt>Context</dt>
                <dd>
                  {p.stale
                    ? 'Changed · Fresh revision required'
                    : 'Current target & authorization snapshot'}
                </dd>
                <dt>Scope</dt>
                <dd>{scopes.map((x) => 'Department #' + x).join(', ')}</dd>
                <dt>Side effects</dt>
                <dd>Internal only</dd>
              </dl>
            </div>
            <div
              className="form-actions"
              style={{ flexDirection: 'column', alignItems: 'stretch' }}
            >
              {p.status === 'DRAFT' && fresh && owner && auth.can('submit', scopes) && (
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => prepare('submit')}
                >
                  Submit for human review
                  <ArrowRight size={14} />
                </button>
              )}
              {p.status === 'PENDING_REVIEW' &&
                fresh &&
                auth.can('review', scopes) &&
                p.proposer_id !== auth.principal.id && (
                  <>
                    <button
                      className="button primary"
                      disabled={busy}
                      onClick={() => prepare('approve')}
                    >
                      <ShieldCheck size={15} />
                      Review & approve
                    </button>
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={() => prepare('reject')}
                    >
                      Reject proposal
                    </button>
                  </>
                )}
              {p.status === 'PENDING_REVIEW' && p.proposer_id === auth.principal.id && (
                <p className="muted" style={{ fontSize: 11 }}>
                  You proposed this action. A different authorized human must review it.
                </p>
              )}
              {p.status === 'APPROVED' && fresh && owner && auth.can('execute', scopes) && (
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => prepare('execute')}
                >
                  Execute approved action
                  <ArrowRight size={14} />
                </button>
              )}
              {p.status === 'COMPLETED' && owner && auth.can('execute', scopes) && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => prepare('execute')}
                >
                  Verify committed receipt
                </button>
              )}
              {['DRAFT', 'PENDING_REVIEW', 'APPROVED'].includes(p.status) &&
                owner &&
                auth.can('propose', scopes) && (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => prepare('cancel')}
                  >
                    Cancel proposal
                  </button>
                )}
              {p.status === 'APPROVED' &&
                auth.can('review', scopes) &&
                p.proposer_id !== auth.principal.id &&
                (auth.can('admin', scopes) ||
                  p.approvals.some((a) => (a as JsonRecord).actor_id === auth.principal.id)) && (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => prepare('revoke')}
                  >
                    Revoke approval
                  </button>
                )}
              {owner &&
                auth.can('propose', scopes) &&
                !['COMPLETED', 'EXECUTING'].includes(p.status) && (
                  <Link className="button secondary" href={'/proposals/' + p.id + '/revise'}>
                    Prepare fresh revision
                  </Link>
                )}
              <Link className="text-link" href={'/audit?proposal_id=' + p.id}>
                Inspect related audit
                <ArrowUpRight size={13} />
              </Link>
            </div>
          </Panel>
          <Limitations items={p.limitations} />
        </div>
      </div>
      <Modal
        open={!!decision}
        onOpenChange={(open) => {
          if (!busy && !open) setDecision(null);
        }}
        title={
          decision === 'approve'
            ? 'Approve this exact proposal?'
            : decision === 'execute'
              ? 'Execute the approved internal action?'
              : label(decision ?? 'Review') + ' proposal'
        }
        description="Current state was refreshed before this review. The server will recheck it at commit."
      >
        <dl className="detail-list">
          <dt>Proposal</dt>
          <dd>
            {shortId(p.id)} · v{reviewed?.version}
          </dd>
          <dt>Action</dt>
          <dd>{actionNames[p.action_type as keyof typeof actionNames]}</dd>
          <dt>Your identity</dt>
          <dd>{auth.principal.username}</dd>
          <dt>Digest</dt>
          <dd className="digest">{reviewed?.digest}</dd>
          <dt>Current state</dt>
          <dd>
            <Status value={reviewed?.effective_status ?? p.effective_status} />
          </dd>
        </dl>
        <div className="notice" style={{ marginTop: 20 }}>
          {decision === 'approve'
            ? 'Approval authorizes the reviewed internal parameters. It does not execute the operation.'
            : decision === 'execute'
              ? 'This explicitly requests a real internal PostgreSQL mutation, subject to all current authorization and evidence checks.'
              : 'This records an explicit authenticated workflow decision.'}
        </div>
        <Field label="Decision comment">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={1000}
            placeholder="Record why you are making this decision."
          />
        </Field>
        <label className="checkbox-row" style={{ marginTop: 18 }}>
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          I have reviewed the exact action, evidence, scope and consequences.
        </label>
        <div className="form-actions">
          <button className="button secondary" disabled={busy} onClick={() => setDecision(null)}>
            Back to review
          </button>
          <button
            className={
              'button ' +
              (['reject', 'revoke', 'cancel'].includes(decision ?? '') ? 'danger' : 'primary')
            }
            disabled={busy || !confirmed || !reviewed}
            onClick={async () => {
              if (!reviewed || !decision || busy) return;
              setBusy(true);
              setError(null);
              try {
                const result = await act<Proposal | Receipt>(
                  'api/v1/workflows/proposals/' + p.id + '/' + decision,
                  {
                    proposal_version: reviewed.version,
                    digest: reviewed.digest,
                    reason: reason || null,
                  },
                );
                if ('proposal_id' in result && 'result' in result) setReceipt(result as Receipt);
                setDecision(null);
                setReason('');
                await data.refetch();
              } catch (e) {
                setError(e instanceof Error ? e : new Error('Decision was not confirmed'));
                setDecision(null);
                await data.refetch();
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy
              ? 'Awaiting confirmation…'
              : decision === 'execute'
                ? 'Confirm execution'
                : 'Confirm ' + (decision ?? 'decision')}
          </button>
        </div>
      </Modal>
    </>
  );
}
function ReceiptView({ receipt }: { receipt: Receipt }) {
  const result = receipt.result as JsonRecord,
    objects =
      result.objects && typeof result.objects === 'object' ? (result.objects as JsonRecord) : {};
  return (
    <section id="receipt">
      <Panel
        title="Committed execution receipt"
        description="Actual PostgreSQL result · No simulated success"
      >
        <div className="panel-body">
          <div className={'notice ' + (receipt.status === 'COMPLETED' ? 'success' : 'danger')}>
            <FileCheck2 size={17} />
            <div>
              <strong>{label(receipt.status)}</strong>
              <p>
                {receipt.status === 'COMPLETED'
                  ? 'The internal operation committed. Repeating execution returns this same receipt.'
                  : 'No successful business mutation was committed.'}
              </p>
            </div>
          </div>
          <dl className="detail-list">
            <dt>Execution</dt>
            <dd>{receipt.id}</dd>
            <dt>Finished (UTC)</dt>
            <dd>{date(receipt.finished_at, true)}</dd>
            <dt>Executor</dt>
            <dd>{shortId(receipt.actor_id)}</dd>
            <dt>Approver</dt>
            <dd>{shortId(receipt.approver_id)}</dd>
            <dt>Proposal digest</dt>
            <dd className="digest">{String(result.proposal_digest ?? 'Unavailable')}</dd>
            {Object.entries(objects).map(([k, v]) => (
              <div key={k} style={{ display: 'contents' }}>
                <dt>{label(k)}</dt>
                <dd>
                  {k === 'task_id' || k === 'escalation_id' ? (
                    <Link
                      className="text-link"
                      href={'/' + (k === 'task_id' ? 'tasks' : 'escalations') + '/' + String(v)}
                    >
                      Open affected {k === 'task_id' ? 'task' : 'escalation'}
                      <ArrowUpRight size={12} />
                    </Link>
                  ) : (
                    String(v)
                  )}
                </dd>
              </div>
            ))}
          </dl>
          {Array.isArray(result.audit_events) && (
            <div className="source-meta" style={{ marginTop: 18 }}>
              {result.audit_events.map((id, i) => (
                <Link key={i} href={'/audit?proposal_id=' + receipt.proposal_id}>
                  Audit {shortId(String(id))}
                </Link>
              ))}
            </div>
          )}
        </div>
      </Panel>
    </section>
  );
}
