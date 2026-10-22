import { useEffect, useRef } from 'react';
import type { Clinic } from '../types';

const formatter = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long' });
function dateLabel(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Data indisponível' : formatter.format(date);
}

export function ClinicDetails({ clinic }: { clinic: Clinic }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [clinic]);
  return (
    <>
      <div className="workspace-clinic-icon" aria-hidden="true">
        ✚
      </div>
      <h2 id="selected-heading" ref={heading} tabIndex={-1} data-route-heading>
        {clinic.name}
      </h2>
      <p className="muted">
        Confira atendimentos, emita cobranças e acompanhe o histórico da clínica.
      </p>
      <dl className="clinic-details">
        <div>
          <dt>Identificação</dt>
          <dd>Clínica #{clinic.id}</dd>
        </div>
        <div>
          <dt>Criada em</dt>
          <dd>{dateLabel(clinic.created_at)}</dd>
        </div>
        <div>
          <dt>Última atualização</dt>
          <dd>{dateLabel(clinic.updated_at)}</dd>
        </div>
      </dl>
      <div className="workspace-info">
        <strong>Você está no espaço desta clínica</strong>
        <p>Acesse os atendimentos para conferir os itens ou consulte as cobranças já emitidas.</p>
      </div>
    </>
  );
}
