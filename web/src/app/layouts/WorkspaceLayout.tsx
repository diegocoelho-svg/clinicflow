import { NavLink, Outlet } from 'react-router';
import { useAuth } from '../../features/auth/useAuth';
import { Brand } from '../../shared/ui/Brand';

export function WorkspaceLayout() {
  const { session, logout } = useAuth();
  const user = session!.user;
  return (
    <div className="workspace-layout">
      <a className="skip-link" href="#workspace-main">
        Pular para o conteúdo
      </a>
      <aside className="app-sidebar">
        <Brand light />
        <div className="sidebar-section">ESPAÇO DE TRABALHO</div>
        <nav aria-label="Navegação principal">
          <NavLink className="nav-link active" to="/clinicas">
            <span aria-hidden="true">▦</span> Minhas clínicas <span className="nav-dot" />
          </NavLink>
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow light">UM PASSO DE CADA VEZ</span>
          <p>
            Organize seu acesso.
            <br />
            Escolha sua clínica.
            <br />
            Continue por aqui.
          </p>
        </div>
        <div className="sidebar-bottom">
          <span className="small-dot" /> Ambiente local
        </div>
      </aside>
      <div className="workspace-body">
        <header className="app-header">
          <div className="breadcrumb">
            Seu espaço <span>/</span> <strong>Clínicas</strong>
          </div>
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
