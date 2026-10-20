import { Link, useParams } from 'react-router';
import { Notice } from '../../../shared/ui/Notice';
import { ClinicDetails } from '../components/ClinicDetails';
import { useClinic } from '../hooks/useClinic';

export function ClinicWorkspacePage() {
  const { clinicId = '' } = useParams();
  const { state, retry } = useClinic(clinicId);
  return (
    <section
      className={`panel selected-panel ${state.status === 'success' ? 'has-selection' : ''}`}
      aria-labelledby="selected-heading"
      aria-busy={state.status === 'loading'}
    >
      <div className="panel-heading">
        <span className="eyebrow">ESPAÇO DA CLÍNICA</span>
        {state.status === 'success' && (
          <span className="selected-badge">
            <span className="small-dot" /> Selecionada
          </span>
        )}
      </div>
      {state.status === 'loading' ? (
        <div className="workspace-empty" role="status">
          <span className="spinner" />
          <h2 id="selected-heading" tabIndex={-1} data-route-heading>
            Abrindo sua clínica…
          </h2>
          <p>Confirmando seu acesso ao espaço selecionado.</p>
        </div>
      ) : state.status === 'error' ? (
        <div className="workspace-empty">
          <h2 id="selected-heading" tabIndex={-1} data-route-heading>
            Não foi possível abrir esta clínica
          </h2>
          <Notice>{state.message}</Notice>
          <div className="workspace-actions">
            <button className="button secondary" onClick={retry}>
              Tentar abrir novamente
            </button>
            <Link className="text-button" to="/clinicas">
              Voltar às clínicas
            </Link>
          </div>
        </div>
      ) : (
        <ClinicDetails clinic={state.clinic} />
      )}
    </section>
  );
}
