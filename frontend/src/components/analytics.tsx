'use client';
import { useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';
import { useData, useReporting } from './providers';
import { PageHeading, Panel, Kpi, Loading, ErrorState, Empty, Pagination, Limitations } from './ui';
import { Period } from './shell';
import { ComparisonChart, TrendChart } from './charts';
import { label, metricValue } from '@/lib/format';
import type { Report, Page, Subject, Person } from '@/lib/types';
const domains = {
  procurement: {
    title: 'Procurement intelligence',
    description: 'Original promises, observed receipts and outstanding commitments.',
    keys: ['purchase_orders', 'on_time_rate', 'open_commitment', 'overdue_commitment'],
    trend: 'purchase_orders',
    segment: 'on_time_rate',
  },
  inventory: {
    title: 'Inventory & warehouses',
    description: 'Historical stock availability, warehouse exposure and recorded shortages.',
    keys: ['stock_on_hand', 'received_units', 'dispatched_units', 'outstanding_shortage_units'],
    trend: 'stock_on_hand',
    segment: 'stock_on_hand',
  },
  fulfilment: {
    title: 'Customer fulfilment',
    description: 'Customer dispatch promises and observed fulfilment. Supplier SLAs are separate.',
    keys: ['sales_orders', 'on_time_rate', 'outstanding_units', 'overdue_outstanding_orders'],
    trend: 'dispatched_units',
    segment: 'outstanding_units',
  },
  finance: {
    title: 'Financial intelligence',
    description: 'Recorded GBP amounts and exposure. Unrecorded loss and profit remain unknown.',
    keys: ['invoice_value', 'paid_amount', 'outstanding_amount', 'additional_costs'],
    trend: 'invoice_value',
    segment: 'outstanding_amount',
  },
  workforce: {
    title: 'Workforce & incidents',
    description: 'Original seeded operational work. New workflow tasks are tracked separately.',
    keys: ['open_tasks', 'overdue_tasks', 'completed_tasks', 'completion_rate'],
    trend: 'tasks_created',
    segment: 'overdue_tasks',
  },
  incidents: {
    title: 'Incident intelligence',
    description: 'Recorded operational incidents, resolution and related corrective work.',
    keys: ['total_incidents', 'open_incidents', 'critical_open_incidents', 'resolved_in_period'],
    trend: 'new_incidents',
    segment: 'open_incidents',
  },
};
export function Analytics({ domain }: { domain: string }) {
  const config = domains[domain as keyof typeof domains];
  return config ? (
    <Domain key={domain} domain={domain as keyof typeof domains} />
  ) : (
    <Empty title="Analytical domain not available" />
  );
}
function Domain({ domain }: { domain: keyof typeof domains }) {
  const c = domains[domain],
    p = useReporting(),
    [offset, setOffset] = useState(0),
    [warehouse, setWarehouse] = useState(''),
    [product, setProduct] = useState(''),
    [productSearch, setProductSearch] = useState(''),
    [department, setDepartment] = useState(''),
    [employee, setEmployee] = useState('');
  const warehouses = useData<Page<Subject>>('api/v1/workspace/subjects?kind=warehouse&limit=100'),
    products = useData<Page<Subject>>(
      'api/v1/workspace/subjects?kind=product&limit=25&search=' + encodeURIComponent(productSearch),
      domain === 'inventory',
    ),
    departments = useData<Page<Subject>>('api/v1/workspace/subjects?kind=department&limit=100'),
    people = useData<Person[]>('api/v1/workspace/people');
  const query = new URLSearchParams(p.query);
  query.set('limit', '10');
  query.set('offset', String(offset));
  if (warehouse) query.set('warehouse_id', warehouse);
  if (product) query.set('product_id', product);
  if (department) query.set('department_id', department);
  if (employee) query.set('employee_id', employee);
  const data = useData<Report>('api/v1/analytics/' + domain + '?' + query, p.ready);
  const comparison = useData<Report>(
    'api/v1/analytics/warehouses?' + query,
    p.ready && domain === 'inventory',
  );
  const recordsKind =
    domain === 'procurement'
      ? 'purchase_order'
      : domain === 'fulfilment'
        ? 'sales_order'
        : domain === 'incidents'
          ? 'incident'
          : null;
  const records = useData<Page<Subject>>(
    'api/v1/workspace/subjects?kind=' +
      (recordsKind ?? 'supplier') +
      '&limit=10&offset=' +
      offset +
      (warehouse ? '&warehouse_id=' + warehouse : '') +
      '&start_date=' +
      p.start +
      '&end_date=' +
      p.end,
    !!recordsKind && p.ready,
  );
  return (
    <>
      <PageHeading
        eyebrow="BUSINESS INTELLIGENCE"
        title={c.title}
        description={c.description}
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
      <nav className="tabs" aria-label="Analytical domains">
        {Object.entries(domains).map(([key, x]) => (
          <Link key={key} href={'/analytics/' + key} className={key === domain ? 'active' : ''}>
            {x.title
              .replace(' intelligence', '')
              .replace('Customer ', '')
              .replace(' & incidents', '')}
          </Link>
        ))}
      </nav>
      <div className="toolbar">
        {['inventory', 'fulfilment', 'procurement'].includes(domain) && (
          <select
            aria-label="Warehouse"
            value={warehouse}
            onChange={(e) => {
              setWarehouse(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All warehouses</option>
            {warehouses.data?.items.map((w) => (
              <option value={w.id} key={w.id}>
                {w.label.replace(' (synthetic)', '')}
              </option>
            ))}
          </select>
        )}
        {domain === 'inventory' && (
          <>
            <input
              aria-label="Search registered products"
              value={productSearch}
              onChange={(e) => {
                setProductSearch(e.target.value);
                setProduct('');
                setOffset(0);
              }}
              placeholder="Find a product…"
            />
            <select
              aria-label="Product"
              value={product}
              onChange={(e) => {
                setProduct(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All products</option>
              {products.data?.items.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </select>
          </>
        )}
        {domain === 'workforce' && (
          <>
            <select
              aria-label="Department"
              value={department}
              onChange={(e) => {
                setDepartment(e.target.value);
                setEmployee('');
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
            <select
              aria-label="Employee"
              value={employee}
              onChange={(e) => {
                setEmployee(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All permitted employees</option>
              {people.data
                ?.filter((x) => !department || x.department_id === Number(department))
                .map((x) => (
                  <option value={x.id} key={x.id}>
                    {x.name}
                  </option>
                ))}
            </select>
          </>
        )}
      </div>
      {!p.ready || data.isPending ? (
        <Loading />
      ) : data.error || !data.data ? (
        <ErrorState error={data.error} retry={() => data.refetch()} />
      ) : (
        <>
          <div className="kpi-strip">
            {c.keys.map((key) => (
              <Kpi key={key} title={label(key)} metric={data.data.metrics[key]} />
            ))}
          </div>
          <div className="two-col">
            <Panel
              title="Monthly observations"
              description="Exact source metrics · No invented observations"
            >
              <TrendChart
                report={data.data}
                series={[{ key: c.trend, name: label(c.trend), color: '#5865df' }]}
                unit={data.data.metrics[c.trend]?.unit}
              />
            </Panel>
            <Panel
              title={
                domain === 'inventory' ? 'Warehouse stock comparison' : 'Population comparison'
              }
              description={
                domain === 'inventory'
                  ? 'Selected warehouse and product scope · Historical period'
                  : 'Current page of source segments'
              }
            >
              {domain === 'inventory' && comparison.data ? (
                <ComparisonChart
                  report={comparison.data}
                  metric="stock_on_hand"
                  title="Warehouse stock"
                />
              ) : domain === 'finance' ? (
                <>
                  <ComparisonChart
                    report={data.data}
                    metric={c.segment}
                    title="Outstanding invoice amount by supplier"
                    segmentLink={(segment) =>
                      segment.entity_id ? '/suppliers/' + segment.entity_id : undefined
                    }
                  />
                  <Pagination
                    total={data.data.total_segments}
                    offset={offset}
                    limit={10}
                    onChange={setOffset}
                  />
                </>
              ) : (
                <ComparisonChart report={data.data} metric={c.segment} title={label(c.segment)} />
              )}
            </Panel>
          </div>
          <div className="section-caption">
            <div>
              <h2>Auditable measurements</h2>
              <p>Definitions and population retained from the analytics engine.</p>
            </div>
          </div>
          <Panel>
            <div className="table-scroll">
              <table className="metric-table">
                <thead>
                  <tr>
                    <th>Measure</th>
                    <th className="num">Value</th>
                    <th>Basis & scope</th>
                    <th className="num">Observation volume</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.data.metrics).map(([key, m]) => (
                    <tr key={key}>
                      <td>{label(key)}</td>
                      <td className="num">{metricValue(m)}</td>
                      <td>
                        {m.grain}
                        <small>{m.time_basis}</small>
                      </td>
                      <td className="num">
                        {m.numerator != null && m.denominator != null
                          ? `${m.numerator} / ${m.denominator}`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          {recordsKind && (
            <>
              <div className="section-caption">
                <h2>
                  {recordsKind === 'purchase_order'
                    ? 'Purchase orders'
                    : recordsKind === 'sales_order'
                      ? 'Sales orders'
                      : 'Recorded incidents'}
                </h2>
                <small className="muted">
                  Selected recorded-date cohort · Stored source status, not historical status
                  reconstruction
                </small>
              </div>
              <Panel>
                {records.data ? (
                  <>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Record</th>
                            <th>State</th>
                            <th>Original promise</th>
                            <th>Investigation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {records.data.items.map((row) => (
                            <tr key={row.id}>
                              <td>
                                {label(recordsKind)} #{row.id}
                              </td>
                              <td>{row.status}</td>
                              <td>{row.promised_on ?? 'Not applicable'}</td>
                              <td>
                                <Link
                                  className="text-link"
                                  href={
                                    '/investigations?question=' +
                                    encodeURIComponent(
                                      'Investigate ' +
                                        recordsKind.replace('_', ' ') +
                                        ' ' +
                                        row.id +
                                        '.',
                                    )
                                  }
                                >
                                  Inspect evidence
                                  <ArrowUpRight size={12} />
                                </Link>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <Pagination
                      total={records.data.total}
                      offset={offset}
                      limit={10}
                      onChange={setOffset}
                    />
                  </>
                ) : records.error ? (
                  <ErrorState error={records.error} />
                ) : (
                  <Loading />
                )}
              </Panel>
            </>
          )}
          <Limitations items={data.data.limitations} />
        </>
      )}
    </>
  );
}
