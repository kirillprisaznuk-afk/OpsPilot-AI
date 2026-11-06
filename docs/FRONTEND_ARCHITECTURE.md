# OpsPilot Stage 6 frontend architecture

The existing FastAPI/PostgreSQL application remains the domain authority. The Next.js application in `frontend/` adds a local authenticated product surface; it owns display, navigation, request coordination and frontend sessions. It does not own source calculations, proposal state, approvals, idempotency receipts or another enterprise database.

| Layer | Responsibility |
|---|---|
| `src/app` | App Router, sign-in, authenticated workspace routes, browser gateway |
| `src/components` | Shell, shared primitives/charts and separate domain modules |
| `src/lib` | Generated OpenAPI types, runtime shape checks, API errors, formatters, session and proxy policy |
| `tests` | Formatting/security unit checks and actual Edge browser scenarios |
| Compose `frontend` | Non-root Next standalone service, loopback host port 3106 |

The catch-all workspace route dispatches only named product sections. Each analytical, evidence, workflow and governance module is code split. An authenticated shell wraps these views. No protected content is hydrated before the session gate succeeds. React Query keys include the authenticated principal and canonical endpoint parameters; historical reads have a short freshness window, while approval details refresh explicitly before decisions. Logout clears client query and operation state.

Stage 5 remains Alembic head 0004. Small authenticated read projections expose real business selectors, scoped employee labels, referenced principal labels, API version, and safe admin directory records. Additive filters reuse the existing workflow read scope. No source calculations, mutation policy, DB grants or migrations changed. Existing read-only tool registry and hybrid engine are unchanged.

Next.js 16.4.5, React 19.3.1, TypeScript 5.9.3 strict, Tailwind 4.3.4, TanStack Query, Radix Dialog, Recharts 3.10.1 and Lucide 1.69.0. Pinned dependencies are in the pnpm lock. Docker builds the standalone server on Node 24 with two workers and no telemetry. See [Next.js App Router installation](https://nextjs.org/docs/app/getting-started/installation) and [Tailwind with Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs).
