import { Link, Outlet, useMatch, useSearchParams } from 'react-router';
import { useAuth } from '../../features/auth/useAuth';
import { ClinicDirectoryProvider } from '../../features/clinics/ClinicDirectoryProvider';
import { clinicSections, findClinicSection } from '../../features/clinics/navigation';
import { Brand } from '../../shared/ui/Brand';
import { WorkspaceBreadcrumb } from './WorkspaceBreadcrumb';

export function WorkspaceLayout() {
  const { session } = useAuth();
  return (
    <ClinicDirectoryProvider key={session!.token}>
      <WorkspaceContent />
    </ClinicDirectoryProvider>
  );
}

function WorkspaceContent() {
  const { session, logout } = useAuth();
  const user = session!.user;
  const clinicRoute = useMatch('/clinicas/:clinicId/*');
  const clinic = clinicRoute?.params.clinicId;
  const [searchParams] = useSearchParams();
  const section = findClinicSection(
    clinic ? clinicRoute?.params['*']?.split('/')[0] : searchParams.get('area'),
  );
  const linkClass = (active: boolean) => `nav-link${active ? ' active' : ''}`;
  return (
    <div className="workspace-layout">
      <a className="skip-link" href="#workspace-main">
        Pular para o conteúdo
      </a>
      <aside className="app-sidebar">
        <Brand light />
        <div className="sidebar-section">ESPAÇO DE TRABALHO</div>
        <nav aria-label="Navegação principal">
          <Link
            className={linkClass(!clinic && !section)}
            aria-current={!clinic && !section ? 'page' : undefined}
            to="/clinicas"
          >
            <span aria-hidden="true">▦</span> Minhas clínicas
          </Link>
          {clinicSections.map((item) => (
            <Link
              key={item.path}
              className={linkClass(section?.path === item.path)}
              aria-current={section?.path === item.path ? 'page' : undefined}
              to={clinic ? `/clinicas/${clinic}/${item.path}` : `/clinicas?area=${item.path}`}
            >
              <span aria-hidden="true">{item.icon}</span> {item.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow light">SUA ROTINA, NO MESMO LUGAR</span>
          <p>
            {clinic
              ? 'Cadastre pacientes, defina os preços e acompanhe os atendimentos pelo menu.'
              : 'Abra uma área pelo menu e escolha a clínica para continuar.'}
          </p>
        </div>
        <div className="sidebar-bottom">
          <span className="small-dot" /> Ambiente local
        </div>
      </aside>
      <div className="workspace-body">
        <header className="app-header">
          <WorkspaceBreadcrumb />
          <div className="account">
            <span className="avatar" aria-hidden="true">
              {user.first_name.charAt(0)}
              {user.last_name.charAt(0)}
            </span>
            <div>
              <strong>
                {user.first_name} {user.last_name}
              </strong>
              <small>@{user.username}</small>
            </div>
            <button className="button subtle" onClick={logout}>
              Sair
            </button>
          </div>
        </header>
        <main className="workspace-main" id="workspace-main">
          <Outlet />
          <footer className="workspace-footer">
            <span>ClinicFlow · Organização para cuidar melhor.</span>
            <span>Somente dados fictícios neste ambiente.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
