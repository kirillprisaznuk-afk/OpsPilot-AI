'use client';
import Link from 'next/link';
import { ArrowRight, ArrowUpRight, ScanSearch, ShieldCheck } from 'lucide-react';
import { useAuth, useData, useReporting } from './providers';
import { PageHeading, Kpi, Panel, Loading, ErrorState, Empty, Status } from './ui';
import { Period } from './shell';
import { TrendChart, ComparisonChart } from './charts';
import { date, metricValue, label } from '@/lib/format';
import type { Report, Summary, Audit, Page } from '@/lib/types';
export function Dashboard() {
  const p = useReporting(),
    auth = useAuth();
  const overview = useData<Report>('api/v1/analytics/overview?' + p.query, p.ready),
    procurement = useData<Report>('api/v1/analytics/procurement?' + p.query, p.ready),
    warehouses = useData<Report>('api/v1/analytics/warehouses?limit=10&' + p.query, p.ready),
    suppliers = useData<Report>(
      'api/v1/analytics/suppliers?sort=on_time_rate&direction=asc&limit=5&' + p.query,
      p.ready,
    ),
    summary = useData<Summary>('api/v1/workflows/summary'),
    activity = useData<Page<Audit>>('api/v1/workflows/audit?limit=5&newest=true');
  if (!p.ready || overview.isPending) return <Loading />;
  if (overview.error || !overview.data)
    return <ErrorState error={overview.error} retry={() => overview.refetch()} />;
  const m = overview.data.metrics;
  return (
    <>
      <PageHeading
        eyebrow="YOUR OPERATIONS, IN FOCUS"
        title="Operations overview"
        description="The signals that matter. The evidence behind them."
        actions={
          <>
            <Period start={p.start} end={p.end} onChange={p.setPeriod} />
            <Link className="button primary" href="/investigations">
              <ScanSearch size={15} />
              Investigate
            </Link>
          </>
        }
      />
      <div className="context-line">
        <span>
          <span className="live-dot" />
          Authoritative business data
        </span>
        <span>
          {date(p.start)} — {date(p.end)}
        </span>
        <span>Historical observation · GBP</span>
      </div>
      <div className="kpi-strip">
        <Kpi
          title="Supplier on-time delivery"
          metric={m['procurement.on_time_rate']}
          href="/suppliers"
          tone="accent"
        />
        <Kpi
          title="Inventory on hand"
          metric={m['inventory.stock_on_hand']}
          href="/analytics/inventory"
        />
        <Kpi
          title="Outstanding invoices"
          metric={m['finance.outstanding_amount']}
          href="/analytics/finance"
        />
        <Kpi
          title="Unfulfilled customer units"
          metric={m['fulfilment.outstanding_units']}
          href="/analytics/fulfilment"
        />
      </div>
      <div className="dashboard-grid">
        <Panel
          title="Delivery performance"
          description="Supplier on-time rate · Monthly order cohorts"
          action={
            <Link href="/analytics/procurement" className="text-link">
              Explore
              <ArrowUpRight size={13} />
            </Link>
          }
        >
          {procurement.data ? (
            <TrendChart
              report={procurement.data}
              series={[{ key: 'on_time_rate', name: 'On-time delivery', color: '#5865df' }]}
              unit="percent"
            />
          ) : procurement.error ? (
            <ErrorState error={procurement.error} />
          ) : (
            <Loading />
          )}
        </Panel>
        <Panel
          title="Operational attention"
          description="Verified exceptions at the selected cutoff"
        >
          <Link href="/analytics/procurement" className="exception">
            <div>
              <h3>Overdue procurement commitments</h3>
              <ArrowUpRight size={14} className="arrow" />
            </div>
            <div>
              <p>Recorded outstanding order value</p>
              <strong>{metricValue(m['procurement.overdue_commitment'])}</strong>
            </div>
          </Link>
          <Link href="/analytics/finance" className="exception">
            <div>
              <h3>Overdue invoice exposure</h3>
              <ArrowUpRight size={14} className="arrow" />
            </div>
            <div>
              <p>Recorded balance · no loss estimate</p>
              <strong>{metricValue(m['finance.overdue_amount'])}</strong>
            </div>
          </Link>
          <Link href="/analytics/workforce" className="exception">
            <div>
              <h3>Overdue source tasks</h3>
              <ArrowUpRight size={14} className="arrow" />
            </div>
            <div>
              <p>Historical seeded operational backlog</p>
              <strong>{metricValue(m['workforce.overdue_tasks'])}</strong>
            </div>
          </Link>
          <div className="source-note">
            Observations flag operational concerns. They do not establish legal breach.
          </div>
        </Panel>
      </div>
      <div className="dashboard-grid">
        <Panel
          title="Suppliers to review"
          description="Lowest observed on-time rate · Complete supplier population"
          action={
            <Link href="/suppliers" className="text-link">
              All suppliers
              <ArrowRight size={13} />
            </Link>
          }
        >
          {suppliers.data ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th className="num">Due orders</th>
                    <th className="num">On-time rate</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {suppliers.data.breakdowns.map((s, i) => (
                    <tr key={s.entity_id}>
                      <td>
                        <Link href={'/suppliers/' + s.entity_id} className="entity-name">
                          <span className="rank">0{i + 1}</span>
                          <span className="entity-symbol">{s.label.slice(0, 2).toUpperCase()}</span>
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
                      <td>
                        <Link href={'/suppliers/' + s.entity_id} aria-label={'Inspect ' + s.label}>
                          <ArrowUpRight size={14} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : suppliers.error ? (
            <ErrorState error={suppliers.error} />
          ) : (
            <Loading />
          )}
        </Panel>
        <Panel title="Inventory by warehouse" description={'Stock snapshot · ' + date(p.end)}>
          {warehouses.data ? (
            <ComparisonChart
              report={warehouses.data}
              metric="stock_on_hand"
              title="Actual warehouse stock units"
            />
          ) : warehouses.error ? (
            <ErrorState error={warehouses.error} />
          ) : (
            <Loading />
          )}
        </Panel>
      </div>
      <div className="section-caption">
        <div>
          <h2>Current workspace</h2>
          <p>Live workflow records · Separate from historical business analytics</p>
        </div>
        {auth.can('propose') && (
          <Link href="/proposals/new" className="text-link">
            Prepare a proposal
            <ArrowRight size={13} />
          </Link>
        )}
      </div>
      <div className="dashboard-grid">
        <Panel
          title="Governed activity"
          description="Authenticated events in your permitted scope"
          action={
            <Link href="/audit" className="text-link">
              View audit
              <ArrowUpRight size={13} />
            </Link>
          }
        >
          {activity.data?.items.length ? (
            <div className="timeline">
              {activity.data.items
                .slice(-5)
                .reverse()
                .map((e) => (
                  <div className="timeline-item" key={e.id}>
                    <span className="timeline-dot" />
                    <div>
                      <strong>{label(e.action)}</strong>
                      <p>
                        {date(e.created_at, true)} · <Status value={e.result} />
                      </p>
                      {e.proposal_id && (
                        <Link className="text-link" href={'/proposals/' + e.proposal_id}>
                          Inspect proposal
                          <ArrowRight size={11} />
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          ) : activity.error ? (
            <ErrorState error={activity.error} />
          ) : (
            <Empty title="No activity in this scope" />
          )}
        </Panel>
        <Panel
          title="Workflow pulse"
          description={
            summary.data
              ? 'Current as of ' + date(summary.data.as_of, true)
              : 'Current operational workflow state'
          }
        >
          {summary.data ? (
            <>
              <Link className="workspace-stat" href="/approvals">
                <span>
                  <ShieldCheck size={13} style={{ display: 'inline', marginRight: 7 }} />
                  Awaiting human review
                </span>
                <strong>{summary.data.pending_proposals}</strong>
              </Link>
              <Link className="workspace-stat" href="/tasks">
                <span>Open workflow tasks</span>
                <strong>{summary.data.open_tasks}</strong>
              </Link>
              <Link className="workspace-stat" href="/escalations">
                <span>Open internal escalations</span>
                <strong>{summary.data.open_escalations}</strong>
              </Link>
              <Link className="workspace-stat" href="/audit">
                <span>Completed actions this month</span>
                <strong>{summary.data.completed_actions_this_month}</strong>
              </Link>
            </>
          ) : summary.error ? (
            <ErrorState error={summary.error} />
          ) : (
            <Loading />
          )}
        </Panel>
      </div>
    </>
  );
}
