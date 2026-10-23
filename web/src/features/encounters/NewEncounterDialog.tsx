import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError } from '../../shared/api/errors';
import { itemSum, money } from '../../shared/format/money';
import { useAsyncForm } from '../../shared/hooks/useAsyncForm';
import { useResource } from '../../shared/hooks/useResource';
import { Dialog } from '../../shared/ui/Dialog';
import { Field } from '../../shared/ui/Field';
import { Notice } from '../../shared/ui/Notice';
import { ResourceMessage } from '../../shared/ui/ResourceMessage';
import { useClinicAccess } from '../clinics/hooks/useClinicAccess';
import { PatientForm } from '../patients/PatientForm';
import { patientApi, type Patient } from '../patients/api';
import { ProcedureForm } from '../procedures/ProcedureForm';
import { procedureApi } from '../procedures/api';
import { encounterApi } from './api';
import type { Encounter, Procedure } from './types';

function localDateTime() {
  const date = new Date();
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export function NewEncounterDialog({
  clinic,
  close,
  created,
}: {
  clinic: number;
  close: () => void;
  created: (id: number) => void;
}) {
  const auth = useClinicAccess();
  const [busy, setBusy] = useState(false);
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [patients, procedures] = await Promise.all([
        patientApi.list(clinic, auth, signal),
        procedureApi.list(clinic, auth, signal),
      ]);
      return { patients, procedures };
    },
    [clinic, auth],
  );
  const { state, retry } = useResource(`${clinic}:new-encounter`, load);
  return (
    <Dialog title="Novo atendimento" close={close} busy={busy}>
      <ResourceMessage state={state} label="pacientes e procedimentos" retry={retry} />
      {state.status === 'success' && (
        <EncounterForm
          clinic={clinic}
          patients={state.data.patients}
          procedures={state.data.procedures}
          close={close}
          created={created}
          busyChanged={setBusy}
        />
      )}
    </Dialog>
  );
}

function EncounterForm({
  clinic,
  patients: initialPatients,
  procedures: initialProcedures,
  close,
  created,
  busyChanged,
}: {
  clinic: number;
  patients: Patient[];
  procedures: Procedure[];
  close: () => void;
  created: (id: number) => void;
  busyChanged: (busy: boolean) => void;
}) {
  const auth = useClinicAccess();
  const form = useAsyncForm();
  const directory = useAsyncForm();
  const [patients, setPatients] = useState(initialPatients);
  const [procedures, setProcedures] = useState(initialProcedures);
  const [patient, setPatient] = useState('');
  const [performedAt, setPerformedAt] = useState(localDateTime);
  const [description, setDescription] = useState('');
  const [rows, setRows] = useState([{ key: 0, procedure: '', quantity: '1' }]);
  const nextRow = useRef(1);
  const savedEncounter = useRef<Encounter | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [newPatient, setNewPatient] = useState(false);
  const [newProcedure, setNewProcedure] = useState(false);
  const [inlineBusy, setInlineBusy] = useState(false);
  useEffect(
    () => busyChanged(form.pending || directory.pending),
    [form.pending, directory.pending, busyChanged],
  );
  async function refreshDirectory() {
    const result = await directory.submit(async (signal) => {
      const [patients, procedures] = await Promise.all([
        patientApi.list(clinic, auth, signal),
        procedureApi.list(clinic, auth, signal),
      ]);
      return { patients, procedures };
    });
    if (result) {
      setPatients(result.data.patients);
      setProcedures(result.data.procedures);
    }
  }
  function closePatientForm() {
    setNewPatient(false);
    void refreshDirectory();
  }
  function closeProcedureForm() {
    setNewProcedure(false);
    void refreshDirectory();
  }
  const active = procedures.filter((item) => item.is_active);
  const selected = rows.filter((row) => row.procedure);
  const total = itemSum(
    selected.map((row) => ({
      unit_price: procedures.find((item) => item.id === Number(row.procedure))?.unit_price ?? '',
      quantity: Number(row.quantity),
    })),
  );
  const validRows = selected.every(
    (row) =>
      /^\d+$/.test(row.quantity) && Number(row.quantity) >= 1 && Number(row.quantity) <= 2147483647,
  );
  const updateRow = (key: number, change: { procedure?: string; quantity?: string }) =>
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...change } : row)));
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !patient ||
      !description.trim() ||
      !validRows ||
      total === null ||
      uncertain ||
      directory.pending
    )
      return;
    const result = await form.submit(async (signal) => {
      if (!savedEncounter.current) {
        try {
          savedEncounter.current = await encounterApi.create(
            clinic,
            {
              patient: Number(patient),
              performed_at: new Date(performedAt).toISOString(),
              description: description.trim(),
            },
            auth,
            signal,
          );
        } catch (failure) {
          if (failure instanceof ApiError && (failure.status === 0 || failure.status >= 500)) {
            setUncertain(true);
            throw new ApiError(
              0,
              'Não foi possível confirmar o cadastro. Feche este formulário e atualize a lista antes de cadastrar novamente.',
            );
          }
          throw failure;
        }
      }
      const encounter = savedEncounter.current;
      const existing = await encounterApi.items(clinic, encounter.id, auth, signal);
      for (const row of selected) {
        const previous = existing.find((item) => item.procedure === Number(row.procedure));
        if (previous) {
          if (previous.quantity !== Number(row.quantity))
            throw new ApiError(
              409,
              'O atendimento já foi salvo com outra quantidade. Feche e confira seus itens na lista.',
            );
          continue;
        }
        await encounterApi.addItem(
          clinic,
          encounter.id,
          Number(row.procedure),
          Number(row.quantity),
          auth,
          signal,
        );
      }
      return encounter;
    });
    if (result) created(result.data.id);
  }
  return (
    <>
      <form onSubmit={submit} aria-label="Cadastrar atendimento">
        {form.error && <Notice>{form.error}</Notice>}
        {directory.error && <Notice>{directory.error}</Notice>}
        <button
          className="text-button"
          type="button"
          disabled={form.pending || directory.pending}
          onClick={() => void refreshDirectory()}
        >
          {directory.pending ? 'Atualizando opções…' : 'Atualizar pacientes e procedimentos'}
        </button>
        {savedEncounter.current && form.error && (
          <Notice kind="info">
            O atendimento #{savedEncounter.current.id} foi salvo. Tentar novamente conclui os itens
            que faltam, sem criar outro atendimento.
          </Notice>
        )}
        <fieldset disabled={form.pending || directory.pending || uncertain}>
          <div className="field-heading">
            <label htmlFor="encounter-patient">Paciente</label>
            <button
              type="button"
              className="text-button"
              onClick={() => setNewPatient(true)}
              disabled={Boolean(savedEncounter.current)}
            >
              + Cadastrar paciente aqui
            </button>
          </div>
          <div className="field">
            <select
              id="encounter-patient"
              required
              value={patient}
              disabled={Boolean(savedEncounter.current)}
              onChange={(event) => setPatient(event.target.value)}
              aria-invalid={Boolean(form.fields.patient)}
            >
              <option value="">Selecione o paciente</option>
              {patients.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.full_name}
                </option>
              ))}
            </select>
            {form.fields.patient && <small className="field-error">{form.fields.patient}</small>}
          </div>
          <Field
            label="Realizado em"
            name="encounter-performed-at"
            type="datetime-local"
            required
            value={performedAt}
            max={localDateTime()}
            disabled={Boolean(savedEncounter.current)}
            onChange={(event) => setPerformedAt(event.target.value)}
            error={form.fields.performed_at}
          />
          <div className="field">
            <label htmlFor="encounter-description">Descrição do atendimento</label>
            <textarea
              id="encounter-description"
              required
              placeholder="Ex.: Consulta de avaliação"
              aria-invalid={Boolean(form.fields.description)}
              aria-describedby={form.fields.description ? 'encounter-description-error' : undefined}
              rows={2}
              value={description}
              disabled={Boolean(savedEncounter.current)}
              onChange={(event) => setDescription(event.target.value)}
            />
            {form.fields.description && (
              <small className="field-error" id="encounter-description-error">
                {form.fields.description}
              </small>
            )}
          </div>
          <div className="section-heading">
            <h3>Procedimentos e valores</h3>
            <button
              type="button"
              className="text-button"
              onClick={() => setNewProcedure(true)}
              disabled={Boolean(savedEncounter.current)}
            >
              + Cadastrar procedimento e preço
            </button>
          </div>
          <p className="muted form-hint">
            Selecione os serviços realizados. O total usa o preço do catálogo e a quantidade de cada
            item.
          </p>
          {rows.map((row, index) => (
            <div className="encounter-draft-item" key={row.key}>
              <div className="field">
                <label htmlFor={`draft-procedure-${row.key}`}>Procedimento {index + 1}</label>
                <select
                  id={`draft-procedure-${row.key}`}
                  value={row.procedure}
                  onChange={(event) => updateRow(row.key, { procedure: event.target.value })}
                  disabled={Boolean(savedEncounter.current)}
                >
                  <option value="">Selecione um procedimento</option>
                  {active
                    .filter(
                      (item) =>
                        String(item.id) === row.procedure ||
                        !selected.some((entry) => entry.procedure === String(item.id)),
                    )
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} — {money(item.unit_price)}
                      </option>
                    ))}
                </select>
              </div>
              <Field
                label={`Quantidade ${index + 1}`}
                name={`draft-quantity-${row.key}`}
                type="number"
                min={1}
                max={2147483647}
                step={1}
                required={Boolean(row.procedure)}
                value={row.quantity}
                disabled={Boolean(savedEncounter.current)}
                onChange={(event) => updateRow(row.key, { quantity: event.target.value })}
              />
              <button
                type="button"
                className="text-button danger"
                disabled={Boolean(savedEncounter.current)}
                aria-label={`Remover procedimento ${index + 1}`}
                onClick={() => setRows((current) => current.filter((item) => item.key !== row.key))}
              >
                Remover
              </button>
            </div>
          ))}
          <button
            className="button secondary"
            type="button"
            disabled={Boolean(savedEncounter.current) || selected.length >= active.length}
            onClick={() =>
              setRows((current) => [
                ...current,
                { key: nextRow.current++, procedure: '', quantity: '1' },
              ])
            }
          >
            Adicionar procedimento
          </button>
          <div className="draft-total">
            <span>Total do atendimento</span>
            <strong className="money">
              {total === null ? 'Confira as quantidades' : money(total)}
            </strong>
          </div>
          {selected.length === 0 && (
            <p className="muted form-hint">
              Você pode salvar sem itens e completá-los depois. A cobrança exige pelo menos um
              procedimento.
            </p>
          )}
          <div className="form-actions">
            <button
              className="button primary"
              type="submit"
              disabled={
                !patient || !performedAt || !description.trim() || !validRows || total === null
              }
            >
              {form.pending
                ? 'Salvando…'
                : savedEncounter.current
                  ? 'Concluir itens do atendimento'
                  : 'Salvar atendimento'}
            </button>
            <button className="text-button" type="button" onClick={close}>
              Cancelar
            </button>
          </div>
        </fieldset>
        {uncertain && (
          <button className="button secondary" type="button" onClick={close}>
            Fechar e conferir a lista
          </button>
        )}
      </form>
      {newPatient && (
        <Dialog busy={inlineBusy} title="Novo paciente" close={closePatientForm}>
          <PatientForm
            onBusyChange={setInlineBusy}
            clinic={clinic}
            cancel={closePatientForm}
            saved={(item) => {
              setPatients((current) => [...current, item]);
              setPatient(String(item.id));
              setNewPatient(false);
            }}
          />
        </Dialog>
      )}
      {newProcedure && (
        <Dialog busy={inlineBusy} title="Novo procedimento e preço" close={closeProcedureForm}>
          <ProcedureForm
            onBusyChange={setInlineBusy}
            clinic={clinic}
            cancel={closeProcedureForm}
            saved={(item) => {
              setProcedures((current) => [...current, item]);
              setRows((current) => {
                const empty = current.find((row) => !row.procedure);
                return empty
                  ? current.map((row) =>
                      row.key === empty.key ? { ...row, procedure: String(item.id) } : row,
                    )
                  : [
                      ...current,
                      { key: nextRow.current++, procedure: String(item.id), quantity: '1' },
                    ];
              });
              setNewProcedure(false);
            }}
          />
        </Dialog>
      )}
    </>
  );
}
