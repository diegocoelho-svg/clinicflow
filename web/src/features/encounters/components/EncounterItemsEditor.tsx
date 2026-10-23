import { useState, type Dispatch, type FormEvent, type SetStateAction } from 'react';
import { ApiError } from '../../../shared/api/errors';
import { money } from '../../../shared/format/money';
import { useAsyncForm } from '../../../shared/hooks/useAsyncForm';
import { Field } from '../../../shared/ui/Field';
import { Notice } from '../../../shared/ui/Notice';
import { useClinicAccess } from '../../clinics/hooks/useClinicAccess';
import { encounterApi } from '../api';
import type { EncounterItem, Procedure } from '../types';

export interface EncounterItemsDraft {
  quantities: Record<number, string>;
  procedure: string;
  quantity: string;
}

export const emptyEncounterItemsDraft = (): EncounterItemsDraft => ({
  quantities: {},
  procedure: '',
  quantity: '1',
});

function quantity(value: string): number | null {
  return /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 2147483647
    ? Number(value)
    : null;
}

export function EncounterItemsEditor({
  clinic,
  encounter,
  items,
  procedures,
  draft,
  setDraft,
  updated,
  close,
}: {
  clinic: number;
  encounter: number;
  items: readonly EncounterItem[];
  procedures: readonly Procedure[];
  draft: EncounterItemsDraft;
  setDraft: Dispatch<SetStateAction<EncounterItemsDraft>>;
  updated: () => void;
  close: () => void;
}) {
  const auth = useClinicAccess();
  const form = useAsyncForm();
  const drafts = draft.quantities;
  const selected = draft.procedure;
  const addQuantity = draft.quantity;
  const [removing, setRemoving] = useState<number | null>(null);
  const [blocked, setBlocked] = useState(false);
  const available = procedures.filter(
    (procedure) => procedure.is_active && !items.some((item) => item.procedure === procedure.id),
  );
  const dirty =
    items.some(
      (item) => drafts[item.id] !== undefined && drafts[item.id] !== String(item.quantity),
    ) || Boolean(selected);
  async function mutate(
    operation: (signal: AbortSignal) => Promise<unknown>,
    applied: () => void = () => {},
  ) {
    const result = await form.submit(async (signal) => {
      try {
        return await operation(signal);
      } catch (failure) {
        if (
          !signal.aborted &&
          failure instanceof ApiError &&
          [403, 404, 409].includes(failure.status)
        )
          setBlocked(true);
        throw failure;
      }
    });
    if (result) {
      applied();
      updated();
    }
  }
  function clearQuantity(itemId: number) {
    setDraft((current) => {
      const quantities = { ...current.quantities };
      delete quantities[itemId];
      return { ...current, quantities };
    });
  }
  function save(event: FormEvent<HTMLFormElement>, item: EncounterItem) {
    event.preventDefault();
    const value = quantity(drafts[item.id] ?? String(item.quantity));
    if (value !== null)
      void mutate(
        (signal) => encounterApi.updateItem(clinic, encounter, item.id, value, auth, signal),
        () => clearQuantity(item.id),
      );
  }
  function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = quantity(addQuantity);
    if (value !== null && available.some((procedure) => procedure.id === Number(selected)))
      void mutate(
        (signal) => encounterApi.addItem(clinic, encounter, Number(selected), value, auth, signal),
        () => setDraft((current) => ({ ...current, procedure: '', quantity: '1' })),
      );
  }
  return (
    <section className="billing-section item-editor" aria-labelledby="edit-items-heading">
      <div className="section-heading">
        <h3 id="edit-items-heading">Editar itens do atendimento</h3>
        <button className="button secondary" disabled={form.pending} onClick={close}>
          {dirty ? 'Descartar rascunhos e voltar' : 'Concluir edição'}
        </button>
      </div>
      <p className="muted">
        Salve cada quantidade antes de concluir. O preço e o nome registrados são preservados.
      </p>
      {form.error && <Notice>{form.error}</Notice>}
      <fieldset disabled={form.pending || blocked}>
        {items.map((item) => (
          <div className="editable-item" key={item.id}>
            <div>
              <strong>{item.procedure_name}</strong>
              <small>{money(item.unit_price)} por unidade</small>
            </div>
            <form
              aria-label={`Quantidade de ${item.procedure_name}`}
              onSubmit={(event) => save(event, item)}
            >
              <Field
                label={`Quantidade de ${item.procedure_name}`}
                name={`quantity-${item.id}`}
                type="number"
                min={1}
                max={2147483647}
                step={1}
                required
                value={drafts[item.id] ?? String(item.quantity)}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    quantities: { ...current.quantities, [item.id]: event.target.value },
                  }))
                }
                error={form.fields.quantity}
              />
              <button
                className="button secondary"
                disabled={
                  quantity(drafts[item.id] ?? String(item.quantity)) === null ||
                  (drafts[item.id] ?? String(item.quantity)) === String(item.quantity)
                }
                type="submit"
              >
                Salvar quantidade
              </button>
            </form>
            {removing === item.id ? (
              <div
                className="remove-confirmation"
                role="group"
                aria-label={`Confirmar remoção de ${item.procedure_name}`}
              >
                <p>Remover {item.procedure_name} deste atendimento?</p>
                <button
                  className="button secondary danger"
                  onClick={() =>
                    void mutate(
                      (signal) => encounterApi.removeItem(clinic, encounter, item.id, auth, signal),
                      () => clearQuantity(item.id),
                    )
                  }
                >
                  Confirmar remoção
                </button>
                <button className="text-button" onClick={() => setRemoving(null)}>
                  Manter item
                </button>
              </div>
            ) : (
              <button className="text-button danger" onClick={() => setRemoving(item.id)}>
                Remover {item.procedure_name}
              </button>
            )}
          </div>
        ))}
        {available.length > 0 ? (
          <form
            className="add-item-form"
            aria-label="Adicionar procedimento ao atendimento"
            onSubmit={add}
          >
            <h4>Adicionar procedimento</h4>
            <div className="field">
              <label htmlFor="add-procedure">Procedimento</label>
              <select
                id="add-procedure"
                required
                value={selected}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, procedure: event.target.value }))
                }
                aria-invalid={Boolean(form.fields.procedure)}
                aria-describedby={form.fields.procedure ? 'add-procedure-error' : undefined}
              >
                <option value="">Selecione um procedimento</option>
                {available.map((procedure) => (
                  <option key={procedure.id} value={procedure.id}>
                    {procedure.name} — {money(procedure.unit_price)}
                  </option>
                ))}
              </select>
              {form.fields.procedure && (
                <small className="field-error" id="add-procedure-error">
                  {form.fields.procedure}
                </small>
              )}
            </div>
            <Field
              label="Quantidade do novo procedimento"
              name="add-quantity"
              type="number"
              min={1}
              max={2147483647}
              step={1}
              required
              value={addQuantity}
              onChange={(event) =>
                setDraft((current) => ({ ...current, quantity: event.target.value }))
              }
            />
            <button
              className="button secondary"
              disabled={!selected || quantity(addQuantity) === null}
              type="submit"
            >
              Adicionar procedimento
            </button>
          </form>
        ) : (
          <p className="muted">
            Não há outros procedimentos ativos disponíveis no catálogo desta clínica.
          </p>
        )}
      </fieldset>
    </section>
  );
}
