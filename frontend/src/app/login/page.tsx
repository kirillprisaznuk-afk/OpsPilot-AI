'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowRight, ChartNoAxesCombined, ShieldCheck, ScanSearch } from 'lucide-react';
import { responseData, clearOperations } from '@/lib/api';
export default function Login() {
  const router = useRouter(),
    cache = useQueryClient();
  const [pending, setPending] = useState(false),
    [error, setError] = useState('');
  return (
    <main className="login">
      <section className="login-form">
        <Link className="brand" href="/login">
          <span className="mark">O</span>OpsPilot<span className="brand-ai">AI</span>
        </Link>
        <div className="login-inner">
          <span className="eyebrow">NORTHSTAR SUPPLY WORKSPACE</span>
          <h1>
            A clear view.
            <br />A confident next step.
          </h1>
          <p className="muted">Sign in to your operations workspace.</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (pending) return;
              setPending(true);
              setError('');
              const data = new FormData(e.currentTarget);
              try {
                await responseData(
                  await fetch('/api/session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      username: data.get('username'),
                      password: data.get('password'),
                    }),
                  }),
                  'session',
                );
                cache.clear();
                clearOperations();
                router.replace('/');
              } catch (e) {
                setError(e instanceof Error ? e.message : 'Sign-in failed.');
              } finally {
                setPending(false);
              }
            }}
          >
            <label>
              Username
              <input
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                required
                minLength={3}
                placeholder="Your workspace username"
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                minLength={12}
                placeholder="Enter your password"
              />
            </label>
            {error && (
              <div className="notice danger" role="alert">
                {error}
              </div>
            )}
            <button className="button primary full" disabled={pending}>
              {pending ? 'Signing in…' : 'Open workspace'}
              <ArrowRight size={17} />
            </button>
          </form>
          <p className="login-help">
            Use your privately generated local account. Account access is managed by your workspace
            administrator.
          </p>
        </div>
        <footer>Local-first. Evidence-led. Human-controlled.</footer>
      </section>
      <aside className="login-story">
        <div className="story-grid" />
        <div className="story-top">
          <span className="pill light">ENTERPRISE OPERATIONS INTELLIGENCE</span>
          <span>LOCAL WORKSPACE</span>
        </div>
        <div className="story-content">
          <span className="story-orbit">
            <ChartNoAxesCombined size={45} />
          </span>
          <h2>
            From operational signals
            <br />
            to accountable action.
          </h2>
          <p>
            Connect performance, source evidence and deliberate human decisions in one workspace.
          </p>
          <div className="story-features">
            <span>
              <ScanSearch size={19} />
              Verified business intelligence
            </span>
            <span>
              <ShieldCheck size={19} />
              Every action, explicitly approved
            </span>
          </div>
        </div>
        <div className="story-bottom">
          NORTHSTAR SUPPLY<span>Fictional enterprise · Synthetic data</span>
        </div>
      </aside>
    </main>
  );
}
