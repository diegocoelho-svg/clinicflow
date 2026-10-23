import { Link, Outlet, useParams } from 'react-router';
import { Notice } from '../../../shared/ui/Notice';
import { useClinic } from '../hooks/useClinic';

export function ClinicOperationsLayout() {
  const { clinicId = '' } = useParams();
  const { state, retry } = useClinic(clinicId);
  if (state.status === 'loading')
    return (
      <section className="panel operations-panel">
        <div className="loading" role="status">
          <span className="spinner" />
          Confirmando acesso à clínica…
        </div>
      </section>
    );
  if (state.status === 'error')
    return (
      <section className="panel operations-panel">
        <Notice>{state.message}</Notice>
        <button className="button secondary" onClick={retry}>
          Tentar abrir novamente
        </button>
        <Link className="text-button" to="/clinicas">
          Voltar às clínicas
        </Link>
      </section>
    );
  const clinic = state.clinic;
  return (
    <section className="panel operations-panel" aria-label={`Área de ${clinic.name}`}>
      <div className="operations-clinic">
        <span className="eyebrow">CLÍNICA SELECIONADA</span>
        <strong>{clinic.name}</strong>
      </div>
      <Outlet context={{ clinic }} />
    </section>
  );
}
