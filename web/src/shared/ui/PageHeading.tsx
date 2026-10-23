import { useEffect, useRef, type ReactNode } from 'react';

export function PageHeading({
  children,
  focusKey,
  level = 2,
}: {
  children: ReactNode;
  focusKey: string;
  level?: 1 | 2;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [focusKey]);
  const Heading = level === 1 ? 'h1' : 'h2';
  return (
    <Heading ref={heading} tabIndex={-1} data-route-heading>
      {children}
    </Heading>
  );
}
