'use client';
import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, ShieldCheck, ScanSearch } from 'lucide-react';
import { useAction, useAuth, useData, useReporting } from './providers';
import { PageHeading, Panel, Field, Modal, ErrorState, Limitations } from './ui';
import { date, label } from '@/lib/format';
import type {
  Proposal,
  ProposalInput,
  Task,
  Escalation,
  Page,
  Subject,
  Person,
  Evidence,
  JsonRecord,
} from '@/lib/types';
export const actionNames = {
  CREATE_WORKFLOW_TASK: 'Create workflow task',
  ASSIGN_WORKFLOW_TASK: 'Assign workflow task',
  UPDATE_WORKFLOW_TASK_STATUS: 'Change task status',
  UPDATE_WORKFLOW_TASK_PRIORITY: 'Change task priority',
  UPDATE_WORKFLOW_TASK_DUE_DATE: 'Change task due date',
  ADD_WORKFLOW_TASK_NOTE: 'Append internal note',
  CREATE_INTERNAL_ESCALATION: 'Create internal escalation',
  CLOSE_INTERNAL_ESCALATION: 'Close internal escalation',
};
type ActionType = keyof typeof actionNames;
type SubjectKind = ProposalInput['action'] extends never ? never : Subject['kind'];
export function ProposalForm({ revision }: { revision?: Proposal } = {}) {
  const params = useSearchParams(),
    router = useRouter(),
    auth = useAuth(),
    act = useAction(),
    period = useReporting();
  const previous = revision?.material.action as JsonRecord | undefined;
  const priorSubject = revision?.material.subject as JsonRecord | undefined;
  const requested = revision?.action_type ?? params.get('action');
  const [type, setType] = useState<ActionType>(
      requested && requested in actionNames ? (requested as ActionType) : 'CREATE_WORKFLOW_TASK',
    ),
    [subjectKind, setSubjectKind] = useState<SubjectKind>(
      (
        [
          'supplier',
          'purchase_order',
          'sales_order',
          'warehouse',
          'product',
          'incident',
          'department',
        ] as const
      ).find((k) => k === (priorSubject?.kind ?? params.get('subject_kind'))) ?? 'supplier',
    ),
    [subjectId, setSubjectId] = useState(
      String(priorSubject?.entity_id ?? params.get('subject_id') ?? ''),
    ),
    [targetId, setTargetId] = useState(
      String(
        previous?.task_id ??
          previous?.escalation_id ??
          params.get('task_id') ??
          params.get('escalation_id') ??
          '',
      ),
    ),
    [search, setSearch] = useState(''),
    [targetSearch, setTargetSearch] = useState(''),
    [relatedTask, setRelatedTask] = useState(
      String(previous?.task_id ?? params.get('related_task_id') ?? ''),
    ),
    [department, setDepartment] = useState(
      String(previous?.department_id ?? revision?.department_id ?? ''),
    ),
    [employee, setEmployee] = useState(String(previous?.employee_id ?? '')),
    [title, setTitle] = useState(String(previous?.title ?? '')),
    [description, setDescription] = useState(
      String(previous?.description ?? previous?.reason ?? ''),
    ),
    [priority, setPriority] = useState<'low' | 'normal' | 'high' | 'urgent'>('normal'),
    [status, setStatus] = useState<'open' | 'active' | 'blocked' | 'completed' | 'cancelled'>(
      'active',
    ),
    [due, setDue] = useState(() => new Date(Date.now() + 172800000).toISOString().slice(0, 16)),
    [note, setNote] = useState(String(previous?.text ?? previous?.resolution ?? '')),
    [reason, setReason] = useState(String(revision?.material.reason ?? '')),
    [context, setContext] = useState(String(revision?.material.business_context ?? '')),
    [evidence, setEvidence] = useState<Evidence | null>(null),
    [busy, setBusy] = useState(false),
    [verifying, setVerifying] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [preview, setPreview] = useState<ProposalInput | null>(null),
    [question, setQuestion] = useState('');
  const isCreate = ['CREATE_WORKFLOW_TASK', 'CREATE_INTERNAL_ESCALATION'].includes(type),
    isClose = type === 'CLOSE_INTERNAL_ESCALATION';
  const departments = useData<Page<Subject>>('api/v1/workspace/subjects?kind=department&limit=100'),
    people = useData<Person[]>('api/v1/workspace/people');
  const selectedDefault =
    (auth.principal.roles as { department_id: number | null }[]).find((x) => x.department_id)
      ?.department_id ?? departments.data?.items[0]?.id;
  const dept = department || String(selectedDefault ?? '');
  const subjects = useData<Page<Subject>>(
    'api/v1/workspace/subjects?kind=' +
      subjectKind +
      '&limit=25&search=' +
      encodeURIComponent(search),
    isCreate,
  );
  const chosenSubject = useData<Page<Subject>>(
    'api/v1/workspace/subjects?kind=' + subjectKind + '&search=' + encodeURIComponent(subjectId),
    isCreate && !!subjectId,
  );
  const targets = useData<Page<Task | Escalation>>(
    'api/v1/workflows/' +
      (isClose ? 'escalations' : 'tasks') +
      '?limit=25&search=' +
      encodeURIComponent(targetSearch),
    !isCreate,
  );
  const target = useData<Task | Escalation>(
    'api/v1/workflows/' + (isClose ? 'escalations' : 'tasks') + '/' + targetId,
    !isCreate && !!targetId,
  );
  const owner = target.data?.department_id ?? Number(dept),
    subject =
      target.data?.subject ??
      (subjectId ? { kind: subjectKind, entity_id: Number(subjectId) } : null);
  const related = useData<Page<Task>>(
    'api/v1/workflows/tasks?limit=100&department_id=' + owner,
    type === 'CREATE_INTERNAL_ESCALATION' && !!owner && !!subject,
  );
  const validRelated =
    related.data?.items.filter(
      (t) => t.subject.kind === subject?.kind && t.subject.entity_id === subject.entity_id,
    ) ?? [];
  const selected = chosenSubject.data?.items.find((s) => s.id === Number(subjectId));
  const subjectOptions = subjects.data?.items ?? [];
  function action(): ProposalInput['action'] {
    const targetVersion = target.data?.version ?? 0;
    const dueAt = due ? new Date(due + 'Z').toISOString() : '';
    switch (type) {
      case 'CREATE_WORKFLOW_TASK':
        return {
          type,
          title,
          description,
          priority,
          due_at: dueAt,
          employee_id: employee ? Number(employee) : null,
          subject: subject!,
        };
      case 'CREATE_INTERNAL_ESCALATION':
        return {
          type,
          title,
          reason: description,
          priority,
          due_at: dueAt,
          subject: subject!,
          task_id: validRelated.some((t) => t.id === relatedTask) ? relatedTask : null,
        };
      case 'ASSIGN_WORKFLOW_TASK':
        return {
          type,
          task_id: targetId,
          expected_version: targetVersion,
          employee_id: employee ? Number(employee) : null,
          department_id: Number(dept),
        };
      case 'UPDATE_WORKFLOW_TASK_STATUS':
        return { type, task_id: targetId, expected_version: targetVersion, status: selectedStatus };
      case 'UPDATE_WORKFLOW_TASK_PRIORITY':
        return { type, task_id: targetId, expected_version: targetVersion, priority };
      case 'UPDATE_WORKFLOW_TASK_DUE_DATE':
        return { type, task_id: targetId, expected_version: targetVersion, due_at: dueAt };
      case 'ADD_WORKFLOW_TASK_NOTE':
        return { type, task_id: targetId, expected_version: targetVersion, text: note };
      case 'CLOSE_INTERNAL_ESCALATION':
        return { type, escalation_id: targetId, expected_version: targetVersion, resolution: note };
    }
  }
  if (!auth.can('propose'))
    return (
      <ErrorState
        error={new Error('Your role can inspect records but cannot prepare proposals.')}
      />
    );
  const requiresEvidence =
    type === 'CREATE_INTERNAL_ESCALATION' || !!params.get('subject_id') || !!revision?.evidence_id;
  const statusOptions: (typeof status)[] =
    target.data?.status === 'open' || target.data?.status === 'blocked'
      ? ['active', 'cancelled']
      : ['blocked', 'completed', 'cancelled'];
  const selectedStatus = statusOptions.includes(status) ? status : statusOptions[0];
  const validTarget = isCreate ? !!selected : !!target.data;
  return (
    <>
      <Link className="text-link" href="/proposals" style={{ marginBottom: 20 }}>
        <ArrowLeft size={13} />
        Action proposals
      </Link>
      <PageHeading
        eyebrow="WORKFLOWS / PREPARE A PROPOSAL"
        title="A deliberate next step."
        description="Define the internal action, inspect its evidence, then save an immutable draft."
      />
      {error && <ErrorState error={error} />}
      {revision && (
        <div className="notice">
          A fresh revision replaces the prior material. Its approvals do not carry over.
        </div>
      )}
      <div className="split-detail">
        <form
          id="proposal-form"
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            setError(null);
            if (!validTarget) {
              setError(
                new Error('Choose an actual registered subject or current workflow target.'),
              );
              return;
            }
            if (requiresEvidence && !evidence) {
              setError(new Error('Verify supporting evidence before preparing this proposal.'));
              return;
            }
            try {
              setPreview({
                department_id: owner,
                action: action(),
                source_type: revision?.source_type ?? 'HUMAN',
                reason,
                business_context: context || null,
                ...(evidence
                  ? {
                      evidence_id: evidence.id,
                      fact_ids: (evidence.payload.facts as { fact_id: string; verified: boolean }[])
                        .filter((x) => x.verified)
                        .slice(0, 16)
                        .map((x) => x.fact_id),
                    }
                  : {}),
              });
            } catch {
              setError(new Error('Check the due date and required values.'));
            }
          }}
        >
          <div className="form-section">
            <h2>01 · Proposed action</h2>
            <Field label="Action type">
              <select
                value={type}
                onChange={(e) => {
                  setType(e.target.value as ActionType);
                  setTargetId('');
                  setEvidence(null);
                }}
              >
                {Object.entries(actionNames).map(([key, value]) => (
                  <option key={key} value={key}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="form-section">
            <h2>02 · Business context & ownership</h2>
            <div className="form-stack">
              {isCreate ? (
                <>
                  <div className="form-grid">
                    <Field label="Subject type">
                      <select
                        value={subjectKind}
                        onChange={(e) => {
                          setSubjectKind(e.target.value as SubjectKind);
                          setSubjectId('');
                          setEvidence(null);
                          setSearch('');
                        }}
                      >
                        {[
                          'supplier',
                          'purchase_order',
                          'sales_order',
                          'warehouse',
                          'product',
                          'incident',
                          'department',
                        ].map((k) => (
                          <option value={k} key={k}>
                            {label(k)}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Search registered subjects">
                      <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search a name or record number"
                      />
                    </Field>
                  </div>
                  <Field
                    label="Registered business subject"
                    hint="Select an actual source record. Search narrows the first 25 matches."
                  >
                    <select
                      required
                      value={subjectId}
                      onChange={(e) => {
                        setSubjectId(e.target.value);
                        setEvidence(null);
                      }}
                    >
                      <option value="">Choose a subject…</option>
                      {selected && !subjectOptions.some((s) => s.id === selected.id) && (
                        <option value={selected.id}>
                          {selected.label} · #{selected.id}
                        </option>
                      )}
                      {subjectOptions.map((s) => (
                        <option value={s.id} key={s.id}>
                          {s.label} · #{s.id}
                        </option>
                      ))}
                    </select>
                  </Field>
                </>
              ) : (
                <>
                  <Field label={'Search current ' + (isClose ? 'escalations' : 'tasks')}>
                    <input
                      value={targetSearch}
                      onChange={(e) => setTargetSearch(e.target.value)}
                      placeholder="Search the title"
                    />
                  </Field>
                  <Field label="Current workflow target">
                    <select
                      required
                      value={targetId}
                      onChange={(e) => {
                        setTargetId(e.target.value);
                        setEvidence(null);
                      }}
                    >
                      <option value="">Choose a record…</option>
                      {target.data && !targets.data?.items.some((t) => t.id === targetId) && (
                        <option value={targetId}>{target.data.title}</option>
                      )}
                      {targets.data?.items.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.title} · {label(t.status)} · v{t.version}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {target.error && <div className="notice danger">{target.error.message}</div>}
                  {target.data && (
                    <div className="notice">
                      Target version {target.data.version} · {label(target.data.subject.kind)} #
                      {target.data.subject.entity_id} · Department #{target.data.department_id}.
                      This exact version is required at execution.
                    </div>
                  )}
                </>
              )}
              <div className="form-grid">
                <Field
                  label={
                    type === 'ASSIGN_WORKFLOW_TASK'
                      ? 'Proposed owning department'
                      : 'Owning department'
                  }
                >
                  <select
                    required
                    value={isCreate || type === 'ASSIGN_WORKFLOW_TASK' ? dept : String(owner)}
                    disabled={!isCreate && type !== 'ASSIGN_WORKFLOW_TASK'}
                    onChange={(e) => {
                      setDepartment(e.target.value);
                      setEmployee('');
                      setEvidence(null);
                    }}
                  >
                    <option value="">Choose department…</option>
                    {departments.data?.items.map((d) => (
                      <option value={d.id} key={d.id}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                </Field>
                {['CREATE_WORKFLOW_TASK', 'ASSIGN_WORKFLOW_TASK'].includes(type) && (
                  <Field label="Assigned employee">
                    <select value={employee} onChange={(e) => setEmployee(e.target.value)}>
                      <option value="">Unassigned · Department queue</option>
                      {people.data
                        ?.filter((x) => x.department_id === Number(dept))
                        .map((x) => (
                          <option value={x.id} key={x.id}>
                            {x.name}
                          </option>
                        ))}
                    </select>
                  </Field>
                )}
              </div>
            </div>
          </div>
          <div className="form-section">
            <h2>03 · Exact proposed change</h2>
            {type === 'CREATE_INTERNAL_ESCALATION' && (
              <div style={{ marginBottom: 18 }}>
                <Field label="Related workflow task (optional)">
                  <select
                    value={validRelated.some((t) => t.id === relatedTask) ? relatedTask : ''}
                    onChange={(e) => setRelatedTask(e.target.value)}
                  >
                    <option value="">No related workflow task</option>
                    {validRelated.map((t) => (
                      <option value={t.id} key={t.id}>
                        {t.title}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
            )}

            <div className="form-stack">
              {isCreate && (
                <>
                  <Field label="Title">
                    <input
                      required
                      minLength={1}
                      maxLength={200}
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="A clear internal action title"
                    />
                  </Field>
                  <Field
                    label={
                      type === 'CREATE_INTERNAL_ESCALATION'
                        ? 'Escalation reason'
                        : 'Task description'
                    }
                  >
                    <textarea
                      required
                      maxLength={4000}
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Describe the internal work and its intended scope."
                    />
                  </Field>
                </>
              )}
              {(isCreate || type === 'UPDATE_WORKFLOW_TASK_PRIORITY') && (
                <Field label="Proposed priority">
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value as typeof priority)}
                  >
                    {['low', 'normal', 'high', 'urgent'].map((x) => (
                      <option value={x} key={x}>
                        {label(x)}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              {(isCreate || type === 'UPDATE_WORKFLOW_TASK_DUE_DATE') && (
                <Field
                  label="Proposed due date (UTC)"
                  hint="An operational setting for human review. Not an inferred contractual deadline."
                >
                  <input
                    type="datetime-local"
                    value={due}
                    required
                    onChange={(e) => setDue(e.target.value)}
                  />
                </Field>
              )}
              {type === 'UPDATE_WORKFLOW_TASK_STATUS' && (
                <Field label="Proposed task status">
                  <select
                    value={selectedStatus}
                    onChange={(e) => setStatus(e.target.value as typeof status)}
                  >
                    {(target.data?.status === 'open'
                      ? ['active', 'cancelled']
                      : target.data?.status === 'blocked'
                        ? ['active', 'cancelled']
                        : ['blocked', 'completed', 'cancelled']
                    ).map((x) => (
                      <option key={x} value={x}>
                        {label(x)}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              {['ADD_WORKFLOW_TASK_NOTE', 'CLOSE_INTERNAL_ESCALATION'].includes(type) && (
                <Field label={isClose ? 'Internal resolution' : 'Note text'}>
                  <textarea
                    required
                    value={note}
                    maxLength={4000}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Recorded text is evidence and context, never an approval instruction."
                  />
                </Field>
              )}
              <Field label="Why is this action needed?">
                <textarea
                  required
                  minLength={1}
                  maxLength={1000}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain the reason for this proposal."
                />
              </Field>
              <Field label="Additional business context (optional)">
                <textarea
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  maxLength={2000}
                />
              </Field>
            </div>
          </div>
          <div className="form-section">
            <h2>04 · Supporting verified evidence</h2>
            <p className="muted" style={{ fontSize: 11, marginBottom: 16 }}>
              {requiresEvidence
                ? 'A real server-verified investigation is required for this proposal.'
                : 'Evidence is optional for this human-authored change. It never substitutes for approval.'}
            </p>
            <div className="form-stack">
              <Field label="Investigation question">
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={
                    subject?.kind === 'supplier'
                      ? 'Compare supplier delivery performance with its agreement and escalation policy.'
                      : 'Ask a supported question about the selected subject.'
                  }
                />
              </Field>
              <button
                type="button"
                className="button secondary"
                disabled={verifying || !subject || !owner}
                onClick={async () => {
                  if (!subject) return;
                  setVerifying(true);
                  setError(null);
                  try {
                    const text =
                      question.trim() ||
                      (subject.kind === 'supplier'
                        ? `Compare Supplier ${subject.entity_id} delivery performance against its contractual SLA and escalation policy.`
                        : `Investigate ${subject.kind.replaceAll('_', ' ')} ${subject.entity_id}.`);
                    setEvidence(
                      await act<Evidence>('api/v1/workflows/evidence', {
                        department_id: owner,
                        subject,
                        question: text,
                        as_of: period.end,
                      }),
                    );
                  } catch (e) {
                    setError(e instanceof Error ? e : new Error('Evidence verification failed'));
                  } finally {
                    setVerifying(false);
                  }
                }}
              >
                <ScanSearch size={15} />
                {verifying
                  ? 'Verifying real evidence…'
                  : evidence
                    ? 'Recapture verified evidence'
                    : 'Verify supporting evidence'}
              </button>
              {evidence && (
                <div className="notice success">
                  <ShieldCheck size={17} />
                  <div>
                    Verified investigation captured · Zero LLM calls
                    <p>
                      Historical cutoff {String(evidence.payload.as_of)} · Expires{' '}
                      {date(evidence.expires_at, true)}
                    </p>
                    <details>
                      <summary style={{ cursor: 'pointer' }}>
                        Inspect captured analytical response
                      </summary>
                      <div style={{ whiteSpace: 'pre-wrap', marginTop: 10 }}>
                        {String(evidence.payload.answer ?? '')}
                      </div>
                    </details>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="form-actions">
            <span className="muted">No task is created by saving a draft.</span>
            <button
              className="button primary"
              disabled={
                busy ||
                verifying ||
                !validTarget ||
                !auth.can('propose', [
                  owner,
                  ...(type === 'ASSIGN_WORKFLOW_TASK' ? [Number(dept)] : []),
                ])
              }
            >
              Review proposal
              <ArrowRight size={14} />
            </button>
          </div>
        </form>
        <div className="stack">
          <Panel title="Human-controlled by design">
            <div className="panel-body">
              <div className="notice">
                <ShieldCheck size={17} />
                <div>
                  One distinct, currently authorized human must approve this exact proposal.
                </div>
              </div>
              <dl className="detail-list">
                <dt>Proposer</dt>
                <dd>{auth.principal.username}</dd>
                <dt>Action</dt>
                <dd>{actionNames[type]}</dd>
                <dt>Source</dt>
                <dd>Human-authored proposal</dd>
                <dt>Execution</dt>
                <dd>Separate authorized request</dd>
                <dt>Side effects</dt>
                <dd>Internal workflow only</dd>
              </dl>
            </div>
          </Panel>
          <Limitations
            items={[
              'Saving creates an immutable draft only. Submission, approval and execution are separate actions.',
              'The server rechecks scope, source evidence, target version, expiry and permissions before execution.',
              'No payment, inventory adjustment, external message or automatic penalty is supported.',
            ]}
          />
        </div>
      </div>
      <Modal
        open={!!preview}
        onOpenChange={(open) => {
          if (!busy && !open) setPreview(null);
        }}
        title="Review your exact proposal"
        description="Saving creates an immutable draft. You must explicitly submit it for a distinct reviewer."
      >
        <dl className="detail-list">
          <dt>Action</dt>
          <dd>{actionNames[type]}</dd>
          <dt>Subject</dt>
          <dd>{subject ? label(subject.kind) + ' #' + subject.entity_id : '—'}</dd>
          <dt>Reason</dt>
          <dd>{preview?.reason}</dd>
          <dt>Department</dt>
          <dd>#{preview?.department_id}</dd>
          <dt>Evidence</dt>
          <dd>{evidence ? 'Verified snapshot attached' : 'Human-authored context'}</dd>
        </dl>
        <details style={{ marginTop: 20 }}>
          <summary className="text-link" style={{ cursor: 'pointer' }}>
            Inspect exact action parameters
          </summary>
          <pre className="code-payload">{JSON.stringify(preview?.action, null, 2)}</pre>
        </details>
        <div className="form-actions">
          <button className="button secondary" disabled={busy} onClick={() => setPreview(null)}>
            Back to edit
          </button>
          <button
            className="button primary"
            disabled={busy}
            onClick={async () => {
              if (!preview || busy) return;
              setBusy(true);
              setError(null);
              try {
                const result = revision
                  ? await act<Proposal>('api/v1/workflows/proposals/' + revision.id + '/revise', {
                      proposal_version: revision.version,
                      digest: revision.digest,
                      proposal: preview,
                    })
                  : await act<Proposal>('api/v1/workflows/proposals', preview);
                router.push('/proposals/' + result.id);
              } catch (e) {
                setError(e instanceof Error ? e : new Error('Draft creation failed'));
                setPreview(null);
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? 'Saving draft…' : revision ? 'Save fresh revision' : 'Save immutable draft'}
          </button>
        </div>
      </Modal>
    </>
  );
}
