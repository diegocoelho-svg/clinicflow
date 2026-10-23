import { useCallback, useState } from 'react';
import { Link } from 'react-router';
import { dateTime } from '../../../shared/format/date';
import { money } from '../../../shared/format/money';
import { useResource } from '../../../shared/hooks/useResource';
import { PageHeading } from '../../../shared/ui/PageHeading';
import { ResourceMessage } from '../../../shared/ui/ResourceMessage';
import { useActiveClinic } from '../../clinics/hooks/useActiveClinic';
import { useClinicAccess } from '../../clinics/hooks/useClinicAccess';
import { chargeApi } from '../api';
import { ChargeStatusBadge } from '../components/ChargeStatusBadge';
import { useChargeOperations } from '../context';
import { statusLabel, type ChargeStatus } from '../types';

export function ChargeIndexPage() {
  const clinic = useActiveClinic();
  const auth = useClinicAccess();
  const { revision, refresh } = useChargeOperations();
  const [filter, setFilter] = useState<ChargeStatus | 'ALL'>('ALL');
  const load = useCallback(
    (signal: AbortSignal) => chargeApi.list(clinic.id, auth, signal),
    [clinic.id, auth],
  );
  const key = `${clinic.id}:charges:${revision}`;
  const { state, retry } = useResource(key, load);
  const filtered =
    state.status === 'success'
      ? [...state.data].reverse().filter((charge) => filter === 'ALL' || charge.status === filter)
      : [];
  return (
    <>
      <header className="operations-heading">
        <div>
          <PageHeading level={1} focusKey={key}>
            Cobranças
          </PageHeading>
          <p className="muted">Consulte os valores emitidos e o histórico de cancelamentos.</p>
        </div>
        <button
          className="button secondary"
          disabled={state.status === 'loading'}
          onClick={refresh}
        >
          Atualizar cobranças
        </button>
      </header>
      <div className="field charge-filter">
        <label htmlFor="charge-status-filter">Situação da cobrança</label>
        <select
          id="charge-status-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value as ChargeStatus | 'ALL')}
        >
          <option value="ALL">Todas as situações</option>
          {(['PENDING', 'NO_PAYMENT_REQUIRED', 'CANCELLED', 'PAID'] as const).map((status) => (
            <option key={status} value={status}>
              {statusLabel(status)}
            </option>
          ))}
        </select>
      </div>
      <ResourceMessage state={state} label="cobranças" retry={retry} />
      {state.status === 'success' &&
        (filtered.length === 0 ? (
          <div className="operations-empty">
            <h3>
              {state.data.length === 0
                ? 'Nenhuma cobrança emitida'
                : 'Nenhuma cobrança nesta situação'}
            </h3>
            <p>Abra um atendimento para conferir os itens e emitir uma cobrança.</p>
            <Link className="button secondary" to={`/clinicas/${clinic.id}/atendimentos`}>
              Ver atendimentos
            </Link>
          </div>
        ) : (
          <ul className="charge-list">
            {filtered.map((charge) => (
              <li key={charge.id}>
                <div>
                  <h3>
                    <Link to={`/clinicas/${clinic.id}/cobrancas/${charge.id}`}>
                      Cobrança #{charge.id}
                    </Link>
                  </h3>
                  <Link
                    className="record-parent-link"
                    to={`/clinicas/${clinic.id}/atendimentos/${charge.encounter}`}
                  >
                    Atendimento #{charge.encounter}
                  </Link>
                  <small>{dateTime(charge.created_at)}</small>
                </div>
                <div>
                  <strong className="charge-list-amount money">{money(charge.amount)}</strong>
                  <ChargeStatusBadge status={charge.status} />
                </div>
              </li>
            ))}
          </ul>
        ))}
    </>
  );
}
