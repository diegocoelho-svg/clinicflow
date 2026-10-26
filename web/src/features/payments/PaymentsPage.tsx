import { useCallback } from 'react';
import { Link, Outlet, useMatch, useNavigate, useParams, useSearchParams } from 'react-router';
import { ApiError } from '../../shared/api/errors';
import { dateTime } from '../../shared/format/date';
import { money } from '../../shared/format/money';
import { useResource } from '../../shared/hooks/useResource';
import { Dialog } from '../../shared/ui/Dialog';
import { PageHeading } from '../../shared/ui/PageHeading';
import { ResourceMessage } from '../../shared/ui/ResourceMessage';
import { useChargeOperations } from '../charges/context';
import { useActiveClinic } from '../clinics/hooks/useActiveClinic';
import { useClinicAccess } from '../clinics/hooks/useClinicAccess';
import { paymentApi } from './api';
import { eventStatusLabels, type EventStatus } from './types';

export function PaymentsPage() {
  const clinic = useActiveClinic();
  const auth = useClinicAccess();
  const { revision, refresh } = useChargeOperations();
  const { paymentId, eventId } = useParams();
  const eventsView = Boolean(useMatch('/clinicas/:clinicId/pagamentos/eventos/*'));
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const search = params.get('busca') ?? '';
  const status = params.get('situacao') ?? 'ALL';
  const filter = Object.hasOwn(eventStatusLabels, status) ? status : 'ALL';
  const base = `/clinicas/${clinic.id}/pagamentos`;
  const listPath = eventsView ? `${base}/eventos` : base;
  const selected = eventsView ? eventId : paymentId;
  const query = params.toString();
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [payments, events] = await Promise.all([
        paymentApi.list(clinic.id, auth, signal),
        paymentApi.events(clinic.id, auth, signal),
      ]);
      if (
        !Array.isArray(payments) ||
        !Array.isArray(events) ||
        [...payments, ...events].some((record) => !record || record.clinic !== clinic.id)
      )
        throw new ApiError(0, 'Não foi possível conferir os recebimentos desta clínica.');
      return { payments, events };
    },
    [clinic.id, auth],
  );
  const { state, retry } = useResource(`${clinic.id}:payments:${revision}`, load);
  const rows =
    state.status === 'success'
      ? (eventsView
          ? state.data.events.map((event) => ({
              ...event,
              charge: event.charge_reference,
              date: event.received_at,
            }))
          : state.data.payments.map((payment) => ({
              ...payment,
              date: payment.paid_at,
              status: 'RECONCILED' as const,
            }))
        ).reverse()
      : [];
  const term = search.trim().toLocaleLowerCase('pt-BR');
  const filtered = rows.filter(
    (row) =>
      (row.payment_reference.toLocaleLowerCase('pt-BR').includes(term) ||
        String(row.charge) === term) &&
      (!eventsView || filter === 'ALL' || row.status === filter),
  );
  const index = filtered.findIndex((row) => String(row.id) === selected);
  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  return (
    <>
      <header className="operations-heading">
        <div>
          <PageHeading level={1} focusKey={`${clinic.id}:payments`}>
            Pagamentos
          </PageHeading>
          <p className="muted">Acompanhe os pagamentos conciliados e confira os recebimentos.</p>
        </div>
        <button
          className="button secondary"
          onClick={refresh}
          disabled={state.status === 'loading'}
        >
          Atualizar pagamentos
        </button>
      </header>
      <nav className="action-row payment-tabs" aria-label="Consultas de pagamento">
        <Link
          className={`button ${eventsView ? 'secondary' : 'primary'}`}
          aria-current={!eventsView ? 'page' : undefined}
          to={{ pathname: base, search: query }}
        >
          Pagamentos conciliados
        </Link>
        <Link
          className={`button ${eventsView ? 'primary' : 'secondary'}`}
          aria-current={eventsView ? 'page' : undefined}
          to={{ pathname: `${base}/eventos`, search: query }}
        >
          Eventos e divergências
        </Link>
      </nav>
      <div className="collection-toolbar">
        <div className="field">
          <label htmlFor="payment-search">Buscar por cobrança ou referência</label>
          <input
            id="payment-search"
            type="search"
            value={search}
            onChange={(event) => updateFilter('busca', event.target.value)}
          />
        </div>
        {eventsView && (
          <div className="field">
            <label htmlFor="payment-status">Situação do recebimento</label>
            <select
              id="payment-status"
              value={filter}
              onChange={(event) => updateFilter('situacao', event.target.value)}
            >
              <option value="ALL">Todas as situações</option>
              {Object.entries(eventStatusLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      <ResourceMessage state={state} label="recebimentos" retry={retry} />
      {state.status === 'success' && (
        <div className="table-scroll">
          <table className="data-table collection-table">
            <caption>
              {filtered.length} {eventsView ? 'evento(s)' : 'pagamento(s)'} · abra um registro para
              conferir
            </caption>
            <thead>
              <tr>
                <th>{eventsView ? 'Evento / referência' : 'Pagamento / referência'}</th>
                <th>Cobrança</th>
                <th>Valor recebido</th>
                <th>{eventsView ? 'Recebido em' : 'Pago em'}</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.id} className={String(row.id) === selected ? 'selected-record' : ''}>
                  <th scope="row">
                    <Link to={{ pathname: `${listPath}/${row.id}`, search: query }}>
                      {eventsView ? 'Evento' : 'Pagamento'} #{row.id}
                    </Link>
                    <small className="payment-list-reference">{row.payment_reference}</small>
                  </th>
                  <td>#{row.charge}</td>
                  <td className="money">{money(row.amount, row.currency)}</td>
                  <td>{dateTime(row.date)}</td>
                  <td>
                    <span
                      className={`charge-status status-${row.status === 'RECONCILED' ? 'paid' : 'pending'}`}
                    >
                      {eventStatusLabels[row.status as EventStatus] ?? 'Situação desconhecida'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="operations-empty">
              <h3>
                {rows.length
                  ? 'Nenhum registro encontrado'
                  : eventsView
                    ? 'Nenhum recebimento registrado'
                    : 'Nenhum pagamento conciliado'}
              </h3>
              <p>
                {rows.length
                  ? 'Ajuste a busca ou o filtro.'
                  : eventsView
                    ? 'Os recebimentos aparecerão aqui quando forem informados.'
                    : 'Os pagamentos aparecerão após a conferência dos recebimentos.'}
              </p>
            </div>
          )}
        </div>
      )}
      {selected && (
        <Dialog
          title={`${eventsView ? 'Evento' : 'Pagamento'} #${selected}`}
          drawer
          close={() => void navigate({ pathname: listPath, search: query })}
          navigation={
            <>
              <button
                className="button subtle"
                onClick={refresh}
                disabled={state.status === 'loading'}
              >
                Atualizar registro
              </button>
              {index > 0 && (
                <Link
                  className="button subtle"
                  aria-label="Registro anterior"
                  to={{ pathname: `${listPath}/${filtered[index - 1].id}`, search: query }}
                >
                  ← Anterior
                </Link>
              )}
              {index >= 0 && index < filtered.length - 1 && (
                <Link
                  className="button subtle"
                  aria-label="Próximo registro"
                  to={{ pathname: `${listPath}/${filtered[index + 1].id}`, search: query }}
                >
                  Próximo →
                </Link>
              )}
            </>
          }
        >
          <ResourceMessage state={state} label="recebimento" retry={retry} />
          {state.status === 'success' && <Outlet context={{ clinic, ...state.data }} />}
        </Dialog>
      )}
    </>
  );
}
