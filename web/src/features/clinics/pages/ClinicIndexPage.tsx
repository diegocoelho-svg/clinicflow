import { useSearchParams } from 'react-router';
import { findClinicSection } from '../navigation';

export function ClinicIndexPage() {
  const [searchParams] = useSearchParams();
  const section = findClinicSection(searchParams.get('area'));
  return (
    <section className="panel selected-panel" aria-labelledby="selected-heading">
      <div className="panel-heading">
        <span className="eyebrow">{section ? section.label : 'ESPAÇO DA CLÍNICA'}</span>
      </div>
      <div className="workspace-empty">
        <div className="workspace-clinic-icon" aria-hidden="true">
          ✚
        </div>
        <h2 id="selected-heading">
          {section ? 'Em qual clínica?' : 'Um espaço para cada clínica'}
        </h2>
        <p>
          {section
            ? `Selecione uma clínica na lista para abrir ${section.label.toLocaleLowerCase('pt-BR')}.`
            : 'Selecione uma clínica na lista ao lado para consultar seus dados e começar por aqui.'}
        </p>
        <span className="empty-footnote">Seu acesso é confirmado a cada seleção.</span>
      </div>
    </section>
  );
}
