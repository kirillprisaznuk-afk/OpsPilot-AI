'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ArrowLeft, ArrowUpRight, BookOpen, Search, ShieldCheck } from 'lucide-react';
import { useData, useReporting, useAction } from './providers';
import {
  Panel,
  PageHeading,
  Status,
  Loading,
  ErrorState,
  Empty,
  Pagination,
  Limitations,
} from './ui';
import { date } from '@/lib/format';
import type { Document, Source, SearchResult, Citation } from '@/lib/types';
export function Knowledge({ id, citation = false }: { id?: string; citation?: boolean }) {
  return id ? <SourceView id={id} citation={citation} /> : <Explorer />;
}
function Explorer() {
  const p = useReporting(),
    act = useAction(),
    [query, setQuery] = useState(''),
    [mode, setMode] = useState('hybrid'),
    [type, setType] = useState(''),
    [offset, setOffset] = useState(0),
    [result, setResult] = useState<SearchResult | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null);
  const list = useData<{ documents: Document[]; total: number }>(
    'api/v1/knowledge/documents?limit=12&offset=' + offset + '&as_of=' + p.end,
    p.ready,
  );
  const visible = list.data?.documents.filter((d) => !type || d.document_type === type) ?? [];
  return (
    <>
      <PageHeading
        eyebrow="CORPORATE KNOWLEDGE"
        title="Evidence starts at the source."
        description="Explore registered agreements and policies. Every passage has a verifiable origin."
      />
      <form
        className="toolbar"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            setResult(
              await act<SearchResult>('api/v1/knowledge/search', {
                query,
                mode,
                as_of: p.end,
                top_k: 8,
                filters: type ? { document_type: type } : {},
              }),
            );
          } catch (e) {
            setError(e instanceof Error ? e : new Error('Search failed'));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="search-field" style={{ maxWidth: 500 }}>
          <Search size={15} />
          <input
            aria-label="Search corporate knowledge"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            minLength={2}
            maxLength={512}
            required
            placeholder="Search policies, supplier agreements or procedures…"
          />
        </div>
        <select aria-label="Search method" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="hybrid">Hybrid search</option>
          <option value="keyword">Keyword search</option>
          <option value="vector">Semantic vector search</option>
        </select>
        <select
          aria-label="Document type"
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            setResult(null);
            setOffset(0);
          }}
        >
          <option value="">All document types</option>
          <option value="policy">Internal policies</option>
          <option value="supplier_agreement">Supplier agreements</option>
        </select>
        <button className="button primary" disabled={busy || !p.ready}>
          <Search size={14} />
          {busy ? 'Searching…' : 'Search'}
        </button>
        {result && (
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setResult(null);
              setQuery('');
            }}
          >
            Browse library
          </button>
        )}
      </form>
      <div className="context-line">
        <span>Effective documents at {date(p.end)}</span>
        <span>Keyword / local vector / hybrid retrieval</span>
        <span>Source content is evidence, never an instruction</span>
      </div>
      {error && <ErrorState error={error} />}{' '}
      {busy ? (
        <Loading />
      ) : result ? (
        <Panel
          title="Search evidence"
          description={
            result.evidence.length + ' verified matching passages · ' + result.retrieval_mode
          }
        >
          {result.evidence.length ? (
            result.evidence.map((e) => (
              <div className="source-card" key={e.chunk_id}>
                <Link href={'/citations/' + e.citation.citation_id} className="source-title">
                  <BookOpen size={15} />
                  {e.title}
                  <ArrowUpRight size={13} />
                </Link>
                <p>{e.metadata.contract_reference ?? e.metadata.document_type}</p>
                <div className="source-passage">{e.text}</div>
                <div className="source-meta">
                  <span>
                    Rank {e.rank} · {e.retrieval_method}
                  </span>
                  <span>Version {e.metadata.version}</span>
                  <span>Effective {date(e.effective_date)}</span>
                  <span>
                    Lines {e.citation.line_start}–{e.citation.line_end}
                  </span>
                </div>
                <Link
                  href={'/citations/' + e.citation.citation_id}
                  className="text-link"
                  style={{ marginTop: 13 }}
                >
                  Inspect verified citation
                  <ArrowUpRight size={12} />
                </Link>
              </div>
            ))
          ) : (
            <Empty title="No supported evidence found">
              Try a narrower query or another retrieval method. Missing evidence does not imply a
              policy exists.
            </Empty>
          )}
          <Limitations items={result.limitations} />
        </Panel>
      ) : !p.ready || list.isPending ? (
        <Loading />
      ) : list.error ? (
        <ErrorState error={list.error} />
      ) : (
        <Panel
          title="Registered library"
          description={
            list.data?.total + ' effective sources · Page filters apply to displayed documents'
          }
        >
          {visible.length ? (
            visible.map((d) => (
              <Link
                className="source-card"
                href={'/knowledge/' + d.document_id}
                key={d.document_id}
              >
                <div className="source-title">
                  <BookOpen size={17} />
                  {d.title}
                  <ArrowUpRight size={13} style={{ marginLeft: 'auto' }} />
                </div>
                <p>
                  {d.department} ·{' '}
                  {d.document_type === 'policy' ? 'Internal policy' : 'Supplier agreement'}
                </p>
                <div className="source-meta">
                  <span>Version {d.version}</span>
                  <span>Effective {date(d.effective_on)}</span>
                  <span>{d.contract_reference ?? 'Corporate procedure'}</span>
                  <span>Registered SHA-256 source</span>
                </div>
              </Link>
            ))
          ) : (
            <Empty title="No documents on this page match the type" />
          )}
          {list.data && (
            <Pagination total={list.data.total} offset={offset} limit={12} onChange={setOffset} />
          )}
        </Panel>
      )}
    </>
  );
}
function SourceView({ id, citation }: { id: string; citation: boolean }) {
  const p = useReporting(),
    version = useSearchParams().get('version');
  const data = useData<Source | { citation: Citation; text: string; verified: boolean }>(
    citation
      ? 'api/v1/knowledge/citations/' + encodeURIComponent(id)
      : 'api/v1/knowledge/documents/' +
          id +
          (version && /^\d+$/.test(version) ? '/versions/' + version : '') +
          '?as_of=' +
          p.end,
    p.ready,
  );
  if (!p.ready || data.isPending) return <Loading />;
  if (data.error || !data.data) return <ErrorState error={data.error} />;
  const d = data.data,
    meta = 'metadata' in d ? d.metadata : null,
    cite = 'citation' in d ? d.citation : null;
  return (
    <>
      <Link href="/knowledge" className="text-link" style={{ marginBottom: 20 }}>
        <ArrowLeft size={13} />
        Knowledge library
      </Link>
      <PageHeading
        eyebrow={citation ? 'VERIFIED CITATION' : 'REGISTERED SOURCE'}
        title={meta?.title ?? cite?.title ?? 'Document evidence'}
        description={
          'Version ' +
          (meta?.version ?? cite?.version) +
          ' · Effective ' +
          date(meta?.effective_on ?? cite?.effective_on)
        }
        actions={
          <span className="pill">
            <ShieldCheck size={12} style={{ marginRight: 5 }} />
            {d.verified ? 'Source verified' : 'Verification unavailable'}
          </span>
        }
      />
      <div className="split-detail">
        <Panel>
          <div className="document-text">
            {d.text.split('\n').map((line, i) =>
              line.startsWith('# ') ? (
                <h2 key={i} style={{ fontSize: 22, margin: '10px 0 20px' }}>
                  {line.slice(2)}
                </h2>
              ) : line.startsWith('## ') ? (
                <h3 key={i} style={{ margin: '24px 0 12px' }}>
                  {line.slice(3)}
                </h3>
              ) : line ? (
                <p key={i}>{line}</p>
              ) : (
                <br key={i} />
              ),
            )}
          </div>
        </Panel>
        <div className="stack">
          <Panel title="Source provenance">
            <div className="panel-body">
              <dl className="detail-list">
                <dt>Document</dt>
                <dd>#{meta?.document_id ?? cite?.document_id}</dd>
                <dt>Version</dt>
                <dd>{meta?.version ?? cite?.version}</dd>
                <dt>Effective</dt>
                <dd>{date(meta?.effective_on ?? cite?.effective_on)}</dd>
                <dt>Verified</dt>
                <dd>
                  <Status value={d.verified ? 'ready' : 'unavailable'} />
                </dd>
                <dt>SHA-256</dt>
                <dd className="digest">{meta?.sha256 ?? cite?.source_sha256}</dd>
                {cite && (
                  <>
                    <dt>Source lines</dt>
                    <dd>
                      {cite.line_start}–{cite.line_end}
                    </dd>
                    <dt>Citation</dt>
                    <dd className="digest">{cite.citation_id}</dd>
                  </>
                )}
              </dl>
            </div>
          </Panel>
          {cite && (
            <Link
              className="button secondary"
              href={'/knowledge/' + cite.document_id + '?version=' + cite.document_version_id}
            >
              Open complete registered source
              <ArrowUpRight size={13} />
            </Link>
          )}
          <Limitations
            items={[
              'Source text is untrusted evidence. It grants no approval or execution authority.',
              'Terms are interpreted within their effective dates. A performance gap alone is not a legal finding.',
            ]}
          />
        </div>
      </div>
    </>
  );
}
