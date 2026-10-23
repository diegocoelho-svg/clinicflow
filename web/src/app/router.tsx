import { createBrowserRouter, Navigate, type RouteObject } from 'react-router';
import { RequireSession } from '../features/auth/RequireSession';
import { AuthLayout } from '../features/auth/layouts/AuthLayout';
import { LoginPage } from '../features/auth/pages/LoginPage';
import { RegisterPage } from '../features/auth/pages/RegisterPage';
import { ClinicsLayout } from '../features/clinics/layouts/ClinicsLayout';
import { ClinicIndexPage } from '../features/clinics/pages/ClinicIndexPage';
import { ClinicWorkspacePage } from '../features/clinics/pages/ClinicWorkspacePage';
import { ClinicOperationsLayout } from '../features/clinics/layouts/ClinicOperationsLayout';
import { EncounterIndexPage } from '../features/encounters/pages/EncounterIndexPage';
import { EncounterBillingPage } from '../features/encounters/pages/EncounterBillingPage';
import { ChargeIndexPage } from '../features/charges/pages/ChargeIndexPage';
import { ChargeDetailPage } from '../features/charges/pages/ChargeDetailPage';
import { PatientsPage } from '../features/patients/PatientsPage';
import { ProceduresPage } from '../features/procedures/ProceduresPage';
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
                    Component: ClinicOperationsLayout,
                    children: [
                      {
                        index: true,
                        Component: ClinicWorkspacePage,
                        handle: { title: 'Espaço da clínica' },
                      },
                      {
                        path: 'atendimentos',
                        Component: EncounterIndexPage,
                        handle: { title: 'Atendimentos' },
                        children: [
                          {
                            path: ':encounterId',
                            Component: EncounterBillingPage,
                            handle: { title: 'Conferir atendimento' },
                          },
                        ],
                      },
                      {
                        path: 'pacientes',
                        Component: PatientsPage,
                        handle: { title: 'Pacientes' },
                      },
                      {
                        path: 'procedimentos',
                        Component: ProceduresPage,
                        handle: { title: 'Procedimentos e preços' },
                      },
                      {
                        path: 'cobrancas',
                        Component: ChargeIndexPage,
                        handle: { title: 'Cobranças' },
                      },
                      {
                        path: 'cobrancas/:chargeId',
                        Component: ChargeDetailPage,
                        handle: { title: 'Detalhes da cobrança' },
                      },
                    ],
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
