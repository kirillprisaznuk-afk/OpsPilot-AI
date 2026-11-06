'use client';
import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowRight,
  ArrowUpRight,
  Building2,
  Network,
  ShieldCheck,
  Sparkles,
  Wallet,
} from 'lucide-react';
import { useAction, useAuth, useReporting } from './providers';
import { Panel, PageHeading, Status, ErrorState, Limitations, Loading } from './ui';
import { Period } from './shell';
import { amount, date, label } from '@/lib/format';
import type { Hybrid, JsonRecord } from '@/lib/types';
const suggestions = [
  {
    title: 'Supplier performance',
    text: 'Compare Supplier 1 delivery performance against its contractual SLA and escalation policy.',
    icon: Building2,
  },
  {
    title: 'Follow the operational chain',
    text: 'Why did customer order 1 experience a fulfilment delay?',
    icon: Network,
  },
  {
    title: 'Recorded financial exposure',
    text: 'Show recorded costs for suppliers 5 and 8.',
    icon: Wallet,
  },
];
const scalar = (value: unknown) =>
  typeof value === 'string' || typeof value === 'number' ? String(value) : '';
export function Investigations({ copilot = false }: { copilot?: boolean }) {
  const params = useSearchParams(),
    p = useReporting(),
    auth = useAuth(),
    act = useAction();
  const [question, setQuestion] = useState(params.get('question') ?? ''),
    [result, setResult] = useState<Hybrid | null>(null),
    [history, setHistory] = useState<Hybrid[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null);
  async function investigate(value: string) {
    if (busy || !value.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const next = await act<Hybrid>('api/v1/hybrid/query', {
        question: value,
        mode: 'DETERMINISTIC',
        as_of: p.end,
        start_date: p.start,
        end_date: p.end,
        ...(copilot && result?.conversation_id ? { conversation_id: result.conversation_id } : {}),
      });
      if (result) setHistory((h) => [...h, result]);
      setResult(next);
      setQuestion('');
    } catch (e) {
      setError(e instanceof Error ? e : new Error('Investigation failed'));
    } finally {
      setBusy(false);
    }
  }
  const metricFacts =
    result?.evidence_graph.facts.filter(
      (f) => f.verified && f.kind === 'metric' && 'metric' in f.value,
    ) ?? [];
  const relevantMetrics = metricFacts
    .filter((f) =>
      [
        'on_time_rate',
        'gap_percentage_points',
        'outstanding_amount',
        'overdue_amount',
        'outstanding_units',
        'stock_on_hand',
        'overdue_tasks',
        'additional_costs',
      ].some((key) => scalar(f.value.metric).endsWith(key)),
    )
    .slice(0, 6);
  const facts = relevantMetrics.length ? relevantMetrics : metricFacts.slice(0, 6);
  return (
    <>
      <PageHeading
        eyebrow={copilot ? 'OPSPILOT / VERIFIED INTELLIGENCE' : 'BUSINESS INVESTIGATIONS'}
        title={copilot ? 'Your operations, in conversation.' : 'Follow the evidence.'}
        description={
          copilot
            ? 'A grounded business copilot. Read-only intelligence with explicit source evidence.'
            : 'Connect business metrics, source documents and related operational records.'
        }
        actions={
          <Period
            start={p.start}
            end={p.end}
            onChange={(s, e) => {
              p.setPeriod(s, e);
              setResult(null);
              setHistory([]);
            }}
          />
        }
      />
      <div className="investigation-welcome">
        <span className="eyebrow">
          {copilot ? 'A CLEARER PICTURE. A BETTER QUESTION.' : 'FROM QUESTION TO VERIFIED FINDINGS'}
        </span>
        <h2>
          {copilot
            ? 'What would you like to understand?'
            : 'Investigate the signal. Understand the context.'}
        </h2>
        <p>
          Ask about your suppliers, inventory, customer fulfilment or recorded costs. Findings come
          from real historical analytics and registered sources.
        </p>
        <form
          className="prompt-box"
          onSubmit={(e) => {
            e.preventDefault();
            void investigate(question);
          }}
        >
          <label className="sr-only" htmlFor="business-question">
            Business question
          </label>
          <textarea
            id="business-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Compare Supplier 1 performance against its agreement…"
            maxLength={2000}
            minLength={2}
            required
          />
          <div>
            <small>
              <ShieldCheck size={12} style={{ display: 'inline', marginRight: 5 }} />
              Verified Intelligence · Zero LLM calls
            </small>
            <button className="button primary" disabled={busy || !p.ready}>
              {busy ? 'Investigating…' : copilot ? 'Ask OpsPilot' : 'Run investigation'}
              <ArrowRight size={14} />
            </button>
          </div>
        </form>
      </div>
      {!result && !busy && (
        <div className="suggestions">
          {suggestions.map((s) => (
            <button className="suggestion" onClick={() => setQuestion(s.text)} key={s.title}>
              <s.icon size={20} />
              <strong>{s.title}</strong>
              {s.text}
            </button>
          ))}
        </div>
      )}
      <div className="context-line">
        <span>
          <Sparkles size={12} style={{ display: 'inline', marginRight: 5 }} />
          Deterministic grounded analysis
        </span>
        <span>As of {date(p.end)}</span>
        <span>Local LLM: experimental / blocked</span>
        {copilot && result && (
          <button
            className="button secondary small"
            disabled={busy}
            onClick={() => {
              setResult(null);
              setHistory([]);
              setQuestion('');
              setError(null);
            }}
          >
            New conversation
          </button>
        )}
      </div>
      {error && <ErrorState error={error} />} {busy && <Loading />}
      {history.length > 0 && (
        <details className="panel" style={{ marginBottom: 18 }}>
          <summary style={{ padding: 17, fontSize: 11, cursor: 'pointer' }}>
            {history.length} previous question{history.length > 1 ? 's' : ''} in this conversation
          </summary>
          {history.map((r) => (
            <div className="source-card" key={r.request_id}>
              <strong>{r.question}</strong>
              <p>
                {label(r.status)} · {r.usage.tool_calls} read-only tools · {r.usage.llm_calls} LLM
                calls
              </p>
              <details>
                <summary style={{ fontSize: 10, marginTop: 9 }}>Inspect preserved response</summary>
                <div className="response-prose">{r.answer}</div>
              </details>
            </div>
          ))}
        </details>
      )}
      {result && !busy && (
        <>
          <Panel>
            <div className="question-heading">
              <div>
                <h2>{result.question}</h2>
                <p>
                  {result.resolved_entities.map((e) => e.label).join(' · ') ||
                    'No resolved business entity'}{' '}
                  · As of {date(result.as_of)}
                </p>
              </div>
              <Status value={result.status} />
            </div>
            <div className="panel-body" style={{ paddingTop: 20 }}>
              {facts.length > 0 && (
                <div className="findings">
                  {facts.map((f) => {
                    const value = f.value as JsonRecord;
                    return (
                      <div key={f.fact_id}>
                        <span className="eyebrow" style={{ letterSpacing: 0.6, fontSize: 9 }}>
                          {label(scalar(value.metric).split('.').pop() ?? 'Observation')}
                        </span>
                        <strong>
                          {amount(
                            typeof value.value === 'number' || typeof value.value === 'string'
                              ? value.value
                              : null,
                            scalar(value.unit),
                          )}
                        </strong>
                        <small>
                          {f.subject?.label ?? 'Scoped source metric'}
                          {value.numerator != null && value.denominator != null
                            ? ' · ' + scalar(value.numerator) + ' / ' + scalar(value.denominator)
                            : ''}
                        </small>
                      </div>
                    );
                  })}
                </div>
              )}
              {result.evidence_graph.missing.length > 0 && (
                <div className="notice">
                  Uncovered scope: {result.evidence_graph.missing.join(' · ')}
                </div>
              )}
              {!facts.length ||
              ['refused', 'clarification_required', 'insufficient_evidence'].includes(
                result.status,
              ) ? (
                <div className="response-prose" style={{ padding: 0 }}>
                  {result.answer}
                </div>
              ) : (
                <>
                  <h3 style={{ margin: '22px 0 10px' }}>Source-grounded findings</h3>
                  {result.key_findings.length ? (
                    result.key_findings.map((f, i) => (
                      <p key={i} className="muted" style={{ fontSize: 12, marginBottom: 9 }}>
                        {scalar((f as unknown as JsonRecord).summary) ||
                          scalar((f as unknown as JsonRecord).finding) ||
                          scalar((f as unknown as JsonRecord).statement)}
                      </p>
                    ))
                  ) : (
                    <p className="muted" style={{ fontSize: 12 }}>
                      Verified metrics and linked evidence are presented above and below. Partial
                      findings retain their actual scope limitations.
                    </p>
                  )}
                  <details style={{ marginTop: 16 }}>
                    <summary className="text-link" style={{ cursor: 'pointer' }}>
                      Read complete analytical response
                    </summary>
                    <div className="response-prose">{result.answer}</div>
                  </details>
                </>
              )}
              <Limitations items={result.limitations} />
            </div>
            <div className="source-note">
              {result.usage.tool_calls} read-only tool calls · {result.usage.llm_calls} LLM calls ·{' '}
              {label(result.response_origin)} · No action executed
            </div>
          </Panel>
          <div className="two-col" style={{ marginTop: 20 }}>
            <Panel
              title="Registered source evidence"
              description="Citations resolve to actual registered document versions"
            >
              {result.citations.length ? (
                result.citations.map((raw, i) => {
                  const c = raw as JsonRecord;
                  const id = scalar(c.citation_id);
                  return (
                    <Link
                      key={id || i}
                      className="source-card"
                      href={'/citations/' + encodeURIComponent(id)}
                    >
                      <div className="source-title">
                        {scalar(c.title) || 'Registered source'}
                        <ArrowUpRight size={13} />
                      </div>
                      <p>
                        Version {scalar(c.version)} · Effective {date(scalar(c.effective_on))}
                      </p>
                      <div className="source-meta">
                        <span>
                          Lines {scalar(c.line_start)}–{scalar(c.line_end)}
                        </span>
                        <span>Verified reference</span>
                      </div>
                    </Link>
                  );
                })
              ) : (
                <div className="empty">
                  <p>No document citation was returned for this scope.</p>
                </div>
              )}
            </Panel>
            <Panel
              title="Operational relationships"
              description="Actual linked records, with evidence class retained"
            >
              {result.evidence_graph.facts
                .filter((f) => f.kind === 'relationship')
                .slice(0, 8)
                .map((f) => (
                  <div className="evidence-row" key={f.fact_id}>
                    <Network size={15} />
                    <div>
                      <strong>{label(scalar(f.value.relationship_type) || 'Linked record')}</strong>
                      <p>
                        {scalar(f.value.entity_type)} {scalar(f.value.entity_id)} →{' '}
                        {scalar(f.value.related_entity_type)} {scalar(f.value.related_entity_id)}
                      </p>
                      <small>
                        {scalar(f.value.evidence_class)} · {scalar(f.value.source_reference)}
                      </small>
                    </div>
                  </div>
                ))}
              {!result.evidence_graph.facts.some((f) => f.kind === 'relationship') && (
                <div className="empty">
                  <p>No relationship evidence was requested or established.</p>
                </div>
              )}
            </Panel>
          </div>
          {auth.can('propose') &&
            result.resolved_entities.some((e) => e.entity_type === 'supplier') && (
              <Panel
                className=""
                title="A deliberate next step"
                description="Prepare a proposed internal review. This does not create a task or grant approval."
              >
                <div className="panel-body">
                  <Link
                    className="button secondary"
                    href={
                      '/proposals/new?subject_kind=supplier&subject_id=' +
                      result.resolved_entities.find((e) => e.entity_type === 'supplier')?.entity_id
                    }
                  >
                    Prepare internal review task
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </Panel>
            )}
        </>
      )}
    </>
  );
}
