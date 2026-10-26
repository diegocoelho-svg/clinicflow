import { useCallback } from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '../../../shared/api/errors';
import { dateTime, resourceId } from '../../../shared/format/date';
import { money } from '../../../shared/format/money';
import { useResource } from '../../../shared/hooks/useResource';
import { Notice } from '../../../shared/ui/Notice';
import { PageHeading } from '../../../shared/ui/PageHeading';
import { ResourceMessage } from '../../../shared/ui/ResourceMessage';
import { useActiveClinic } from '../../clinics/hooks/useActiveClinic';
import { useClinicAccess } from '../../clinics/hooks/useClinicAccess';
import { chargeApi } from '../api';
import { CancelChargeForm } from '../components/CancelChargeForm';
import { ChargeItems } from '../components/ChargeItems';
import { ChargeStatusBadge } from '../components/ChargeStatusBadge';
import { useChargeOperations } from '../context';

export function ChargeDetailPage() {
  const { chargeId } = useParams();
  const clinic = useActiveClinic();
  const id = resourceId(chargeId);
  return id === null ? (
    <>
      <PageHeading level={1} focusKey="invalid-charge">
        Cobrança indisponível
      </PageHeading>
      <Notice>Escolha uma cobrança da lista desta clínica.</Notice>
    </>
  ) : (
    <ChargeDetail key={`${clinic.id}:${id}`} id={id} />
  );
}

function ChargeDetail({ id }: { id: number }) {
  const clinic = useActiveClinic();
  const auth = useClinicAccess();
  const { revision, refresh } = useChargeOperations();
  const load = useCallback(
    async (signal: AbortSignal) => {
      const charge = await chargeApi.get(clinic.id, id, auth, signal);
      if (charge.id !== id || charge.clinic !== clinic.id)
        throw new ApiError(
          0,
          'Não foi possível conferir esta cobrança. Atualize antes de continuar.',
        );
      return charge;
    },
    [clinic.id, id, auth],
  );
  const key = `${clinic.id}:charge:${id}:${revision}`;
  const { state, retry } = useResource(key, load);
  const charge = state.status === 'success' ? state.data : undefined;
  return (
    <>
      <Link className="back-link" to={`/clinicas/${clinic.id}/cobrancas`}>
        ← Voltar às cobranças
      </Link>
      <header className="operations-heading">
        <PageHeading level={1} focusKey={key}>
          Cobrança #{id}
        </PageHeading>
        <button
          className="button secondary"
          disabled={state.status === 'loading'}
          onClick={refresh}
        >
          Atualizar cobrança
        </button>
      </header>
      <ResourceMessage state={state} label="cobrança" retry={retry} />
      {charge && (
        <>
          <div className="charge-total">
            <strong className="money">{money(charge.amount)}</strong>
            <ChargeStatusBadge status={charge.status} />
          </div>
          {charge.status === 'PAID' && (
            <Link
              className="button secondary"
              to={`/clinicas/${clinic.id}/pagamentos?busca=${charge.id}`}
            >
              Ver pagamento conciliado
            </Link>
          )}
          {charge.status === 'NO_PAYMENT_REQUIRED' && (
            <p className="muted">Esta cobrança tem valor zero. Não há pagamento a receber.</p>
          )}
          <dl className="record-details">
            <div>
              <dt>Atendimento</dt>
              <dd>
                <Link to={`/clinicas/${clinic.id}/atendimentos/${charge.encounter}`}>
                  Atendimento #{charge.encounter}
                </Link>
              </dd>
            </div>
            <div>
              <dt>Emitida em</dt>
              <dd>{dateTime(charge.created_at)}</dd>
            </div>
            <div>
              <dt>Emitida por</dt>
              <dd>Usuário #{charge.created_by}</dd>
            </div>
          </dl>
          <section className="billing-section" aria-labelledby="issued-items-heading">
            <h3 id="issued-items-heading">Itens desta cobrança</h3>
            <p className="muted">Valores e quantidades registrados na emissão.</p>
            <ChargeItems items={charge.items} caption="Itens preservados na cobrança" />
          </section>
          {charge.status === 'CANCELLED' && (
            <section
              className="billing-section cancellation-audit"
              aria-labelledby="cancellation-heading"
            >
              <h3 id="cancellation-heading">Registro de cancelamento</h3>
              <dl className="record-details">
                <div>
                  <dt>Cancelada em</dt>
                  <dd>
                    {charge.cancelled_at ? dateTime(charge.cancelled_at) : 'Data indisponível'}
                  </dd>
                </div>
                <div>
                  <dt>Cancelada por</dt>
                  <dd>Usuário #{charge.cancelled_by}</dd>
                </div>
              </dl>
              <p className="cancellation-reason">{charge.cancellation_reason}</p>
              <Link
                className="button secondary"
                to={`/clinicas/${clinic.id}/atendimentos/${charge.encounter}`}
              >
                Corrigir atendimento e emitir novamente
              </Link>
            </section>
          )}
          <CancelChargeForm charge={charge} />
        </>
      )}
    </>
  );
}
