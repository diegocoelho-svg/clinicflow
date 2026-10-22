import { useCallback, useState } from 'react';
import { Link, Outlet, useNavigate, useParams } from 'react-router';
import { dateTime } from '../../../shared/format/date';
import { money } from '../../../shared/format/money';
import { useResource } from '../../../shared/hooks/useResource';
import { Dialog } from '../../../shared/ui/Dialog';
import { PageHeading } from '../../../shared/ui/PageHeading';
import { ResourceMessage } from '../../../shared/ui/ResourceMessage';
import { chargeApi } from '../../charges/api';
import { ChargeStatusBadge } from '../../charges/components/ChargeStatusBadge';
import { useChargeOperations } from '../../charges/context';
import { useActiveClinic } from '../../clinics/hooks/useActiveClinic';
import { useClinicAccess } from '../../clinics/hooks/useClinicAccess';
import { encounterApi } from '../api';
import { NewEncounterDialog } from '../NewEncounterDialog';

export function EncounterIndexPage() {
  const clinic = useActiveClinic();
  const auth = useClinicAccess();
  const { revision, refresh } = useChargeOperations();
  const { encounterId } = useParams();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('ALL');
  const base = `/clinicas/${clinic.id}/atendimentos`;
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [encounters, patients, charges] = await Promise.all([
        encounterApi.list(clinic.id, auth, signal),
        encounterApi.patients(clinic.id, auth, signal),
        chargeApi.list(clinic.id, auth, signal),
      ]);
      return { encounters, patients, charges };
    },
    [clinic.id, auth],
  );
  const { state, retry } = useResource(`${clinic.id}:encounters:${revision}`, load);
  const allRecords =
    state.status === 'success'
      ? [...state.data.encounters].reverse().map((encounter) => ({
          encounter,
          patient: state.data.patients.find((patient) => patient.id === encounter.patient),
          active: state.data.charges.find(
            (charge) => charge.encounter === encounter.id && charge.status !== 'CANCELLED',
          ),
        }))
      : [];
  const records = allRecords.filter(
    ({ encounter, patient, active }) =>
      `${patient?.full_name ?? ''} ${encounter.id} ${encounter.description}`
        .toLocaleLowerCase('pt-BR')
        .includes(search.toLocaleLowerCase('pt-BR')) &&
      (filter === 'ALL' || (filter === 'UNBILLED' ? !active : active?.status === filter)),
  );
  const selectedIndex = records.findIndex(({ encounter }) => String(encounter.id) === encounterId);
  const closeRecord = () => {
    void navigate(base);
  };
  return (
    <>
      <header className="operations-heading">
        <div>
          <PageHeading level={1} focusKey={`${clinic.id}:encounters`}>
            Atendimentos
          </PageHeading>
          <p className="muted">
            Cadastre, confira os itens e acompanhe a cobrança sem perder a lista.
          </p>
        </div>
        <div className="action-row">
          <button className="button subtle" onClick={refresh} disabled={state.status === 'loading'}>
            Atualizar atendimentos
          </button>
          <button className="button primary" onClick={() => setCreating(true)}>
            Novo atendimento
          </button>
        </div>
      </header>
      <div className="collection-toolbar">
        <div className="field">
          <label htmlFor="encounter-search">Buscar atendimento</label>
          <input
            id="encounter-search"
            type="search"
            placeholder="Paciente, número ou descrição"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="encounter-filter">Situação</label>
          <select
            id="encounter-filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="ALL">Todos os atendimentos</option>
            <option value="UNBILLED">Sem cobrança ativa</option>
            <option value="PENDING">Aguardando pagamento</option>
            <option value="NO_PAYMENT_REQUIRED">Sem pagamento necessário</option>
            <option value="PAID">Pagos</option>
          </select>
        </div>
      </div>
      <ResourceMessage state={state} label="atendimentos" retry={retry} />
      {state.status === 'success' && (
        <div className="table-scroll">
          <table className="data-table collection-table encounter-table">
            <caption>
              {records.length} atendimento(s) · clique no paciente para abrir o painel
            </caption>
            <thead>
              <tr>
                <th>Paciente / atendimento</th>
                <th>Realizado em</th>
                <th>Cobrança</th>
                <th>Valor emitido</th>
                <th>
                  <span className="sr-only">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {records.map(({ encounter, patient, active }) => (
                <tr
                  key={encounter.id}
                  className={String(encounter.id) === encounterId ? 'selected-record' : ''}
                >
                  <th scope="row">
                    <Link to={`${base}/${encounter.id}`}>
                      {patient?.full_name || `Paciente #${encounter.patient}`}
                    </Link>
                    <small>Atendimento #{encounter.id}</small>
                    {encounter.description && (
                      <p className="record-preview">{encounter.description}</p>
                    )}
                  </th>
                  <td>
                    <time dateTime={encounter.performed_at}>
                      {dateTime(encounter.performed_at)}
                    </time>
                  </td>
                  <td>
                    {active ? (
                      <ChargeStatusBadge status={active.status} />
                    ) : (
                      <span className="plain-status">Sem cobrança ativa</span>
                    )}
                  </td>
                  <td className="money">{active ? money(active.amount) : '—'}</td>
                  <td>
                    <Link className="button subtle" to={`${base}/${encounter.id}`}>
                      Ver atendimento #{encounter.id}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {records.length === 0 && (
            <div className="operations-empty">
              <h3>
                {allRecords.length
                  ? 'Nenhum atendimento encontrado'
                  : 'Nenhum atendimento registrado'}
              </h3>
              <p>
                {allRecords.length
                  ? 'Ajuste a busca ou o filtro.'
                  : 'Use Novo atendimento para escolher o paciente, os procedimentos e as quantidades.'}
              </p>
            </div>
          )}
        </div>
      )}
      {creating && (
        <NewEncounterDialog
          clinic={clinic.id}
          close={() => {
            setCreating(false);
            refresh();
          }}
          created={(id) => {
            setCreating(false);
            refresh();
            void navigate(`${base}/${id}`);
          }}
        />
      )}
      {encounterId && (
        <Dialog
          title={`Atendimento #${encounterId}`}
          drawer
          close={closeRecord}
          navigation={
            <>
              {selectedIndex > 0 && (
                <Link
                  className="button subtle"
                  aria-label="Atendimento anterior"
                  to={`${base}/${records[selectedIndex - 1].encounter.id}`}
                >
                  ← Anterior
                </Link>
              )}
              {selectedIndex >= 0 && selectedIndex < records.length - 1 && (
                <Link
                  className="button subtle"
                  aria-label="Próximo atendimento"
                  to={`${base}/${records[selectedIndex + 1].encounter.id}`}
                >
                  Próximo →
                </Link>
              )}
            </>
          }
        >
          <Outlet context={{ clinic }} />
        </Dialog>
      )}
    </>
  );
}
