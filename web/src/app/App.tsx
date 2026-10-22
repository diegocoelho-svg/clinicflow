import type { ReactNode } from 'react';
import { RouterProvider } from 'react-router/dom';
import type { createBrowserRouter } from 'react-router';
import { AuthProvider } from '../features/auth/AuthProvider';
import { useAuth } from '../features/auth/useAuth';
import { ChargeOperationsProvider } from '../features/charges/ChargeOperationsProvider';

function SessionOperations({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  return (
    <ChargeOperationsProvider key={session?.token ?? 'anonymous'}>
      {children}
    </ChargeOperationsProvider>
  );
}

export function App({ router }: { router: ReturnType<typeof createBrowserRouter> }) {
  return (
    <AuthProvider>
      <SessionOperations>
        <RouterProvider router={router} />
      </SessionOperations>
    </AuthProvider>
  );
}
