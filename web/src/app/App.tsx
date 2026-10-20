import { RouterProvider } from 'react-router/dom';
import type { createBrowserRouter } from 'react-router';
import { AuthProvider } from '../features/auth/AuthProvider';

export function App({ router }: { router: ReturnType<typeof createBrowserRouter> }) {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
