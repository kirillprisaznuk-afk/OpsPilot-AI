import type { Metric } from './types';
export function label(value: string) {
  const text = value === value.toUpperCase() ? value.toLowerCase() : value;
  return text
    .replaceAll('_', ' ')
    .replaceAll('.', ' · ')
    .replace(/^./, (x) => x.toUpperCase());
}
export function amount(value: number | string | null | undefined, unit = 'count') {
  if (
    value === null ||
    value === undefined ||
    (typeof value === 'string' && !value.trim()) ||
    !Number.isFinite(Number(value))
  )
    return 'Not available';
  const n = Number(value);
  if (unit === 'GBP')
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
      maximumFractionDigits: 2,
    }).format(n);
  if (unit === 'percent')
    return new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 }).format(n) + '%';
  if (unit === 'percentage_points')
    return new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 }).format(n) + ' pp';
  return (
    new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 }).format(n) +
    (unit === 'units' ? ' units' : unit === 'days' ? ' days' : '')
  );
}
export function metricValue(m?: Metric) {
  return !m || m.status !== 'available' ? 'Not available' : amount(m.value, m.unit);
}
export function date(value?: string | null, time = false) {
  if (!value || !Number.isFinite(Date.parse(value))) return '—';
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    ...(time ? { hour: '2-digit', minute: '2-digit' } : {}),
    timeZone: 'UTC',
  }).format(new Date(value));
}
export function shortId(value?: string | null) {
  return value ? value.slice(0, 8).toUpperCase() : '—';
}
