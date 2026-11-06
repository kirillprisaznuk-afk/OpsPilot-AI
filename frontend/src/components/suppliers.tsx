'use client';
import Link from 'next/link';
import { useState } from 'react';
import { ArrowLeft, ArrowUpRight, Plus, Search, ScanSearch } from 'lucide-react';
import { useData, useReporting, useAuth } from './providers';
import {
  Panel,
  PageHeading,
  Kpi,
  Status,
  Pagination,
  Loading,
  ErrorState,
  Empty,
  Limitations,
} from './ui';
import { Period } from './shell';
import { TrendChart } from './charts';
import { amount, date, metricValue } from '@/lib/format';
import type { Report, Page, Subject, Document } from '@/lib/types';
export function Suppliers({ id }: { id?: string }) {
  return id ? <SupplierProfile id={id} /> : <Directory />;
}
function Directory() {
  const p = useReporting(),
    [search, setSearch] = useState(''),
    [offset, setOffset] = useState(0),
    [sort, setSort] = useState('on_time_rate'),
    [category, setCategory] = useState('');
  const directory = useData<Page<Subject>>(
    'api/v1/workspace/subjects?kind=supplier&limit=10&offset=' +
      offset +
      '&search=' +
      encodeURIComponent(search),
  );
  const ranking = useData<Report>(
    'api/v1/analytics/suppliers?limit=10&offset=' +
      offset +
      '&sort=' +
      sort +
      '&direction=' +
      (sort === 'on_time_rate' ? 'asc' : 'desc') +
      (category ? '&supplier_category=' + category : '') +
      '&' +
      p.query,
    p.ready,
  );
  return (
    <>
      <PageHeading
        eyebrow="INTELLIGENCE / SUPPLIERS"
        title="Supplier intelligence"
        description="Understand the partner. Inspect the performance. Follow the evidence."
        actions={
          <Period
            start={p.start}
            end={p.end}
            onChange={(s, e) => {
              p.setPeriod(s, e);
              setOffset(0);
            }}
          />
        }
      />
      <nav className="tabs" aria-label="Supplier views">
        <span
          className="active"
          style={{
            padding: '12px 0',
            fontSize: 12,
            color: 'var(--accent)',
            borderBottom: '2px solid var(--accent)',
          }}
        >
          Performance & directory
        </span>
      </nav>
      <div className="toolbar">
        <div className="search-field">
          <Search size={15} />
          <input
            aria-label="Search suppliers"
            placeholder="Search supplier name or ID…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        {!search && (
          <>
            <select
              aria-label="Rank suppliers by"
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setOffset(0);
              }}
            >
              <option value="on_time_rate">Lowest on-time rate</option>
              <option value="overdue_commitment">Highest overdue commitment</option>
              <option value="purchase_orders">Most purchase orders</option>
            </select>
            <select
              aria-label="Supplier category"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All categories</option>
              <option value="office">Office</option>
              <option value="industrial">Industrial</option>
              <option value="technology">Technology</option>
            </select>
          </>
        )}
      </div>
      {search ? (
        <Panel title="Supplier directory" description="Matches across actual registered suppliers">
          {directory.isPending ? (
            <Loading />
          ) : directory.error ? (
            <ErrorState error={directory.error} />
          ) : directory.data?.items.length ? (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Supplier</th>
                      <th>Status</th>
                      <th>Profile</th>
                    </tr>
                  </thead>
                  <tbody>
                    {directory.data.items.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <Link href={'/suppliers/' + s.id}>
                            {s.label}
                            <small>Supplier #{s.id}</small>
                          </Link>
                        </td>
                        <td>
                          <Status value={s.status ?? 'unknown'} />
                        </td>
                        <td>
                          <Link className="text-link" href={'/suppliers/' + s.id}>
                            Open profile
                            <ArrowUpRight size={13} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                total={directory.data.total}
                limit={10}
                offset={offset}
                onChange={setOffset}
              />
            </>
          ) : (
            <Empty />
          )}
        </Panel>
      ) : ranking.isPending ? (
        <Loading />
      ) : ranking.error || !ranking.data ? (
        <ErrorState error={ranking.error} retry={() => ranking.refetch()} />
      ) : (
        <>
          <div className="kpi-strip">
            <Kpi
              title="Observed on-time delivery"
              metric={ranking.data.metrics.on_time_rate}
              tone="accent"
            />
            <Kpi title="Due purchase orders" metric={ranking.data.metrics.due_orders} />
            <Kpi title="Overdue commitment" metric={ranking.data.metrics.overdue_commitment} />
            <Kpi
              title="Additional recorded costs"
              metric={ranking.data.metrics.additional_linked_costs}
            />
          </div>
          <Panel
            title="Performance ranking"
            description={
              'Complete scoped population: ' +
              ranking.data.total_segments +
              ' suppliers · Undefined rates remain undefined'
            }
          >
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th className="num">Due orders</th>
                    <th className="num">On-time rate</th>
                    <th className="num">Applicable target</th>
                    <th className="num">Observed gap</th>
                    <th className="num">Overdue GBP</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {ranking.data.breakdowns.map((s, i) => {
                    const contract = ranking.data.contracts.find(
                      (c) => c.supplier_id === s.entity_id,
                    );
                    return (
                      <tr key={s.entity_id}>
                        <td>
                          <Link href={'/suppliers/' + s.entity_id} className="entity-name">
                            <span className="rank">{String(offset + i + 1).padStart(2, '0')}</span>
                            <span className="entity-symbol">
                              {s.label.slice(0, 2).toUpperCase()}
                            </span>
                            <span>
                              {s.label.replace(' (synthetic)', '')}
                              <small>Supplier #{s.entity_id} · Synthetic</small>
                            </span>
                          </Link>
                        </td>
                        <td className="num">{metricValue(s.metrics.due_orders)}</td>
                        <td className="num">
                          <div className="performance">
                            <span className="performance-bar warning">
                              <span
                                style={{
                                  width:
                                    Math.min(100, Number(s.metrics.on_time_rate.value ?? 0)) + '%',
                                }}
                              />
                            </span>
                            {metricValue(s.metrics.on_time_rate)}
                          </div>
                        </td>
                        <td className="num">
                          {contract ? amount(contract.target_percent, 'percent') : 'Not available'}
                        </td>
                        <td className="num">
                          {contract
                            ? amount(contract.gap_percentage_points, 'percentage_points')
                            : 'Not available'}
                        </td>
                        <td className="num">{metricValue(s.metrics.overdue_commitment)}</td>
                        <td>
                          <Link href={'/suppliers/' + s.entity_id} aria-label={'Open ' + s.label}>
                            <ArrowUpRight size={14} />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              total={ranking.data.total_segments}
              limit={10}
              offset={offset}
              onChange={setOffset}
            />
            <div className="source-note">
              Below-target observations are operational concerns. No legal breach or automatic
              penalty is inferred.
            </div>
          </Panel>
          <Limitations items={ranking.data.limitations} />
        </>
      )}
    </>
  );
}
function SupplierProfile({ id }: { id: string }) {
  const p = useReporting(),
    auth = useAuth();
  const report = useData<Report>('api/v1/analytics/suppliers/' + id + '?' + p.query, p.ready),
    identity = useData<Page<Subject>>(
      'api/v1/workspace/subjects?kind=supplier&search=' + encodeURIComponent(id),
    ),
    docs = useData<{ documents: Document[]; total: number }>(
      'api/v1/knowledge/documents?limit=100&as_of=' + p.end,
      p.ready,
    ),
    orders = useData<Page<Subject>>(
      'api/v1/workspace/subjects?kind=purchase_order&supplier_id=' +
        encodeURIComponent(id) +
        '&limit=8&start_date=' +
        p.start +
        '&end_date=' +
        p.end,
      p.ready,
    );
  if (!p.ready || report.isPending) return <Loading />;
  if (report.error || !report.data) return <ErrorState error={report.error} />;
  const name = identity.data?.items.find((x) => x.id === Number(id))?.label ?? 'Supplier #' + id,
    m = report.data.metrics,
    contracts = report.data.contracts;
  const relevant =
    docs.data?.documents.filter((x) => x.supplier_id === Number(id) || x.code === 'POL-001') ?? [];
  return (
    <>
      <Link className="text-link" style={{ marginBottom: 20 }} href="/suppliers">
        <ArrowLeft size={13} />
        Supplier intelligence
      </Link>
      <PageHeading
        eyebrow={'SUPPLIER #' + id + ' / SYNTHETIC ENTERPRISE'}
        title={name.replace(' (synthetic)', '')}
        description="Performance observations, agreement evidence and operational context."
        actions={<Period start={p.start} end={p.end} onChange={p.setPeriod} />}
      />
      <div className="toolbar">
        <Link
          className="button secondary"
          href={
            '/investigations?question=' +
            encodeURIComponent(
              'Compare Supplier ' +
                id +
                ' delivery performance against its contractual SLA and escalation policy.',
            )
          }
        >
          <ScanSearch size={14} />
          Investigate supplier
        </Link>
        {auth.can('propose') && (
          <Link
            className="button primary"
            href={'/proposals/new?subject_kind=supplier&subject_id=' + id}
          >
            <Plus size={15} />
            Prepare internal review
          </Link>
        )}
      </div>
      <div className="kpi-strip">
        <Kpi title="Observed on-time rate" metric={m.on_time_rate} tone="accent" />
        <Kpi title="Due purchase orders" metric={m.due_orders} />
        <Kpi title="Late orders" metric={m.late_orders} />
        <Kpi title="Overdue commitments" metric={m.overdue_commitment} />
      </div>
      <div className="split-detail">
        <div className="stack">
          <Panel
            title="Delivery performance"
            description="Monthly observations under the original purchase promises"
          >
            <TrendChart
              report={report.data}
              series={[{ key: 'on_time_rate', name: 'Observed on-time rate', color: '#5865df' }]}
              unit="percent"
            />
          </Panel>
          <Panel
            title="Related purchase orders"
            description="Selected recorded-date cohort · Stored states and original promises"
          >
            {orders.data ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Order</th>
                      <th>State</th>
                      <th>Original promise</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {orders.data.items.map((o) => (
                      <tr key={o.id}>
                        <td>PO #{o.id}</td>
                        <td>
                          <Status value={o.status ?? 'unknown'} />
                        </td>
                        <td>{date(o.promised_on)}</td>
                        <td>
                          <Link
                            className="text-link"
                            href={
                              '/investigations?question=' +
                              encodeURIComponent('Investigate purchase order ' + o.id + '.')
                            }
                          >
                            Investigate
                            <ArrowUpRight size={12} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : orders.error ? (
              <ErrorState error={orders.error} />
            ) : (
              <Loading />
            )}
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Agreement & target" description="Applicable registered supplier terms">
            {contracts.length ? (
              contracts.map((c) => (
                <div key={c.contract_id} className="contract-meter">
                  <div className="meter-labels">
                    <strong>{c.reference}</strong>
                    <span>Operational SLA</span>
                  </div>
                  <div className="meter">
                    <span
                      style={{
                        width: Math.max(0, Math.min(100, Number(c.observed_percent ?? 0))) + '%',
                      }}
                    />
                    <i style={{ left: Math.min(100, Number(c.target_percent)) + '%' }} />
                  </div>
                  <div className="meter-labels">
                    <span>Observed {amount(c.observed_percent, 'percent')}</span>
                    <span>Target {amount(c.target_percent, 'percent')}</span>
                  </div>
                  <dl className="detail-list" style={{ marginTop: 23 }}>
                    <dt>Observed gap</dt>
                    <dd>{amount(c.gap_percentage_points, 'percentage_points')}</dd>
                    <dt>Observation</dt>
                    <dd>
                      {c.on_time_orders} / {c.due_orders} due orders
                    </dd>
                    <dt>Effective</dt>
                    <dd>{date(c.effective_date)}</dd>
                    <dt>Expires</dt>
                    <dd>{date(c.expires_on)}</dd>
                  </dl>
                </div>
              ))
            ) : (
              <Empty title="No applicable target" />
            )}
            <div className="source-note">
              Below-target performance does not establish legal breach. Inspect the registered
              terms.
            </div>
          </Panel>
          <Panel
            title="Supporting documents"
            description="Registered agreements and escalation procedure"
          >
            {relevant.map((d) => (
              <Link
                href={'/knowledge/' + d.document_id}
                className="source-card"
                key={d.document_id}
              >
                <div className="source-title">
                  {d.code}
                  <ArrowUpRight size={13} />
                </div>
                <p>{d.title}</p>
                <div className="source-meta">
                  <span>Version {d.version}</span>
                  <span>Effective {date(d.effective_on)}</span>
                </div>
              </Link>
            ))}
          </Panel>
        </div>
      </div>
      <Limitations items={report.data.limitations} />
    </>
  );
}
