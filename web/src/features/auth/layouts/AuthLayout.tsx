import { Navigate, Outlet } from 'react-router';
import { Brand } from '../../../shared/ui/Brand';
import { useAuth } from '../useAuth';

export function AuthLayout() {
  if (useAuth().session) return <Navigate to="/clinicas" replace />;
  return (
    <main className="auth-layout" id="main-content">
      <aside className="auth-story" aria-label="Sobre o ClinicFlow">
        <Brand light />
        <div className="story-copy">
          <span className="eyebrow light">CUIDADO COMEÇA COM ORGANIZAÇÃO</span>
          <p className="story-title">
            Um espaço para
            <br />
            sua clínica fluir.
          </p>
          <p>Suas clínicas e seu acesso, reunidos em um lugar simples de usar.</p>
        </div>
        <div className="care-art" aria-hidden="true">
          <div className="care-orbit" />
          <div className="care-cross">✚</div>
          <div className="care-caption">
            <span className="small-dot" /> Tudo começa por aqui
          </div>
        </div>
        <div className="story-footer">
          <span className="small-dot" /> Ambiente local · Dados fictícios
        </div>
      </aside>
      <section className="auth-content" aria-labelledby="auth-title">
        <div className="auth-topline">
          <span>SEU ESPAÇO DE TRABALHO</span>
          <span className="local-badge">Versão local</span>
        </div>
        <div className="auth-form-wrap">
          <Outlet />
        </div>
        <footer className="auth-footer">
          ClinicFlow <span>Organização para cuidar melhor.</span>
        </footer>
      </section>
    </main>
  );
}
