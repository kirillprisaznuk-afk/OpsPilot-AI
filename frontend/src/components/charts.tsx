'use client';
import Link from 'next/link';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Report } from '@/lib/types';
import { amount, date, label } from '@/lib/format';
import { Empty } from './ui';
export function TrendChart({
  report,
  series,
  unit = 'count',
}: {
  report: Report;
  series: { key: string; name: string; color: string }[];
  unit?: string;
}) {
  const rows: ({ period: string; name: string } & Record<string, string | number | null>)[] =
    report.trends.map((point) => ({
      period: date(point.window.observation_end),
      name: new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' }).format(
        new Date(point.window.observation_end),
      ),
      ...Object.fromEntries(
        series.map((s) => [
          s.key,
          point.metrics[s.key]?.status === 'available' && point.metrics[s.key].value != null
            ? Number(point.metrics[s.key].value)
            : null,
        ]),
      ),
    }));
  if (!rows.length)
    return (
      <Empty title="No time-series observations">
        No trend is returned for this scope. The summary remains available.
      </Empty>
    );
  return (
    <>
      <div
        className="chart-wrap"
        role="img"
        aria-label={
          series.map((x) => x.name).join(' and ') +
          ', monthly source observations. Exact values in the table below.'
        }
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={rows} margin={{ top: 12, right: 17, left: 0, bottom: 6 }}>
            <defs>
              {series.map((s, i) => (
                <linearGradient
                  key={s.key}
                  id={'fill' + i + report.domain}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor={s.color} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={s.color} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid vertical={false} strokeDasharray="3 4" />
            <XAxis dataKey="name" axisLine={false} tickLine={false} dy={10} />
            <YAxis
              axisLine={false}
              tickLine={false}
              width={48}
              domain={unit === 'percent' ? [0, 100] : [0, 'auto']}
              tickFormatter={(v) =>
                Number(v) >= 1000
                  ? new Intl.NumberFormat('en-GB', { notation: 'compact' }).format(Number(v))
                  : String(v)
              }
            />
            <Tooltip
              contentStyle={{
                borderRadius: 8,
                border: '1px solid #e5e8ef',
                fontSize: 11,
                boxShadow: '0 4px 20px #1e315212',
              }}
              formatter={(value) => amount(typeof value === 'number' ? value : null, unit)}
              labelFormatter={(_, payload) => String(payload[0]?.payload?.period ?? '')}
            />
            {series.map((s, i) => (
              <Area
                type="monotone"
                key={s.key}
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                strokeWidth={2}
                fill={'url(#fill' + i + report.domain + ')'}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-legend">
        {series.map((s) => (
          <span key={s.key}>
            <i style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
      <details className="chart-data">
        <summary>View exact source observations</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Period ending</th>
                {series.map((s) => (
                  <th key={s.key} className="num">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.period}>
                  <td>{r.period}</td>
                  {series.map((s) => (
                    <td className="num" key={s.key}>
                      {amount(r[s.key] as number | null, unit)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
export function ComparisonChart({
  report,
  metric,
  title,
  segmentLink,
}: {
  report: Report;
  metric: string;
  title: string;
  segmentLink?: (segment: Report['breakdowns'][number]) => string | undefined;
}) {
  const rows = report.breakdowns.map((segment) => ({
    id: segment.entity_id,
    name: segment.label.replace('Northstar ', '').replace(' (synthetic)', ''),
    value: segment.metrics[metric]?.value == null ? null : Number(segment.metrics[metric].value),
    href: segmentLink?.(segment),
  }));
  const unit = report.breakdowns[0]?.metrics[metric]?.unit ?? 'count';
  if (!rows.length) return <Empty title="No comparison population" />;
  return (
    <>
      <div
        className="chart-wrap"
        role="img"
        aria-label={title + '. Exact source values in the following table.'}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 14, right: 18, left: 0, bottom: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 4" />
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
            <YAxis
              domain={[0, 'auto']}
              axisLine={false}
              tickLine={false}
              width={48}
              tickFormatter={(v) =>
                new Intl.NumberFormat('en-GB', { notation: 'compact' }).format(Number(v))
              }
            />
            <Tooltip
              formatter={(v) => amount(typeof v === 'number' ? v : null, unit)}
              contentStyle={{ fontSize: 11, borderRadius: 7 }}
            />
            <Bar
              dataKey="value"
              name={label(metric)}
              fill="#6c7bcb"
              radius={[4, 4, 0, 0]}
              maxBarSize={43}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="chart-data">
        <summary>View exact comparison values</summary>
        <table>
          <thead>
            <tr>
              <th>Segment</th>
              <th className="num">{label(metric)}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id ?? row.name}>
                <td>
                  {row.href ? (
                    <Link className="text-link" href={row.href}>
                      {row.name}
                    </Link>
                  ) : (
                    row.name
                  )}
                </td>
                <td className="num">{amount(row.value, unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}
