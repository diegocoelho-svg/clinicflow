import { useCallback, useState } from 'react';
import { useParams } from 'react-router';
import { ApiError } from '../../../shared/api/errors';
import { dateTime, resourceId } from '../../../shared/format/date';
import { itemSum } from '../../../shared/format/money';
import { useResource } from '../../../shared/hooks/useResource';
import { Notice } from '../../../shared/ui/Notice';
import { PageHeading } from '../../../shared/ui/PageHeading';
import { ResourceMessage } from '../../../shared/ui/ResourceMessage';
import { chargeApi } from '../../charges/api';
import { CancelChargeForm } from '../../charges/components/CancelChargeForm';
import { ChargeHistory } from '../../charges/components/ChargeHistory';
import { ChargeItems } from '../../charges/components/ChargeItems';
import { IssueCharge } from '../../charges/components/IssueCharge';
import { issuanceScope, useChargeOperations } from '../../charges/context';
import { useActiveClinic } from '../../clinics/hooks/useActiveClinic';
import { useClinicAccess } from '../../clinics/hooks/useClinicAccess';
import { encounterApi } from '../api';
import { EncounterItemsEditor } from '../components/EncounterItemsEditor';

export function EncounterBillingPage() {
  const { encounterId } = useParams();
  const clinic = useActiveClinic();
  const id = resourceId(encounterId);
  return id === null ? (
    <>
      <PageHeading focusKey="invalid-encounter">Atendimento indisponível</PageHeading>
      <Notice>Escolha um atendimento da lista desta clínica.</Notice>
    </>
  ) : (
    <EncounterBilling key={`${clinic.id}:${id}`} id={id} />
  );
}

function EncounterBilling({ id }: { id: number }) {
  const clinic = useActiveClinic();
  const auth = useClinicAccess();
  const operations = useChargeOperations();
  const [editing, setEditing] = useState(false);
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [encounter, items, patients, procedures, charges] = await Promise.all([
        encounterApi.get(clinic.id, id, auth, signal),
        encounterApi.items(clinic.id, id, auth, signal),
        encounterApi.patients(clinic.id, auth, signal),
        encounterApi.procedures(clinic.id, auth, signal),
        chargeApi.list(clinic.id, auth, signal),
      ]);
      if (encounter.id !== id || encounter.clinic !== clinic.id)
        throw new ApiError(
          0,
          'Não foi possível conferir este atendimento. Atualize antes de continuar.',
        );
      return {
        encounter,
        items,
        patient: patients.find((patient) => patient.id === encounter.patient),
        procedures,
        charges: charges.filter((charge) => charge.encounter === id),
      };
    },
    [clinic.id, id, auth],
  );
  const key = `${clinic.id}:encounter:${id}:${operations.revision}`;
  const { state, retry } = useResource(key, load);
  const active =
    state.status === 'success'
      ? state.data.charges.find((charge) => charge.status !== 'CANCELLED')
      : undefined;
  const intent = operations.intents.get(issuanceScope(clinic.id, id));
  const uncertain = intent?.status === 'pending' || intent?.status === 'uncertain';
  const locked = Boolean(active) || uncertain;
  return (
    <>
      <header className="operations-heading">
        <h3>Dados do atendimento</h3>
        <button
          className="button secondary"
          disabled={state.status === 'loading'}
          onClick={operations.refresh}
        >
          Atualizar atendimento
        </button>
      </header>
      <ResourceMessage state={state} label="atendimento" retry={retry} />
      {state.status === 'success' && (
        <>
          <dl className="record-details">
            <div>
              <dt>Paciente</dt>
              <dd>
                {state.data.patient?.full_name || `Paciente #${state.data.encounter.patient}`}
              </dd>
            </div>
            <div>
              <dt>Realizado em</dt>
              <dd>{dateTime(state.data.encounter.performed_at)}</dd>
            </div>
          </dl>
          <p className="clinical-description">{state.data.encounter.description}</p>
          {editing && !locked ? (
            <EncounterItemsEditor
              clinic={clinic.id}
              encounter={id}
              items={state.data.items}
              procedures={state.data.procedures}
              updated={operations.refresh}
              close={() => {
                setEditing(false);
                operations.refresh();
              }}
            />
          ) : (
            <section className="billing-section" aria-labelledby="encounter-items-heading">
              <div className="section-heading">
                <h3 id="encounter-items-heading">Itens do atendimento</h3>
                <button
                  className="button secondary"
                  disabled={locked && !editing}
                  onClick={() => {
                    setEditing(!editing);
                    if (editing) operations.refresh();
                  }}
                >
                  {editing ? 'Concluir edição' : 'Editar itens'}
                </button>
              </div>
              {locked && (
                <p className="muted">
                  {uncertain
                    ? 'Confirme a emissão pendente antes de alterar os itens.'
                    : active?.status === 'PAID'
                      ? 'Esta cobrança está paga. Os itens e valores do atendimento estão preservados.'
                      : 'Uma cobrança ativa preserva estes itens. Para corrigir, um proprietário precisa cancelar a cobrança primeiro.'}
                </p>
              )}
              {state.data.items.length ? (
                <ChargeItems
                  items={state.data.items}
                  caption="Procedimentos registrados no atendimento"
                />
              ) : (
                <p className="muted">Nenhum procedimento adicionado.</p>
              )}
            </section>
          )}
          <IssueCharge
            clinic={clinic.id}
            encounter={id}
            active={active}
            total={itemSum(state.data.items)}
            itemCount={state.data.items.length}
            editing={editing}
          />
          {active && <CancelChargeForm charge={active} />}
          <section className="billing-section" aria-labelledby="charge-history-heading">
            <h3 id="charge-history-heading">Histórico de cobranças</h3>
            <ChargeHistory clinic={clinic.id} charges={state.data.charges} />
          </section>
        </>
      )}
    </>
  );
}
