import { useEffect } from 'react';
import { Outlet, useLocation, useMatches } from 'react-router';

export function RouteLayout() {
  const { key } = useLocation();
  const matches = useMatches();
  const handle = matches.at(-1)?.handle as { title?: string } | undefined;
  const title = handle?.title || 'ClinicFlow';
  useEffect(() => {
    document.title = `ClinicFlow · ${title}`;
    const main = document.querySelector('main');
    // Only session-expiry alerts persist across routes. Form alerts focus
    // themselves when shown but must not capture focus on later navigation.
    const target =
      main?.querySelector<HTMLElement>('[data-route-alert]') ||
      main?.querySelector<HTMLElement>('[data-route-heading]') ||
      main?.querySelector<HTMLElement>('[data-page-heading]');
    target?.focus();
  }, [key, title]);
  return <Outlet />;
}
