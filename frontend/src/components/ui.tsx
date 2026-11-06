'use client';
import type { ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {
  AlertCircle,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  X,
  Inbox,
  Info,
} from 'lucide-react';
import Link from 'next/link';
import { label, metricValue } from '@/lib/format';
import type { Metric } from '@/lib/types';
export function Status({ value }: { value: string }) {
  return (
    <span className={'status status-' + value.toLowerCase()}>
      <i />
      {label(value)}
    </span>
  );
}
export function PageHeading({
  eyebrow = 'OPERATIONS WORKSPACE',
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}
export function Panel({
  title,
  description,
  action,
  children,
  className = '',
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={'panel ' + className}>
      {title && (
        <header className="panel-header">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
export function Kpi({
  metric,
  title,
  href,
  tone,
}: {
  metric?: Metric;
  title: string;
  href?: string;
  tone?: string;
}) {
  return (
    <div className={'kpi ' + (tone ?? '')}>
      <span>
        {title}
        {href && (
          <Link href={href} aria-label={'Explore ' + title}>
            <ArrowUpRight size={16} />
          </Link>
        )}
      </span>
      <strong>{metricValue(metric)}</strong>
      <p>
        {metric?.numerator != null && metric.denominator != null
          ? `${Number(metric.numerator).toLocaleString('en-GB')} of ${Number(metric.denominator).toLocaleString('en-GB')} observed`
          : metric?.unit === 'GBP'
            ? 'Recorded GBP · net of VAT'
            : (metric?.grain ?? 'Authoritative source metric')}
      </p>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" aria-busy="true" role="status">
      <span className="sr-only">Loading workspace data</span>
      <div className="skeleton heading" />
      <div className="skeleton-grid">
        {[0, 1, 2, 3].map((x) => (
          <div className="skeleton" key={x} />
        ))}
      </div>
      <div className="skeleton chart" />
    </div>
  );
}
export function ErrorState({ error, retry }: { error: Error | null; retry?: () => void }) {
  return (
    <div className="empty error" role="alert">
      <AlertCircle size={27} />
      <h2>Unable to load this view</h2>
      <p>{error?.message ?? 'The service is unavailable. Please try again.'}</p>
      {retry && (
        <button className="button secondary" onClick={retry}>
          <RefreshCw size={15} />
          Retry
        </button>
      )}
    </div>
  );
}
export function Empty({
  title = 'No records found',
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Inbox size={28} />
      <h3>{title}</h3>
      <p>
        {children ??
          'Try another filter or reporting period. Missing records are not reported as zero.'}
      </p>
    </div>
  );
}
export function Pagination({
  total,
  offset,
  limit,
  onChange,
}: {
  total: number;
  offset: number;
  limit: number;
  onChange: (offset: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {total ? `${offset + 1}–${Math.min(total, offset + limit)} of ${total}` : '0 records'}
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="Previous page"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          <ChevronLeft size={17} />
        </button>
        <button
          className="icon-button"
          aria-label="Next page"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          <ChevronRight size={17} />
        </button>
      </div>
    </div>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className={'modal ' + (wide ? 'wide' : '')}>
          <div className="modal-header">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>
                {description ?? 'Review the information before continuing.'}
              </Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label="Close dialog">
              <X size={19} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Limitations({ items }: { items: string[] }) {
  return items.length ? (
    <div className="limitations">
      <Info size={17} />
      <div>
        <strong>Evidence & scope</strong>
        {[...new Set(items)].map((x, i) => (
          <p key={i}>{x}</p>
        ))}
      </div>
    </div>
  ) : null;
}
export function Field({
  label: caption,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label>
      {caption}
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}
