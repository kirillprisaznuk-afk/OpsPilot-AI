import { Workspace } from '@/components/workspace';
export default async function Page({ params }: { params: Promise<{ route?: string[] }> }) {
  return <Workspace route={(await params).route ?? []} />;
}
