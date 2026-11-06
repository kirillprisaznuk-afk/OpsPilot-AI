'use client';
import dynamic from 'next/dynamic';
import { Shell } from './shell';
import { Empty, ErrorState, Loading } from './ui';
import { useReporting } from './providers';
const Dashboard = dynamic(() => import('./dashboard').then((x) => x.Dashboard), {
  loading: Loading,
});
const Analytics = dynamic(() => import('./analytics').then((x) => x.Analytics), {
  loading: Loading,
});
const Suppliers = dynamic(() => import('./suppliers').then((x) => x.Suppliers), {
  loading: Loading,
});
const Knowledge = dynamic(() => import('./knowledge').then((x) => x.Knowledge), {
  loading: Loading,
});
const Investigations = dynamic(() => import('./investigations').then((x) => x.Investigations), {
  loading: Loading,
});
const Workflows = dynamic(() => import('./workflows').then((x) => x.Workflows), {
  loading: Loading,
});
const Proposals = dynamic(() => import('./proposals').then((x) => x.Proposals), {
  loading: Loading,
});
const Governance = dynamic(() => import('./governance').then((x) => x.Governance), {
  loading: Loading,
});
export function Workspace({ route }: { route: string[] }) {
  const [section, id] = route;
  const observation = useReporting();
  if (
    observation.error &&
    (!section ||
      ['analytics', 'suppliers', 'knowledge', 'citations', 'investigations', 'copilot'].includes(
        section,
      ))
  )
    return (
      <Shell>
        <ErrorState error={observation.error} retry={observation.retry} />
      </Shell>
    );
  let content;
  if (!section) content = <Dashboard />;
  else if (section === 'analytics') content = <Analytics domain={id ?? 'procurement'} />;
  else if (section === 'suppliers') content = <Suppliers id={id} />;
  else if (['knowledge', 'citations'].includes(section))
    content = <Knowledge id={id} citation={section === 'citations'} />;
  else if (['investigations', 'copilot'].includes(section))
    content = <Investigations copilot={section === 'copilot'} />;
  else if (['tasks', 'escalations'].includes(section))
    content = <Workflows kind={section === 'tasks' ? 'task' : 'escalation'} id={id} />;
  else if (['proposals', 'approvals'].includes(section))
    content = (
      <Proposals id={id} inbox={section === 'approvals'} revision={route[2] === 'revise'} />
    );
  else if (['audit', 'settings', 'status'].includes(section))
    content = <Governance section={section} />;
  else
    content = <Empty title="Page not found">Choose a workspace section from the navigation.</Empty>;
  return <Shell>{content}</Shell>;
}
