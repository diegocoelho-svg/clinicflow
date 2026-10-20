import { createBrowserRouter, Navigate, type RouteObject } from 'react-router';
import { RequireSession } from '../features/auth/RequireSession';
import { AuthLayout } from '../features/auth/layouts/AuthLayout';
import { LoginPage } from '../features/auth/pages/LoginPage';
import { RegisterPage } from '../features/auth/pages/RegisterPage';
import { ClinicsLayout } from '../features/clinics/layouts/ClinicsLayout';
import { ClinicIndexPage } from '../features/clinics/pages/ClinicIndexPage';
import { ClinicWorkspacePage } from '../features/clinics/pages/ClinicWorkspacePage';
import { WorkspaceLayout } from './layouts/WorkspaceLayout';
import { RouteLayout } from './layouts/RouteLayout';
import { NotFoundPage } from './pages/NotFoundPage';
import { RouteErrorPage } from './pages/RouteErrorPage';

export const routes: RouteObject[] = [
  {
    Component: RouteLayout,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <Navigate to="/clinicas" replace /> },
      {
        element: <AuthLayout />,
        children: [
          { path: 'entrar', Component: LoginPage, handle: { title: 'Entrar' } },
          { path: 'cadastro', Component: RegisterPage, handle: { title: 'Criar conta' } },
        ],
      },
      {
        element: <RequireSession />,
        children: [
          {
            element: <WorkspaceLayout />,
            children: [
              {
                path: 'clinicas',
                Component: ClinicsLayout,
                children: [
                  { index: true, Component: ClinicIndexPage, handle: { title: 'Suas clínicas' } },
                  {
                    path: ':clinicId',
                    Component: ClinicWorkspacePage,
                    handle: { title: 'Espaço da clínica' },
                  },
                ],
              },
            ],
          },
        ],
      },
      { path: '*', Component: NotFoundPage, handle: { title: 'Página não encontrada' } },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(routes);
