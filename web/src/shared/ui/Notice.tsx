import { useEffect, useRef, type ReactNode } from 'react';

export interface NoticeData {
  message: string;
  kind: 'error' | 'success' | 'info';
  routeAlert?: boolean;
}

export function Notice({
  children,
  kind = 'error',
  routeAlert = false,
}: {
  children: ReactNode;
  kind?: NoticeData['kind'];
  routeAlert?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (kind === 'error') ref.current?.focus();
  }, [children, kind]);
  return (
    <div
      ref={ref}
      className={`notice notice-${kind}`}
      role={kind === 'error' ? 'alert' : 'status'}
      tabIndex={-1}
      data-route-alert={routeAlert || undefined}
    >
      {children}
    </div>
  );
}
