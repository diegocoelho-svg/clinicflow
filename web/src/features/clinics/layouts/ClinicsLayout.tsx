import { Outlet } from 'react-router';
import { useAuth } from '../../auth/useAuth';
import { ClinicDirectoryProvider } from '../ClinicDirectoryProvider';
import { ClinicDirectory } from '../components/ClinicDirectory';
import { IdentityCard } from '../components/IdentityCard';

export function ClinicsLayout() {
  const { session } = useAuth();
  return (
    <ClinicDirectoryProvider key={session!.token}>
      <div className="page-intro">
        <div>
          <span className="eyebrow">SEU PONTO DE PARTIDA</span>
          <h1 tabIndex={-1} data-page-heading>
            Minhas clínicas
          </h1>
          <p className="muted">
            Olá, {session!.user.first_name}. Escolha uma clínica para abrir seu espaço.
          </p>
        </div>
        <span className="local-badge">Versão local</span>
      </div>
      <div className="clinic-grid">
        <ClinicDirectory />
        <div className="workspace-column">
          <Outlet />
          <IdentityCard />
        </div>
      </div>
    </ClinicDirectoryProvider>
  );
}
