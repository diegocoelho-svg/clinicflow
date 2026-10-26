import { Link } from 'react-router';
import { ClinicDetails } from '../components/ClinicDetails';
import { useActiveClinic } from '../hooks/useActiveClinic';

export function ClinicWorkspacePage() {
  const clinic = useActiveClinic();
  return (
    <div className="selected-panel has-selection" aria-labelledby="selected-heading">
      <ClinicDetails clinic={clinic} />
      <div className="clinic-entry-actions">
        <Link className="button primary" to={'/clinicas/' + clinic.id + '/atendimentos'}>
          Ver atendimentos
        </Link>
        <Link className="button secondary" to={'/clinicas/' + clinic.id + '/cobrancas'}>
          Ver cobranças
        </Link>
        <Link className="button secondary" to={'/clinicas/' + clinic.id + '/pagamentos'}>
          Ver pagamentos
        </Link>
      </div>
    </div>
  );
}
