import { Link, Outlet, useMatch, useNavigate, useSearchParams } from 'react-router';
import { useAuth } from '../../auth/useAuth';
import { ClinicDirectory } from '../components/ClinicDirectory';
import { IdentityCard } from '../components/IdentityCard';
import { useClinicDirectory } from '../context';
import { findClinicSection } from '../navigation';

function ClinicSwitcher({ clinicId, section }: { clinicId: string; section: string }) {
  const directory = useClinicDirectory();
  const navigate = useNavigate();
  return (
    <div className="clinic-module-context">
      <Link className="text-button" to="/clinicas">
        ← Minhas clínicas
      </Link>
      <div className="clinic-switcher">
        <label htmlFor="current-clinic">Clínica atual</label>
        <select
          id="current-clinic"
          value={clinicId}
          disabled={directory.loading}
          onChange={(event) => void navigate(`/clinicas/${event.target.value}/${section}`)}
        >
          {!directory.clinics.some((clinic) => String(clinic.id) === clinicId) && (
            <option value={clinicId}>Clínica #{clinicId}</option>
          )}
          {directory.clinics.map((clinic) => (
            <option key={clinic.id} value={clinic.id}>
              {clinic.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export function ClinicsLayout() {
  const { session } = useAuth();
  const operationRoute = useMatch('/clinicas/:clinicId/*');
  const section = operationRoute?.params['*']?.split('/')[0];
  const [searchParams] = useSearchParams();
  const requestedSection = !operationRoute
    ? findClinicSection(searchParams.get('area'))
    : undefined;
  const modulePage = Boolean(section);
  return modulePage ? (
    <>
      <ClinicSwitcher clinicId={operationRoute!.params.clinicId!} section={section!} />
      <Outlet />
    </>
  ) : (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">SEU PONTO DE PARTIDA</span>
          <h1 tabIndex={-1} data-page-heading>
            {requestedSection?.label ?? 'Minhas clínicas'}
          </h1>
          <p className="muted">
            {requestedSection
              ? 'Escolha uma clínica para acessar esta área.'
              : `Olá, ${session!.user.first_name}. Escolha uma clínica para abrir seu espaço.`}
          </p>
        </div>
        <span className="local-badge">Versão local</span>
      </div>
      <div className={`clinic-grid ${operationRoute ? 'operations-grid' : ''}`}>
        <ClinicDirectory />
        <div className="workspace-column">
          <Outlet />
          <IdentityCard />
        </div>
      </div>
    </>
  );
}
