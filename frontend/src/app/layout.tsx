import type { Metadata } from 'next';
import { Providers } from '@/components/providers';
import './globals.css';
export const metadata: Metadata = {
  title: { default: 'OpsPilot · Operations intelligence', template: '%s · OpsPilot' },
  description:
    'Evidence-led operations intelligence and human-governed workflows for the fictional Northstar Supply workspace.',
  robots: { index: false, follow: false },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
