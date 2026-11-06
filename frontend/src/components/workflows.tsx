'use client';
import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ArrowUpRight, Plus, Search } from 'lucide-react';
import { useData, useAuth } from './providers';
import {
  PageHeading,
  Panel,
  Status,
  Loading,
  ErrorState,
  Empty,
  Pagination,
  Limitations,
} from './ui';
import { date, label, shortId } from '@/lib/format';
import { actionNames } from './proposal-form';
import type { Task, Escalation, Page, Person, Audit, Subject } from '@/lib/types';
type Kind = 'task' | 'escalation';
export function Workflows({ kind, id }: { kind: Kind; id?: string }) {
  return id ? <Detail kind={kind} id={id} /> : <Listing key={kind} kind={kind} />;
}
function Listing({ kind }: { kind: Kind }) {
  const auth = useAuth(),
    [status, setStatus] = useState(''),
    [priority, setPriority] = useState(''),
    [department, setDepartment] = useState(''),
    [assignee, setAssignee] = useState(''),
    [search, setSearch] = useState(''),
    [offset, setOffset] = useState(0);
  const departments = useData<Page<Subject>>('api/v1/workspace/subjects?kind=department&limit=100'),
    people = useData<Person[]>('api/v1/workspace/people');
  const query = new URLSearchParams({ limit: '12', offset: String(offset) });
  if (status) query.set('status', status);
  if (priority) query.set('priority', priority);
  if (department) query.set('department_id', department);
  if (assignee && kind === 'task') query.set('employee_id', assignee);
  if (search) query.set('search', search);
  const path = kind === 'task' ? 'tasks' : 'escalations',
    data = useData<Page<Task | Escalation>>('api/v1/workflows/' + path + '?' + query);
  return (
    <>
      <PageHeading
        eyebrow="CURRENT WORKFLOWS / HUMAN-GOVERNED"
        title={kind === 'task' ? 'Workflow tasks' : 'Internal escalations'}
        description={
          kind === 'task'
            ? 'Internal work, with ownership and a complete chain of accountability.'
            : 'Evidence-led internal review. No external notification or legal finding.'
        }
        actions={
          auth.can('propose') && (
            <Link
              className="button primary"
              href={
                '/proposals/new?action=' +
                (kind === 'task' ? 'CREATE_WORKFLOW_TASK' : 'CREATE_INTERNAL_ESCALATION')
              }
            >
              <Plus size={15} />
              Propose {kind}
            </Link>
          )
        }
      />
      <div className="toolbar">
        <div className="search-field">
          <Search size={15} />
          <input
            aria-label={'Search ' + path}
            placeholder={'Search ' + path + '…'}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <select
          aria-label="Workflow status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All states</option>
          {(kind === 'task'
            ? ['open', 'active', 'blocked', 'completed', 'cancelled']
            : ['open', 'closed']
          ).map((x) => (
            <option value={x} key={x}>
              {label(x)}
            </option>
          ))}
        </select>
        <select
          aria-label="Priority"
          value={priority}
          onChange={(e) => {
            setPriority(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All priorities</option>
          {['low', 'normal', 'high', 'urgent'].map((x) => (
            <option key={x} value={x}>
              {label(x)}
            </option>
          ))}
        </select>
        <select
          aria-label="Owning department"
          value={department}
          onChange={(e) => {
            setDepartment(e.target.value);
            setAssignee('');
            setOffset(0);
          }}
        >
          <option value="">All departments</option>
          {departments.data?.items.map((d) => (
            <option value={d.id} key={d.id}>
              {d.label}
            </option>
          ))}
        </select>
        {kind === 'task' && (
          <select
            aria-label="Assignee"
            value={assignee}
            onChange={(e) => {
              setAssignee(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All assignees</option>
            {people.data
              ?.filter((e) => !department || e.department_id === Number(department))
              .map((e) => (
                <option value={e.id} key={e.id}>
                  {e.name}
                </option>
              ))}
          </select>
        )}
      </div>
      {data.isPending ? (
        <Loading />
      ) : data.error ? (
        <ErrorState error={data.error} retry={() => data.refetch()} />
      ) : (
        <Panel
          title={kind === 'task' ? 'Operational work queue' : 'Internal review queue'}
          description="Current workflow records · These are separate from historical seeded tasks"
        >
          {data.data?.items.length ? (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{label(kind)}</th>
                      <th>Status</th>
                      <th>Priority</th>
                      <th>Business subject</th>
                      <th>Due (UTC)</th>
                      <th>Owner</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.data.items.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <Link href={'/' + path + '/' + row.id}>
                            {row.title}
                            <small>
                              {shortId(row.id)} · Version {row.version}
                            </small>
                          </Link>
                        </td>
                        <td>
                          <Status value={row.status} />
                        </td>
                        <td>
                          <Status value={row.priority} />
                        </td>
                        <td>
                          {label(row.subject.kind)} #{row.subject.entity_id}
                        </td>
                        <td>{date(row.due_at, true)}</td>
                        <td>
                          {'employee_id' in row && row.employee_id
                            ? (people.data?.find((x) => x.id === row.employee_id)?.name ??
                              'Employee #' + row.employee_id)
                            : (departments.data?.items.find((x) => x.id === row.department_id)
                                ?.label ?? 'Department #' + row.department_id)}
                        </td>
                        <td>
                          <Link aria-label={'Open ' + row.title} href={'/' + path + '/' + row.id}>
                            <ArrowUpRight size={15} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination total={data.data.total} offset={offset} limit={12} onChange={setOffset} />
            </>
          ) : (
            <Empty title={'No ' + path + ' in this scope'}>
              Adjust the filters or prepare a proposal. Records appear only after an approved
              execution commits.
            </Empty>
          )}
        </Panel>
      )}
    </>
  );
}
function Detail({ kind, id }: { kind: Kind; id: string }) {
  const auth = useAuth(),
    path = kind === 'task' ? 'tasks' : 'escalations',
    data = useData<Task | Escalation>('api/v1/workflows/' + path + '/' + id),
    people = useData<Person[]>('api/v1/workspace/people');
  const notes = useData<Page<{ id: string; text: string; created_at: string; actor_id: string }>>(
      'api/v1/workflows/tasks/' + id + '/notes',
      kind === 'task',
    ),
    assignments = useData<
      Page<{ id: string; employee_id: number | null; department_id: number; created_at: string }>
    >('api/v1/workflows/tasks/' + id + '/assignments', kind === 'task');
  const changes = useData<Page<Audit>>(
    'api/v1/workflows/audit?object_id=' + id + '&limit=100&newest=true',
    !!data.data,
  );
  const audit = useData<Page<Audit>>(
    'api/v1/workflows/audit?limit=100&proposal_id=' + (data.data?.proposal_id ?? ''),
    !!data.data,
  );
  if (data.isPending) return <Loading />;
  if (data.error || !data.data) return <ErrorState error={data.error} />;
  const row = data.data,
    terminal = ['completed', 'cancelled', 'closed'].includes(row.status);
  const actions =
    kind === 'task'
      ? [
          ...(!terminal
            ? [
                'ASSIGN_WORKFLOW_TASK',
                'UPDATE_WORKFLOW_TASK_STATUS',
                'UPDATE_WORKFLOW_TASK_PRIORITY',
                'UPDATE_WORKFLOW_TASK_DUE_DATE',
              ]
            : []),
          'ADD_WORKFLOW_TASK_NOTE',
        ]
      : !terminal
        ? ['CLOSE_INTERNAL_ESCALATION']
        : [];
  return (
    <>
      <Link href={'/' + path} className="text-link" style={{ marginBottom: 20 }}>
        <ArrowLeft size={13} />
        All {path}
      </Link>
      <PageHeading
        eyebrow={'CURRENT WORKFLOW / ' + shortId(id)}
        title={row.title}
        description={'Version ' + row.version + ' · Created ' + date(row.created_at, true)}
        actions={
          <>
            <Status value={row.status} />
            <Status value={row.priority} />
          </>
        }
      />
      <div className="split-detail">
        <div className="stack">
          <Panel
            title={kind === 'task' ? 'Task brief' : 'Escalation brief'}
            description="Committed state, not a proposed change"
          >
            <div className="panel-body">
              <p className="muted" style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
                {'description' in row ? row.description : row.reason}
              </p>
              {'resolution' in row && row.resolution && (
                <div className="notice success" style={{ marginTop: 20 }}>
                  Resolution: {row.resolution}
                </div>
              )}
              <dl className="detail-list" style={{ marginTop: 24 }}>
                <dt>Status</dt>
                <dd>
                  <Status value={row.status} />
                </dd>
                <dt>Due (UTC)</dt>
                <dd>{date(row.due_at, true)}</dd>
                <dt>Owning department</dt>
                <dd>Department #{row.department_id}</dd>
                {'employee_id' in row && (
                  <>
                    <dt>Assigned to</dt>
                    <dd>
                      {row.employee_id
                        ? (people.data?.find((e) => e.id === row.employee_id)?.name ??
                          'Employee #' + row.employee_id)
                        : 'Department queue'}
                    </dd>
                  </>
                )}
                <dt>Business subject</dt>
                <dd>
                  {label(row.subject.kind)} #{row.subject.entity_id}
                  {row.subject.kind === 'supplier' && (
                    <Link
                      className="text-link"
                      href={'/suppliers/' + row.subject.entity_id}
                      style={{ marginLeft: 10 }}
                    >
                      Open profile
                      <ArrowUpRight size={12} />
                    </Link>
                  )}
                </dd>
                <dt>Origin</dt>
                <dd>{label(row.source_type)}</dd>
                <dt>Last update</dt>
                <dd>{date(row.updated_at, true)}</dd>
              </dl>
            </div>
          </Panel>
          {auth.can('propose', [row.department_id]) && (
            <Panel
              title="Propose a change"
              description="Every change creates a new immutable proposal. Nothing updates directly."
            >
              <div className="panel-body" style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
                {actions.map((a) => (
                  <Link
                    className="button secondary small"
                    key={a}
                    href={
                      '/proposals/new?action=' +
                      a +
                      '&' +
                      (kind === 'task' ? 'task_id' : 'escalation_id') +
                      '=' +
                      id
                    }
                  >
                    {actionNames[a as keyof typeof actionNames]}
                  </Link>
                ))}
              </div>
            </Panel>
          )}
          {kind === 'task' && (
            <>
              <Panel title="Internal notes" description="Append-only text · No approval authority">
                {notes.data?.items.length ? (
                  notes.data.items.map((n) => (
                    <div className="note-item" key={n.id}>
                      {n.text}
                      <small>
                        {date(n.created_at, true)} · Principal {shortId(n.actor_id)}
                      </small>
                    </div>
                  ))
                ) : notes.error ? (
                  <ErrorState error={notes.error} />
                ) : (
                  <Empty title="No internal notes" />
                )}
              </Panel>
              <Panel title="Assignment history">
                {assignments.data?.items.map((a) => (
                  <div className="evidence-row" key={a.id}>
                    <div>
                      <strong>
                        {a.employee_id
                          ? (people.data?.find((e) => e.id === a.employee_id)?.name ??
                            'Employee #' + a.employee_id)
                          : 'Department queue'}
                      </strong>
                      <p>
                        Department #{a.department_id} · {date(a.created_at, true)}
                      </p>
                    </div>
                  </div>
                ))}
              </Panel>
            </>
          )}
        </div>
        <div className="stack">
          <Panel title="Provenance & execution">
            <div className="panel-body">
              <dl className="detail-list">
                <dt>Created by</dt>
                <dd>{shortId(row.created_by)}</dd>
                <dt>Proposal</dt>
                <dd>
                  <Link className="text-link" href={'/proposals/' + row.proposal_id}>
                    {shortId(row.proposal_id)}
                    <ArrowUpRight size={12} />
                  </Link>
                </dd>
                <dt>Execution</dt>
                <dd>
                  <Link className="text-link" href={'/proposals/' + row.proposal_id + '#receipt'}>
                    {shortId(row.execution_id)}
                    <ArrowUpRight size={12} />
                  </Link>
                </dd>
                <dt>Record version</dt>
                <dd>{row.version}</dd>
              </dl>
            </div>
          </Panel>
          <Panel title="Creation audit" description="Real events from the originating proposal">
            <div className="timeline">
              {audit.data?.items.map((e) => (
                <div className="timeline-item" key={e.id}>
                  <span className="timeline-dot" />
                  <div>
                    <strong>{label(e.action)}</strong>
                    <p>
                      {date(e.created_at, true)} · {e.result}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <div className="panel-body">
              <Link className="text-link" href={'/audit?proposal_id=' + row.proposal_id}>
                Inspect full audit
                <ArrowRightIcon />
              </Link>
            </div>
          </Panel>
          <Panel
            title="Record change history"
            description="Actual committed effects across proposals"
          >
            <div className="timeline">
              {changes.data?.items.map((e) => (
                <div key={e.id} className="timeline-item">
                  <span className="timeline-dot" />
                  <div>
                    <strong>{label(e.action)}</strong>
                    <p>
                      {date(e.created_at, true)} · {e.result}
                    </p>
                    {e.proposal_id && (
                      <Link className="text-link" href={'/proposals/' + e.proposal_id}>
                        Inspect change
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
          <Limitations
            items={[
              'This is internal workflow state. A completed review does not prove the underlying business issue has been resolved.',
              'Operational changes always require a new proposal and a distinct authorized human approval.',
            ]}
          />
        </div>
      </div>
    </>
  );
}
function ArrowRightIcon() {
  return <ArrowUpRight size={12} />;
}
