'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, type ReactNode } from 'react';
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Building2,
  ChartNoAxesCombined,
  ChevronDown,
  FileCheck2,
  FileClock,
  LayoutDashboard,
  ListTodo,
  LogOut,
  Menu,
  PanelLeftClose,
  ScanSearch,
  Settings2,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
} from 'lucide-react';
import { useAuth, useData } from './providers';
import { date, label } from '@/lib/format';
import type { Summary } from '@/lib/types';
const groups = [
  { label: 'OVERVIEW', items: [{ href: '/', name: 'Operations overview', icon: LayoutDashboard }] },
  {
    label: 'INTELLIGENCE',
    items: [
      { href: '/analytics/procurement', name: 'Business intelligence', icon: ChartNoAxesCombined },
      { href: '/suppliers', name: 'Supplier intelligence', icon: Building2 },
      { href: '/investigations', name: 'Investigations', icon: ScanSearch },
      { href: '/knowledge', name: 'Knowledge base', icon: BookOpen },
    ],
  },
  {
    label: 'WORKFLOWS',
    items: [
      { href: '/tasks', name: 'Workflow tasks', icon: ListTodo },
      { href: '/escalations', name: 'Internal escalations', icon: TriangleAlert },
      { href: '/approvals', name: 'Approval inbox', icon: ShieldCheck },
      { href: '/proposals', name: 'Action proposals', icon: FileCheck2 },
    ],
  },
  {
    label: 'GOVERNANCE',
    items: [
      { href: '/audit', name: 'Audit trail', icon: FileClock },
      { href: '/status', name: 'System status', icon: Activity },
      { href: '/settings', name: 'Account & access', icon: Settings2 },
    ],
  },
];
export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname(),
    auth = useAuth(),
    [open, setOpen] = useState(false),
    [error, setError] = useState('');
  const summary = useData<Summary>('api/v1/workflows/summary');
  const active = (href: string) =>
    href === '/'
      ? path === '/'
      : href.includes('/analytics/')
        ? path.startsWith('/analytics/')
        : path.startsWith(href);
  const title =
    groups.flatMap((x) => x.items).find((x) => active(x.href))?.name ??
    (path === '/copilot' ? 'OpsPilot Copilot' : 'Workspace');
  return (
    <div className={'app ' + (open ? 'nav-open' : '')}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {open && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className="sidebar" aria-label="Main navigation">
        <Link className="brand" href="/" onClick={() => setOpen(false)}>
          <span className="mark">O</span>OpsPilot<span className="brand-ai">AI</span>
        </Link>
        <div className="workspace-label">
          <span className="workspace-symbol">N</span>
          <div>
            <strong>Northstar Supply</strong>
            <small>Enterprise workspace</small>
          </div>
          <ChevronDown size={13} />
        </div>
        <nav>
          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <span>{group.label}</span>
              {group.items.map((item) => (
                <Link
                  aria-current={active(item.href) ? 'page' : undefined}
                  onClick={() => setOpen(false)}
                  className={active(item.href) ? 'active' : ''}
                  href={item.href}
                  key={item.href}
                >
                  <item.icon size={18} />
                  {item.name}
                  {item.href === '/approvals' &&
                    summary.data &&
                    summary.data.pending_proposals > 0 && <b>{summary.data.pending_proposals}</b>}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <Link
          href="/copilot"
          className={'copilot-nav ' + (path === '/copilot' ? 'active' : '')}
          onClick={() => setOpen(false)}
        >
          <Sparkles size={19} />
          <span>
            OpsPilot Copilot<small>Verified Intelligence</small>
          </span>
          <ArrowUpRight size={15} />
        </Link>
        <div className="sidebar-foot">
          <span className="live-dot" />
          Local workspace<span>Synthetic enterprise</span>
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <div>
            <button
              className="icon-button nav-toggle"
              aria-label={open ? 'Close navigation' : 'Open navigation'}
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              {open ? <X size={19} /> : <Menu size={19} />}
            </button>
            <PanelLeftClose size={17} className="desktop-only" />
            <span className="breadcrumb">
              Workspace<span>/</span>
              <strong>{title}</strong>
            </span>
          </div>
          <div>
            <span className="local-label">
              <span className="live-dot" />
              Local-first
            </span>
            <Link href="/settings" className="user-menu" title="Account settings">
              <span className="avatar">{auth.principal.username.slice(0, 2).toUpperCase()}</span>
              <span>
                {auth.principal.username}
                <small>
                  {label(String(auth.principal.roles[0]?.role_code ?? 'Workspace member'))}
                </small>
              </span>
              <span className="sr-only">Account settings</span>
              <ChevronDown size={13} />
            </Link>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={async () => {
                try {
                  await auth.logout();
                } catch (e) {
                  setError(e instanceof Error ? e.message : 'Logout failed');
                }
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        {error && (
          <div className="notice danger" role="alert">
            {error}
          </div>
        )}
        <main id="main" className="main" tabIndex={-1}>
          {children}
        </main>
        <footer className="app-footer">
          <span>Northstar Supply · Entirely synthetic enterprise data</span>
          <span>Historical analytics · Current workflows · Times in UTC</span>
        </footer>
      </div>
    </div>
  );
}
export function Period({
  start,
  end,
  onChange,
}: {
  start: string;
  end: string;
  onChange: (start: string, end: string) => void;
}) {
  return (
    <div className="period-control">
      <span className="calendar-icon">▦</span>
      <label className="sr-only" htmlFor="period">
        Reporting period
      </label>
      <select
        id="period"
        value={start + '|' + end}
        onChange={(e) => {
          const [s, v] = e.target.value.split('|');
          onChange(s, v);
        }}
      >
        <option value="2025-10-01|2026-09-30">FY 2025/26 · Full observation</option>
        <option value="2026-07-01|2026-09-30">Q4 · Jul–Sep 2026</option>
        <option value="2026-04-01|2026-06-30">Q3 · Apr–Jun 2026</option>
        <option value="2026-08-01|2026-08-31">August 2026</option>
        <option value="2026-09-01|2026-09-30">September 2026</option>
      </select>
      <span className="period-detail">{date(end)}</span>
    </div>
  );
}
