import { Link, useOutletContext, useParams } from 'react-router';
import { dateTime, resourceId } from '../../shared/format/date';
import { money } from '../../shared/format/money';
import { Notice } from '../../shared/ui/Notice';
import { useActiveClinic } from '../clinics/hooks/useActiveClinic';
import { discrepancyLabel, eventStatusLabels, type PaymentWorkspaceData } from './types';

export function PaymentDetailPage() {
  const { paymentId } = useParams();
  const clinic = useActiveClinic();
  const { payments } = useOutletContext<PaymentWorkspaceData>();
  const payment = payments.find((record) => record.id === resourceId(paymentId));
  if (!payment)
    return <Notice>Pagamento indisponível nesta clínica. Escolha um registro da lista.</Notice>;
  return (
    <>
      <div className="charge-total">
        <strong className="money">{money(payment.amount, payment.currency)}</strong>
        <span className="charge-status status-paid">Conciliado</span>
      </div>
      <dl className="record-details">
        <div>
          <dt>Referência do pagamento</dt>
          <dd className="payment-detail-reference">{payment.payment_reference}</dd>
        </div>
        <div>
          <dt>Pago em</dt>
          <dd>{dateTime(payment.paid_at)}</dd>
        </div>
        <div>
          <dt>Conciliado em</dt>
          <dd>{dateTime(payment.reconciled_at)}</dd>
        </div>
        <div>
          <dt>Cobrança</dt>
          <dd>
            <Link to={`/clinicas/${clinic.id}/cobrancas/${payment.charge}`}>
              Cobrança #{payment.charge}
            </Link>
          </dd>
        </div>
      </dl>
      <Link
        className="button secondary"
        to={`/clinicas/${clinic.id}/pagamentos/eventos/${payment.source_event}`}
      >
        Ver recebimento de origem
      </Link>
    </>
  );
}

export function PaymentEventDetailPage() {
  const { eventId } = useParams();
  const clinic = useActiveClinic();
  const { events } = useOutletContext<PaymentWorkspaceData>();
  const event = events.find((record) => record.id === resourceId(eventId));
  if (!event)
    return <Notice>Recebimento indisponível nesta clínica. Escolha um registro da lista.</Notice>;
  return (
    <>
      <div className="charge-total">
        <strong className="money">{money(event.amount, event.currency)}</strong>
        <span
          className={`charge-status status-${event.status === 'RECONCILED' ? 'paid' : 'pending'}`}
        >
          {eventStatusLabels[event.status] ?? 'Situação desconhecida'}
        </span>
      </div>
      {event.status === 'DISCREPANCY' && (
        <Notice>
          {discrepancyLabel(event.discrepancy_code)} A cobrança não foi marcada como paga por este
          recebimento.
        </Notice>
      )}
      {event.status === 'RECEIVED' && (
        <Notice kind="info">
          Recebimento registrado e aguardando conciliação. Atualize para conferir a situação.
        </Notice>
      )}
      <dl className="record-details">
        <div>
          <dt>Referência do pagamento</dt>
          <dd className="payment-detail-reference">{event.payment_reference}</dd>
        </div>
        <div>
          <dt>Identificador do evento</dt>
          <dd className="payment-detail-reference">{event.event_id}</dd>
        </div>
        <div>
          <dt>Pago em</dt>
          <dd>{dateTime(event.paid_at)}</dd>
        </div>
        <div>
          <dt>Recebido em</dt>
          <dd>{dateTime(event.received_at)}</dd>
        </div>
        <div>
          <dt>Processado em</dt>
          <dd>{event.processed_at ? dateTime(event.processed_at) : 'Aguardando conciliação'}</dd>
        </div>
        <div>
          <dt>Cobrança informada</dt>
          <dd>
            {event.discrepancy_code === 'CHARGE_NOT_FOUND' ? (
              `#${event.charge_reference} · não encontrada`
            ) : (
              <Link to={`/clinicas/${clinic.id}/cobrancas/${event.charge_reference}`}>
                Cobrança #{event.charge_reference}
              </Link>
            )}
          </dd>
        </div>
      </dl>
      {event.payment !== null && (
        <Link
          className="button secondary"
          to={`/clinicas/${clinic.id}/pagamentos/${event.payment}`}
        >
          Ver pagamento conciliado
        </Link>
      )}
    </>
  );
}
