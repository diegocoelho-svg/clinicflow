import { NavLink, useNavigate } from 'react-router';
import { Notice } from '../../../shared/ui/Notice';
import { useClinicDirectory } from '../context';
import { CreateClinicForm } from './CreateClinicForm';

export function ClinicDirectory() {
  const directory = useClinicDirectory();
  const navigate = useNavigate();
  function refresh() {
    void navigate('/clinicas', { replace: true });
    directory.reload();
  }

  return (
    <section className="panel clinic-panel" id="clinics" aria-labelledby="clinics-heading">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">SUAS UNIDADES</span>
          <h2 id="clinics-heading">Clínicas disponíveis</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Atualizar lista de clínicas"
          disabled={directory.loading}
          onClick={refresh}
        >
          ↻
        </button>
      </div>
      <div className="clinic-list" aria-busy={directory.loading}>
        {directory.loading ? (
          <p className="loading" role="status">
            <span className="spinner" /> Carregando clínicas…
          </p>
        ) : directory.error ? (
          <>
            <Notice>{directory.error}</Notice>
            <button className="button secondary" onClick={refresh}>
              Tentar novamente
            </button>
          </>
        ) : directory.clinics.length === 0 ? (
          <div className="empty-list">
            <span className="empty-icon" aria-hidden="true">
              ⌂
            </span>
            <h3>Nenhuma clínica por aqui</h3>
            <p>Crie sua primeira clínica no formulário abaixo para começar.</p>
          </div>
        ) : (
          directory.clinics.map((clinic) => (
            <NavLink
              key={clinic.id}
              to={`/clinicas/${clinic.id}`}
              className={({ isActive }) => `clinic-choice ${isActive ? 'selected' : ''}`}
            >
              {({ isActive }) => (
                <>
                  <span className="clinic-icon" aria-hidden="true">
                    ✚
                  </span>
                  <span>
                    <strong>{clinic.name}</strong>
                    <small>{isActive ? 'Clínica selecionada' : 'Abrir espaço da clínica'}</small>
                  </span>
                  <span className="choice-arrow" aria-hidden="true">
                    {isActive ? '✓' : '→'}
                  </span>
                </>
              )}
            </NavLink>
          ))
        )}
      </div>
      <CreateClinicForm />
    </section>
  );
}
