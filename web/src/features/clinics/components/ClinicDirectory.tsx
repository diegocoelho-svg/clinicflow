import { NavLink, useNavigate, useSearchParams } from 'react-router';
import { Notice } from '../../../shared/ui/Notice';
import { useClinicDirectory } from '../context';
import { findClinicSection } from '../navigation';
import { CreateClinicForm } from './CreateClinicForm';

export function ClinicDirectory() {
  const directory = useClinicDirectory();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedSection = findClinicSection(searchParams.get('area'));
  function refresh() {
    void navigate(requestedSection ? `/clinicas?area=${requestedSection.path}` : '/clinicas', {
      replace: true,
    });
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
              to={
                requestedSection
                  ? `/clinicas/${clinic.id}/${requestedSection.path}`
                  : `/clinicas/${clinic.id}`
              }
              className={({ isActive }) => `clinic-choice ${isActive ? 'selected' : ''}`}
            >
              {({ isActive }) => (
                <>
                  <span className="clinic-icon" aria-hidden="true">
                    ✚
                  </span>
                  <span>
                    <strong>{clinic.name}</strong>
                    <small>
                      {isActive
                        ? 'Clínica selecionada'
                        : requestedSection
                          ? `Abrir ${requestedSection.label.toLocaleLowerCase('pt-BR')}`
                          : 'Abrir espaço da clínica'}
                    </small>
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
